from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from app import enums
from app.api.deps import get_actor
from app.db import get_session
from app.domain.requests import RequestError, request_days
from app.integrations import employee_service
from app.main import app
from app.models import BalanceSnapshot, LedgerEntry, TimeOffCategory, TimeOffRequest
from app.schema_setup import recreate_schema
from app.services import assignment_service, ledger_service, policy_service, request_service
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker


def _setup(
    session,
    *,
    credit=2400,
    allow_negative=False,
    floor=0,
    category_name="Vacation",
):
    category = TimeOffCategory(company_id="cmp_warp_demo", name=category_name)
    session.add(category)
    session.flush()
    policy = policy_service.create(
        session,
        company_id="cmp_warp_demo",
        actor_id="adm_lindsey",
        name=category_name,
        category_id=category.id,
        effective_from=date(2026, 1, 1),
        kind=enums.PolicyKind.ACCRUAL,
        change_reason="Initial policy",
        allow_negative=allow_negative,
        negative_floor_minutes=floor,
        rules=[{
            "method": enums.AccrualMethod.TIME,
            "amount": 10,
            "unit": enums.RateUnit.DAY,
            "frequency": enums.Schedule.YEARLY,
            "accrues_at": enums.AccruesAt.START_OF_PERIOD,
            "per_minutes_worked": None,
        }],
    )
    assignment_service.assign(
        session,
        policy=policy,
        employee_ids=["emp_ada"],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )
    version = policy_service.latest_version(session, policy.id)
    if credit:
        ledger_service.post(
            session,
            company_id="cmp_warp_demo",
            employee_id="emp_ada",
            policy_id=policy.id,
            policy_version_id=version.id,
            entry_type=enums.EntryType.ACCRUAL,
            amount_minutes=credit,
            effective_date=date(2026, 1, 1),
            source_type=enums.SourceType.SCHEDULED_ACCRUAL,
            source_id="opening-credit",
            note="test credit",
        )
    return category, policy


def _submit(session, category, *, start=date(2027, 1, 4), end=date(2027, 1, 5)):
    return request_service.submit(
        session,
        actor_id="emp_ada",
        reason="Vacation",
        employee_id="emp_ada",
        category_id=category.id,
        start_date=start,
        end_date=end,
        partial_minutes=None,
    )


def test_preview_and_submit_freeze_the_same_weekday_cost(session):
    category, _ = _setup(session)
    preview = request_service.preview(
        session,
        employee_id="emp_ada",
        category_id=category.id,
        start_date=date(2027, 1, 8),
        end_date=date(2027, 1, 11),
        partial_minutes=None,
    )
    request = _submit(
        session,
        category,
        start=date(2027, 1, 8),
        end=date(2027, 1, 11),
    )
    assert preview["total_minutes"] == 960
    assert request.total_minutes == preview["total_minutes"]
    assert [day.date for day in request.days] == [date(2027, 1, 8), date(2027, 1, 11)]


def test_two_pending_requests_cannot_spend_the_same_balance(session):
    category, _ = _setup(session, credit=480)
    _submit(session, category, end=date(2027, 1, 4))
    with pytest.raises(RequestError, match="available balance"):
        _submit(session, category, start=date(2027, 1, 5), end=date(2027, 1, 5))


def test_a_category_without_a_policy_rejects_requests_clearly(session):
    category = TimeOffCategory(company_id="cmp_warp_demo", name="Maternity")
    session.add(category)
    session.flush()

    with pytest.raises(RequestError, match="No policy covers"):
        request_service.preview(
            session,
            employee_id="emp_ada",
            category_id=category.id,
            start_date=date(2027, 1, 4),
            end_date=date(2027, 1, 4),
            partial_minutes=None,
        )


def test_negative_balance_is_disabled_by_default_and_respects_an_explicit_floor(session):
    blocked_category, _ = _setup(session, credit=0)
    with pytest.raises(RequestError, match="available balance"):
        _submit(session, blocked_category, end=date(2027, 1, 4))

    allowed_category, _ = _setup(
        session,
        credit=0,
        allow_negative=True,
        floor=-480,
        category_name="Sick",
    )
    request = _submit(session, allowed_category, end=date(2027, 1, 4))
    assert request.total_minutes == 480


def test_pending_and_approved_requests_block_overlapping_dates(session):
    category, _ = _setup(session)
    first = _submit(session, category)
    with pytest.raises(RequestError, match="overlaps"):
        _submit(
            session,
            category,
            start=date(2027, 1, 5),
            end=date(2027, 1, 6),
        )

    request_service.decide(
        session, request=first, approve=True, actor_id="adm_lindsey", note=None
    )
    with pytest.raises(RequestError, match="overlaps"):
        _submit(
            session,
            category,
            start=date(2027, 1, 5),
            end=date(2027, 1, 6),
        )


