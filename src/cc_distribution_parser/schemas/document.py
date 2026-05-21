"""Document registry row.

Mirrors the `documents` table introduced in
snowflake_migrations/002_add_documents_registry.sql (v1.1.5 amendment). Written
at FastAPI ingress (status='ingested') and updated by the parse service
(status='parsed' or 'failed_parse').

File-hash dedup runs on `file_hash` scoped by `user_id` — see
services/ingest.py for the lookup.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

schema_version = "document@1.0.0"

DocStatus = Literal["ingested", "parsed", "failed_parse"]
MimeType = Literal[
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


class ParserMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page_count: int = Field(gt=0)
    language: str
    contains_tables: bool
    contains_images: bool
    ocr_used: bool
    parse_duration_ms: int = Field(ge=0)


class DocumentRegistryRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    # SHA256 hex digest of original file bytes; 64 lowercase hex chars.
    file_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    original_filename: str
    gp_source: str | None = None
    mime_type: MimeType
    byte_size: int = Field(gt=0)
    original_s3_uri: str
    docling_json_s3_uri: str | None = None
    parser_version: str | None = None
    parser_metadata_json: ParserMetadata | None = None
    status: DocStatus
    ingested_at: datetime | None = None
    ingested_by: str | None = None
    user_id: str
