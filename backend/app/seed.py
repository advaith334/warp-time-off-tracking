"""One deterministic story for the five-minute reviewer walkthrough."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock, enums
from app.config import DEMO_COMPANY_ID
from app.db import SessionLocal
from app.models import EmployeeGroup, Policy, TimeOffCategory
from app.services import (
    accrual_service,
    group_service,
    holiday_service,
    policy_service,
    request_service,
)

DEMO_TODAY = date(2026, 3, 16)


def seed(session: Session) -> bool:
    categories = {
        category.name: category
        for category in session.scalars(
            select(TimeOffCategory).where(
                TimeOffCategory.company_id == DEMO_COMPANY_ID
            )
        )
    }
    changed = False
    for name, icon in [
        ("Vacation", "🏝️"),
        ("Sick leave", "✚"),
        ("Maternity leave", "🌱"),
        ("Other", "◇"),
    ]:
        if name == "Maternity leave" and name not in categories and "Maternity" in categories:
            category = categories.pop("Maternity")
            category.name = name
            category.icon = icon
            categories[name] = category
            changed = True
            continue
        if name not in categories:
            category = TimeOffCategory(
                company_id=DEMO_COMPANY_ID, name=name, icon=icon
            )
            session.add(category)
            categories[name] = category
            changed = True
    session.flush()
    groups = {
        group.name: group
        for group in session.scalars(
            select(EmployeeGroup).where(EmployeeGroup.company_id == DEMO_COMPANY_ID)
        )
    }
    default_groups = {
        "Full-time employees": ["emp_ada", "emp_grace", "emp_linus"],
        "Part-time employees": ["emp_alan"],
        "Contractors": ["emp_katherine"],
        "Interns": [],
    }
    for name, employee_ids in default_groups.items():
        if name not in groups:
            groups[name] = group_service.create(
                session,
                company_id=DEMO_COMPANY_ID,
                name=name,
                employee_ids=employee_ids,
                actor_id="adm_lindsey",
            )
            changed = True
    core_policy = session.scalar(
        select(Policy).where(
            Policy.company_id == DEMO_COMPANY_ID,
            Policy.name == "Core vacation",
        )
    )
    core_created = core_policy is None
    if core_policy is None:
        core_policy = policy_service.create(
            session,
            company_id=DEMO_COMPANY_ID,
            actor_id="adm_lindsey",
            name="Core vacation",
            category_id=categories["Vacation"].id,
            effective_from=date(2026, 1, 1),
            kind=enums.PolicyKind.ACCRUAL,
            change_reason="Demo policy",
            max_balance_minutes=14_400,
            carryover_cap_minutes=4_800,
            rules=[
                {
                    "method": enums.AccrualMethod.TIME,
                    "amount": 15,
                    "unit": enums.RateUnit.DAY,
                    "frequency": enums.Schedule.YEARLY,
                    "accrues_at": enums.AccruesAt.START_OF_PERIOD,
                    "per_minutes_worked": None,
                    "min_tenure_months": 0,
                }
            ],
        )
        changed = True
    audience_created = not core_policy.group_targets and not core_policy.all_employees
    if audience_created:
        group_service.set_policy_audience(
            session,
            policy=core_policy,
            all_employees=False,
            group_ids=[groups["Full-time employees"].id, groups["Part-time employees"].id],
            effective_from=date(2026, 1, 1),
            actor_id="adm_lindsey",
        )
        changed = True
    if core_created or audience_created:
        holiday_service.ensure_year(session, company_id=DEMO_COMPANY_ID, year=2026)
        clock.set_today(session, DEMO_TODAY)
        accrual_service.run_scheduled(
            session, company_id=DEMO_COMPANY_ID, as_of=DEMO_TODAY
        )
    if core_created:
        request_service.submit(
            session,
            actor_id="emp_ada",
            reason="Summer break",
            employee_id="emp_ada",
            category_id=categories["Vacation"].id,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
            partial_minutes=None,
        )

    other_policy = session.scalar(
        select(Policy).where(
            Policy.company_id == DEMO_COMPANY_ID,
            Policy.name == "Other leave requests",
        )
    )
    if other_policy is None:
        other_policy = policy_service.create(
            session,
            company_id=DEMO_COMPANY_ID,
            actor_id="adm_lindsey",
            name="Other leave requests",
            category_id=categories["Other"].id,
            effective_from=date(2026, 1, 1),
            kind=enums.PolicyKind.UNLIMITED,
            change_reason="Catch-all approval path",
            rules=[],
        )
        changed = True
    if not other_policy.all_employees:
        group_service.set_policy_audience(
            session,
            policy=other_policy,
            all_employees=True,
            group_ids=[],
            effective_from=date(2026, 1, 1),
            actor_id="adm_lindsey",
        )
        changed = True
    return changed


if __name__ == "__main__":
    with SessionLocal() as database:
        changed = seed(database)
        database.commit()
        print("Seeded demo data." if changed else "Demo data already exists.")
