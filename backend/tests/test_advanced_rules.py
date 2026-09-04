from datetime import date, timedelta
from itertools import pairwise

import pytest
from app import enums
from app.api.deps import get_actor
from app.db import get_session
from app.domain.periods import iter_periods
from app.integrations import employee_service
from app.main import app
from app.models import Holiday, LedgerEntry, TimeOffCategory
from app.services import (
    accrual_service,
    assignment_service,
    holiday_service,
    ledger_service,
    policy_service,
    request_service,
    rollover_service,
)
from fastapi.testclient import TestClient
from sqlalchemy import select


def _policy(
    session,
    *,
    employee_id="emp_ada",
    rules=None,
    carryover_cap_minutes=None,
    max_balance_minutes=None,
):
    category = TimeOffCategory(company_id="cmp_warp_demo", name="Vacation")
    session.add(category)
    session.flush()
    rules = rules or [
        {
            "method": enums.AccrualMethod.TIME,
            "amount": 1,
            "unit": enums.RateUnit.DAY,
            "frequency": enums.Schedule.MONTHLY,
            "accrues_at": enums.AccruesAt.START_OF_PERIOD,
            "per_minutes_worked": None,
            "min_tenure_months": 0,
        }
    ]
    policy = policy_service.create(
        session,
        company_id="cmp_warp_demo",
        actor_id="adm_lindsey",
        name="Vacation",
        category_id=category.id,
        effective_from=date(2026, 1, 1),
        kind=enums.PolicyKind.ACCRUAL,
        change_reason="Initial policy",
        carryover_cap_minutes=carryover_cap_minutes,
        max_balance_minutes=max_balance_minutes,
        rules=rules,
    )
    assignment_service.assign(
        session,
        policy=policy,
        employee_ids=[employee_id],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )
    return category, policy


def _credit(session, policy, *, employee_id="emp_ada", minutes=2400):
    version = policy_service.latest_version(session, policy.id)
    ledger_service.post(
        session,
        company_id="cmp_warp_demo",
        employee_id=employee_id,
        policy_id=policy.id,
        policy_version_id=version.id,
        entry_type=enums.EntryType.ACCRUAL,
        amount_minutes=minutes,
        effective_date=date(2026, 1, 1),
        source_type=enums.SourceType.SCHEDULED_ACCRUAL,
        source_id=f"opening:{employee_id}",
        note="Opening test balance",
    )


def test_six_hour_employee_uses_a_six_hour_day_for_accrual_and_requests(session):
    category, _policy_row = _policy(session, employee_id="emp_alan")
    accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 1, 1)
    )
    entry = session.scalar(select(LedgerEntry))
    assert entry.amount_minutes == 360

    preview = request_service.preview(
        session,
        employee_id="emp_alan",
        category_id=category.id,
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 5),
        partial_minutes=None,
    )
    assert preview["total_minutes"] == 360


def test_observed_holiday_is_stored_and_a_request_does_not_charge_it(session):
    category, policy = _policy(session)
    _credit(session, policy)
    holiday_service.ensure_year(session, company_id="cmp_warp_demo", year=2026)
    observed = session.scalar(
        select(Holiday).where(Holiday.date == date(2026, 7, 3))
    )
    assert observed is not None
    assert observed.observed is True

    preview = request_service.preview(
        session,
        employee_id="emp_ada",
        category_id=category.id,
        start_date=date(2026, 7, 2),
        end_date=date(2026, 7, 6),
        partial_minutes=None,
    )
    assert preview["days"] == [
        (date(2026, 7, 2), 480),
        (date(2026, 7, 6), 480),
    ]


def test_holiday_changes_after_submission_do_not_reprice_frozen_request_days(session):
    category, policy = _policy(session)
    _credit(session, policy)
    request = request_service.submit(
        session,
        actor_id="emp_ada",
        reason="Two-day break",
        employee_id="emp_ada",
        category_id=category.id,
        start_date=date(2026, 7, 2),
        end_date=date(2026, 7, 3),
        partial_minutes=None,
    )
    session.add(
        Holiday(
            company_id="cmp_warp_demo",
            date=date(2026, 7, 3),
            name="New company holiday",
            observed=False,
        )
    )
    session.flush()

    request_service.decide(
        session, request=request, approve=True, actor_id="adm_lindsey", note=None
    )
    debits = list(
        session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.entry_type == enums.EntryType.REQUEST_DEBIT
            )
        )
    )
    assert request.total_minutes == 960
    assert [day.date for day in request.days] == [date(2026, 7, 2), date(2026, 7, 3)]
    assert [entry.amount_minutes for entry in debits] == [-960]


