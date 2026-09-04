"""The system clock, indirected through the database (decision I3).

Nothing in this codebase calls `date.today()` directly. Accrual, carryover and
tenure tiers are only observable in a live demo if "today" can be moved, and
storing the simulated date in Postgres rather than process memory means an API
request and a background job never disagree about what day it is.

In production this module is the one place that changes: `today()` returns the
real date and the dev endpoints are removed.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DevClock


def today(session: Session) -> date:
    row = session.execute(select(DevClock).where(DevClock.id == 1)).scalar_one_or_none()
    if row is None:
        # The single real-clock read in the codebase, by design (see the module
        # docstring): it seeds the simulated clock the first time it is asked for.
        row = DevClock(id=1, current_date=date.today())  # noqa: DTZ011
        session.add(row)
        session.flush()
    return row.current_date


def set_today(session: Session, value: date) -> date:
    row = session.execute(select(DevClock).where(DevClock.id == 1)).scalar_one_or_none()
    if row is None:
        row = DevClock(id=1, current_date=value)
        session.add(row)
    else:
        row.current_date = value
    session.flush()
    return value
