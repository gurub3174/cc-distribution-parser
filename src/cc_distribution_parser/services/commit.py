"""Commit service — idempotent Snowflake insert (extractions + audit).

Asserts `documents` row exists before inserting (foreign-key integrity is
enforced in app per snowflake_migrations/001_initial.sql convention —
Snowflake parses but does not enforce FK).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from cc_distribution_parser.observability.logging import get_logger

log = get_logger(__name__)


class DocumentMissing(Exception):  # noqa: N818 — domain term, not a generic error
    """documents row absent - refuse to insert orphan extraction."""


def assert_document_exists(*, doc_id: str, fetch_one: Any) -> None:
    row = fetch_one("SELECT id FROM documents WHERE id = %s", (doc_id,))
    if not row:
        raise DocumentMissing(f"documents row absent for doc_id={doc_id}")


def insert_extraction(*, state: dict[str, Any], execute: Any) -> str:
    """INSERT a row into extractions; returns extraction_id."""
    extraction_id = state.get("extraction_id") or str(uuid.uuid4())
    payload = state.get("extraction_payload") or {}
    provenance = state.get("provenance") or {}
    doc_class = state.get("doc_class") or "other_or_reject"

    execute(
        "INSERT INTO extractions ("
        "id, doc_id, class, payload_variant, payload_json, "
        "model_id, prompt_hash, prompt_version, parser_version, schema_version, "
        "temperature, provenance_json, user_id, committed_by, committed_at"
        ") VALUES ("
        "%s, %s, %s, %s, PARSE_JSON(%s), "
        "%s, %s, %s, %s, %s, "
        "%s, PARSE_JSON(%s), %s, %s, %s)",
        (
            extraction_id,
            state["doc_id"],
            doc_class,
            doc_class,
            json.dumps(payload),
            state.get("model_id", ""),
            state.get("prompt_hash", ""),
            state.get("prompt_version", ""),
            state.get("parser_version", ""),
            state.get("schema_version", ""),
            float(state.get("temperature", 0.0) or 0.0),
            json.dumps(provenance),
            state.get("user_id", ""),
            state.get("committed_by"),
            datetime.now(UTC),
        ),
    )
    return extraction_id


def insert_audit(*, actor: str, action: str, target: str, metadata: dict, execute: Any) -> None:
    execute(
        "INSERT INTO audit (id, actor, action, target, ts, metadata_json) "
        "VALUES (%s, %s, %s, %s, %s, PARSE_JSON(%s))",
        (
            str(uuid.uuid4()),
            actor,
            action,
            target,
            datetime.now(UTC),
            json.dumps(metadata),
        ),
    )


def run(state: Any, *, fetch_one: Any, execute: Any) -> Any:
    """Service entry. fetch_one + execute are injected so unit tests stub Snowflake."""
    assert_document_exists(doc_id=state["doc_id"], fetch_one=fetch_one)
    extraction_id = insert_extraction(state=state, execute=execute)
    insert_audit(
        actor=state.get("committed_by") or "system",
        action="extraction.commit",
        target=extraction_id,
        metadata={"doc_id": state["doc_id"], "doc_class": state.get("doc_class")},
        execute=execute,
    )
    state["extraction_id"] = extraction_id
    state["stage"] = "commit"
    log.info("commit.complete", doc_id=state["doc_id"], extraction_id=extraction_id)
    return state