def test_balance_cap_keeps_credit_and_forfeiture_explainable(session):
    _, policy = _policy(session, max_balance_minutes=300)
    run = accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 1, 1)
    )
    entries = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.created_at)))
    assert run.entries_created == 2
    assert [(entry.entry_type, entry.amount_minutes) for entry in entries] == [
        (enums.EntryType.ACCRUAL, 480),
        (enums.EntryType.FORFEITURE, -180),
    ]
    assert ledger_service.balance(session, employee_id="emp_ada", policy_id=policy.id) == 300


def test_rollover_replay_is_a_no_op_and_expiry_is_separate_from_carryover(session):
    _, policy = _policy(session, carryover_cap_minutes=600)
    _credit(session, policy, minutes=900)

    first = rollover_service.run(
        session, company_id="cmp_warp_demo", as_of=date(2027, 1, 1)
    )
    second = rollover_service.run(
        session, company_id="cmp_warp_demo", as_of=date(2027, 1, 1)
    )
    entries = list(
        session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.source_type == enums.SourceType.PERIOD_ROLLOVER
            ).order_by(LedgerEntry.effective_date)
        )
    )
    assert first.entries_created == 2
    assert second.entries_created == 0
    assert [(entry.entry_type, entry.amount_minutes) for entry in entries] == [
        (enums.EntryType.EXPIRATION, -900),
        (enums.EntryType.CARRYOVER, 600),
    ]
    assert ledger_service.balance(session, employee_id="emp_ada", policy_id=policy.id) == 600


def test_tenure_tier_starts_on_the_first_future_period_boundary(session):
    rules = [
        {
            "method": enums.AccrualMethod.TIME,
            "amount": amount,
            "unit": enums.RateUnit.HOUR,
            "frequency": enums.Schedule.MONTHLY,
            "accrues_at": enums.AccruesAt.START_OF_PERIOD,
            "per_minutes_worked": None,
            "min_tenure_months": tenure,
        }
        for amount, tenure in ((1, 0), (2, 1))
    ]
    _policy(session, employee_id="emp_grace", rules=rules)
    accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 4, 1)
    )
    entries = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.effective_date)))
    assert [(entry.effective_date, entry.amount_minutes) for entry in entries] == [
        (date(2026, 2, 18), 23),
        (date(2026, 3, 1), 60),
        (date(2026, 4, 1), 120),
    ]


def test_future_policy_version_changes_only_future_accrual_periods(session):
    _, policy = _policy(session)
    policy_service.update(
        session,
        policy=policy,
        actor_id="adm_lindsey",
        effective_from=date(2026, 3, 1),
        kind=enums.PolicyKind.ACCRUAL,
        change_reason="Increase future monthly accrual",
        name=None,
        rules=[
            {
                "method": enums.AccrualMethod.TIME,
                "amount": 2,
                "unit": enums.RateUnit.DAY,
                "frequency": enums.Schedule.MONTHLY,
                "accrues_at": enums.AccruesAt.START_OF_PERIOD,
                "per_minutes_worked": None,
                "min_tenure_months": 0,
            }
        ],
    )
    accrual_service.run_scheduled(
        session, company_id="cmp_warp_demo", as_of=date(2026, 4, 1)
    )
    entries = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.effective_date)))
    assert [(entry.effective_date, entry.amount_minutes) for entry in entries] == [
        (date(2026, 1, 1), 480),
        (date(2026, 2, 1), 480),
        (date(2026, 3, 1), 960),
        (date(2026, 4, 1), 960),
    ]


def test_full_year_end_expiration_leaves_no_carryover(session):
    _, policy = _policy(session)
    version = policy_service.latest_version(session, policy.id)
    version.expires_at_period_end = True
    _credit(session, policy, minutes=900)

    run = rollover_service.run(
        session, company_id="cmp_warp_demo", as_of=date(2027, 1, 1)
    )
    rollover_entries = list(
        session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.source_type == enums.SourceType.PERIOD_ROLLOVER
            )
        )
    )
    assert run.entries_created == 1
    assert [(entry.entry_type, entry.amount_minutes) for entry in rollover_entries] == [
        (enums.EntryType.EXPIRATION, -900)
    ]
    assert ledger_service.balance(session, employee_id="emp_ada", policy_id=policy.id) == 0


