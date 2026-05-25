"""Unit tests for the Phase-1 SQLite commit backend."""

from __future__ import annotations

import pathlib

from cc_distribution_parser.services import commit as commit_service
from cc_distribution_parser.services.commit_sqlite import (
    _to_sqlite_sql,
    ensure_documents_row,
    init_db,
    make_executors,
)


def _new_db(tmp_path: pathlib.Path) -> str:
    path = str(tmp_path / "ops.sqlite")
    init_db(path=path)
    return path


def test_sql_translation_handles_parse_json() -> None:
    sql = (
        "INSERT INTO extractions (id, payload_json, provenance_json) "
        "VALUES (%s, PARSE_JSON(%s), PARSE_JSON(%s))"
    )
    out = _to_sqlite_sql(sql)
    assert out == ("INSERT INTO extractions (id, payload_json, provenance_json) VALUES (?, ?, ?)")


def test_sql_translation_preserves_select_paramstyle() -> None:
    assert _to_sqlite_sql("SELECT id FROM documents WHERE id = %s") == (
        "SELECT id FROM documents WHERE id = ?"
    )


def test_ensure_documents_row_idempotent(tmp_path: pathlib.Path) -> None:
    db = _new_db(tmp_path)
    state = {
        "doc_id": "d1",
        "file_hash": "abc",
        "original_filename": "n.pdf",
        "mime_type": "application/pdf",
        "byte_size": 100,
        "original_s3_uri": "s3://x/y",
        "user_id": "u1",
        "parser_metadata": {"page_count": 1},
    }
    ensure_documents_row(state, path=db)
    ensure_documents_row(state, path=db)  # second call must not error
    fetch_one, _ = make_executors(path=db)
    row = fetch_one("SELECT id, file_hash FROM documents WHERE id = %s", ("d1",))
    assert row == ("d1", "abc")


def test_end_to_end_commit_via_sqlite_executors(tmp_path: pathlib.Path) -> None:
    """commit.run with sqlite-backed fetch_one/execute writes both rows."""
    db = _new_db(tmp_path)
    ensure_documents_row(
        {
            "doc_id": "d42",
            "file_hash": "h",
            "original_filename": "n.pdf",
            "mime_type": "application/pdf",
            "byte_size": 10,
            "original_s3_uri": "s3://x/y",
            "user_id": "u1",
            "parser_metadata": {},
        },
        path=db,
    )
    fetch_one, execute = make_executors(path=db)
    state = {
        "doc_id": "d42",
        "doc_class": "capital_call",
        "extraction_payload": {"gp_name": "Acme"},
        "provenance": {"few_shot_ids": []},
        "model_id": "m",
        "prompt_hash": "p",
        "prompt_version": "v",
        "parser_version": "pv",
        "schema_version": "sv",
        "temperature": 0.0,
        "user_id": "u1",
    }
    out = commit_service.run(state, fetch_one=fetch_one, execute=execute)
    assert "extraction_id" in out
    row = fetch_one("SELECT class, payload_json FROM extractions WHERE doc_id = %s", ("d42",))
    assert row is not None
    assert row[0] == "capital_call"
    assert '"gp_name": "Acme"' in row[1]


def test_audit_row_written(tmp_path: pathlib.Path) -> None:
    db = _new_db(tmp_path)
    ensure_documents_row(
        {
            "doc_id": "d1",
            "file_hash": "h",
            "original_filename": "n.pdf",
            "mime_type": "application/pdf",
            "byte_size": 1,
            "original_s3_uri": "s3://x/y",
            "user_id": "u1",
            "parser_metadata": {},
        },
        path=db,
    )
    fetch_one, execute = make_executors(path=db)
    commit_service.run(
        {
            "doc_id": "d1",
            "doc_class": "capital_call",
            "extraction_payload": {},
            "provenance": {},
            "model_id": "m",
            "prompt_hash": "p",
            "prompt_version": "v",
            "parser_version": "pv",
            "schema_version": "sv",
            "temperature": 0.0,
            "user_id": "u1",
        },
        fetch_one=fetch_one,
        execute=execute,
    )
    audit_row = fetch_one("SELECT action FROM audit WHERE action = %s", ("extraction.commit",))
    assert audit_row == ("extraction.commit",)
