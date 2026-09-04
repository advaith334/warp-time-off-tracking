"""Policy catalogue and immutable-version endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_company_id, require_admin
from app.api.responses import CategoryOut, PolicyOut, PolicyVersionOut
from app.db import get_session
from app.integrations import Employee
from app.models import Policy, TimeOffCategory
from app.schemas import CategoryCreateIn, PolicyCreateIn, PolicyUpdateIn
from app.services import policy_service

router = APIRouter(prefix="/api", tags=["policies"])


def _policy(session: Session, policy_id: str, company_id: str) -> Policy:
    policy = session.get(Policy, policy_id)
    if policy is None or policy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Unknown policy")
    return policy


@router.get("/categories", response_model=list[CategoryOut])
def categories(
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
):
    return list(
        session.scalars(
            select(TimeOffCategory)
            .where(TimeOffCategory.company_id == company_id)
            .order_by(TimeOffCategory.name)
        )
    )


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreateIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    category = TimeOffCategory(company_id=company_id, **payload.model_dump())
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.get("/policies", response_model=list[PolicyOut])
def policies(
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
):
    rows = session.scalars(
        select(Policy).where(Policy.company_id == company_id).order_by(Policy.name)
    )
    return [PolicyOut.of(row, policy_service.latest_version(session, row.id)) for row in rows]


@router.post("/policies", response_model=PolicyOut, status_code=201)
def create_policy(
    payload: PolicyCreateIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(require_admin),
):
    try:
        policy = policy_service.create(
            session,
            company_id=company_id,
            actor_id=actor.id,
            **payload.model_dump(exclude={"rules"}),
            rules=[rule.model_dump() for rule in payload.rules],
        )
    except policy_service.PolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    session.commit()
    return PolicyOut.of(policy, policy_service.latest_version(session, policy.id))


@router.put("/policies/{policy_id}", response_model=PolicyVersionOut)
def update_policy(
    policy_id: str,
    payload: PolicyUpdateIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(require_admin),
):
    try:
        version = policy_service.update(
            session,
            policy=_policy(session, policy_id, company_id),
            actor_id=actor.id,
            **payload.model_dump(exclude={"rules"}),
            rules=[rule.model_dump() for rule in payload.rules],
        )
    except policy_service.PolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    session.commit()
    return version


@router.get("/policies/{policy_id}/versions", response_model=list[PolicyVersionOut])
def versions(
    policy_id: str,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
):
    return list(reversed(_policy(session, policy_id, company_id).versions))
