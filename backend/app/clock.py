"""Single clock seam with a persisted demo override."""
from datetime import date

from sqlalchemy.orm import Session

from app.models import DemoState

KEY = "today"


def today(session: Session) -> date:
    state = session.get(DemoState, KEY)
    return state.current_date if state else date.today()  # noqa: DTZ011


def set_today(session: Session, value: date) -> date:
    state = session.get(DemoState, KEY)
    if state is None:
        state = DemoState(key=KEY, current_date=value)
        session.add(state)
    else:
        state.current_date = value
    session.flush()
    return value
