"""Company-managed employee groups and policy audience endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_company_id, require_admin
from app.api.responses import EmployeeGroupOut, GroupMemberOut, PolicyOut
from app.clock import today
from app.db import get_session
from app.integrations import Employee, employee_service
from app.models import EmployeeGroup, Policy
from app.schemas import GroupCreateIn, GroupMembersIn, PolicyAudienceIn
from app.services import group_service, policy_service

router = APIRouter(prefix="/api", tags=["groups"])


def _group_out(group: EmployeeGroup) -> EmployeeGroupOut:
    members = []
    for member in sorted(group.members, key=lambda row: employee_service.get(row.employee_id).name):
        employee = employee_service.get(member.employee_id)
        members.append(
            GroupMemberOut(
                employee_id=employee.id,
                employee_name=employee.name,
                employment_type=employee.employment_type,
            )
        )
    return EmployeeGroupOut(id=group.id, name=group.name, members=members)


def _group(session: Session, group_id: str, company_id: str) -> EmployeeGroup:
    group = session.scalar(
        select(EmployeeGroup)
        .options(selectinload(EmployeeGroup.members))
        .where(EmployeeGroup.id == group_id, EmployeeGroup.company_id == company_id)
        .with_for_update()
    )
    if group is None:
        raise HTTPException(status_code=404, detail="Unknown employee group")
    return group


@router.get("/groups", response_model=list[EmployeeGroupOut])
def list_groups(
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    groups = session.scalars(
        select(EmployeeGroup)
        .options(selectinload(EmployeeGroup.members))
        .where(EmployeeGroup.company_id == company_id)
        .order_by(EmployeeGroup.name)
    )
    return [_group_out(group) for group in groups]


@router.post("/groups", response_model=EmployeeGroupOut, status_code=201)
def create_group(
    payload: GroupCreateIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(require_admin),
):
    try:
        group = group_service.create(
            session,
            company_id=company_id,
            name=payload.name,
            employee_ids=payload.employee_ids,
            actor_id=actor.id,
        )
        session.commit()
    except (group_service.GroupError, IntegrityError) as exc:
        session.rollback()
        detail = (
            str(exc)
            if isinstance(exc, group_service.GroupError)
            else "Group name already exists."
        )
        raise HTTPException(status_code=409, detail=detail) from None
    return _group_out(group)


@router.put("/groups/{group_id}/members", response_model=EmployeeGroupOut)
def replace_group_members(
    group_id: str,
    payload: GroupMembersIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(require_admin),
):
    group = _group(session, group_id, company_id)
    try:
        group_service.replace_members(
            session,
            group=group,
            employee_ids=payload.employee_ids,
            effective_from=payload.effective_from,
            actor_id=actor.id,
        )
        session.commit()
    except group_service.GroupError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return _group_out(group)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(require_admin),
):
    group = _group(session, group_id, company_id)
    try:
        group_service.remove(
            session, group=group, effective_from=today(session), actor_id=actor.id
        )
        session.commit()
    except group_service.GroupError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return Response(status_code=204)


@router.put("/policies/{policy_id}/audience", response_model=PolicyOut)
def set_policy_audience(
    policy_id: str,
    payload: PolicyAudienceIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(require_admin),
):
    policy = session.scalar(
        select(Policy)
        .where(Policy.id == policy_id, Policy.company_id == company_id)
        .with_for_update()
    )
    if policy is None or policy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Unknown policy")
    try:
        group_service.set_policy_audience(
            session,
            policy=policy,
            all_employees=payload.all_employees,
            group_ids=payload.group_ids,
            effective_from=payload.effective_from,
            actor_id=actor.id,
        )
        session.commit()
    except group_service.GroupError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    session.refresh(policy)
    return PolicyOut.of(policy, policy_service.latest_version(session, policy.id))
