"""Employee balance and ledger views."""

from datetime import date

from fastapi import APIRouter, Depends
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
    session: Session = Depends(get_session),
    actor: Employee = Depends(get_actor),
):
    require_self_or_admin(employee_id, actor)
    return list(
        session.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.employee_id == employee_id)
            .order_by(LedgerEntry.effective_date, LedgerEntry.created_at)
        )
    )
