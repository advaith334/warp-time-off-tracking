"""Admin-only controls for demonstrating time-dependent behavior."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import clock
from app.api.deps import get_actor, get_company_id, require_admin
from app.api.responses import JobRunOut
from app.db import get_session
from app.integrations import Employee
from app.schemas import ClockIn
from app.services import accrual_service, rollover_service

router = APIRouter(prefix="/api/dev", tags=["demo"])


@router.get("/state")
def state(
    session: Session = Depends(get_session),
    _actor: Employee = Depends(get_actor),
):
    return {"today": clock.today(session)}


@router.post("/clock")
def set_clock(
    payload: ClockIn,
    session: Session = Depends(get_session),
    _actor: Employee = Depends(require_admin),
):
    value = clock.set_today(session, payload.current_date)
    session.commit()
    return {"today": value}


@router.post("/accruals", response_model=JobRunOut)
def run_accruals(
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    run = accrual_service.run_scheduled(
        session, company_id=company_id, as_of=clock.today(session)
    )
    session.commit()
    return run


@router.post("/rollover", response_model=JobRunOut)
def run_rollover(
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    run = rollover_service.run(session, company_id=company_id, as_of=clock.today(session))
    session.commit()
    return run
