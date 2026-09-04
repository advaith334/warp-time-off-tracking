from datetime import date

import pytest
from app import enums
from app.api.deps import get_actor
from app.db import get_session
from app.integrations import employee_service
from app.main import app
from app.models import LedgerEntry, TimeOffCategory, TimeOffRequest
from app.services import assignment_service, policy_service
from fastapi.testclient import TestClient


def test_company_scoped_routes_hide_another_companys_records(session):
    category = TimeOffCategory(company_id="cmp_other", name="Other vacation")
    session.add(category)
    session.flush()
    policy = policy_service.create(
        session,
        company_id="cmp_other",
        actor_id="other_admin",
        name="Other policy",
        category_id=category.id,
        effective_from=date(2026, 1, 1),
        kind=enums.PolicyKind.ACCRUAL,
        change_reason="Initial policy",
        rules=[
            {
                "method": enums.AccrualMethod.TIME,
                "amount": 10,
                "unit": enums.RateUnit.DAY,
                "frequency": enums.Schedule.YEARLY,
                "accrues_at": enums.AccruesAt.START_OF_PERIOD,
            }
        ],
    )
    version = policy_service.latest_version(session, policy.id)
    request = TimeOffRequest(
        company_id="cmp_other",
        employee_id="emp_ada",
        policy_id=policy.id,
        policy_version_id=version.id,
        category_id=category.id,
        reason="Private request",
        status=enums.RequestStatus.PENDING,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 1),
        total_minutes=480,
        is_partial_day=False,
        created_by="emp_ada",
    )
    session.add(request)
    session.add(
        LedgerEntry(
            company_id="cmp_other",
            employee_id="emp_ada",
            policy_id=policy.id,
            policy_version_id=version.id,
            entry_type=enums.EntryType.ACCRUAL,
            amount_minutes=480,
            effective_date=date(2026, 1, 1),
            source_type=enums.SourceType.SCHEDULED_ACCRUAL,
            source_id="other-company-credit",
        )
    )
    session.flush()

    with pytest.raises(assignment_service.AssignmentError, match="another company"):
        assignment_service.assign(
            session,
            policy=policy,
            employee_ids=["emp_ada"],
            effective_from=date(2026, 1, 1),
            actor_id="other_admin",
        )

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_actor] = lambda: employee_service.get("adm_lindsey")
    try:
        client = TestClient(app)
        assert client.get("/api/requests").json() == []
        assert client.post(f"/api/requests/{request.id}/approve", json={}).status_code == 404
        assert client.get(f"/api/policies/{policy.id}/assignments").status_code == 404
        assert client.get("/api/employees/emp_ada/ledger").json() == []
    finally:
        app.dependency_overrides.clear()
