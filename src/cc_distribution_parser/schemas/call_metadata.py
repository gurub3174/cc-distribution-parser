"""CallMetadata — per-LLM-call accounting.

Returned alongside the parsed response from llm_client.call(). Persisted to
extractions.provenance_json via ExtractionProvenance (shapes overlap; this
struct is the LLM-client-internal one).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

schema_version = "call_metadata@1.0.0"


class CallMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    prompt_hash: str
    prompt_version: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_tokens: int = Field(ge=0)
    cost_usd: Decimal = Field(ge=0)
    latency_ms: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    temperature: float = Field(ge=0.0, le=2.0)
    used_fallback: bool = False
