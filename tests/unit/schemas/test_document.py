"""Tests for cc_distribution_parser.schemas.document."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas import document as doc_module
from cc_distribution_parser.schemas.document import (
    DocumentRegistryRow,
    ParserMetadata,
)


def _boundary_doc(**overrides) -> dict:
    base = {
        "id": "doc-uuid-0001",
        "file_hash": "a" * 64,
        "original_filename": "notice.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "original_s3_uri": "s3://bucket/raw/user-1/doc-uuid-0001.pdf",
        "status": "ingested",
        "user_id": "user-1",
    }
    base.update(overrides)
    return base


def test_schema_version_exported():
    assert isinstance(doc_module.schema_version, str)
    assert doc_module.schema_version != ""


def test_boundary_fixture_constructs_ingested():
    row = DocumentRegistryRow(**_boundary_doc())
    assert row.status == "ingested"
    assert row.docling_json_s3_uri is None
    assert row.parser_version is None
    assert row.parser_metadata_json is None


def test_parsed_status_carries_full_parser_metadata():
    row = DocumentRegistryRow(
        **_boundary_doc(
            status="parsed",
            docling_json_s3_uri="s3://bucket/parsed/user-1/doc-uuid-0001.json",
            parser_version="docling@2.0.0",
            parser_metadata_json=ParserMetadata(
                page_count=3,
                language="en",
                contains_tables=True,
                contains_images=False,
                ocr_used=False,
                parse_duration_ms=420,
            ),
        )
    )
    assert row.parser_metadata_json is not None
    assert row.parser_metadata_json.contains_tables is True


def test_status_literal_rejects_unknown():
    with pytest.raises(ValidationError):
        DocumentRegistryRow(**_boundary_doc(status="archived"))


def test_file_hash_must_be_sha256_hex_length():
    with pytest.raises(ValidationError):
        DocumentRegistryRow(**_boundary_doc(file_hash="tooshort"))


def test_mime_type_restricted_to_pdf_or_docx():
    DocumentRegistryRow(**_boundary_doc(mime_type="application/pdf"))
    DocumentRegistryRow(
        **_boundary_doc(
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    )
    with pytest.raises(ValidationError):
        DocumentRegistryRow(**_boundary_doc(mime_type="image/png"))


def test_user_id_required():
    payload = _boundary_doc()
    del payload["user_id"]
    with pytest.raises(ValidationError):
        DocumentRegistryRow(**payload)


def test_byte_size_must_be_positive():
    with pytest.raises(ValidationError):
        DocumentRegistryRow(**_boundary_doc(byte_size=0))
