"""Calendar periods used by the scheduled accrual planner."""

from dataclasses import dataclass
from datetime import date, timedelta

from app import enums


@dataclass(frozen=True)
class Period:
    start: date
    end: date


def containing(
    day: date, schedule: enums.Schedule, pay_period_anchor: date | None = None
) -> Period:
    if schedule == enums.Schedule.DAILY:
        return Period(day, day)
    if schedule in (enums.Schedule.WEEKLY, enums.Schedule.BIWEEKLY):
        if pay_period_anchor is None:
            raise ValueError(f"{schedule.value} requires a pay-period anchor")
        stride = 7 if schedule == enums.Schedule.WEEKLY else 14
        blocks = (day - pay_period_anchor).days // stride
        start = pay_period_anchor + timedelta(days=blocks * stride)
        return Period(start, start + timedelta(days=stride - 1))
    if schedule == enums.Schedule.SEMIMONTHLY:
        if day.day <= 15:
            return Period(day.replace(day=1), day.replace(day=15))
        start = day.replace(day=16)
        next_month = date(
            start.year + (start.month == 12), (start.month % 12) + 1, 1
        )
        return Period(start, next_month - timedelta(days=1))
    if schedule == enums.Schedule.YEARLY:
        return Period(date(day.year, 1, 1), date(day.year, 12, 31))
    start = day.replace(day=1)
    next_month = date(start.year + (start.month == 12), (start.month % 12) + 1, 1)
    return Period(start, next_month - timedelta(days=1))


def iter_periods(
    first_day: date,
    through: date,
    schedule: enums.Schedule,
    pay_period_anchor: date | None = None,
):
    cursor = containing(first_day, schedule, pay_period_anchor)
    while cursor.start <= through:
        yield cursor
        cursor = containing(cursor.end + timedelta(days=1), schedule, pay_period_anchor)