def test_monthly_periods_tile_for_month_end_and_leap_day_hires():
    for hire in (
        date(2024, 1, 29),
        date(2024, 1, 30),
        date(2024, 1, 31),
        date(2024, 2, 29),
    ):
        periods = list(iter_periods(hire, date(2025, 4, 1), enums.Schedule.MONTHLY))
        assert periods[0].start <= hire <= periods[0].end
        for earlier, later in pairwise(periods):
            assert later.start == earlier.end + timedelta(days=1)


@pytest.mark.parametrize(
    "schedule",
    [
        enums.Schedule.DAILY,
        enums.Schedule.WEEKLY,
        enums.Schedule.SEMIMONTHLY,
        enums.Schedule.BIWEEKLY,
    ],
)
def test_additional_accrual_cadences_tile_without_gaps(schedule):
    start = date(2026, 1, 1)
    periods = list(
        iter_periods(
            start,
            date(2026, 2, 5),
            schedule,
            pay_period_anchor=date(2026, 1, 5),
        )
    )
    assert periods[0].start <= start <= periods[0].end
    for earlier, later in pairwise(periods):
        assert later.start == earlier.end + timedelta(days=1)


def test_cross_year_request_debits_and_reverses_each_policy_year(session):
    category, policy = _policy(session)
    _credit(session, policy)
    request = request_service.submit(
        session,
        actor_id="emp_ada",
        reason="New year break",
        employee_id="emp_ada",
        category_id=category.id,
        start_date=date(2026, 12, 31),
        end_date=date(2027, 1, 1),
        partial_minutes=None,
    )
    request_service.decide(
        session, request=request, approve=True, actor_id="adm_lindsey", note=None
    )
    request_service.cancel(
        session, request=request, actor_id="emp_ada", today=date(2026, 12, 1)
    )

    request_entries = list(
        session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.entry_type.in_(
                    [enums.EntryType.REQUEST_DEBIT, enums.EntryType.REQUEST_REVERSAL]
                )
            )
            .order_by(LedgerEntry.entry_type, LedgerEntry.effective_date)
        )
    )
    assert len(request_entries) == 4
    assert {entry.effective_date.year for entry in request_entries} == {2026, 2027}
    assert sum(entry.amount_minutes for entry in request_entries) == 0


def test_advanced_policy_settings_round_trip_through_the_admin_api(session):
    category = TimeOffCategory(company_id="cmp_warp_demo", name="Vacation")
    session.add(category)
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_actor] = lambda: employee_service.get("adm_lindsey")
    try:
        response = TestClient(app).post(
            "/api/policies",
            json={
                "name": "Tiered vacation",
                "category_id": category.id,
                "effective_from": "2026-01-01",
                "kind": "ACCRUAL",
                "all_employees": True,
                "change_reason": "Initial policy",
                "new_hire_proration": "FULL",
                "allow_negative": True,
                "negative_floor_minutes": -480,
                "max_balance_minutes": 2400,
                "carryover_cap_minutes": 1200,
                "tenure_transition": "NEXT_PERIOD",
                "rules": [
                    {
                        "method": "TIME",
                        "amount": 10,
                        "unit": "DAY",
                        "frequency": "YEARLY",
                        "accrues_at": "START_OF_PERIOD",
                        "min_tenure_months": 0,
                    },
                    {
                        "method": "TIME",
                        "amount": 15,
                        "unit": "DAY",
                        "frequency": "YEARLY",
                        "accrues_at": "START_OF_PERIOD",
                        "min_tenure_months": 24,
                    },
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    version = response.json()["current_version"]
    assert version["max_balance_minutes"] == 2400
    assert version["carryover_cap_minutes"] == 1200
    assert version["new_hire_proration"] == "FULL"
    assert version["allow_negative"] is True
    assert version["negative_floor_minutes"] == -480
    assert [rule["min_tenure_months"] for rule in version["rules"]] == [0, 24]
