"""Validator service — domain reconciliation + tri-state per-field signals.

Pydantic at extraction time already enforces the CC unfunded invariant +
date ordering + currency. This service adds:

- Cross-checks beyond a single Pydantic model (e.g., the CC invariant is
  ALSO checked here for defense in depth — Pydantic can be bypassed by a
  bad tool_use response).
- Per-field tri-state classification: validated | absent | failed.
- ValidationReport that feeds the gate.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

FieldState = Literal["validated", "absent", "failed"]


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    per_field: dict[str, FieldState]
    invariant_violations: list[str]
    passed: bool


def _to_decimal(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def validate_capital_call(payload: dict[str, Any]) -> ValidationReport:
    per_field: dict[str, FieldState] = {}
    violations: list[str] = []

    required = (
        "gp_name",
        "fund_name",
        "investor_name",
        "notice_date",
        "due_date",
        "capital_call_amount",
        "currency",
        "unfunded_before",
        "unfunded_after",
    )
    for f in required:
        v = payload.get(f)
        if v is None or v == "":
            per_field[f] = "absent"
        else:
            per_field[f] = "validated"

    call = _to_decimal(payload.get("capital_call_amount"))
    before = _to_decimal(payload.get("unfunded_before"))
    after = _to_decimal(payload.get("unfunded_after"))
    if call is not None and before is not None and after is not None:
        diff = (before - call) - after
        if abs(diff) >= Decimal("0.01"):
            violations.append(f"unfunded invariant: ({before} - {call}) - {after} = {diff}")
            per_field["unfunded_after"] = "failed"

    notice = payload.get("notice_date")
    due = payload.get("due_date")
    if notice and due and str(due) < str(notice):
        violations.append(f"due_date {due} before notice_date {notice}")
        per_field["due_date"] = "failed"

    passed = not violations and all(s == "validated" for s in per_field.values())
    return ValidationReport(per_field=per_field, invariant_violations=violations, passed=passed)


def validate_distribution(payload: dict[str, Any]) -> ValidationReport:
    per_field: dict[str, FieldState] = {}
    violations: list[str] = []

    required = (
        "gp_name",
        "fund_name",
        "investor_name",
        "notice_date",
        "payment_date",
        "distribution_amount",
        "currency",
        "distribution_type",
    )
    for f in required:
        v = payload.get(f)
        if v is None or v == "":
            per_field[f] = "absent"
        else:
            per_field[f] = "validated"

    amt = _to_decimal(payload.get("distribution_amount"))
    if amt is not None and amt <= 0:
        violations.append(f"distribution_amount must be > 0; got {amt}")
        per_field["distribution_amount"] = "failed"

    passed = not violations and all(s == "validated" for s in per_field.values())
    return ValidationReport(per_field=per_field, invariant_violations=violations, passed=passed)


def run(state: Any) -> Any:
    """Service entry — dispatch on doc_class."""
    doc_class = state.get("doc_class")
    payload = state.get("extraction_payload") or {}
    if doc_class == "capital_call":
        report = validate_capital_call(payload)
    elif doc_class == "distribution":
        report = validate_distribution(payload)
    else:
        # other_or_reject: nothing to validate. Empty report = trivially passed.
        report = ValidationReport(per_field={}, invariant_violations=[], passed=True)
    state["validation_report"] = report.model_dump()
    state["stage"] = "validate"
    return state
