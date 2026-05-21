"""Parser output schema.

Mirrors what `DoclingParser` (and any other ParserProtocol implementation) emits
on `parse()`. Carries `parser_version` so downstream extractions can persist it
as a first-class column on `extractions` (see snowflake_migrations/001_initial.sql
and .claude/rules/snowflake-migrations.md rule 4).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

schema_version = "parsed_doc@1.0.0"


class ParsedDoc(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str
    text: str
    parser_version: str
    page_count: int = Field(gt=0)
    language: str
    contains_tables: bool
    contains_images: bool
    ocr_used: bool
    parse_duration_ms: int = Field(ge=0)
