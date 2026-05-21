"""Tests for cc_distribution_parser.services.gate.

Threshold is locked at 0.0 per .claude/rules/threshold-unlock.md — every row
routes to HITL even with a passing validation report.
"""

from __future__ import annotations

from cc_distribution_parser.config import get_settings
from cc_distribution_parser.services.gate import decide, run


def test_threshold_locked_at_zero():
    get_settings.cache_clear()
    assert get_settings().auto_approve_threshold == 0.0


def test_invariant_violation_routes_to_reclassify():
    rep = {"per_field": {}, "invariant_violations": ["unfunded mismatch"], "passed": False}
    assert decide(validation_report=rep, confidence=1.0) == "reclassify"


def test_failed_field_routes_to_hitl():
    rep = {"per_field": {"x": "failed"}, "invariant_violations": [], "passed": False}
    assert decide(validation_report=rep, confidence=1.0) == "hitl"


def test_passing_with_threshold_zero_still_hitl():
    rep = {"per_field": {"x": "validated"}, "invariant_violations": [], "passed": True}
    assert decide(validation_report=rep, confidence=1.0) == "hitl"


def test_run_writes_gate_decision_to_state():
    state = {
        "validation_report": {"per_field": {}, "invariant_violations": [], "passed": True},
        "classification_confidence": 1.0,
    }
    out = run(state)
    assert out["gate_decision"] == "hitl"
    assert out["stage"] == "gate"
