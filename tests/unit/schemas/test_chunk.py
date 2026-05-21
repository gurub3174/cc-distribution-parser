"""Tests for cc_distribution_parser.schemas.chunk."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas import chunk as chunk_module
from cc_distribution_parser.schemas.chunk import ChunkRow


def _boundary_chunk(**overrides) -> dict:
    base = {
        "id": "chunk-0001",
        "doc_id": "doc-uuid-0001",
        "page": 1,
        "layout_role": "body",
        "text": "Capital call notice paragraph.",
        "bbox": (0.0, 0.0, 100.0, 12.0),
        "read_order": 1,
        "parent_chunk_id": None,
        "hierarchy_level": 3,
        "char_offset_start": 0,
        "char_offset_end": 30,
        "user_id": "user-1",
    }
    base.update(overrides)
    return base


def test_schema_version_exported():
    assert isinstance(chunk_module.schema_version, str)
    assert chunk_module.schema_version != ""


def test_boundary_fixture_constructs():
    row = ChunkRow(**_boundary_chunk())
    assert row.layout_role == "body"
    assert row.embedding is None  # Sprint 3 backfill
    assert row.doc_summary_context is None


def test_hierarchy_level_bounded_0_to_3():
    for ok in (0, 1, 2, 3):
        ChunkRow(**_boundary_chunk(hierarchy_level=ok))
    with pytest.raises(ValidationError):
        ChunkRow(**_boundary_chunk(hierarchy_level=4))
    with pytest.raises(ValidationError):
        ChunkRow(**_boundary_chunk(hierarchy_level=-1))


def test_read_order_must_be_positive():
    with pytest.raises(ValidationError):
        ChunkRow(**_boundary_chunk(read_order=0))


def test_char_offsets_must_be_ordered():
    with pytest.raises(ValidationError):
        ChunkRow(**_boundary_chunk(char_offset_start=50, char_offset_end=40))


def test_layout_role_restricted():
    for ok in ("header", "body", "table", "footer"):
        ChunkRow(**_boundary_chunk(layout_role=ok))
    with pytest.raises(ValidationError):
        ChunkRow(**_boundary_chunk(layout_role="banner"))


def test_bbox_is_four_tuple_of_floats():
    with pytest.raises(ValidationError):
        ChunkRow(**_boundary_chunk(bbox=(0.0, 0.0, 100.0)))  # 3-tuple


def test_page_must_be_positive():
    with pytest.raises(ValidationError):
        ChunkRow(**_boundary_chunk(page=0))


def test_parent_chunk_id_optional():
    row = ChunkRow(**_boundary_chunk(parent_chunk_id="parent-0001"))
    assert row.parent_chunk_id == "parent-0001"
