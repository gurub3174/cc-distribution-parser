"""Tests for cc_distribution_parser.schemas.distribution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas import distribution as distro_module
from cc_distribution_parser.schemas.distribution import DistributionV1


def _boundary_distro(**overrides) -> dict:
    base = {
        "reasoning": "Identified income distribution from page 2.",
        "gp_name": "Acme Capital",
        "fund_name": "Acme Fund IV",
        "investor_name": "Alpha Pension",
        "notice_date": date(2026, 5, 1),
        "payment_date": date(2026, 5, 15),
        "distribution_amount": Decimal("75000.00"),
        "currency": "USD",
        "distribution_type": "income",
    }
    base.update(overrides)
    return base


def test_schema_version():
    assert distro_module.schema_version == "distribution@1.0.0"


def test_boundary_fixture_constructs():
    obj = DistributionV1(**_boundary_distro())
    assert obj.distribution_type == "income"


def test_distribution_type_literal_enforced():
    for ok in ("income", "return_of_capital", "realized_gain", "other"):
        DistributionV1(**_boundary_distro(distribution_type=ok))
    with pytest.raises(ValidationError):
        DistributionV1(**_boundary_distro(distribution_type="dividend"))


def test_amount_must_be_positive():
    with pytest.raises(ValidationError):
        DistributionV1(**_boundary_distro(distribution_amount=Decimal("0")))
