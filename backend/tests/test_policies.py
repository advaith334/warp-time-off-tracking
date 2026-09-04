from datetime import date

import pytest
from app import enums
from app.api.deps import get_actor
from app.db import get_session
from app.integrations import employee_service
from app.main import app
from app.models import PolicyAssignment, TimeOffCategory
from app.services import assignment_service, policy_service
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


def _category(session) -> TimeOffCategory:
    row = TimeOffCategory(company_id="cmp_warp_demo", name="Vacation")
    session.add(row)
    session.flush()
    return row


def _policy(session):
    category = _category(session)
    return policy_service.create(
        session,
        company_id="cmp_warp_demo",
        actor_id="adm_lindsey",
        name="Vacation",
        category_id=category.id,
        effective_from=date(2026, 1, 1),
        kind=enums.PolicyKind.ACCRUAL,
        change_reason="Initial policy",
        rules=[{
            "method": enums.AccrualMethod.TIME,
            "amount": 20,
            "unit": enums.RateUnit.DAY,
            "frequency": enums.Schedule.YEARLY,
            "accrues_at": enums.AccruesAt.START_OF_PERIOD,
        }],
    )


def test_editing_a_policy_appends_a_version_without_rewriting_history(session):
    policy = _policy(session)
    first = policy_service.latest_version(session, policy.id)

    second = policy_service.update(
        session,
        policy=policy,
        actor_id="adm_lindsey",
        effective_from=date(2027, 1, 1),
        kind=enums.PolicyKind.ACCRUAL,
        change_reason="Increase allowance",
        name=None,
        rules=[{
            "method": enums.AccrualMethod.TIME,
            "amount": 25,
            "unit": enums.RateUnit.DAY,
            "frequency": enums.Schedule.YEARLY,
            "accrues_at": enums.AccruesAt.START_OF_PERIOD,
        }],
    )

    assert first.version_no == 1
    assert first.rules[0].amount == 20
    assert second.version_no == 2
    assert second.rules[0].amount == 25
    assert second.change_reason == "Increase allowance"


def test_arbitrary_employee_lists_become_assignment_rows(session):
    policy = _policy(session)
    rows = assignment_service.assign(
        session,
        policy=policy,
        employee_ids=["emp_ada", "emp_alan"],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )
    assert [row.employee_id for row in rows] == ["emp_ada", "emp_alan"]


def test_an_unknown_employee_cannot_be_assigned(session):
    policy = _policy(session)
    with pytest.raises(assignment_service.AssignmentError, match="Unknown employee"):
        assignment_service.assign(
            session,
            policy=policy,
            employee_ids=["emp_missing"],
            effective_from=date(2026, 1, 1),
            actor_id="adm_lindsey",
        )


def test_a_one_day_assignment_still_blocks_an_overlap(session):
    policy = _policy(session)
    first = PolicyAssignment(
        company_id=policy.company_id,
        employee_id="emp_ada",
        policy_id=policy.id,
        category_id=policy.category_id,
        effective_from=date(2026, 2, 1),
        effective_to=date(2026, 2, 1),
        created_by="adm_lindsey",
    )
    session.add(first)
    session.flush()
    session.add(
        PolicyAssignment(
            company_id=policy.company_id,
            employee_id="emp_ada",
            policy_id=policy.id,
            category_id=policy.category_id,
            effective_from=date(2026, 2, 1),
            effective_to=date(2026, 2, 2),
            created_by="adm_lindsey",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_non_admin_policy_writes_return_403(session):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_actor] = lambda: employee_service.get("emp_ada")
    try:
        response = TestClient(app).post(
            "/api/categories", json={"name": "Sick"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
