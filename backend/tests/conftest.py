from __future__ import annotations

import pytest
from app.config import DATABASE_URL
from app.schema_setup import recreate_schema
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = DATABASE_URL.rsplit("/", 1)[0] + "/timeoff_test"


def _ensure_database() -> None:
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'timeoff_test'")
        ).scalar()
        if not exists:
            connection.execute(text("CREATE DATABASE timeoff_test"))
    engine.dispose()


@pytest.fixture(scope="session")
def engine():
    _ensure_database()
    value = create_engine(TEST_DATABASE_URL)
    yield value
    value.dispose()


@pytest.fixture()
def session(engine):
    recreate_schema(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as value:
        yield value
