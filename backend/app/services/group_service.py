"""Company-managed employee groups and policy audience reconciliation."""

from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.integrations import employee_service
from app.models import (
    EmployeeGroup,
    EmployeeGroupMember,
    Policy,
    PolicyAssignment,
    PolicyGroupTarget,
)
from app.services import assignment_service


class GroupError(ValueError):
    pass


def _employees(company_id: str, employee_ids: list[str]) -> list[str]:
    unique_ids = list(dict.fromkeys(employee_ids))
    for employee_id in unique_ids:
        try:
            employee = employee_service.get(employee_id)
        except LookupError:
            raise GroupError(f"Unknown employee {employee_id!r}.") from None
        if employee.company_id != company_id or employee.is_admin:
            raise GroupError(f"Employee {employee_id!r} cannot join this group.")
    return unique_ids


def _ensure_available(
    session: Session,
    *,
    company_id: str,
    employee_ids: list[str],
    except_group_id: str | None = None,
) -> None:
    if not employee_ids:
        return
    query = select(EmployeeGroupMember).where(
        EmployeeGroupMember.company_id == company_id,
        EmployeeGroupMember.employee_id.in_(employee_ids),
    )
    if except_group_id:
        query = query.where(EmployeeGroupMember.group_id != except_group_id)
    existing = session.scalar(query.limit(1))
    if existing:
        employee = employee_service.get(existing.employee_id)
        raise GroupError(f"{employee.name} already belongs to another group.")


def create(
    session: Session, *, company_id: str, name: str, employee_ids: list[str], actor_id: str
) -> EmployeeGroup:
    employee_ids = _employees(company_id, employee_ids)
    _ensure_available(session, company_id=company_id, employee_ids=employee_ids)
    name = name.strip()
    if not name:
        raise GroupError("Group name cannot be blank.")
    duplicate = session.scalar(
        select(EmployeeGroup).where(
            EmployeeGroup.company_id == company_id,
            EmployeeGroup.name == name,
        )
    )
    if duplicate:
        raise GroupError("A group with this name already exists.")
    group = EmployeeGroup(company_id=company_id, name=name)
    session.add(group)
    session.flush()
    group.members = [
        EmployeeGroupMember(
            employee_id=employee_id, company_id=company_id, created_by=actor_id
        )
        for employee_id in employee_ids
    ]
    session.flush()
    return group


def audience_employee_ids(session: Session, policy: Policy) -> set[str]:
    if policy.all_employees:
        return {
            employee.id
            for employee in employee_service.list_for_company(policy.company_id)
            if not employee.is_admin
        }
    return set(
        session.scalars(
            select(EmployeeGroupMember.employee_id)
            .join(
                PolicyGroupTarget,
                PolicyGroupTarget.group_id == EmployeeGroupMember.group_id,
            )
            .where(PolicyGroupTarget.policy_id == policy.id)
        )
    )


def reconcile_policy(
    session: Session, *, policy: Policy, effective_from: date, actor_id: str
) -> None:
    desired = audience_employee_ids(session, policy)
    active = list(
        session.scalars(
            select(PolicyAssignment).where(
                PolicyAssignment.policy_id == policy.id,
                PolicyAssignment.effective_from <= effective_from,
                (PolicyAssignment.effective_to.is_(None))
                | (PolicyAssignment.effective_to >= effective_from),
            )
        )
    )
    active_ids = {row.employee_id for row in active}
    missing = sorted(desired - active_ids)
    if missing:
        try:
            assignment_service.assign(
                session,
                policy=policy,
                employee_ids=missing,
                effective_from=effective_from,
                actor_id=actor_id,
            )
        except assignment_service.AssignmentError as exc:
            raise GroupError(str(exc)) from exc
    for row in active:
        if row.employee_id in desired:
            continue
        if row.effective_from == effective_from:
            session.delete(row)
        else:
            row.effective_to = effective_from - timedelta(days=1)
    session.flush()


def set_policy_audience(
    session: Session,
    *,
    policy: Policy,
    all_employees: bool,
    group_ids: list[str],
    effective_from: date,
    actor_id: str,
) -> None:
    group_ids = list(dict.fromkeys(group_ids))
    groups = list(
        session.scalars(
            select(EmployeeGroup).where(
                EmployeeGroup.company_id == policy.company_id,
                EmployeeGroup.id.in_(group_ids),
            )
        )
    ) if group_ids else []
    if len(groups) != len(group_ids):
        raise GroupError("One or more selected groups do not exist.")
    if not all_employees and not group_ids:
        raise GroupError("Choose all employees or at least one employee group.")
    policy.all_employees = all_employees
    session.execute(delete(PolicyGroupTarget).where(PolicyGroupTarget.policy_id == policy.id))
    if not all_employees:
        session.add_all([
            PolicyGroupTarget(policy_id=policy.id, group_id=group_id, created_by=actor_id)
            for group_id in group_ids
        ])
    session.flush()
    reconcile_policy(
        session, policy=policy, effective_from=effective_from, actor_id=actor_id
    )


