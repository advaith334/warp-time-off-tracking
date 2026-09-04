"""Exact conversions into the ledger's integer-minute unit."""

from decimal import ROUND_FLOOR, Decimal

from app import enums

STANDARD_DAY_MINUTES = 480


def to_minutes(
    amount: Decimal,
    unit: enums.RateUnit,
    day_minutes: int = STANDARD_DAY_MINUTES,
) -> int:
    multiplier = {
        enums.RateUnit.DAY: day_minutes,
        enums.RateUnit.HOUR: 60,
        enums.RateUnit.MINUTE: 1,
    }[unit]
    return int((amount * multiplier).to_integral_value(rounding=ROUND_FLOOR))
