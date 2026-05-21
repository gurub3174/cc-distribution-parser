"""Tests for cc_distribution_parser.schemas.call_metadata."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas.call_metadata import CallMetadata


def _boundary(**overrides) -> dict:
    base = {
        "model_id": "us.anthropic.claude-sonnet-4-6-20250929-v1:0",
        "prompt_hash": "abc123",
        "prompt_version": "extract_cc@0.1.0",
        "input_tokens": 100,
        "output_tokens": 50,
        "cached_tokens": 0,
        "cost_usd": Decimal("0.0125"),
        "latency_ms": 1200,
        "retry_count": 0,
        "temperature": 0.0,
        "used_fallback": False,
    }
    base.update(overrides)
    return base


def test_boundary_constructs():
    m = CallMetadata(**_boundary())
    assert m.used_fallback is False


def test_temperature_bounds():
    CallMetadata(**_boundary(temperature=0.0))
    CallMetadata(**_boundary(temperature=2.0))
    with pytest.raises(ValidationError):
        CallMetadata(**_boundary(temperature=-0.01))
    with pytest.raises(ValidationError):
        CallMetadata(**_boundary(temperature=2.01))


def test_cost_non_negative():
    with pytest.raises(ValidationError):
        CallMetadata(**_boundary(cost_usd=Decimal("-0.01")))
