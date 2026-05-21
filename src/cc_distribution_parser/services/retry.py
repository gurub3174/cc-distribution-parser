"""Tiered retry stack + DLQ writer.

Per architecture.md §6.3 + .claude/rules/structured-output-fallback.md:
- Transport layer: boto3 adaptive mode + max_attempts=5 (handles 5xx, throttle)
- App layer: tenacity 3-attempt exponential backoff on TransientError
- Validation: Instructor max-2 retries on ValidationError (in llm_client)
- Tool-use fallback: ONE more attempt via Bedrock Converse toolConfig
- DLQ: write to Snowflake dlq table when all budgets exhausted

ValidationError is NEVER retried via tenacity (rule 5). It is exclusively
the Instructor retry's responsibility.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cc_distribution_parser.observability.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T")


class TransientError(Exception):
    """Marker for retryable transport/network failures."""


class NonRecoverableError(Exception):
    """Marker for failures that must NOT be retried (auth, schema mismatch, etc.)."""


# Sentinel: list of exception types that signal transient failures and SHOULD
# be retried via tenacity. ValidationError is deliberately excluded.
TRANSIENT_TYPES: tuple[type[BaseException], ...] = (TransientError,)


with_app_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
    retry=retry_if_exception_type(TRANSIENT_TYPES),
    reraise=True,
)


def is_validation_error(exc: BaseException) -> bool:
    """Explicit predicate — exclude from tenacity by construction."""
    return isinstance(exc, ValidationError)


def write_to_dlq(
    *,
    doc_id: str,
    stage: str,
    error_class: str,
    error_message: str,
    retry_count: int,
    payload: dict[str, Any] | None,
    user_id: str,
    execute: Any,
) -> str:
    """INSERT a DLQ row into Snowflake.

    `execute(sql, params)` is injected so unit tests can capture the call
    without a real Snowflake connection.

    Returns the inserted dlq.id (uuid).
    """
    dlq_id = str(uuid.uuid4())
    sql = (
        "INSERT INTO dlq (id, doc_id, stage, error_class, error_message, "
        "retry_count, last_attempt_at, payload_json, user_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), %s)"
    )
    import json

    execute(
        sql,
        (
            dlq_id,
            doc_id,
            stage,
            error_class,
            (error_message or "")[:2000],  # bound the size; never log secrets
            retry_count,
            datetime.now(UTC),
            json.dumps(payload or {}),
            user_id,
        ),
    )
    log.error(
        "dlq.write",
        doc_id=doc_id,
        stage=stage,
        error_class=error_class,
        retry_count=retry_count,
    )
    return dlq_id
