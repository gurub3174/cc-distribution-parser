"""Connection context managers for Snowflake + SQLite.

Lazy connect; release on exit. Real Snowflake creds come from Settings;
when unset, Snowflake helpers raise rather than connect to a bogus account.
SQLite is always available (file-backed; default `.ccdp-ops.sqlite`).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from cc_distribution_parser.config import get_settings


@contextmanager
def sqlite_session(*, path: str | None = None) -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    target = path or settings.sqlite_path
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def snowflake_session() -> Iterator[Any]:
    """Lazy snowflake connector — only imported when actually needed.

    Raises RuntimeError if credentials are not configured rather than
    crashing on import in dev environments without Snowflake.
    """
    settings = get_settings()
    if not (settings.snowflake_account and settings.snowflake_user and settings.snowflake_password):
        raise RuntimeError(
            "Snowflake credentials not configured. "
            "Set CCDP_SNOWFLAKE_ACCOUNT / USER / PASSWORD env vars."
        )
    import snowflake.connector

    conn = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
