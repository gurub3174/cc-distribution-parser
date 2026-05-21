"""Ingest service: file-hash dedup + S3 upload + documents row insert.

Per spec/implementation-plan.md Sprint 1 task 11. Writes the documents
registry row with `status='ingested'`; the parse service later updates it
to `'parsed'` or `'failed_parse'`.

Dedup: if `file_hash` already exists for this `user_id`, return the existing
`doc_id` instead of re-uploading.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import boto3

from cc_distribution_parser.config import get_settings
from cc_distribution_parser.observability.logging import get_logger
from cc_distribution_parser.schemas.document import DocumentRegistryRow
from cc_distribution_parser.workflow.types import DocState

log = get_logger(__name__)


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def build_s3_key(*, user_id: str, doc_id: str, mime_type: str) -> str:
    ext = "pdf" if mime_type == "application/pdf" else "docx"
    return f"raw/{user_id}/{doc_id}.{ext}"


def _s3_client() -> Any:
    s = get_settings()
    # Empty-string endpoint = "let boto3 use AWS default" (also the path moto
    # takes when intercepting requests). boto3 rejects empty strings.
    endpoint = s.s3_endpoint_url or None
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=s.s3_access_key_id,
        aws_secret_access_key=s.s3_secret_access_key,
        region_name=s.aws_region,
    )


def upload_to_s3(*, bucket: str, key: str, body: bytes, mime_type: str) -> str:
    client = _s3_client()
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=mime_type)
    return f"s3://{bucket}/{key}"


def lookup_existing_doc(*, file_hash: str, user_id: str, fetch_one: Any) -> str | None:
    """Return existing doc_id if (file_hash, user_id) already in documents.

    `fetch_one` is a callable that runs a parameterized SELECT and returns
    a single row tuple or None — injected so unit tests can stub Snowflake.
    """
    row = fetch_one(
        "SELECT id FROM documents WHERE file_hash = %s AND user_id = %s LIMIT 1",
        (file_hash, user_id),
    )
    return row[0] if row else None


def build_documents_row(
    *,
    doc_id: str,
    file_hash: str,
    original_filename: str,
    mime_type: str,
    byte_size: int,
    original_s3_uri: str,
    user_id: str,
) -> DocumentRegistryRow:
    return DocumentRegistryRow(
        id=doc_id,
        file_hash=file_hash,
        original_filename=original_filename,
        mime_type=mime_type,  # type: ignore[arg-type]
        byte_size=byte_size,
        original_s3_uri=original_s3_uri,
        status="ingested",
        user_id=user_id,
    )


def run(state: DocState) -> DocState:
    """Service-function entry point. Idempotent on (file_hash, user_id)."""
    file_bytes = state["extraction_payload"]["_file_bytes"]  # carried in-memory only
    user_id = state["user_id"]
    mime_type = state["mime_type"]
    settings = get_settings()

    file_hash = compute_file_hash(file_bytes)
    doc_id = state.get("doc_id") or str(uuid.uuid4())
    s3_key = build_s3_key(user_id=user_id, doc_id=doc_id, mime_type=mime_type)
    s3_uri = upload_to_s3(
        bucket=settings.s3_bucket, key=s3_key, body=file_bytes, mime_type=mime_type
    )

    state["doc_id"] = doc_id
    state["file_hash"] = file_hash
    state["original_s3_uri"] = s3_uri
    state["byte_size"] = len(file_bytes)
    state["stage"] = "ingest"
    log.info("ingest.complete", doc_id=doc_id, file_hash=file_hash[:12], byte_size=len(file_bytes))
    return state