def replace_members(
    session: Session,
    *,
    group: EmployeeGroup,
    employee_ids: list[str],
    effective_from: date,
    actor_id: str,
) -> EmployeeGroup:
    employee_ids = _employees(group.company_id, employee_ids)
    _ensure_available(
        session,
        company_id=group.company_id,
        employee_ids=employee_ids,
        except_group_id=group.id,
    )
    session.execute(
        delete(EmployeeGroupMember).where(EmployeeGroupMember.group_id == group.id)
    )
    session.add_all([
        EmployeeGroupMember(
            group_id=group.id,
            employee_id=employee_id,
            company_id=group.company_id,
            created_by=actor_id,
        )
        for employee_id in employee_ids
    ])
    session.flush()
    policies = list(
        session.scalars(
            select(Policy)
            .join(PolicyGroupTarget, PolicyGroupTarget.policy_id == Policy.id)
            .where(PolicyGroupTarget.group_id == group.id)
            .with_for_update(of=Policy)
        )
    )
    for policy in policies:
        reconcile_policy(
            session, policy=policy, effective_from=effective_from, actor_id=actor_id
        )
    session.refresh(group)
    return group


def set_employee_group(
    session: Session,
    *,
    company_id: str,
    employee_id: str,
    group_id: str | None,
    effective_from: date,
    actor_id: str,
) -> None:
    _employees(company_id, [employee_id])
    target_group = None
    if group_id:
        target_group = session.scalar(
            select(EmployeeGroup)
            .where(
                EmployeeGroup.id == group_id,
                EmployeeGroup.company_id == company_id,
            )
            .with_for_update()
        )
        if target_group is None:
            raise GroupError("The selected group does not exist.")
    current = session.scalar(
        select(EmployeeGroupMember)
        .where(
            EmployeeGroupMember.company_id == company_id,
            EmployeeGroupMember.employee_id == employee_id,
        )
        .with_for_update()
    )
    if current and current.group_id == group_id:
        return
    old_group_id = current.group_id if current else None
    old_policy_ids = set(
        session.scalars(
            select(PolicyGroupTarget.policy_id).where(
                PolicyGroupTarget.group_id == old_group_id
            )
        )
    ) if old_group_id else set()
    new_policy_ids = set(
        session.scalars(
            select(PolicyGroupTarget.policy_id).where(
                PolicyGroupTarget.group_id == group_id
            )
        )
    ) if group_id else set()
    affected_policy_ids = old_policy_ids | new_policy_ids
    policies_by_id = {
        policy.id: policy
        for policy in session.scalars(
            select(Policy)
            .where(Policy.id.in_(affected_policy_ids))
            .order_by(Policy.id)
            .with_for_update()
        )
    } if affected_policy_ids else {}
    if current:
        session.delete(current)
        session.flush()
    if target_group:
        session.add(
            EmployeeGroupMember(
                group_id=target_group.id,
                employee_id=employee_id,
                company_id=company_id,
                created_by=actor_id,
            )
        )
    session.flush()
    ordered_policy_ids = [
        *sorted(old_policy_ids - new_policy_ids),
        *sorted(old_policy_ids & new_policy_ids),
        *sorted(new_policy_ids - old_policy_ids),
    ]
    for policy_id in ordered_policy_ids:
        reconcile_policy(
            session,
            policy=policies_by_id[policy_id],
            effective_from=effective_from,
            actor_id=actor_id,
        )


def remove(
    session: Session, *, group: EmployeeGroup, effective_from: date, actor_id: str
) -> None:
    policies = list(
        session.scalars(
            select(Policy)
            .join(PolicyGroupTarget, PolicyGroupTarget.policy_id == Policy.id)
            .where(PolicyGroupTarget.group_id == group.id)
            .with_for_update(of=Policy)
        )
    )
    session.execute(delete(PolicyGroupTarget).where(PolicyGroupTarget.group_id == group.id))
    session.flush()
    for policy in policies:
        reconcile_policy(
            session, policy=policy, effective_from=effective_from, actor_id=actor_id
        )
    session.delete(group)
    session.flush()
