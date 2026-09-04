"""Policy assignment endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_company_id, require_admin, require_self_or_admin
from app.api.responses import AssignmentOut
from app.db import get_session
from app.integrations import Employee, employee_service
from app.models import Policy, PolicyAssignment
from app.schemas import AssignIn, EndAssignmentIn
from app.services import assignment_service

router = APIRouter(prefix="/api", tags=["assignments"])


def _out(row: PolicyAssignment) -> AssignmentOut:
    return AssignmentOut.model_validate(
        {
            **{column.name: getattr(row, column.name) for column in row.__table__.columns},
            "employee_name": employee_service.get(row.employee_id).name,
            "policy_name": row.policy.name,
        }
    )


@router.get("/policies/{policy_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(
    policy_id: str,
    session: Session = Depends(get_session),
    _actor: Employee = Depends(require_admin),
):
    return [
        _out(row)
        for row in session.scalars(
            select(PolicyAssignment)
            .where(PolicyAssignment.policy_id == policy_id)
            .order_by(PolicyAssignment.effective_from)
        )
    ]


@router.post(
    "/policies/{policy_id}/assignments",
    response_model=list[AssignmentOut],
    status_code=201,
)
def assign(
    policy_id: str,
    payload: AssignIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(require_admin),
):
    policy = session.get(Policy, policy_id)
    if policy is None or policy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Unknown policy")
    try:
        rows = assignment_service.assign(
            session,
            policy=policy,
            employee_ids=payload.employee_ids,
            effective_from=payload.effective_from,
            actor_id=actor.id,
        )
    except assignment_service.AssignmentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    session.commit()
    return [_out(row) for row in rows]


@router.get("/employees/{employee_id}/assignments", response_model=list[AssignmentOut])
def employee_assignments(
    employee_id: str,
    session: Session = Depends(get_session),
    actor: Employee = Depends(get_actor),
):
    require_self_or_admin(employee_id, actor)
    return [
        _out(row)
        for row in assignment_service.assignments_for_employee(
            session, employee_id=employee_id
        )
    ]


@router.post("/assignments/{assignment_id}/end", response_model=AssignmentOut)
def end_assignment(
    assignment_id: str,
    payload: EndAssignmentIn,
    session: Session = Depends(get_session),
    actor: Employee = Depends(require_admin),
):
    row = session.get(PolicyAssignment, assignment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown assignment")
    try:
        assignment_service.end(
            session, assignment=row, effective_to=payload.effective_to
        )
    except assignment_service.AssignmentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    session.commit()
    return _out(row)
