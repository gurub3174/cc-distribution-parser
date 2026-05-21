"""Smoke tests for FastAPI app via TestClient.

Uses a stub parser to avoid importing docling. S3 is mocked via moto.
"""

from __future__ import annotations

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from cc_distribution_parser.main import create_app

from .test_services_ingest_parse import BUCKET, StubParser


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("CCDP_S3_ENDPOINT_URL", "")
    from cc_distribution_parser.config import get_settings

    get_settings.cache_clear()
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        app = create_app(parser=StubParser())
        with TestClient(app) as client:
            yield client
    get_settings.cache_clear()


def test_healthz(app_client):
    r = app_client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_upload_pdf_returns_doc_metadata(app_client):
    files = {"file": ("notice.pdf", b"%PDF-fake", "application/pdf")}
    data = {"user_id": "u-test"}
    r = app_client.post("/upload", files=files, data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "parsed"
    assert body["chunk_count"] == 1
    assert body["page_count"] == 1
    assert body["byte_size"] == len(b"%PDF-fake")
    assert len(body["file_hash"]) == 64


def test_upload_rejects_unsupported_mime(app_client):
    files = {"file": ("img.png", b"\x89PNG", "image/png")}
    data = {"user_id": "u-test"}
    r = app_client.post("/upload", files=files, data=data)
    assert r.status_code == 415


def test_upload_rejects_empty(app_client):
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    data = {"user_id": "u-test"}
    r = app_client.post("/upload", files=files, data=data)
    assert r.status_code == 400
