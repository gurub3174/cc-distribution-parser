"""Unit tests for services.ingest + services.parse.

S3 is mocked via moto; the parser is a stub. No external network calls.
"""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from cc_distribution_parser.schemas.chunk import ChunkRow
from cc_distribution_parser.schemas.document import ParserMetadata
from cc_distribution_parser.schemas.parsed_doc import ParsedDoc
from cc_distribution_parser.services import ingest as ingest_service
from cc_distribution_parser.services import parse as parse_service
from cc_distribution_parser.workflow.types import DocState

BUCKET = "ccdp-dev"


class StubParser:
    name = "stub"
    version = "stub@1.0.0"

    def parse(self, file_bytes, mime_type, *, doc_id, user_id):
        text = "Hello world"
        parsed = ParsedDoc(
            doc_id=doc_id,
            text=text,
            parser_version=self.version,
            page_count=1,
            language="en",
            contains_tables=False,
            contains_images=False,
            ocr_used=False,
            parse_duration_ms=5,
        )
        chunks = [
            ChunkRow(
                id=f"{doc_id}:c1",
                doc_id=doc_id,
                page=1,
                layout_role="body",
                text=text,
                bbox=(0.0, 0.0, 10.0, 10.0),
                read_order=1,
                hierarchy_level=3,
                char_offset_start=0,
                char_offset_end=len(text),
                user_id=user_id,
            )
        ]
        meta = ParserMetadata(
            page_count=1,
            language="en",
            contains_tables=False,
            contains_images=False,
            ocr_used=False,
            parse_duration_ms=5,
        )
        return parsed, chunks, meta


@pytest.fixture
def s3_env(monkeypatch):
    # moto's mock_aws intercepts boto3.client('s3') regardless of endpoint;
    # we still set fake creds so boto3 doesn't try to read ~/.aws/credentials.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("CCDP_S3_ENDPOINT_URL", "")  # let moto handle it
    # bust the lru_cache so the empty endpoint takes effect
    from cc_distribution_parser.config import get_settings

    get_settings.cache_clear()
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield
    get_settings.cache_clear()


def test_compute_file_hash_deterministic():
    h1 = ingest_service.compute_file_hash(b"abc")
    h2 = ingest_service.compute_file_hash(b"abc")
    assert h1 == h2
    assert len(h1) == 64


def test_build_s3_key_pdf_vs_docx():
    pdf_key = ingest_service.build_s3_key(user_id="u1", doc_id="d1", mime_type="application/pdf")
    docx_key = ingest_service.build_s3_key(
        user_id="u1",
        doc_id="d1",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert pdf_key == "raw/u1/d1.pdf"
    assert docx_key == "raw/u1/d1.docx"


def test_lookup_existing_doc_returns_id_when_present():
    def fake_fetch(_sql, _params):
        return ("existing-doc-id",)

    out = ingest_service.lookup_existing_doc(file_hash="h", user_id="u", fetch_one=fake_fetch)
    assert out == "existing-doc-id"


def test_lookup_existing_doc_returns_none_when_absent():
    def fake_fetch(_sql, _params):
        return None

    out = ingest_service.lookup_existing_doc(file_hash="h", user_id="u", fetch_one=fake_fetch)
    assert out is None


def test_build_documents_row_status_ingested():
    row = ingest_service.build_documents_row(
        doc_id="d1",
        file_hash="a" * 64,
        original_filename="x.pdf",
        mime_type="application/pdf",
        byte_size=100,
        original_s3_uri="s3://b/raw/u/d1.pdf",
        user_id="u",
    )
    assert row.status == "ingested"
    assert row.parser_version is None


def test_ingest_run_writes_to_s3_and_populates_state(s3_env):
    state: DocState = {
        "user_id": "u-1",
        "mime_type": "application/pdf",
        "original_filename": "x.pdf",
        "pipeline_run_id": "r-1",
        "extraction_payload": {"_file_bytes": b"%PDF-fake"},
    }
    out = ingest_service.run(state)
    assert out["doc_id"]
    assert out["file_hash"]
    assert out["original_s3_uri"].startswith("s3://ccdp-dev/raw/u-1/")
    assert out["byte_size"] == len(b"%PDF-fake")
    # blob actually landed in S3
    client = boto3.client("s3", region_name="us-east-1")
    key = out["original_s3_uri"].split(f"{BUCKET}/", 1)[1]
    body = client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    assert body == b"%PDF-fake"


def test_parse_run_uploads_parsed_json_and_emits_chunks(s3_env):
    state: DocState = {
        "doc_id": "d-1",
        "user_id": "u-1",
        "mime_type": "application/pdf",
        "pipeline_run_id": "r-1",
    }
    out = parse_service.run(state, parser=StubParser(), file_bytes=b"%PDF-fake")
    assert out["parser_version"] == "stub@1.0.0"
    assert out["docling_json_s3_uri"].endswith("/d-1.json")
    assert len(out["chunks"]) == 1
    assert out["parser_metadata"]["page_count"] == 1
