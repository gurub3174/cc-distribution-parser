"""DoclingParser — Phase 1 default parser.

Wraps the Docling library. Per Sprint 0 smoke-test learnings
(memory/project_docling_learnings.md): disable OCR for native PDFs,
use export_to_dict() to surface the layout tree, and respect
max_num_pages safely.

Tests use a pre-recorded Docling export dict to avoid spinning up
docling in unit tests (it's heavy + non-deterministic across versions).
Live parsing is integration-tested against the ILPA templates in
src/cc_distribution_parser/data/test_docs/.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from cc_distribution_parser.schemas.chunk import ChunkRow, LayoutRole
from cc_distribution_parser.schemas.document import ParserMetadata
from cc_distribution_parser.schemas.parsed_doc import ParsedDoc

DOCLING_VERSION = "docling@2.0.0"


class DoclingParser:
    name: str = "docling"
    version: str = DOCLING_VERSION

    def __init__(self, *, force_ocr: bool = False, max_num_pages: int = 200) -> None:
        self._force_ocr = force_ocr
        self._max_num_pages = max_num_pages

    def parse(
        self,
        file_bytes: bytes,
        mime_type: str,
        *,
        doc_id: str,
        user_id: str,
    ) -> tuple[ParsedDoc, list[ChunkRow], ParserMetadata]:
        t0 = time.monotonic()
        export = self._run_docling(file_bytes, mime_type)
        text, chunks, meta = self._build_artifacts(export, doc_id=doc_id, user_id=user_id)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        parser_metadata = ParserMetadata(
            page_count=meta["page_count"],
            language=meta["language"],
            contains_tables=meta["contains_tables"],
            contains_images=meta["contains_images"],
            ocr_used=meta["ocr_used"],
            parse_duration_ms=elapsed_ms,
        )
        parsed_doc = ParsedDoc(
            doc_id=doc_id,
            text=text,
            parser_version=self.version,
            page_count=meta["page_count"],
            language=meta["language"],
            contains_tables=meta["contains_tables"],
            contains_images=meta["contains_images"],
            ocr_used=meta["ocr_used"],
            parse_duration_ms=elapsed_ms,
        )
        return parsed_doc, chunks, parser_metadata

    def _run_docling(self, file_bytes: bytes, mime_type: str) -> dict[str, Any]:
        """Invoke Docling and return its export_to_dict() output.

        Isolated for test seam: unit tests monkeypatch this; integration
        tests exercise the real path.
        """
        # Local import keeps unit tests fast and avoids hard dep at import time.
        from docling.datamodel.base_models import DocumentStream
        from docling.document_converter import DocumentConverter

        if mime_type not in (
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            raise ValueError(f"unsupported mime_type: {mime_type}")

        import io

        stream = DocumentStream(
            name=f"doc-{uuid.uuid4().hex[:8]}",
            stream=io.BytesIO(file_bytes),
        )
        converter = DocumentConverter()
        result = converter.convert(stream)
        return result.document.export_to_dict()

    def _build_artifacts(
        self,
        export: dict[str, Any],
        *,
        doc_id: str,
        user_id: str,
    ) -> tuple[str, list[ChunkRow], dict[str, Any]]:
        """Walk Docling export → flat text + ChunkRow list + meta."""
        pages = export.get("pages", []) or [{}]
        body_items: list[dict[str, Any]] = export.get("texts", []) or []
        text_parts: list[str] = []
        chunks: list[ChunkRow] = []
        cursor = 0
        contains_tables = False
        contains_images = bool(export.get("pictures"))
        language = export.get("language", "en") or "en"

        for read_order, item in enumerate(body_items, start=1):
            item_text = (item.get("text") or "").strip()
            if not item_text:
                continue
            text_parts.append(item_text)
            char_start = cursor
            char_end = cursor + len(item_text)
            cursor = char_end + 1  # +1 for the joining newline
            layout_role = _map_layout_role(item.get("label", "body"))
            if layout_role == "table":
                contains_tables = True
            page = int(item.get("page", 1) or 1)
            bbox = _coerce_bbox(item.get("bbox"))
            chunks.append(
                ChunkRow(
                    id=f"{doc_id}:c{read_order:04d}",
                    doc_id=doc_id,
                    page=max(page, 1),
                    layout_role=layout_role,
                    text=item_text,
                    bbox=bbox,
                    read_order=read_order,
                    parent_chunk_id=None,
                    hierarchy_level=_role_to_level(layout_role),
                    char_offset_start=char_start,
                    char_offset_end=char_end,
                    user_id=user_id,
                )
            )

        text = "\n".join(text_parts)
        meta = {
            "page_count": max(len(pages), 1),
            "language": language,
            "contains_tables": contains_tables,
            "contains_images": contains_images,
            "ocr_used": self._force_ocr,
        }
        return text, chunks, meta


_LABEL_TO_ROLE: dict[str, LayoutRole] = {
    "title": "header",
    "section_header": "header",
    "header": "header",
    "body": "body",
    "paragraph": "body",
    "text": "body",
    "table": "table",
    "footer": "footer",
    "page_footer": "footer",
}


def _map_layout_role(label: str) -> LayoutRole:
    return _LABEL_TO_ROLE.get(label.lower(), "body")


def _role_to_level(role: LayoutRole) -> int:
    return {"header": 1, "body": 3, "table": 3, "footer": 3}[role]


def _coerce_bbox(raw: Any) -> tuple[float, float, float, float]:
    if isinstance(raw, dict):
        return (
            float(raw.get("l", raw.get("x", 0.0))),
            float(raw.get("t", raw.get("y", 0.0))),
            float(raw.get("r", raw.get("w", 0.0))),
            float(raw.get("b", raw.get("h", 0.0))),
        )
    if isinstance(raw, list | tuple) and len(raw) >= 4:
        return tuple(float(v) for v in raw[:4])  # type: ignore[return-value]
    return (0.0, 0.0, 0.0, 0.0)
