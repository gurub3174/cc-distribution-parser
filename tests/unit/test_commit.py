"""Tests for cc_distribution_parser.services.commit."""

from __future__ import annotations

from typing import Any

import pytest

from cc_distribution_parser.services.commit import (
    DocumentMissing,
    assert_document_exists,
    run,
)


def test_assert_raises_when_document_absent():
    def fetch_none(_sql, _params):
        return None

    with pytest.raises(DocumentMissing):
        assert_document_exists(doc_id="missing", fetch_one=fetch_none)


def test_assert_passes_when_document_present():
    def fetch_ok(_sql, _params):
        return ("doc-id",)

    assert_document_exists(doc_id="doc-id", fetch_one=fetch_ok)


def test_run_inserts_extraction_and_audit():
    inserts: list[tuple[str, tuple]] = []

    def fetch_ok(_sql, _params):
        return ("d-1",)

    def execute(sql: str, params: tuple) -> None:
        inserts.append((sql, params))

    state: dict[str, Any] = {
        "doc_id": "d-1",
        "user_id": "u-1",
        "doc_class": "capital_call",
        "extraction_payload": {"gp_name": "Acme"},
        "model_id": "m",
        "prompt_hash": "h",
        "prompt_version": "v",
        "parser_version": "docling@2",
        "schema_version": "capital_call@1.0.0",
        "temperature": 0.0,
        "provenance": {},
    }
    out = run(state, fetch_one=fetch_ok, execute=execute)

    sqls = [sql for sql, _ in inserts]
    assert any("INSERT INTO extractions" in s for s in sqls)
    assert any("INSERT INTO audit" in s for s in sqls)
    assert out["extraction_id"]
    assert out["stage"] == "commit"
