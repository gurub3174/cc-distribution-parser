"""ParserProtocol — the contract every parser implementation honors.

Implementations live alongside this file (Phase 1: DoclingParser; Phase 1.5:
BedrockDataAutomationParser, AzureDIParser). The emit shape is the 3-tuple
(ParsedDoc, list[ChunkRow], ParserMetadata) — schemas defined in
cc_distribution_parser.schemas.

`parser_version` is propagated onto the ParsedDoc (so it surfaces as a
first-class column on `extractions.parser_version` per snowflake_migrations/
001_initial.sql + .claude/rules/snowflake-migrations.md rule 4).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cc_distribution_parser.schemas.chunk import ChunkRow
from cc_distribution_parser.schemas.document import ParserMetadata
from cc_distribution_parser.schemas.parsed_doc import ParsedDoc


@runtime_checkable
class ParserProtocol(Protocol):
    name: str
    version: str

    def parse(
        self,
        file_bytes: bytes,
        mime_type: str,
        *,
        doc_id: str,
        user_id: str,
    ) -> tuple[ParsedDoc, list[ChunkRow], ParserMetadata]:
        """Parse a file into ParsedDoc + chunk rows + parser-level metadata.

        Implementations MUST set `parser_version` on the returned ParsedDoc
        equal to `self.version`. Char offsets in chunks MUST be absolute
        within `ParsedDoc.text`.
        """
        ...
