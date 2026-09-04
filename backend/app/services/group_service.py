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


def create(
    session: Session, *, company_id: str, name: str, employee_ids: list[str], actor_id: str
) -> EmployeeGroup:
    employee_ids = _employees(company_id, employee_ids)
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
        EmployeeGroupMember(employee_id=employee_id, created_by=actor_id)
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
    session.execute(
        delete(EmployeeGroupMember).where(EmployeeGroupMember.group_id == group.id)
    )
    session.add_all([
        EmployeeGroupMember(
            group_id=group.id, employee_id=employee_id, created_by=actor_id
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
