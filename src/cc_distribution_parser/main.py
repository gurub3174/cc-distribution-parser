"""FastAPI entrypoint.

Endpoints:
- GET  /healthz             — liveness probe
- POST /upload              — multipart file upload; runs ingest + parse
                              synchronously, caches state in-process, returns
                              process_url
- POST /process/{doc_id}    — invokes the LangGraph DAG on cached parsed state;
                              returns gate decision + extraction payload.

Phase-1 parsed-state cache is process-local memory. Phase 1.5 replaces with
SQLite-backed state restoration (decouples /upload from /process; survives
restart).
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
from cc_distribution_parser.workflow import runner as graph_runner
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

    # Process-local cache of parsed states between /upload and /process.
    # Phase-1 stand-in — see module docstring.
    parsed_states: dict[str, DocState] = {}
    app.state.parsed_states = parsed_states

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
            doc_id = state["doc_id"]
            # Drop the raw bytes before caching — they were ingest-only.
            state.get("extraction_payload", {}).pop("_file_bytes", None)
            parsed_states[doc_id] = state
            return {
                "doc_id": doc_id,
                "file_hash": state["file_hash"],
                "byte_size": state["byte_size"],
                "page_count": state["parser_metadata"]["page_count"],
                "chunk_count": len(state["chunks"]),
                "status": "parsed",
                "process_url": f"/process/{doc_id}",
            }
        finally:
            clear_pipeline_context()

    @app.post("/process/{doc_id}")
    async def process(doc_id: str) -> dict[str, Any]:
        state = parsed_states.get(doc_id)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail=f"no parsed state for doc_id={doc_id} (was it uploaded in this process?)",
            )
        bind_pipeline_context(doc_id=doc_id, pipeline_run_id=state.get("pipeline_run_id", doc_id))
        try:
            final = graph_runner.run_pipeline(state)
            return {
                "doc_id": doc_id,
                "doc_class": final.get("doc_class"),
                "classification_confidence": final.get("classification_confidence"),
                "extraction_payload": final.get("extraction_payload"),
                "validation_report": final.get("validation_report"),
                "gate_decision": final.get("gate_decision"),
                "model_id": final.get("model_id"),
                "prompt_version": final.get("prompt_version"),
                "cost_usd": final.get("cost_usd"),
                "stage": final.get("stage"),
            }
        finally:
            clear_pipeline_context()

    return app


app = create_app()
