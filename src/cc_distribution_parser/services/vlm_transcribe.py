"""VLM-based transcription via Bedrock Converse Document block.

Used as a fallback when DoclingParser returns 0 chunks (image-only PDFs
where docling's layout model classifies every page as a Picture region).

Goes through Bedrock Converse with a document attachment + a strict
"transcribe verbatim, no interpretation" prompt. Wrapped through the
existing cassette layer so eval stays deterministic — the cassette key
folds in a sha256 of the document bytes so different documents land in
different cassettes.

Schema choice: TranscribedText with reasoning prefix per
.claude/rules/structured-output-fallback.md rule 6 (preserves chain of
thought; the reasoning gets discarded but blocks the 10-15% degradation
documented in Tam et al. EMNLP 2024).
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from cc_distribution_parser.observability.logging import get_logger
from cc_distribution_parser.schemas.call_metadata import CallMetadata
from cc_distribution_parser.services.llm_cassette import wrap as cassette_wrap

log = get_logger(__name__)


class TranscribedText(BaseModel):
    reasoning: str = Field(
        description="Briefly note what kind of document this is and any transcription "
        "challenges (handwriting, low-quality scan, multi-column layout)."
    )
    text: str = Field(
        description="Verbatim transcription of all text visible in the document. "
        "Preserve line breaks. Do not interpret or summarize."
    )


_SYSTEM_PROMPT = (
    "You are a document OCR assistant. Your job is to read every word visible in "
    "the attached document and reproduce it verbatim as plain text. Preserve "
    "headings, line breaks, list markers, and table cell separators (use tabs or "
    "pipes for table cells). Do NOT interpret, summarize, fill in placeholders, "
    "or correct apparent typos — copy exactly what is visible. If a region is "
    "illegible, write [ILLEGIBLE]."
)


def _doc_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()[:16]


def _bedrock_send(
    *,
    model_id: str,
    system: str,
    user: str,
    response_model: type[BaseModel],
    temperature: float,
    prompt_cache_keys: list[str],
    max_retries: int,
    file_bytes: bytes,
    bedrock_format: str,
) -> tuple[BaseModel, dict[str, Any]]:
    """Real Bedrock Converse call with a Document block.

    Document API: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
    Sonnet 4.6 reads PDFs natively via the document content block — no
    pdf2image / pytesseract dance required.
    """
    import json as _json

    from pydantic import ValidationError

    from cc_distribution_parser.services.bedrock_pricing import compute_cost
    from cc_distribution_parser.services.llm_client import (
        InstructorRetriesExhausted,
        _bedrock_client,
        _strip_code_fences,
    )

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
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "document": {
                                "name": "doc",
                                "format": bedrock_format,
                                "source": {"bytes": file_bytes},
                            }
                        },
                        {"text": convo_user},
                    ],
                }
            ],
            inferenceConfig={"temperature": float(temperature), "maxTokens": 8192},
        )
        try:
            text_block = response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"unexpected Converse response shape: {response}") from exc
        candidate = _strip_code_fences(text_block)
        try:
            parsed = response_model.model_validate_json(candidate)
        except ValidationError as exc:
            last_error = exc
            convo_user = (
                f"{base_instruction}\n\n"
                f"Previous attempt failed validation:\n{exc}\n"
                f"Return ONLY the corrected JSON object."
            )
            continue

        usage = response.get("usage", {})
        in_tok = int(usage.get("inputTokens", 0))
        out_tok = int(usage.get("outputTokens", 0))
        cached = int(usage.get("cacheReadInputTokens", 0))
        raw_meta = {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cached_tokens": cached,
            "cost_usd": str(compute_cost(model_id, in_tok, out_tok)),
        }
        return parsed, raw_meta

    raise InstructorRetriesExhausted(
        f"vlm_transcribe validation failed after {max_retries + 1} attempts: {last_error}"
    )


_MIME_TO_BEDROCK_FORMAT: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def transcribe(
    *,
    file_bytes: bytes,
    mime_type: str,
    model_id: str,
    temperature: float = 0.0,
    # Test seam: inject a fake (real_send) callable; defaults to the real Bedrock path.
    real_send: Callable[..., tuple[BaseModel, dict[str, Any]]] | None = None,
) -> tuple[str, CallMetadata]:
    """Transcribe a document via Bedrock VLM. Returns (text, CallMetadata).

    Cassette-wrapped so eval replays are deterministic. The document hash
    is folded into the user-prompt prefix so different files key to
    different cassettes.
    """
    if model_id.startswith(("sonnet", "haiku", "claude-")):
        raise ValueError(
            f"loose model id rejected: {model_id!r}. Use the pinned ID from config/models.yaml."
        )
    if mime_type not in _MIME_TO_BEDROCK_FORMAT:
        raise ValueError(f"unsupported mime_type for VLM transcribe: {mime_type}")

    bedrock_format = _MIME_TO_BEDROCK_FORMAT[mime_type]
    doc_hash = _doc_hash(file_bytes)
    user_prompt = (
        f"[doc_sha:{doc_hash}] Transcribe all text visible in the attached document verbatim."
    )

    # The cassette layer hashes (model_id, system, user, response_model, temperature).
    # `user_prompt` carries `[doc_sha:...]` so different documents get different keys.
    def _real(**kwargs: Any) -> tuple[BaseModel, dict[str, Any]]:
        if real_send is not None:
            return real_send(**kwargs, file_bytes=file_bytes, bedrock_format=bedrock_format)
        return _bedrock_send(
            file_bytes=file_bytes,
            bedrock_format=bedrock_format,
            **kwargs,
        )

    cached_send = cassette_wrap(_real, path_label="vlm_transcribe")

    t0 = time.monotonic()
    parsed, raw_meta = cached_send(
        model_id=model_id,
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        response_model=TranscribedText,
        temperature=temperature,
        prompt_cache_keys=[],
        max_retries=2,
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    assert isinstance(parsed, TranscribedText)
    meta = CallMetadata(
        model_id=model_id,
        prompt_hash=doc_hash,
        prompt_version="vlm_transcribe@0.1.0",
        input_tokens=int(raw_meta.get("input_tokens", 0)),
        output_tokens=int(raw_meta.get("output_tokens", 0)),
        cached_tokens=int(raw_meta.get("cached_tokens", 0)),
        cost_usd=Decimal(str(raw_meta.get("cost_usd", "0"))),
        latency_ms=elapsed_ms,
        retry_count=0,
        temperature=temperature,
        used_fallback=False,
    )
    log.info(
        "vlm_transcribe.complete",
        doc_hash=doc_hash,
        text_len=len(parsed.text),
        cost_usd=str(meta.cost_usd),
        input_tokens=meta.input_tokens,
        output_tokens=meta.output_tokens,
    )
    return parsed.text, meta
