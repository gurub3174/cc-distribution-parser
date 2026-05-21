"""parsed_doc_chunks row.

Mirrors the table from snowflake_migrations/001_initial.sql plus the v1.1.5
additions in 005_alter_chunks_add_hierarchy.sql. Sprint 1 populates everything
except `embedding`, `doc_summary_context`, `embedding_input_hash` — those are
backfilled in Sprint 3 when Bedrock Titan v2 integration ships.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

schema_version = "chunk@1.0.0"

LayoutRole = Literal["header", "body", "table", "footer"]


class ChunkRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    doc_id: str
    page: int = Field(gt=0)
    layout_role: LayoutRole
    text: str
    bbox: tuple[float, float, float, float]
    read_order: int = Field(gt=0)
    parent_chunk_id: str | None = None
    hierarchy_level: int = Field(ge=0, le=3)
    char_offset_start: int = Field(ge=0)
    char_offset_end: int = Field(ge=0)
    doc_summary_context: str | None = None
    embedding_input_hash: str | None = None
    embedding: list[float] | None = None
    user_id: str

    @model_validator(mode="after")
    def _offsets_ordered(self) -> ChunkRow:
        if self.char_offset_end < self.char_offset_start:
            raise ValueError("char_offset_end must be >= char_offset_start")
        return self
