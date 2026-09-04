"""Stub for the existing Employee Service (decision I6).

The brief says this service already exists and returns employee data, pay rates
and work configurations. We depend on the interface, not the implementation:
swapping `_FIXTURES` for an HTTP client is the whole production change.

We deliberately do not store a copy of employee records. Work-day length,
start date, employment type and work state are read through here every time
they are needed, so time-off never disagrees with HR.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.config import DEMO_COMPANY_ID


@dataclass(frozen=True)
class Employee:
    id: str
    company_id: str
    name: str
    email: str
    employment_type: str          # FULL_TIME | PART_TIME | CONTRACTOR
    start_date: date
    work_minutes_per_day: int     # 480 standard; 360 for a 6-hour day (B1)
    work_days: tuple[int, ...]    # ISO weekdays, Mon=1
    work_state: str               # drives compliance rules (e.g. CA)
    is_admin: bool = False


_WEEKDAYS = (1, 2, 3, 4, 5)

_FIXTURES: dict[str, Employee] = {
    e.id: e
    for e in [
        Employee(
            id="emp_ada", company_id=DEMO_COMPANY_ID, name="Ada Lovelace",
            email="ada@example.com", employment_type="FULL_TIME",
            start_date=date(2023, 3, 1), work_minutes_per_day=480,
            work_days=_WEEKDAYS, work_state="CA",
        ),
        Employee(
            id="emp_grace", company_id=DEMO_COMPANY_ID, name="Grace Hopper",
            email="grace@example.com", employment_type="FULL_TIME",
            # Joins mid-period - the C3 proration case.
            start_date=date(2026, 2, 18), work_minutes_per_day=480,
            work_days=_WEEKDAYS, work_state="NY",
        ),
        Employee(
            id="emp_alan", company_id=DEMO_COMPANY_ID, name="Alan Turing",
            email="alan@example.com", employment_type="PART_TIME",
            # Works 6-hour days - the B1 custom work hours case.
            start_date=date(2024, 1, 15), work_minutes_per_day=360,
            work_days=_WEEKDAYS, work_state="WA",
        ),
        Employee(
            id="emp_katherine", company_id=DEMO_COMPANY_ID, name="Katherine Johnson",
            email="katherine@example.com", employment_type="CONTRACTOR",
            start_date=date(2025, 11, 1), work_minutes_per_day=480,
            work_days=_WEEKDAYS, work_state="TX",
        ),
        Employee(
            id="emp_linus", company_id=DEMO_COMPANY_ID, name="Linus Torvalds",
            email="linus@example.com", employment_type="FULL_TIME",
            start_date=date(2025, 1, 6), work_minutes_per_day=480,
            work_days=_WEEKDAYS, work_state="CA",
        ),
        Employee(
            id="adm_lindsey", company_id=DEMO_COMPANY_ID, name="Lindsey Poisson",
            email="lindsey@example.com", employment_type="FULL_TIME",
            start_date=date(2022, 1, 3), work_minutes_per_day=480,
            work_days=_WEEKDAYS, work_state="CA", is_admin=True,
        ),
    ]
}


class EmployeeService:
    def get(self, employee_id: str) -> Employee:
        try:
            return _FIXTURES[employee_id]
        except KeyError:
            raise LookupError(f"unknown employee {employee_id!r}") from None

    def list_for_company(self, company_id: str) -> list[Employee]:
        return [e for e in _FIXTURES.values() if e.company_id == company_id]


employee_service = EmployeeService()
