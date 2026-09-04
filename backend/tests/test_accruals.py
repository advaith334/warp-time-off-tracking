from datetime import date
from decimal import Decimal

from app import enums
from app.domain.accrual import scheduled_amount
from app.domain.periods import Period
from app.models import BalanceSnapshot, LedgerEntry, TimeOffCategory
from app.services import accrual_service, assignment_service, policy_service
from sqlalchemy import func, select


def _policy(session, *, method=enums.AccrualMethod.TIME, frequency=enums.Schedule.MONTHLY):
    category = TimeOffCategory(company_id="cmp_warp_demo", name="Vacation")
    session.add(category)
    session.flush()
    rule = {
        "method": method,
        "amount": 1,
        "unit": enums.RateUnit.HOUR,
        "frequency": frequency if method == enums.AccrualMethod.TIME else None,
        "accrues_at": (
            enums.AccruesAt.START_OF_PERIOD
            if method == enums.AccrualMethod.TIME
            else None
        ),
        "per_minutes_worked": 1440 if method == enums.AccrualMethod.HOURS_WORKED else None,
    }
    return policy_service.create(
        session,
        company_id="cmp_warp_demo",
        actor_id="adm_lindsey",
        name="Vacation",
        category_id=category.id,
        effective_from=date(2026, 1, 1),
        kind=enums.PolicyKind.ACCRUAL,
        change_reason="Initial policy",
        rules=[rule],
    )


def _assign(session, policy, employee_id="emp_ada"):
    return assignment_service.assign(
        session,
        policy=policy,
        employee_ids=[employee_id],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )[0]


def test_a_missed_scheduler_run_catches_up_and_a_replay_is_a_no_op(session):
    policy = _policy(session)
    _assign(session, policy)

    first = accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 3, 1)
    )
    second = accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 3, 1)
    )

    assert first.entries_created == 3
    assert second.entries_created == 0


def test_a_mid_period_joiner_is_prorated_by_eligible_calendar_days(session):
    policy = _policy(session, frequency=enums.Schedule.YEARLY)
    _assign(session, policy, "emp_grace")

    accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 3, 1)
    )
    entry = session.scalar(select(LedgerEntry))

    assert entry.effective_date == date(2026, 2, 18)
    assert entry.amount_minutes == 52  # floor(60 minutes * 317 / 365)


def test_new_hire_setting_supports_prorated_full_or_next_period_accrual():
    values = {
        mode: scheduled_amount(
            amount=Decimal(20),
            unit=enums.RateUnit.DAY,
            period=Period(date(2026, 1, 1), date(2026, 1, 31)),
            eligible_from=date(2026, 1, 16),
            proration=mode,
        )
        for mode in enums.NewHireProration
    }
    assert values == {
        enums.NewHireProration.PRORATE: 4954,
        enums.NewHireProration.FULL: 9600,
        enums.NewHireProration.NONE: 0,
    }


def test_payroll_replay_cannot_credit_the_same_work_twice(session):
    policy = _policy(session, method=enums.AccrualMethod.HOURS_WORKED)
    _assign(session, policy, "emp_katherine")

    first = accrual_service.on_payroll_processed(
        session,
        company_id="cmp_warp_demo",
        payroll_run_id="pay_2026_01",
        period_end=date(2026, 1, 31),
        minutes_by_employee={"emp_katherine": 2880},
    )
    second = accrual_service.on_payroll_processed(
        session,
        company_id="cmp_warp_demo",
        payroll_run_id="pay_2026_01",
        period_end=date(2026, 1, 31),
        minutes_by_employee={"emp_katherine": 2880},
    )

    assert first.entries_created == 1
    assert second.entries_created == 0
    assert session.scalar(select(func.sum(LedgerEntry.amount_minutes))) == 120


def test_snapshot_is_exactly_the_sum_of_the_ledger(session):
    policy = _policy(session)
    _assign(session, policy)
    accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 2, 1)
    )

    ledger_total = session.scalar(select(func.sum(LedgerEntry.amount_minutes)))
    snapshot = session.scalar(select(BalanceSnapshot))
    assert snapshot.balance_minutes == ledger_total
