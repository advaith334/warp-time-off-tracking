"""Stub for the existing Company Service (decision I6)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.config import DEMO_COMPANY_ID


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    timezone: str
    # Anchor for BIWEEKLY accrual periods; also the payroll cadence.
    pay_period_anchor: date
    standard_work_minutes_per_day: int = 480


_FIXTURES = {
    DEMO_COMPANY_ID: Company(
        id=DEMO_COMPANY_ID,
        name="Northstar Robotics",
        timezone="America/Los_Angeles",
        pay_period_anchor=date(2026, 1, 5),
    )
}


class CompanyService:
    def get(self, company_id: str) -> Company:
        try:
            return _FIXTURES[company_id]
        except KeyError:
            raise LookupError(f"unknown company {company_id!r}") from None


company_service = CompanyService()
