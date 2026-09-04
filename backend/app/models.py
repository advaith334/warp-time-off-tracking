"""SQLAlchemy metadata; product tables are added beside their behavior."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
