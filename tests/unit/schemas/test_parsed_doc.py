"""Tests for cc_distribution_parser.schemas.parsed_doc."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas import parsed_doc as pd_module
from cc_distribution_parser.schemas.parsed_doc import ParsedDoc


def _boundary_parsed_doc(**overrides) -> dict:
    base = {
        "doc_id": "11111111-1111-1111-1111-111111111111",
        "text": "Sample doc text.",
        "parser_version": "docling@2.0.0",
        "page_count": 1,
        "language": "en",
        "contains_tables": False,
        "contains_images": False,
        "ocr_used": False,
        "parse_duration_ms": 250,
    }
    base.update(overrides)
    return base


def test_schema_version_exported():
    assert isinstance(pd_module.schema_version, str)
    assert pd_module.schema_version != ""


def test_boundary_fixture_constructs():
    doc = ParsedDoc(**_boundary_parsed_doc())
    assert doc.doc_id == "11111111-1111-1111-1111-111111111111"
    assert doc.parser_version == "docling@2.0.0"


def test_missing_required_field_rejected():
    payload = _boundary_parsed_doc()
    del payload["parser_version"]
    with pytest.raises(ValidationError):
        ParsedDoc(**payload)


def test_page_count_must_be_positive():
    with pytest.raises(ValidationError):
        ParsedDoc(**_boundary_parsed_doc(page_count=0))


def test_parse_duration_ms_non_negative():
    with pytest.raises(ValidationError):
        ParsedDoc(**_boundary_parsed_doc(parse_duration_ms=-1))


def test_immutable_after_construction():
    doc = ParsedDoc(**_boundary_parsed_doc())
    with pytest.raises(ValidationError):
        doc.parser_version = "different@9.9.9"  # type: ignore[misc]
