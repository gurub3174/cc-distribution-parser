"""Tests for cc_distribution_parser.workflow.types."""

from __future__ import annotations

from cc_distribution_parser.workflow.types import DocState


def test_docstate_allows_partial_dict():
    s: DocState = {"doc_id": "d1"}
    assert s["doc_id"] == "d1"


def test_docstate_accepts_full_pipeline_keys():
    s: DocState = {
        "doc_id": "d1",
        "pipeline_run_id": "r1",
        "user_id": "u1",
        "stage": "parse",
        "doc_class": "capital_call",
    }
    assert s["stage"] == "parse"
    assert s["doc_class"] == "capital_call"
