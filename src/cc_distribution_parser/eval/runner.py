"""Eval harness — pytest entry point.

Marker: `pytest -m eval`. Skips clean (no docs) in CI when the golden corpus
is empty.

LLM mode is controlled by the cassette layer (CCDP_LLM_MODE):
- CI default (no env var, or `=replay`): replays from tests/eval/cassettes/
- `EVAL_LIVE=1` aliases to record-mode for backwards-compat with the
  pre-Sprint-7 contract documented in .claude/rules/testing.md §Golden-eval
  rule 6. Call sites should prefer setting CCDP_LLM_MODE directly going forward.
"""

from __future__ import annotations

import os
import pathlib
import uuid
from typing import Any

from cc_distribution_parser.eval.golden_set import GoldenDoc, load_golden_set
from cc_distribution_parser.eval.metrics import Metrics


def _eval_live() -> bool:
    return os.environ.get("EVAL_LIVE", "0") == "1"


def _default_run_pipeline(doc: GoldenDoc) -> dict[str, Any]:
    """Real-pipeline default: ingest -> parse -> graph -> return extraction.

    Local imports keep `import cc_distribution_parser.eval.runner` cheap.
    Stubs S3 uploads so the harness doesn't require MinIO / live S3.
    """
    from cc_distribution_parser.parsing.docling_parser import DoclingParser
    from cc_distribution_parser.parsing.vlm_parser import VLMParser
    from cc_distribution_parser.services import ingest as ingest_module
    from cc_distribution_parser.services import parse as parse_module
    from cc_distribution_parser.workflow import runner as graph_runner
    from cc_distribution_parser.workflow.types import DocState

    # Pinned VLM model for fallback when docling returns 0 chunks (image-only PDFs).
    # Lives in eval runner — main.py / config.py is the production wiring site.
    VLM_FALLBACK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

    # Stub S3 if it hasn't been stubbed already in this process.
    if not getattr(ingest_module.upload_to_s3, "_eval_stub", False):

        def _noop_upload_to_s3(*, bucket: str, key: str, body: bytes, mime_type: str) -> str:
            return f"s3://{bucket}/{key}"

        _noop_upload_to_s3._eval_stub = True  # type: ignore[attr-defined]
        ingest_module.upload_to_s3 = _noop_upload_to_s3  # type: ignore[assignment]

    if not getattr(parse_module.upload_parsed_json, "_eval_stub", False):

        def _noop_upload_parsed_json(*, bucket: str, key: str, body: dict) -> str:
            return f"s3://{bucket}/{key}"

        _noop_upload_parsed_json._eval_stub = True  # type: ignore[attr-defined]
        parse_module.upload_parsed_json = _noop_upload_parsed_json  # type: ignore[assignment]

    body = doc.file_path.read_bytes()
    mime = (
        "application/pdf"
        if doc.file_path.suffix.lower() == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    state: DocState = {
        "user_id": "eval-harness",
        "mime_type": mime,
        "original_filename": doc.file_path.name,
        "pipeline_run_id": f"eval-{uuid.uuid4().hex[:8]}",
        "extraction_payload": {"_file_bytes": body},
    }
    state = ingest_module.run(state)
    state = parse_module.run(
        state,
        parser=DoclingParser(),
        file_bytes=body,
        fallback_parser=VLMParser(model_id=VLM_FALLBACK_MODEL_ID),
    )
    state.get("extraction_payload", {}).pop("_file_bytes", None)
    final = graph_runner.run_pipeline(state)
    return final.get("extraction_payload") or {}


def run_eval(
    *,
    root: pathlib.Path | None = None,
    run_pipeline: Any | None = None,
) -> tuple[Metrics, list[GoldenDoc]]:
    """Run the eval harness. Returns (metrics, docs).

    `run_pipeline(doc) -> dict[field, value]` defaults to the full pipeline
    runner. Tests inject fakes; CI runs the real graph in replay mode against
    committed cassettes.
    """
    docs = load_golden_set(root)
    metrics = Metrics()
    if not docs:
        return metrics, docs
    if run_pipeline is None:
        # EVAL_LIVE=1 was the pre-Sprint-7 alias for "actually run the
        # pipeline"; preserve the semantic for that flag's history.
        if _eval_live() and "CCDP_LLM_MODE" not in os.environ:
            os.environ["CCDP_LLM_MODE"] = "auto"
        run_pipeline = _default_run_pipeline
    for doc in docs:
        prediction = run_pipeline(doc)
        for field_name, truth in doc.ground_truth.items():
            pred = prediction.get(field_name)
            tp = int(pred == truth and pred is not None and pred != "")
            fp = int(pred not in (None, "", truth))
            fn = int(pred in (None, "") and truth not in (None, ""))
            metrics.add(
                field_name=field_name,
                template_id=doc.template_id,
                tp=tp,
                fp=fp,
                fn=fn,
            )
    return metrics, docs
