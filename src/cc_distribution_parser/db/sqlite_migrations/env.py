"""Alembic env for SQLite ops state.

Reads SQLITE_OPS_PATH from env (set by docker-compose / production deploy);
falls back to alembic.ini sqlalchemy.url for local CLI use.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from env if present (production / docker-compose).
ops_path = os.environ.get("SQLITE_OPS_PATH")
if ops_path:
    config.set_main_option("sqlalchemy.url", f"sqlite:///{ops_path}")

# Models registered via this import. sqlite_models.py exports `metadata`.
# Import is lazy because Sprint 1 will populate sqlite_models.py; until then
# autogenerate is unavailable but raw migrations work fine.
# TODO(Sprint 1): remove try/except once sqlite_models lands — this guard is
# scaffolding-time only and shouldn't ship past Sprint 1.
target_metadata = None
try:
    from cc_distribution_parser.db import sqlite_models  # type: ignore

    target_metadata = sqlite_models.metadata
except (ImportError, AttributeError):
    pass


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER TABLE
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
