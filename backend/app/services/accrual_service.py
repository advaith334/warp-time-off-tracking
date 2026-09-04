"""Retry-safe scheduled and payroll accrual entry points."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums
from app.domain.accrual import completed_tenure_months, payroll_amount, scheduled_amount
from app.domain.periods import iter_periods
from app.integrations import company_service, employee_service
from app.models import JobRun, PolicyAssignment
from app.services import ledger_service, policy_service


def _post_accrual(
    session: Session,
    *,
    amount: int,
    max_balance_minutes: int | None,
    source_id: str,
    note: str,
    **values,
) -> int:
    """Post the earned credit and make any cap loss explicit in the ledger."""
    before = ledger_service.balance(
        session,
        employee_id=values["employee_id"],
        policy_id=values["policy_id"],
        as_of=values["effective_date"],
    )
    created = ledger_service.post(
        session,
        **values,
        entry_type=enums.EntryType.ACCRUAL,
        amount_minutes=amount,
        source_id=source_id,
        note=note,
    )
    if max_balance_minutes is None:
        return created
    forfeited = max(before + amount - max_balance_minutes, 0)
    if forfeited:
        created += ledger_service.post(
            session,
            **values,
            entry_type=enums.EntryType.FORFEITURE,
            amount_minutes=-forfeited,
            source_id=f"{source_id}:forfeiture",
            note=f"Balance cap of {max_balance_minutes} minutes",
        )
    return created


def run_scheduled(session: Session, *, company_id: str, as_of: date) -> JobRun:
    created = 0
    company = company_service.get(company_id)
    assignments = session.scalars(
        select(PolicyAssignment).where(
            PolicyAssignment.company_id == company_id,
            PolicyAssignment.effective_from <= as_of,
        )
    )
    for assignment in assignments:
        employee = employee_service.get(assignment.employee_id)
        eligible_from = max(employee.start_date, assignment.effective_from)
        through = min(as_of, assignment.effective_to or as_of)
        for version in assignment.policy.versions:
            for rule in version.rules:
                if rule.method != enums.AccrualMethod.TIME or rule.frequency is None:
                    continue
                first = max(eligible_from, version.effective_from)
                for period in iter_periods(
                    first,
                    through,
                    rule.frequency,
                    pay_period_anchor=company.pay_period_anchor,
                ):
                    nominal = (
                        period.start
                        if rule.accrues_at == enums.AccruesAt.START_OF_PERIOD
                        else period.end
                    )
                    effective = max(nominal, first)
                    if effective > through:
                        continue
                    active = policy_service.version_effective_on(
                        session, assignment.policy_id, effective
                    )
                    if active is None or active.id != version.id:
                        continue
                    tenure = completed_tenure_months(employee.start_date, period.start)
                    eligible = [
                        candidate
                        for candidate in version.rules
                        if candidate.method == enums.AccrualMethod.TIME
                        and candidate.min_tenure_months <= tenure
                    ]
                    selected = max(eligible, key=lambda candidate: candidate.min_tenure_months)
                    if selected.id != rule.id:
                        continue
                    amount = scheduled_amount(
                        amount=rule.amount,
                        unit=rule.unit,
                        period=period,
                        eligible_from=eligible_from,
                        proration=version.new_hire_proration,
                        day_minutes=employee.work_minutes_per_day,
                    )
                    if not amount:
                        continue
                    created += _post_accrual(
                        session,
                        amount=amount,
                        max_balance_minutes=version.max_balance_minutes,
                        company_id=company_id,
                        employee_id=assignment.employee_id,
                        policy_id=assignment.policy_id,
                        policy_version_id=version.id,
                        effective_date=effective,
                        source_type=enums.SourceType.SCHEDULED_ACCRUAL,
                        source_id=f"{assignment.id}:{rule.id}:{period.start.isoformat()}",
                        note=(
                            f"{rule.amount} {rule.unit.value.lower()} per "
                            f"{rule.frequency.value.lower()}"
                        ),
                    )
    run = JobRun(
        company_id=company_id,
        kind=enums.JobKind.SCHEDULED,
        source_id=as_of.isoformat(),
        status="SUCCESS",
        entries_created=created,
    )
    session.add(run)
    session.flush()
    return run


def on_payroll_processed(
    session: Session,
    *,
    company_id: str,
    payroll_run_id: str,
    period_end: date,
    minutes_by_employee: dict[str, int],
) -> JobRun:
    created = 0
    for employee_id, minutes_worked in minutes_by_employee.items():
        assignments = session.scalars(
            select(PolicyAssignment).where(
                PolicyAssignment.company_id == company_id,
                PolicyAssignment.employee_id == employee_id,
                PolicyAssignment.effective_from <= period_end,
                (PolicyAssignment.effective_to.is_(None))
                | (PolicyAssignment.effective_to >= period_end),
            )
        )
        for assignment in assignments:
            employee = employee_service.get(employee_id)
            version = policy_service.version_effective_on(
                session, assignment.policy_id, period_end
            )
            if version is None:
                continue
            for rule in version.rules:
                if rule.method != enums.AccrualMethod.HOURS_WORKED:
                    continue
                tenure = completed_tenure_months(
                    employee.start_date, period_end
                )
                eligible = [
                    candidate
                    for candidate in version.rules
                    if candidate.method == enums.AccrualMethod.HOURS_WORKED
                    and candidate.min_tenure_months <= tenure
                ]
                selected = max(eligible, key=lambda candidate: candidate.min_tenure_months)
                if selected.id != rule.id:
                    continue
                amount = payroll_amount(
                    minutes_worked=minutes_worked,
                    amount=rule.amount,
                    unit=rule.unit,
                    per_minutes_worked=rule.per_minutes_worked,
                    day_minutes=employee.work_minutes_per_day,
                )
                if amount:
                    created += _post_accrual(
                        session,
                        amount=amount,
                        max_balance_minutes=version.max_balance_minutes,
                        company_id=company_id,
                        employee_id=employee_id,
                        policy_id=assignment.policy_id,
                        policy_version_id=version.id,
                        effective_date=period_end,
                        source_type=enums.SourceType.PAYROLL_ACCRUAL,
                        source_id=f"{payroll_run_id}:{employee_id}:{rule.id}",
                        note=f"{minutes_worked} minutes worked",
                    )
    run = JobRun(
        company_id=company_id,
        kind=enums.JobKind.PAYROLL,
        source_id=payroll_run_id,
        status="SUCCESS",
        entries_created=created,
    )
    session.add(run)
    session.flush()
    return run
