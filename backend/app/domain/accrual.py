"""Pure accrual calculations; persistence and retries live in services."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from app import enums
from app.domain.periods import Period
from app.domain.units import to_minutes


@dataclass(frozen=True)
class AccrualIntent:
    amount_minutes: int
    effective_date: date
    note: str


def scheduled_amount(
    *,
    amount: Decimal,
    unit: enums.RateUnit,
    period: Period,
    eligible_from: date,
    proration: enums.NewHireProration,
) -> int:
    full = to_minutes(amount, unit)
    if eligible_from <= period.start or proration == enums.NewHireProration.FULL:
        return full
    if proration == enums.NewHireProration.NONE:
        return 0
    covered = (period.end - eligible_from).days + 1
    total = (period.end - period.start).days + 1
    return int((Decimal(full) * covered / total).to_integral_value(rounding=ROUND_FLOOR))


def payroll_amount(
    *,
    minutes_worked: int,
    amount: Decimal,
    unit: enums.RateUnit,
    per_minutes_worked: int,
) -> int:
    earned = Decimal(minutes_worked) * to_minutes(amount, unit) / per_minutes_worked
    return int(earned.to_integral_value(rounding=ROUND_FLOOR))
