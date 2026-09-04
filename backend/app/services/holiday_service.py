"""Persist company holidays without letting a refresh delete admin changes."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.integrations.holiday_source import statutory
from app.models import Holiday


def ensure_year(session: Session, *, company_id: str, year: int) -> int:
    created = 0
    for day, name in statutory(years=[year]).items():
        holiday_id = session.scalar(
            insert(Holiday)
            .values(
                company_id=company_id,
                date=day,
                name=name,
                observed="observed" in name.lower(),
            )
            .on_conflict_do_nothing(index_elements=["company_id", "date"])
            .returning(Holiday.id)
        )
        created += int(holiday_id is not None)
    return created


def list_for_year(session: Session, *, company_id: str, year: int) -> list[Holiday]:
    return list(
        session.scalars(
            select(Holiday)
            .where(
                Holiday.company_id == company_id,
                Holiday.date >= date(year, 1, 1),
                Holiday.date <= date(year, 12, 31),
            )
            .order_by(Holiday.date)
        )
    )
