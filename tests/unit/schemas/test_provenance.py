"""Tests for cc_distribution_parser.schemas.provenance."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas import provenance as prov_module
from cc_distribution_parser.schemas.provenance import (
    ExtractionProvenance,
    FieldProvenance,
)


def _boundary_field_provenance(**overrides) -> dict:
    base = {
        "page": 1,
        "bbox": (0.0, 0.0, 100.0, 12.0),
        "char_offset_start": 0,
        "char_offset_end": 30,
        "chunk_id": uuid4(),
    }
    base.update(overrides)
    return base


def _boundary_extraction_provenance(**overrides) -> dict:
    base = {
        "few_shot_ids": [],
        "field_provenance": {},
        "input_tokens": 100,
        "output_tokens": 50,
        "cached_tokens": 0,
        "cost_usd": Decimal("0.001"),
        "latency_ms": 1200,
        "signals": {},
    }
    base.update(overrides)
    return base


def test_schema_version_exported():
    assert isinstance(prov_module.schema_version, str)
    assert prov_module.schema_version != ""


def test_field_provenance_boundary_constructs():
    fp = FieldProvenance(**_boundary_field_provenance())
    assert isinstance(fp.chunk_id, UUID)


def test_field_provenance_offsets_must_be_ordered():
    with pytest.raises(ValidationError):
        FieldProvenance(**_boundary_field_provenance(char_offset_start=50, char_offset_end=40))


def test_field_provenance_page_must_be_positive():
    with pytest.raises(ValidationError):
        FieldProvenance(**_boundary_field_provenance(page=0))


def test_field_provenance_bbox_is_four_tuple():
    with pytest.raises(ValidationError):
        FieldProvenance(**_boundary_field_provenance(bbox=(0.0, 0.0, 100.0)))


def test_extraction_provenance_boundary_constructs():
    ep = ExtractionProvenance(**_boundary_extraction_provenance())
    assert ep.cost_usd == Decimal("0.001")
    assert ep.field_provenance == {}


def test_extraction_provenance_field_provenance_keys_are_field_names():
    fp = FieldProvenance(**_boundary_field_provenance())
    ep = ExtractionProvenance(
        **_boundary_extraction_provenance(
            field_provenance={"capital_call_amount": fp},
        )
    )
    assert ep.field_provenance["capital_call_amount"].page == 1


def test_extraction_provenance_token_counts_non_negative():
    with pytest.raises(ValidationError):
        ExtractionProvenance(**_boundary_extraction_provenance(input_tokens=-1))
    with pytest.raises(ValidationError):
        ExtractionProvenance(**_boundary_extraction_provenance(output_tokens=-1))
    with pytest.raises(ValidationError):
        ExtractionProvenance(**_boundary_extraction_provenance(cached_tokens=-1))


def test_extraction_provenance_cost_non_negative():
    with pytest.raises(ValidationError):
        ExtractionProvenance(**_boundary_extraction_provenance(cost_usd=Decimal("-0.0001")))


def test_extraction_provenance_latency_non_negative():
    with pytest.raises(ValidationError):
        ExtractionProvenance(**_boundary_extraction_provenance(latency_ms=-1))
