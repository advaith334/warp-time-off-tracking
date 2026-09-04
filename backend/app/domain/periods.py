"""Calendar periods used by the scheduled accrual planner."""

from dataclasses import dataclass
from datetime import date, timedelta

from app import enums


@dataclass(frozen=True)
class Period:
    start: date
    end: date


def containing(day: date, schedule: enums.Schedule) -> Period:
    if schedule == enums.Schedule.YEARLY:
        return Period(date(day.year, 1, 1), date(day.year, 12, 31))
    start = day.replace(day=1)
    next_month = date(start.year + (start.month == 12), (start.month % 12) + 1, 1)
    return Period(start, next_month - timedelta(days=1))


def iter_periods(first_day: date, through: date, schedule: enums.Schedule):
    cursor = containing(first_day, schedule)
    while cursor.start <= through:
        yield cursor
        cursor = containing(cursor.end + timedelta(days=1), schedule)
