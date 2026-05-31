"""Parse service: ParserProtocol → S3 parsed.json → documents update → chunks.

The parser is injected so unit tests pass a stub. In prod the DoclingParser
is wired in `main.py` at startup.
"""

from __future__ import annotations

import json
from typing import Any

from cc_distribution_parser.config import get_settings
from cc_distribution_parser.observability.logging import get_logger
from cc_distribution_parser.parsing.base import ParserProtocol
from cc_distribution_parser.services.ingest import _s3_client
from cc_distribution_parser.workflow.types import DocState

log = get_logger(__name__)


def build_parsed_s3_key(*, user_id: str, doc_id: str) -> str:
    return f"parsed/{user_id}/{doc_id}.json"


def upload_parsed_json(*, bucket: str, key: str, body: dict[str, Any]) -> str:
    client = _s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(body).encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"


def run(
    state: DocState,
    *,
    parser: ParserProtocol,
    file_bytes: bytes,
    fallback_parser: ParserProtocol | None = None,
) -> DocState:
    """Parse the file, store parsed JSON, write chunks to state.

    `file_bytes` is passed explicitly rather than fished out of state because
    state must remain JSON-serializable for LangGraph checkpoints. Binary
    payloads stay in process memory and S3.

    `fallback_parser`: if the primary parser returns 0 chunks AND a fallback
    is wired, retry through the fallback. Used for image-only PDFs where
    Docling's layout classifier marks every page as a Picture region and no
    text is extracted — VLMParser then transcribes via Bedrock Sonnet.
    """
    settings = get_settings()
    doc_id = state["doc_id"]
    user_id = state["user_id"]
    mime_type = state["mime_type"]

    parsed_doc, chunks, parser_metadata = parser.parse(
        file_bytes, mime_type, doc_id=doc_id, user_id=user_id
    )

    if len(chunks) == 0 and fallback_parser is not None:
        log.info(
            "parse.primary_empty.fallback",
            doc_id=doc_id,
            primary_parser=parser.version,
            fallback_parser=fallback_parser.version,
        )
        parsed_doc, chunks, parser_metadata = fallback_parser.parse(
            file_bytes, mime_type, doc_id=doc_id, user_id=user_id
        )

    parsed_json_uri = upload_parsed_json(
        bucket=settings.s3_bucket,
        key=build_parsed_s3_key(user_id=user_id, doc_id=doc_id),
        body=parsed_doc.model_dump(),
    )

    state["parsed_doc"] = parsed_doc.model_dump()
    state["chunks"] = [c.model_dump() for c in chunks]
    state["parser_version"] = parsed_doc.parser_version
    state["parser_metadata"] = parser_metadata.model_dump()
    state["docling_json_s3_uri"] = parsed_json_uri
    state["stage"] = "parse"
    log.info(
        "parse.complete",
        doc_id=doc_id,
        parser_version=parsed_doc.parser_version,
        chunk_count=len(chunks),
        page_count=parser_metadata.page_count,
    )
    return state
