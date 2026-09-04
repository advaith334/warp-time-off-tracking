"""Append-only ledger writes and rebuildable balance snapshots."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import BalanceSnapshot, LedgerEntry


def balance(session: Session, *, employee_id: str, policy_id: str) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_minutes), 0)).where(
                LedgerEntry.employee_id == employee_id,
                LedgerEntry.policy_id == policy_id,
            )
        )
    )


def refresh_snapshot(session: Session, *, employee_id: str, policy_id: str) -> int:
    total = balance(session, employee_id=employee_id, policy_id=policy_id)
    statement = insert(BalanceSnapshot).values(
        employee_id=employee_id,
        policy_id=policy_id,
        balance_minutes=total,
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["employee_id", "policy_id"],
            set_={"balance_minutes": total},
        )
    )
    return total


def post(session: Session, **values) -> int:
    entry_id = session.scalar(
        insert(LedgerEntry)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["source_type", "source_id"])
        .returning(LedgerEntry.id)
    )
    if entry_id is not None:
        refresh_snapshot(
            session,
            employee_id=values["employee_id"],
            policy_id=values["policy_id"],
        )
    return int(entry_id is not None)
