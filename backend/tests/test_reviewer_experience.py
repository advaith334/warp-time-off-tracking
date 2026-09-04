from datetime import date

from app.api.deps import get_actor
from app.db import get_session
from app.integrations import employee_service
from app.main import app
from app.models import JobRun, TimeOffRequest
from app.seed import DEMO_TODAY, seed
from fastapi.testclient import TestClient
from sqlalchemy import func, select


def _client(session, actor_id: str) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_actor] = lambda: employee_service.get(actor_id)
    return TestClient(app)


def test_seed_creates_one_coherent_idempotent_demo_story(session):
    assert seed(session) is True
    assert seed(session) is False
    assert session.scalar(select(func.count()).select_from(JobRun)) == 1
    assert session.scalar(select(func.count()).select_from(TimeOffRequest)) == 1

    client = _client(session, "adm_lindsey")
    try:
        ada = client.get(f"/api/employees/emp_ada/balances?on_date={DEMO_TODAY}")
        alan = client.get(f"/api/employees/emp_alan/balances?on_date={DEMO_TODAY}")
    finally:
        app.dependency_overrides.clear()
    assert ada.status_code == alan.status_code == 200
    ada_rows = {row["category_name"]: row for row in ada.json()}
    alan_rows = {row["category_name"]: row for row in alan.json()}
    assert ada_rows["Vacation"]["balance_minutes"] == 15 * 480
    assert alan_rows["Vacation"]["balance_minutes"] == 15 * 360
    assert ada_rows["Maternity"]["has_policy"] is False


def test_demo_clock_and_job_history_are_admin_only(session):
    employee = _client(session, "emp_ada")
    try:
        assert employee.post(
            "/api/dev/clock", json={"current_date": "2027-01-02"}
        ).status_code == 403
        assert employee.get("/api/audit/job-runs").status_code == 403
    finally:
        app.dependency_overrides.clear()

    seed(session)
    admin = _client(session, "adm_lindsey")
    try:
        changed = admin.post(
            "/api/dev/clock", json={"current_date": "2027-01-02"}
        )
        state = admin.get("/api/dev/state")
        runs = admin.get("/api/audit/job-runs")
    finally:
        app.dependency_overrides.clear()
    assert changed.status_code == state.status_code == runs.status_code == 200
    assert changed.json()["today"] == state.json()["today"] == "2027-01-02"
    assert runs.json()[0]["kind"] == "SCHEDULED"


def test_ledger_can_be_filtered_to_the_selected_policy(session):
    seed(session)
    client = _client(session, "adm_lindsey")
    try:
        balances = client.get(
            f"/api/employees/emp_ada/balances?on_date={date(2026, 3, 16)}"
        ).json()
        policy_id = next(row["policy_id"] for row in balances if row["has_policy"])
        response = client.get(
            f"/api/employees/emp_ada/ledger?policy_id={policy_id}"
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()
    assert all(entry["source_type"] == "SCHEDULED_ACCRUAL" for entry in response.json())
