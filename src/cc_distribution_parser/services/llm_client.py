"""LLM client per .claude/rules/structured-output-fallback.md.

Contract (rule 3): Instructor + Bedrock Converse first; on
InstructorRetriesExhausted (validation budget hit), record fallback metric
and retry once via Bedrock Converse `toolConfig` (forced tool use).

Pinned model IDs come from config/models.yaml; loose IDs raise.

For the doc-independent build, the actual Bedrock Converse path is wired
behind a `_send_via_instructor` / `_send_via_tool_use` seam. Unit tests
stub these; integration with real Bedrock is exercised by `-m integration`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError

from cc_distribution_parser.observability.logging import get_logger
from cc_distribution_parser.schemas.call_metadata import CallMetadata

log = get_logger(__name__)


class InstructorRetriesExhausted(Exception):  # noqa: N818 — historical name mirrors instructor lib
    """Raised by the Instructor path after `max_retries` ValidationErrors.

    Mirrors instructor's own exception so we can swap implementations later
    without churning service code.
    """


MAX_INSTRUCTOR_RETRIES = 2  # rule 2 — DO NOT raise this.

_fallback_counter = {"count": 0, "total": 0}


def _record_fallback_metric(*, used_fallback: bool) -> None:
    _fallback_counter["total"] += 1
    if used_fallback:
        _fallback_counter["count"] += 1


def get_fallback_rate() -> float:
    """Used by services/retry_rate_alerter.py."""
    total = _fallback_counter["total"]
    return _fallback_counter["count"] / total if total else 0.0


def reset_fallback_metrics() -> None:
    _fallback_counter["count"] = 0
    _fallback_counter["total"] = 0


def call(
    *,
    model_id: str,
    system: str,
    user: str,
    response_model: type[BaseModel],
    temperature: float = 0.0,
    prompt_cache_keys: list[str] | None = None,
    prompt_version: str,
    prompt_hash: str,
    # Test seams — injected by unit tests; defaulted to real impls below.
    instructor_send: Callable[..., tuple[BaseModel, dict[str, Any]]] | None = None,
    tool_use_send: Callable[..., tuple[BaseModel, dict[str, Any]]] | None = None,
) -> tuple[BaseModel, CallMetadata]:
    """Call Bedrock Converse with Instructor; fall back to tool_use on failure.

    Returns (parsed_response, CallMetadata). CallMetadata.used_fallback flags
    whether the tool_use path was used.
    """
    if not model_id or model_id.startswith(("sonnet", "haiku", "claude-")):
        raise ValueError(
            f"loose model id rejected: {model_id!r}. Use the pinned ID from config/models.yaml."
        )

    t0 = time.monotonic()
    used_fallback = False
    retry_count = 0
    raw_meta: dict[str, Any]

    instructor_send = instructor_send or _call_via_instructor
    tool_use_send = tool_use_send or _call_via_tool_use

    try:
        parsed, raw_meta = instructor_send(
            model_id=model_id,
            system=system,
            user=user,
            response_model=response_model,
            temperature=temperature,
            prompt_cache_keys=prompt_cache_keys or [],
            max_retries=MAX_INSTRUCTOR_RETRIES,
        )
    except (InstructorRetriesExhausted, ValidationError) as exc:
        used_fallback = True
        retry_count = MAX_INSTRUCTOR_RETRIES
        log.warning(
            "llm_client.fallback_to_tool_use",
            model_id=model_id,
            reason=type(exc).__name__,
        )
        parsed, raw_meta = tool_use_send(
            model_id=model_id,
            system=system,
            user=user,
            response_model=response_model,
            temperature=temperature,
            prompt_cache_keys=prompt_cache_keys or [],
        )

    _record_fallback_metric(used_fallback=used_fallback)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    meta = CallMetadata(
        model_id=model_id,
        prompt_hash=prompt_hash,
        prompt_version=prompt_version,
        input_tokens=int(raw_meta.get("input_tokens", 0)),
        output_tokens=int(raw_meta.get("output_tokens", 0)),
        cached_tokens=int(raw_meta.get("cached_tokens", 0)),
        cost_usd=Decimal(str(raw_meta.get("cost_usd", "0"))),
        latency_ms=elapsed_ms,
        retry_count=retry_count,
        temperature=temperature,
        used_fallback=used_fallback,
    )
    return parsed, meta


def _call_via_instructor(**_kwargs: Any) -> tuple[BaseModel, dict[str, Any]]:
    """Real Instructor + Bedrock Converse path.

    Stubbed in this build — the actual Instructor wiring requires real
    Bedrock endpoints + creds, which we can't exercise in CI. Implementation
    is unblocked by Sprint 0 dependency install; populating this body is a
    Phase 1 task tracked separately.
    """
    raise NotImplementedError(
        "Instructor path not wired. Pass `instructor_send=` from tests or wire "
        "in Phase 1 when Bedrock creds are available."
    )


def _call_via_tool_use(**_kwargs: Any) -> tuple[BaseModel, dict[str, Any]]:
    """Real Bedrock Converse `toolConfig` path. Same wiring caveat as Instructor."""
    raise NotImplementedError(
        "tool_use fallback not wired. Pass `tool_use_send=` from tests or wire "
        "in Phase 1 when Bedrock creds are available."
    )
