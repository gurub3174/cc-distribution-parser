"""Phase-1 stand-in for Snowflake commit, backed by the ops SQLite database.

CRITICAL — this is NOT the production commit backend. Production target is
Snowflake; that path lives in `services/commit.py` and is exercised by the
Snowflake migrations under `db/snowflake_migrations/`. This module exists to
keep the end-to-end loop runnable on a dev machine before Snowflake
credentials are configured.

Wired by `services/graph_runner.py`: it provides `fetch_one` + `execute`
callables matching the contract that `commit.py:run` consumes, plus an
`ensure_documents_row` helper so the documents-FK assertion in
`commit.py:assert_document_exists` passes.

SQL translation: commit.py's SQL strings are written for Snowflake
(`%s` paramstyle, `PARSE_JSON(...)` wrapper). The two-step translation
in `_to_sqlite_sql` keeps commit.py untouched.

See .claude/rules/snowflake-migrations.md for the Phase-1.5 swap to real
Snowflake (entry in change-log when wired).
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from cc_distribution_parser.db.session import sqlite_session
from cc_distribution_parser.observability.logging import get_logger

log = get_logger(__name__)

_PARSE_JSON_RE = re.compile(r"PARSE_JSON\(\s*%s\s*\)")


def _to_sqlite_sql(sql: str) -> str:
    """Translate Snowflake INSERT/SELECT SQL to SQLite-friendly form.

    - PARSE_JSON(%s)  -> ? (JSON stays as TEXT)
    - %s              -> ?
    """
    return _PARSE_JSON_RE.sub("?", sql).replace("%s", "?")


@contextmanager
def _cursor(*, path: str | None = None) -> Iterator[sqlite3.Cursor]:
    with sqlite_session(path=path) as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()


def make_executors(*, path: str | None = None) -> tuple[Any, Any]:
    """Returns (fetch_one, execute) callables bound to a SQLite path.

    Each call opens a fresh connection — fine for Phase 1 throughput
    (single-doc latency). A connection pool can come later if needed.
    """

    def fetch_one(sql: str, params: tuple[Any, ...]) -> tuple[Any, ...] | None:
        sqlite_sql = _to_sqlite_sql(sql)
        with _cursor(path=path) as cur:
            cur.execute(sqlite_sql, params)
            row = cur.fetchone()
            return tuple(row) if row is not None else None

    def execute(sql: str, params: tuple[Any, ...]) -> None:
        sqlite_sql = _to_sqlite_sql(sql)
        with _cursor(path=path) as cur:
            cur.execute(sqlite_sql, params)

    return fetch_one, execute


def ensure_documents_row(state: dict[str, Any], *, path: str | None = None) -> str:
    """Insert a documents row if absent. Returns the canonical doc_id.

    Dedup contract: (file_hash, user_id) is the natural key (matches the
    UNIQUE index). If a row with the same content+owner already exists,
    return the EXISTING doc_id — callers must rewrite `state["doc_id"]`
    so the rest of the pipeline operates on the canonical row. If absent,
    insert using the state's doc_id and return it unchanged.

    Required precondition for `commit.assert_document_exists`.
    """
    file_hash = state.get("file_hash", "")
    user_id = state.get("user_id", "")
    doc_id = state["doc_id"]
    with _cursor(path=path) as cur:
        if file_hash and user_id:
            cur.execute(
                "SELECT id FROM documents WHERE file_hash = ? AND user_id = ?",
                (file_hash, user_id),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
        cur.execute("SELECT id FROM documents WHERE id = ?", (doc_id,))
        if cur.fetchone():
            return doc_id
        parser_metadata_json = json.dumps(state.get("parser_metadata") or {})
        cur.execute(
            "INSERT INTO documents ("
            "id, file_hash, original_filename, mime_type, byte_size, "
            "original_s3_uri, docling_json_s3_uri, status, user_id, "
            "parser_metadata_json, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                file_hash,
                state.get("original_filename", ""),
                state.get("mime_type", ""),
                int(state.get("byte_size", 0) or 0),
                state.get("original_s3_uri", ""),
                state.get("docling_json_s3_uri"),
                "parsed",
                user_id,
                parser_metadata_json,
                datetime.now(UTC),
            ),
        )
        log.info("commit_sqlite.documents_inserted", doc_id=doc_id)
        return doc_id


def init_db(*, path: str | None = None) -> None:
    """Create tables in-place if they don't exist.

    The Alembic migration is the source of truth, but for `scripts/run_doc.py`
    + ad-hoc local runs we don't want to require `alembic upgrade head`
    beforehand. This helper applies the same schema idempotently.

    SQL kept aligned with `2026_05_24_0002_phase1_extractions.py`.
    """
    ddl = [
        """CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            file_hash TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            byte_size INTEGER NOT NULL,
            original_s3_uri TEXT NOT NULL,
            docling_json_s3_uri TEXT,
            status TEXT NOT NULL DEFAULT 'ingested',
            user_id TEXT NOT NULL,
            parser_metadata_json TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_file_hash_user "
        "ON documents (file_hash, user_id)",
        """CREATE TABLE IF NOT EXISTS extractions (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            class TEXT NOT NULL,
            payload_variant TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            parser_version TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            temperature REAL NOT NULL DEFAULT 0,
            provenance_json TEXT,
            extraction_quality_json TEXT,
            user_id TEXT NOT NULL,
            committed_by TEXT,
            committed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_extractions_doc_id ON extractions (doc_id)",
        """CREATE TABLE IF NOT EXISTS audit (
            id TEXT PRIMARY KEY,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_audit_target ON audit (target)",
    ]
    with _cursor(path=path) as cur:
        for stmt in ddl:
            cur.execute(stmt)


# Re-export for callers that want a one-shot diagnostic insert.
def smoke_test_id() -> str:
    return f"smoke-{uuid.uuid4().hex[:8]}"
