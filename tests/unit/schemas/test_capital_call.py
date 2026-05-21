"""Tests for cc_distribution_parser.schemas.capital_call."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas import capital_call as cc_module
from cc_distribution_parser.schemas.capital_call import CapitalCallV1


def _boundary_cc(**overrides) -> dict:
    base = {
        "reasoning": "Identified amount and unfunded balances from page 1.",
        "gp_name": "Acme Capital",
        "fund_name": "Acme Fund IV",
        "investor_name": "Alpha Pension",
        "notice_date": date(2026, 5, 1),
        "due_date": date(2026, 5, 15),
        "capital_call_amount": Decimal("100000.00"),
        "currency": "USD",
        "unfunded_before": Decimal("500000.00"),
        "unfunded_after": Decimal("400000.00"),
    }
    base.update(overrides)
    return base


def test_schema_version_exported():
    assert cc_module.schema_version == "capital_call@1.0.0"


def test_boundary_fixture_constructs():
    obj = CapitalCallV1(**_boundary_cc())
    assert obj.capital_call_amount == Decimal("100000.00")


def test_reasoning_required():
    with pytest.raises(ValidationError):
        CapitalCallV1(**_boundary_cc(reasoning=""))


def test_unfunded_invariant_enforced():
    # before - call != after
    with pytest.raises(ValidationError):
        CapitalCallV1(
            **_boundary_cc(unfunded_after=Decimal("350000.00"))  # wrong by 50k
        )


def test_unfunded_invariant_tolerance_at_one_cent():
    # Within 1 cent (|diff| < 0.01) passes.
    CapitalCallV1(**_boundary_cc(unfunded_after=Decimal("399999.995")))
    # At/beyond 1 cent fails (strict |diff| >= 0.01).
    with pytest.raises(ValidationError):
        CapitalCallV1(**_boundary_cc(unfunded_after=Decimal("399999.99")))


def test_dates_ordered():
    with pytest.raises(ValidationError):
        CapitalCallV1(**_boundary_cc(notice_date=date(2026, 5, 20), due_date=date(2026, 5, 15)))


def test_currency_iso_3_uppercase():
    with pytest.raises(ValidationError):
        CapitalCallV1(**_boundary_cc(currency="usd"))
    with pytest.raises(ValidationError):
        CapitalCallV1(**_boundary_cc(currency="DOLLAR"))


def test_amount_must_be_positive():
    with pytest.raises(ValidationError):
        CapitalCallV1(**_boundary_cc(capital_call_amount=Decimal("0")))


def test_frozen():
    obj = CapitalCallV1(**_boundary_cc())
    with pytest.raises(ValidationError):
        obj.gp_name = "Other"  # type: ignore[misc]