def test_partial_time_is_single_day_and_cannot_exceed_a_workday():
    with pytest.raises(RequestError, match="single-day"):
        request_days(
            start=date(2027, 1, 4),
            end=date(2027, 1, 5),
            partial_minutes=60,
        )
    with pytest.raises(RequestError, match="between 1 and 480"):
        request_days(
            start=date(2027, 1, 4),
            end=date(2027, 1, 4),
            partial_minutes=481,
        )


def test_a_weekend_only_request_is_rejected():
    with pytest.raises(RequestError, match="no working days"):
        request_days(
            start=date(2027, 1, 9),
            end=date(2027, 1, 10),
            partial_minutes=None,
        )


def test_approval_debits_once_and_releases_the_hold(session):
    category, policy = _setup(session)
    request = _submit(session, category)
    request_service.decide(
        session, request=request, approve=True, actor_id="adm_lindsey", note=None
    )
    with pytest.raises(RequestError, match="pending"):
        request_service.decide(
            session, request=request, approve=True, actor_id="adm_lindsey", note=None
        )
    snapshot = session.get(BalanceSnapshot, ("emp_ada", policy.id))
    assert snapshot.balance_minutes == 1440
    assert snapshot.pending_hold_minutes == 0


def test_two_admins_approving_concurrently_create_one_debit(engine):
    recreate_schema(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as setup_session:
        category, _ = _setup(setup_session)
        request_id = _submit(setup_session, category).id
        setup_session.commit()

    ready = Barrier(2)

    def approve(actor_id):
        with factory() as worker:
            request = worker.get(TimeOffRequest, request_id)
            ready.wait()
            try:
                request_service.decide(
                    worker,
                    request=request,
                    approve=True,
                    actor_id=actor_id,
                    note=None,
                )
                worker.commit()
                return "approved"
            except RequestError:
                worker.rollback()
                return "already decided"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(approve, ["adm_lindsey", "adm_robin"]))

    assert sorted(outcomes) == ["already decided", "approved"]
    with factory() as verification:
        request = verification.get(TimeOffRequest, request_id)
        debits = verification.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(
                LedgerEntry.source_type == enums.SourceType.REQUEST,
                LedgerEntry.source_id == f"{request_id}:2027",
            )
        )
        assert request.status == enums.RequestStatus.APPROVED
        assert debits == 1


def test_denial_releases_the_hold_without_a_ledger_entry(session):
    category, _ = _setup(session)
    request = _submit(session, category)
    before = session.scalar(select(func.count()).select_from(LedgerEntry))
    request_service.decide(
        session, request=request, approve=False, actor_id="adm_lindsey", note="Busy week"
    )
    after = session.scalar(select(func.count()).select_from(LedgerEntry))
    assert before == after


def test_approval_revalidates_a_balance_that_changed_after_submission(session):
    category, policy = _setup(session, credit=960)
    request = _submit(session, category)
    snapshot = session.get(BalanceSnapshot, ("emp_ada", policy.id))
    snapshot.balance_minutes = 0
    with pytest.raises(RequestError, match="balance changed"):
        request_service.decide(
            session, request=request, approve=True, actor_id="adm_lindsey", note=None
        )


def test_cancelling_an_approved_request_appends_a_reversal(session):
    category, policy = _setup(session)
    request = _submit(session, category)
    request_service.decide(
        session, request=request, approve=True, actor_id="adm_lindsey", note=None
    )
    request_service.cancel(
        session, request=request, actor_id="emp_ada", today=date(2026, 12, 1)
    )
    entries = list(
        session.scalars(
            select(LedgerEntry).where(LedgerEntry.policy_id == policy.id)
        )
    )
    assert [entry.entry_type for entry in entries][-2:] == [
        enums.EntryType.REQUEST_DEBIT,
        enums.EntryType.REQUEST_REVERSAL,
    ]
    assert sum(entry.amount_minutes for entry in entries) == 2400


def test_an_employee_cannot_cancel_leave_that_has_started(session):
    category, _ = _setup(session)
    request = _submit(session, category)
    with pytest.raises(RequestError, match="started"):
        request_service.cancel(
            session, request=request, actor_id="emp_ada", today=request.start_date
        )


def test_an_employee_cannot_read_another_employees_requests(session):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_actor] = lambda: employee_service.get("emp_ada")
    try:
        response = TestClient(app).get("/api/requests?employee_id=emp_alan")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
