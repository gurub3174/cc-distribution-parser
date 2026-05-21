"""Tests for cc_distribution_parser.services.audit."""

from __future__ import annotations

from typing import Any

from cc_distribution_parser.services.audit import write_audit


def test_write_audit_inserts_row():
    captured: dict[str, Any] = {}

    def execute(sql: str, params: tuple) -> None:
        captured["sql"] = sql
        captured["params"] = params

    audit_id = write_audit(
        actor="reviewer-1",
        action="hitl.approve",
        target="extr-1",
        metadata={"doc_id": "d-1"},
        execute=execute,
    )
    assert "INSERT INTO audit" in captured["sql"]
    # id, actor, action, target, ts, metadata
    assert captured["params"][1] == "reviewer-1"
    assert captured["params"][2] == "hitl.approve"
    assert captured["params"][3] == "extr-1"
    assert isinstance(audit_id, str) and len(audit_id) > 10


def test_write_audit_handles_no_metadata():
    captured: dict[str, Any] = {}

    def execute(sql, params):
        captured["params"] = params

    write_audit(
        actor="system",
        action="config.threshold_change",
        target=None,
        metadata=None,
        execute=execute,
    )
    assert captured["params"][3] == ""
