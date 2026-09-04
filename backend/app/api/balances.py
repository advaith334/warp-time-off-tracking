"""Employee balance and ledger views."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_company_id, require_self_or_admin
from app.api.responses import BalanceOut, LedgerEntryOut
from app.db import get_session
from app.integrations import Employee
from app.models import LedgerEntry
from app.services import balance_service

router = APIRouter(prefix="/api/employees/{employee_id}", tags=["balances"])


@router.get("/balances", response_model=list[BalanceOut])
def balances(
    employee_id: str,
    on_date: date,
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(get_actor),
):
    require_self_or_admin(employee_id, actor)
    return balance_service.list_balances(
        session, company_id=company_id, employee_id=employee_id, on_date=on_date
    )


@router.get("/ledger", response_model=list[LedgerEntryOut])
def ledger(
    employee_id: str,
    policy_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
    company_id: str = Depends(get_company_id),
    actor: Employee = Depends(get_actor),
):
    require_self_or_admin(employee_id, actor)
    query = select(LedgerEntry).where(
        LedgerEntry.company_id == company_id,
        LedgerEntry.employee_id == employee_id,
    )
    if policy_id:
        query = query.where(LedgerEntry.policy_id == policy_id)
    return list(session.scalars(query.order_by(LedgerEntry.effective_date, LedgerEntry.created_at)))
