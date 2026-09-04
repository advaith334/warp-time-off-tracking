"""Replay-safe annual policy rollover."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums
from app.domain.rollover import plan
from app.models import JobRun, PolicyAssignment
from app.services import ledger_service, policy_service


def run(session: Session, *, company_id: str, as_of: date) -> JobRun:
    period_end = date(as_of.year, 1, 1) - timedelta(days=1)
    created = 0
    assignments = session.scalars(
        select(PolicyAssignment).where(
            PolicyAssignment.company_id == company_id,
            PolicyAssignment.effective_from <= period_end,
            (PolicyAssignment.effective_to.is_(None))
            | (PolicyAssignment.effective_to >= period_end),
        )
    )
    for assignment in assignments:
        version = policy_service.version_effective_on(
            session, assignment.policy_id, period_end
        )
        if version is None or version.kind == enums.PolicyKind.UNLIMITED:
            continue
        balance = ledger_service.balance(
            session,
            employee_id=assignment.employee_id,
            policy_id=assignment.policy_id,
            as_of=period_end,
        )
        source = f"{assignment.policy_id}:{assignment.employee_id}:{period_end.isoformat()}"
        for entry in plan(
            balance_minutes=balance,
            period_end=period_end,
            carryover_cap_minutes=version.carryover_cap_minutes,
            expires_at_period_end=version.expires_at_period_end,
        ):
            created += ledger_service.post(
                session,
                company_id=company_id,
                employee_id=assignment.employee_id,
                policy_id=assignment.policy_id,
                policy_version_id=version.id,
                entry_type=entry.entry_type,
                amount_minutes=entry.amount_minutes,
                effective_date=entry.effective_date,
                source_type=enums.SourceType.PERIOD_ROLLOVER,
                source_id=f"{source}:{entry.source_suffix}",
                note=entry.note,
            )
    run = JobRun(
        kind=enums.JobKind.ROLLOVER,
        source_id=period_end.isoformat(),
        status="SUCCESS",
        entries_created=created,
    )
    session.add(run)
    session.flush()
    return run
