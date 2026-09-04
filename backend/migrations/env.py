"""Alembic environment.

The database URL and the model metadata both come from the application rather
than from `alembic.ini`, so there is exactly one definition of each and a
migration run cannot drift from what the app is configured to talk to.
"""
from __future__ import annotations

from alembic import context
from app.config import settings
from app.models import Base
from sqlalchemy import engine_from_config, pool

config = context.config

# Default to the configured database, but never override a URL the caller set:
# `schema_setup.create_schema` and the test suite both point this at a specific
# engine, and silently migrating the app's own database instead would be a very
# unpleasant surprise.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", settings.database_url)

DATABASE_URL = config.get_main_option("sqlalchemy.url")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
