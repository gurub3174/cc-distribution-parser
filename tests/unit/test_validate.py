"""Tests for cc_distribution_parser.services.validate."""

from __future__ import annotations

from cc_distribution_parser.services.validate import (
    run,
    validate_capital_call,
    validate_distribution,
)


def _cc_payload(**overrides) -> dict:
    base = {
        "gp_name": "Acme",
        "fund_name": "Fund IV",
        "investor_name": "Alpha",
        "notice_date": "2026-05-01",
        "due_date": "2026-05-15",
        "capital_call_amount": "100.00",
        "currency": "USD",
        "unfunded_before": "500.00",
        "unfunded_after": "400.00",
    }
    base.update(overrides)
    return base


def test_cc_happy_path_passes():
    rep = validate_capital_call(_cc_payload())
    assert rep.passed is True
    assert all(s == "validated" for s in rep.per_field.values())


def test_cc_unfunded_invariant_violation_failed():
    rep = validate_capital_call(_cc_payload(unfunded_after="350.00"))
    assert rep.passed is False
    assert any("unfunded" in v for v in rep.invariant_violations)
    assert rep.per_field["unfunded_after"] == "failed"


def test_cc_absent_field_marked_absent():
    rep = validate_capital_call(_cc_payload(gp_name=""))
    assert rep.per_field["gp_name"] == "absent"
    assert rep.passed is False


def test_cc_date_order_violation():
    rep = validate_capital_call(_cc_payload(notice_date="2026-05-20", due_date="2026-05-15"))
    assert any("due_date" in v for v in rep.invariant_violations)
    assert rep.per_field["due_date"] == "failed"


def test_distro_happy_path():
    payload = {
        "gp_name": "x",
        "fund_name": "y",
        "investor_name": "z",
        "notice_date": "2026-05-01",
        "payment_date": "2026-05-10",
        "distribution_amount": "100",
        "currency": "USD",
        "distribution_type": "income",
    }
    rep = validate_distribution(payload)
    assert rep.passed is True


def test_distro_negative_amount_fails():
    payload = {
        "gp_name": "x",
        "fund_name": "y",
        "investor_name": "z",
        "notice_date": "2026-05-01",
        "payment_date": "2026-05-10",
        "distribution_amount": "-1",
        "currency": "USD",
        "distribution_type": "income",
    }
    rep = validate_distribution(payload)
    assert rep.passed is False
    assert rep.per_field["distribution_amount"] == "failed"


def test_run_dispatches_on_doc_class():
    state = {"doc_class": "capital_call", "extraction_payload": _cc_payload()}
    out = run(state)
    assert out["validation_report"]["passed"] is True
    assert out["stage"] == "validate"


def test_run_other_class_trivially_passes():
    state = {"doc_class": "other_or_reject", "extraction_payload": {}}
    out = run(state)
    assert out["validation_report"]["passed"] is True
