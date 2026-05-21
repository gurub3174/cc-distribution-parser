"""Structured extraction provenance.

Stored inside `extractions.provenance_json` (Snowflake VARIANT). The structured
shape lets Phase 1.5 calibration + the HITL UI join `field_provenance.{field}.chunk_id`
against `parsed_doc_chunks` without storing duplicate snippets on the extraction
row. See architecture.md §7.6 (v1.1.5).

`latency_ms` is additive vs §7.6 — paired with `CallMetadata` per
implementation-plan.md §Interface Contracts, so the LLM client can persist
per-call latency on the same provenance object.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

schema_version = "provenance@1.0.0"


class FieldProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page: int = Field(gt=0)
    bbox: tuple[float, float, float, float]
    char_offset_start: int = Field(ge=0)
    char_offset_end: int = Field(ge=0)
    chunk_id: UUID

    @model_validator(mode="after")
    def _offsets_ordered(self) -> FieldProvenance:
        if self.char_offset_end < self.char_offset_start:
            raise ValueError("char_offset_end must be >= char_offset_start")
        return self


class ExtractionProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    few_shot_ids: list[UUID]
    field_provenance: dict[str, FieldProvenance]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_tokens: int = Field(ge=0)
    cost_usd: Decimal = Field(ge=0)
    latency_ms: int = Field(ge=0)
    signals: dict[str, Any]
