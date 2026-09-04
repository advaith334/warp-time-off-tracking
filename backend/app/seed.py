"""One deterministic story for the five-minute reviewer walkthrough."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock, enums
from app.config import DEMO_COMPANY_ID
from app.db import SessionLocal
from app.models import TimeOffCategory
from app.services import (
    accrual_service,
    assignment_service,
    holiday_service,
    policy_service,
    request_service,
)

DEMO_TODAY = date(2026, 3, 16)


def seed(session: Session) -> bool:
    existing = session.scalar(
        select(TimeOffCategory.id).where(
            TimeOffCategory.company_id == DEMO_COMPANY_ID
        ).limit(1)
    )
    if existing:
        return False

    vacation = TimeOffCategory(
        company_id=DEMO_COMPANY_ID, name="Vacation", icon="🏝️"
    )
    maternity = TimeOffCategory(
        company_id=DEMO_COMPANY_ID, name="Maternity", icon="🌱"
    )
    session.add_all([vacation, maternity])
    session.flush()
    policy = policy_service.create(
        session,
        company_id=DEMO_COMPANY_ID,
        actor_id="adm_lindsey",
        name="Core vacation",
        category_id=vacation.id,
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
    assignment_service.assign(
        session,
        policy=policy,
        employee_ids=["emp_ada", "emp_alan"],
        effective_from=date(2026, 1, 1),
        actor_id="adm_lindsey",
    )
    holiday_service.ensure_year(session, company_id=DEMO_COMPANY_ID, year=2026)
    clock.set_today(session, DEMO_TODAY)
    accrual_service.run_scheduled(
        session, company_id=DEMO_COMPANY_ID, as_of=DEMO_TODAY
    )
    request_service.submit(
        session,
        actor_id="emp_ada",
        reason="Summer break",
        employee_id="emp_ada",
        category_id=vacation.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        partial_minutes=None,
    )
    return True


if __name__ == "__main__":
    with SessionLocal() as database:
        changed = seed(database)
        database.commit()
        print("Seeded demo data." if changed else "Demo data already exists.")
