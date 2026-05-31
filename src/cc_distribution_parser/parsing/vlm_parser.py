"""VLMParser — fallback parser for image-only PDFs.

Wired in services/parse.py as a fallback when the primary parser
(DoclingParser) returns 0 chunks. Delegates to services/vlm_transcribe,
which calls Bedrock Sonnet with the PDF as a Document attachment.

Emits a single-chunk ParsedDoc: the whole transcribed text becomes one
body chunk. Downstream classify/extract treat it as ordinary parsed text.
This is intentional — VLMs don't reliably emit per-region bboxes, so we
don't try to fake them. If/when GraniteDocling local layout-aware
inference becomes worth the latency cost, the chunk granularity can grow
here without changing the contract.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from cc_distribution_parser.schemas.chunk import ChunkRow
from cc_distribution_parser.schemas.document import ParserMetadata
from cc_distribution_parser.schemas.parsed_doc import ParsedDoc
from cc_distribution_parser.services import vlm_transcribe

VLM_PARSER_VERSION = "vlm-bedrock@0.1.0"


class VLMParser:
    name: str = "vlm-bedrock"
    version: str = VLM_PARSER_VERSION

    def __init__(
        self,
        *,
        model_id: str,
        # Test seam: inject a fake transcribe so unit tests don't touch boto3.
        transcribe_fn: Callable[..., tuple[str, Any]] | None = None,
        real_send: Callable[..., tuple[BaseModel, dict[str, Any]]] | None = None,
    ) -> None:
        self._model_id = model_id
        self._transcribe = transcribe_fn or vlm_transcribe.transcribe
        self._real_send = real_send

    def parse(
        self,
        file_bytes: bytes,
        mime_type: str,
        *,
        doc_id: str,
        user_id: str,
    ) -> tuple[ParsedDoc, list[ChunkRow], ParserMetadata]:
        t0 = time.monotonic()
        kwargs: dict[str, Any] = {
            "file_bytes": file_bytes,
            "mime_type": mime_type,
            "model_id": self._model_id,
        }
        if self._real_send is not None:
            kwargs["real_send"] = self._real_send
        text, _meta = self._transcribe(**kwargs)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        text = text.strip()
        parser_metadata = ParserMetadata(
            page_count=1,  # VLM transcription doesn't preserve page boundaries
            language="en",
            contains_tables=False,
            contains_images=True,  # by definition — this only runs on image-only PDFs
            ocr_used=True,
            parse_duration_ms=elapsed_ms,
        )
        parsed_doc = ParsedDoc(
            doc_id=doc_id,
            text=text,
            parser_version=self.version,
            page_count=1,
            language="en",
            contains_tables=False,
            contains_images=True,
            ocr_used=True,
            parse_duration_ms=elapsed_ms,
        )
        chunks: list[ChunkRow] = []
        if text:
            chunks.append(
                ChunkRow(
                    id=f"{doc_id}:vlm0001",
                    doc_id=doc_id,
                    page=1,
                    layout_role="body",
                    text=text,
                    bbox=(0.0, 0.0, 0.0, 0.0),
                    read_order=1,
                    parent_chunk_id=None,
                    hierarchy_level=3,
                    char_offset_start=0,
                    char_offset_end=len(text),
                    user_id=user_id,
                )
            )
        return parsed_doc, chunks, parser_metadata
