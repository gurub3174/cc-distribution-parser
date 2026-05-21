"""FastAPI entrypoint.

Endpoints:
- GET  /healthz       — liveness probe
- POST /upload        — multipart file upload; runs ingest + parse synchronously
                        for MVP (background worker comes Sprint 5+)

The async story for Phase 1 is simple: the request blocks until parse
completes. Acceptable because Docling on a 5-page PDF is <2s. Move to
worker queue when median parse time exceeds 10s.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from cc_distribution_parser.config import get_settings
from cc_distribution_parser.observability.logging import (
    bind_pipeline_context,
    clear_pipeline_context,
    configure_logging,
    get_logger,
)
from cc_distribution_parser.observability.tracing import configure_tracing
from cc_distribution_parser.parsing.docling_parser import DoclingParser
from cc_distribution_parser.services import ingest as ingest_service
from cc_distribution_parser.services import parse as parse_service
from cc_distribution_parser.workflow.types import DocState

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(strict=False)
    settings = get_settings()
    try:
        configure_tracing(service_name=settings.service_name, otlp_endpoint=settings.otlp_endpoint)
    except Exception as exc:  # OTel not reachable in some dev setups
        log.warning("tracing.disabled", reason=str(exc))
    yield


def create_app(*, parser: Any | None = None) -> FastAPI:
    app = FastAPI(title="cc-distribution-parser", version="0.1.0", lifespan=lifespan)
    parser_instance = parser or DoclingParser()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/upload")
    async def upload(
        file: Annotated[UploadFile, File(...)],
        user_id: Annotated[str, Form(...)],
    ) -> dict[str, Any]:
        if file.content_type not in (
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            raise HTTPException(status_code=415, detail=f"unsupported mime: {file.content_type}")
        body = await file.read()
        if not body:
            raise HTTPException(status_code=400, detail="empty file")

        import uuid

        pipeline_run_id = str(uuid.uuid4())
        bind_pipeline_context(doc_id="pending", pipeline_run_id=pipeline_run_id)
        try:
            state: DocState = {
                "user_id": user_id,
                "mime_type": file.content_type,
                "original_filename": file.filename or "unnamed",
                "pipeline_run_id": pipeline_run_id,
                "extraction_payload": {"_file_bytes": body},
            }
            state = ingest_service.run(state)
            state = parse_service.run(state, parser=parser_instance, file_bytes=body)
            return {
                "doc_id": state["doc_id"],
                "file_hash": state["file_hash"],
                "byte_size": state["byte_size"],
                "page_count": state["parser_metadata"]["page_count"],
                "chunk_count": len(state["chunks"]),
                "status": "parsed",
            }
        finally:
            clear_pipeline_context()

    return app


app = create_app()
