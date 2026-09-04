from datetime import date

import pytest
from app import enums
from app.api.deps import get_actor
from app.db import get_session
from app.integrations import employee_service
from app.main import app
from app.models import EmployeeGroupMember, Policy, PolicyAssignment, TimeOffCategory
from app.services import group_service, policy_service
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def _policy(session):
    category = TimeOffCategory(company_id="cmp_warp_demo", name="Vacation")
    session.add(category)
    session.flush()
    return policy_service.create(
        session,
        company_id="cmp_warp_demo",
        actor_id="adm_lindsey",
        name="Grouped vacation",
        category_id=category.id,
        effective_from=date(2026, 1, 1),
        kind=enums.PolicyKind.UNLIMITED,
        change_reason="Initial policy",
        rules=[],
    )


def test_multiple_groups_can_target_one_policy(session):
    policy = _policy(session)
    full_time = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Full-time employees",
        employee_ids=["emp_ada", "emp_grace"],
        actor_id="adm_lindsey",
    )
    west_coast = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="West Coast",
        employee_ids=["emp_alan"],
        actor_id="adm_lindsey",
    )

    group_service.set_policy_audience(
        session,
        policy=policy,
        all_employees=False,
        group_ids=[full_time.id, west_coast.id],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )

    assignments = list(
        session.scalars(select(PolicyAssignment).where(PolicyAssignment.policy_id == policy.id))
    )
    assert {row.employee_id for row in assignments} == {
        "emp_ada",
        "emp_grace",
        "emp_alan",
    }


def test_an_employee_can_belong_to_only_one_group(session):
    group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Full-time employees",
        employee_ids=["emp_ada"],
        actor_id="adm_lindsey",
    )

    with pytest.raises(group_service.GroupError, match="already belongs"):
        group_service.create(
            session,
            company_id="cmp_warp_demo",
            name="Interns",
            employee_ids=["emp_ada"],
            actor_id="adm_lindsey",
        )


def test_database_prevents_bypassing_single_group_rule(session):
    first = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Full-time employees",
        employee_ids=["emp_ada"],
        actor_id="adm_lindsey",
    )
    second = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Interns",
        employee_ids=[],
        actor_id="adm_lindsey",
    )
    assert first.id != second.id
    session.add(
        EmployeeGroupMember(
            group_id=second.id,
            employee_id="emp_ada",
            company_id="cmp_warp_demo",
            created_by="adm_lindsey",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_changing_group_membership_reconciles_effective_dated_policy_access(session):
    policy = _policy(session)
    group = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Interns",
        employee_ids=["emp_ada"],
        actor_id="adm_lindsey",
    )
    group_service.set_policy_audience(
        session,
        policy=policy,
        all_employees=False,
        group_ids=[group.id],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )

    group_service.replace_members(
        session,
        group=group,
        employee_ids=["emp_alan"],
        effective_from=date(2026, 3, 16),
        actor_id="adm_lindsey",
    )

    assignments = list(
        session.scalars(
            select(PolicyAssignment)
            .where(PolicyAssignment.policy_id == policy.id)
            .order_by(PolicyAssignment.employee_id)
        )
    )
    assert [(row.employee_id, row.effective_from, row.effective_to) for row in assignments] == [
        ("emp_ada", date(2026, 1, 1), date(2026, 3, 15)),
        ("emp_alan", date(2026, 3, 16), None),
    ]


def test_moving_an_employee_switches_same_category_policies_without_overlap(session):
    vacation = _policy(session)
    intern_vacation = policy_service.create(
        session,
        company_id="cmp_warp_demo",
        actor_id="adm_lindsey",
        name="Intern vacation",
        category_id=vacation.category_id,
        effective_from=date(2026, 1, 1),
        kind=enums.PolicyKind.UNLIMITED,
        change_reason="Initial policy",
        rules=[],
    )
    full_time = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Full-time employees",
        employee_ids=["emp_ada"],
        actor_id="adm_lindsey",
    )
    interns = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Interns",
        employee_ids=[],
        actor_id="adm_lindsey",
    )
    group_service.set_policy_audience(
        session,
        policy=vacation,
        all_employees=False,
        group_ids=[full_time.id],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )
    group_service.set_policy_audience(
        session,
        policy=intern_vacation,
        all_employees=False,
        group_ids=[interns.id],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )

    group_service.set_employee_group(
        session,
        company_id="cmp_warp_demo",
        employee_id="emp_ada",
        group_id=interns.id,
        effective_from=date(2026, 3, 16),
        actor_id="adm_lindsey",
    )

    memberships = list(
        session.scalars(
            select(EmployeeGroupMember).where(EmployeeGroupMember.employee_id == "emp_ada")
        )
    )
    assert [membership.group_id for membership in memberships] == [interns.id]
    assignments = list(
        session.scalars(
            select(PolicyAssignment)
            .where(PolicyAssignment.employee_id == "emp_ada")
            .order_by(PolicyAssignment.effective_from)
        )
    )
    assert [(row.policy_id, row.effective_from, row.effective_to) for row in assignments] == [
        (vacation.id, date(2026, 1, 1), date(2026, 3, 15)),
        (intern_vacation.id, date(2026, 3, 16), None),
    ]


def test_all_employees_audience_excludes_admins(session):
    policy = _policy(session)
    group_service.set_policy_audience(
        session,
        policy=policy,
        all_employees=True,
        group_ids=[],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )
    employee_ids = set(
        session.scalars(
            select(PolicyAssignment.employee_id).where(
                PolicyAssignment.policy_id == policy.id
            )
        )
    )
    assert employee_ids == {
        "emp_ada",
        "emp_grace",
        "emp_alan",
        "emp_katherine",
        "emp_linus",
    }


def test_removing_a_group_ends_its_policy_eligibility(session):
    policy = _policy(session)
    group = group_service.create(
        session,
        company_id="cmp_warp_demo",
        name="Contractors",
        employee_ids=["emp_katherine"],
        actor_id="adm_lindsey",
    )
    group_service.set_policy_audience(
        session,
        policy=policy,
        all_employees=False,
        group_ids=[group.id],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )

    group_service.remove(
        session,
        group=group,
        effective_from=date(2026, 3, 16),
        actor_id="adm_lindsey",
    )

    assignment = session.scalar(
        select(PolicyAssignment).where(PolicyAssignment.policy_id == policy.id)
    )
    assert assignment.effective_to == date(2026, 3, 15)
    assert session.get(EmployeeGroupMember, (group.id, "emp_katherine")) is None


def test_policy_and_audience_are_created_atomically(session):
    category = TimeOffCategory(company_id="cmp_warp_demo", name="Vacation")
    session.add(category)
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_actor] = lambda: employee_service.get("adm_lindsey")
    try:
        response = TestClient(app).post(
            "/api/policies",
            json={
                "name": "Invalid audience",
                "category_id": category.id,
                "effective_from": "2026-01-01",
                "kind": "UNLIMITED",
                "rules": [],
                "all_employees": False,
                "group_ids": ["missing-group"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert session.scalar(select(Policy).where(Policy.name == "Invalid audience")) is None
