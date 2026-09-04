"""Single clock seam; PR 6 will make it controllable for the demo."""
from datetime import date

from sqlalchemy.orm import Session


def today(session: Session) -> date:
    del session
    return date.today()  # noqa: DTZ011
