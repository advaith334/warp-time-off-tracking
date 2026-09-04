"""Operational entry points for scheduled and payroll accrual."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_company_id, require_admin
from app.api.responses import JobRunOut
from app.db import get_session
from app.integrations import Employee
from app.schemas import PayrollAccrualIn
from app.services import accrual_service, rollover_service

router = APIRouter(prefix="/api/accruals", tags=["accruals"])


@router.post("/scheduled", response_model=JobRunOut)
def scheduled(
    as_of: date,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    run = accrual_service.run_scheduled(session, company_id=company_id, as_of=as_of)
    session.commit()
    return run


@router.post("/payroll", response_model=JobRunOut)
def payroll(
    payload: PayrollAccrualIn,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    run = accrual_service.on_payroll_processed(
        session, company_id=company_id, **payload.model_dump()
    )
    session.commit()
    return run


@router.post("/rollover", response_model=JobRunOut)
def rollover(
    as_of: date,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    _actor: Employee = Depends(require_admin),
):
    run = rollover_service.run(session, company_id=company_id, as_of=as_of)
    session.commit()
    return run
