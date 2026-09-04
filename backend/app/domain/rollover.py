"""Pure year-end carryover and expiration planning."""

from dataclasses import dataclass
from datetime import date, timedelta

from app import enums


@dataclass(frozen=True)
class RolloverEntry:
    entry_type: enums.EntryType
    amount_minutes: int
    effective_date: date
    source_suffix: str
    note: str


def plan(
    *, balance_minutes: int, period_end: date, carryover_cap_minutes: int | None,
    expires_at_period_end: bool,
) -> list[RolloverEntry]:
    if balance_minutes <= 0:
        return []
    if expires_at_period_end:
        carried = 0
    elif carryover_cap_minutes is not None:
        carried = min(balance_minutes, carryover_cap_minutes)
    else:
        return []
    entries = [
        RolloverEntry(
            entry_type=enums.EntryType.EXPIRATION,
            amount_minutes=-balance_minutes,
            effective_date=period_end,
            source_suffix="expiration",
            note=f"Closed policy year with {balance_minutes} minutes",
        )
    ]
    if carried:
        entries.append(
            RolloverEntry(
                entry_type=enums.EntryType.CARRYOVER,
                amount_minutes=carried,
                effective_date=period_end + timedelta(days=1),
                source_suffix="carryover",
                note=f"Carried {carried} minutes into the next policy year",
            )
        )
    return entries
