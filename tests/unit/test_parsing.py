"""Tests for parsing.base + docling_parser._build_artifacts.

We don't import the real docling library in unit tests; we exercise
_build_artifacts against a synthetic export dict. The DocumentConverter
call path is exercised in tests/integration/.
"""

from __future__ import annotations

import pytest

from cc_distribution_parser.parsing.base import ParserProtocol
from cc_distribution_parser.parsing.docling_parser import (
    DoclingParser,
    _coerce_bbox,
    _map_layout_role,
)


def test_docling_parser_satisfies_protocol():
    parser = DoclingParser()
    assert isinstance(parser, ParserProtocol)


def test_map_layout_role_defaults_to_body():
    assert _map_layout_role("title") == "header"
    assert _map_layout_role("paragraph") == "body"
    assert _map_layout_role("table") == "table"
    assert _map_layout_role("footer") == "footer"
    assert _map_layout_role("anything_else") == "body"


def test_coerce_bbox_handles_dict_and_list_and_missing():
    assert _coerce_bbox({"l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0}) == (1.0, 2.0, 3.0, 4.0)
    assert _coerce_bbox([5.0, 6.0, 7.0, 8.0, 99.0]) == (5.0, 6.0, 7.0, 8.0)
    assert _coerce_bbox(None) == (0.0, 0.0, 0.0, 0.0)


def test_build_artifacts_emits_chunks_with_offsets():
    parser = DoclingParser()
    export = {
        "pages": [{}, {}],
        "language": "en",
        "texts": [
            {"text": "Hello", "page": 1, "label": "title", "bbox": [0.0, 0.0, 10.0, 10.0]},
            {"text": "World line", "page": 1, "label": "paragraph"},
            {"text": "", "page": 2, "label": "paragraph"},  # skipped
            {"text": "End", "page": 2, "label": "footer"},
        ],
    }
    text, chunks, meta = parser._build_artifacts(export, doc_id="d-1", user_id="u-1")
    assert text == "Hello\nWorld line\nEnd"
    assert [c.text for c in chunks] == ["Hello", "World line", "End"]
    assert chunks[0].layout_role == "header"
    assert chunks[1].layout_role == "body"
    assert chunks[2].layout_role == "footer"
    # offsets are absolute + monotonic
    assert chunks[0].char_offset_start == 0
    assert chunks[0].char_offset_end == 5
    assert chunks[1].char_offset_start == 6
    assert meta["page_count"] == 2
    assert meta["language"] == "en"


def test_build_artifacts_flags_tables():
    parser = DoclingParser()
    export = {
        "pages": [{}],
        "texts": [{"text": "row1", "page": 1, "label": "table"}],
    }
    _, _, meta = parser._build_artifacts(export, doc_id="d", user_id="u")
    assert meta["contains_tables"] is True


def test_run_docling_unsupported_mime_raises():
    parser = DoclingParser()
    with pytest.raises(ValueError):
        parser._run_docling(b"x", "image/png")
