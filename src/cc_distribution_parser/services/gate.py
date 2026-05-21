"""Gate service — route to auto-commit / HITL / reclassify.

Hard-signal-only at Phase 1 per .claude/rules/threshold-unlock.md.
auto_approve_threshold = 0.0 means EVERY row routes to HITL today. The
shape is locked so Phase 1.5 calibration can flip the gate without
schema churn.
"""

from __future__ import annotations

from typing import Any

from cc_distribution_parser.config import get_settings


def decide(*, validation_report: dict[str, Any], confidence: float) -> str:
    """Pure decision function. Inputs are JSON-serializable; no I/O.

    Returns one of: auto_commit | hitl | reclassify | skip_extract.
    """
    settings = get_settings()
    threshold = settings.auto_approve_threshold

    has_failures = any(
        state == "failed" for state in validation_report.get("per_field", {}).values()
    )
    has_invariant_violation = bool(validation_report.get("invariant_violations"))

    if has_invariant_violation:
        # Reconciliation failure → Sonnet escalation per Critic W4.
        return "reclassify"
    if has_failures:
        return "hitl"
    if validation_report.get("passed") and confidence >= threshold:
        # threshold=0.0 means everything still routes to HITL because the
        # default upstream confidence is 1.0 — the route below catches the
        # explicit lock at 0.0 by short-circuiting.
        if threshold == 0.0:
            return "hitl"
        return "auto_commit"
    return "hitl"


def run(state: Any) -> Any:
    validation_report = state.get("validation_report") or {}
    confidence = float(state.get("classification_confidence", 0.0) or 0.0)
    decision = decide(validation_report=validation_report, confidence=confidence)
    state["gate_decision"] = decision
    state["stage"] = "gate"
    return state
