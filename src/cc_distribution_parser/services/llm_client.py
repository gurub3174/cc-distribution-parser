"""LLM client per .claude/rules/structured-output-fallback.md.

Contract (rule 3): Instructor + Bedrock Converse first; on
InstructorRetriesExhausted (validation budget hit), record fallback metric
and retry once via Bedrock Converse `toolConfig` (forced tool use).

Pinned model IDs come from config/models.yaml; loose IDs raise.

The Bedrock Converse path is implemented at `_call_via_instructor` (manual
JSON-mode + bounded ValidationError retries; preserves Instructor pattern
without coupling to instructor library API churn) and `_call_via_tool_use`
(Converse `toolConfig` with forced tool-use). Unit tests inject stub
callables via `instructor_send=` / `tool_use_send=` and never touch boto3.
"""

from __future__ import annotations

import re
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


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fences(s: str) -> str:
    return _JSON_FENCE_RE.sub("", s).strip()


def _bedrock_client() -> Any:
    """Lazy-imported boto3 client. Lazy so unit tests that inject senders
    never touch boto3 / AWS auth at all.

    Loads `.env` into os.environ here (not at module import) so boto3's
    default credential provider chain picks up AWS_ACCESS_KEY_ID /
    AWS_SECRET_ACCESS_KEY. pydantic-settings reads .env for our CCDP_*
    vars but doesn't push them to os.environ — boto3 needs them there.
    """
    import boto3
    from dotenv import load_dotenv

    from cc_distribution_parser.config import get_settings

    load_dotenv()
    return boto3.client("bedrock-runtime", region_name=get_settings().aws_region)


def _usage_to_raw_meta(model_id: str, usage: dict[str, Any]) -> dict[str, Any]:
    from cc_distribution_parser.services.bedrock_pricing import compute_cost

    in_tok = int(usage.get("inputTokens", 0))
    out_tok = int(usage.get("outputTokens", 0))
    cached = int(usage.get("cacheReadInputTokens", 0))
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cached_tokens": cached,
        "cost_usd": str(compute_cost(model_id, in_tok, out_tok)),
    }


def _call_via_instructor(
    *,
    model_id: str,
    system: str,
    user: str,
    response_model: type[BaseModel],
    temperature: float,
    prompt_cache_keys: list[str],
    max_retries: int,
) -> tuple[BaseModel, dict[str, Any]]:
    """Bedrock Converse + JSON-mode + bounded Pydantic validation retries.

    Implements the Instructor pattern manually for stability across instructor
    library minor versions. Contract:
      - Ask for raw JSON conforming to response_model.model_json_schema()
      - Validate with response_model.model_validate_json
      - On ValidationError, append the error and retry up to `max_retries` more times
      - On exhaustion, raise InstructorRetriesExhausted (outer call() falls back to tool_use)
    """
    import json as _json

    client = _bedrock_client()
    schema_json = _json.dumps(response_model.model_json_schema(), indent=2)
    base_instruction = (
        f"{user}\n\n"
        f"Return ONLY a JSON object matching this schema:\n{schema_json}\n\n"
        f"No prose, no markdown fences — just the JSON object."
    )

    convo_user = base_instruction
    last_error: ValidationError | None = None

    for _attempt in range(max_retries + 1):
        response = client.converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": convo_user}]}],
            inferenceConfig={"temperature": float(temperature), "maxTokens": 4096},
        )
        try:
            text_block = response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"unexpected Converse response shape: {response}") from exc
        candidate = _strip_code_fences(text_block)
        try:
            parsed = response_model.model_validate_json(candidate)
            return parsed, _usage_to_raw_meta(model_id, response.get("usage", {}))
        except ValidationError as exc:
            last_error = exc
            convo_user = (
                f"{base_instruction}\n\n"
                f"Previous attempt failed validation:\n{exc}\n"
                f"Return ONLY the corrected JSON object."
            )

    raise InstructorRetriesExhausted(
        f"validation failed after {max_retries + 1} attempts: {last_error}"
    )


def _call_via_tool_use(
    *,
    model_id: str,
    system: str,
    user: str,
    response_model: type[BaseModel],
    temperature: float,
    prompt_cache_keys: list[str],
) -> tuple[BaseModel, dict[str, Any]]:
    """Bedrock Converse `toolConfig` with forced tool use.

    Per .claude/rules/structured-output-fallback.md rule 3: tools have a
    different output path than freeform text — empirically catches a class
    of validation failures that JSON-mode doesn't.
    """
    client = _bedrock_client()

    tool_name = response_model.__name__
    schema = response_model.model_json_schema()
    tools = [
        {
            "toolSpec": {
                "name": tool_name,
                "description": f"Return a {tool_name} extraction.",
                "inputSchema": {"json": schema},
            }
        }
    ]

    response = client.converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        toolConfig={"tools": tools, "toolChoice": {"tool": {"name": tool_name}}},
        inferenceConfig={"temperature": float(temperature), "maxTokens": 4096},
    )

    content = response.get("output", {}).get("message", {}).get("content", [])
    tool_input: dict[str, Any] | None = None
    for block in content:
        tu = block.get("toolUse")
        if tu and tu.get("name") == tool_name:
            tool_input = tu.get("input")
            break
    if tool_input is None:
        raise RuntimeError(f"tool_use fallback: no toolUse block in response: {response}")

    parsed = response_model.model_validate(tool_input)
    return parsed, _usage_to_raw_meta(model_id, response.get("usage", {}))
