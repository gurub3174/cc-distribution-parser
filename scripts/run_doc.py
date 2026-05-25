"""Smoke-test driver for the full pipeline.

Usage:
    uv run python scripts/run_doc.py <pdf-path> [--dump-text] [--mode auto|live|replay|record]

Runs ingest -> parse -> classify -> extract -> validate -> gate on a single
PDF and prints the result. S3 calls are stubbed in-process (no MinIO / no
AWS S3 required) — we only need the parsed text + extraction.

LLM mode passes through to the cassette layer via CCDP_LLM_MODE; --mode
overrides for one invocation. `auto` (default) replays existing cassettes,
records on miss. First-time live runs need AWS Bedrock credentials.

--dump-text writes the parsed plain-text to `<pdf>.txt` next to the PDF so
prompt-tuning can read what the model saw.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import uuid

# Stub S3 BEFORE importing services that touch it. The smoke test doesn't
# need real S3 — we want to validate the LLM + graph end-to-end.
from cc_distribution_parser.services import ingest as ingest_module
from cc_distribution_parser.services import parse as parse_module


def _noop_upload_to_s3(*, bucket: str, key: str, body: bytes, mime_type: str) -> str:
    return f"s3://{bucket}/{key}"


def _noop_upload_parsed_json(*, bucket: str, key: str, body: dict) -> str:
    return f"s3://{bucket}/{key}"


ingest_module.upload_to_s3 = _noop_upload_to_s3  # type: ignore[assignment]
parse_module.upload_parsed_json = _noop_upload_parsed_json  # type: ignore[assignment]


from cc_distribution_parser.observability.logging import configure_logging  # noqa: E402
from cc_distribution_parser.parsing.docling_parser import DoclingParser  # noqa: E402
from cc_distribution_parser.workflow import runner as graph_runner  # noqa: E402
from cc_distribution_parser.workflow.types import DocState  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one PDF through the pipeline")
    p.add_argument("pdf_path", type=pathlib.Path)
    p.add_argument("--dump-text", action="store_true", help="write parsed text to <pdf>.txt")
    p.add_argument(
        "--mode",
        choices=["auto", "live", "replay", "record"],
        default=None,
        help="cassette mode override (default: env CCDP_LLM_MODE or 'auto')",
    )
    p.add_argument("--user-id", default="smoke-test-user")
    p.add_argument(
        "--ocr",
        action="store_true",
        help="force-OCR the PDF (slow; needed for image-only PDFs like the ILPA samples)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    configure_logging(strict=False)

    if not args.pdf_path.exists():
        print(f"error: {args.pdf_path} does not exist", file=sys.stderr)
        return 2

    body = args.pdf_path.read_bytes()
    pipeline_run_id = str(uuid.uuid4())

    state: DocState = {
        "user_id": args.user_id,
        "mime_type": "application/pdf",
        "original_filename": args.pdf_path.name,
        "pipeline_run_id": pipeline_run_id,
        "extraction_payload": {"_file_bytes": body},
    }

    # The cassette layer in workflow.runner respects CCDP_LLM_MODE; if --mode
    # was passed, honor it here. The `live` alias maps to record-on-call.
    if args.mode == "live":
        os.environ["CCDP_LLM_MODE"] = "record"
    elif args.mode is not None:
        os.environ["CCDP_LLM_MODE"] = args.mode

    print(
        f"[1/3] ingest+parse: {args.pdf_path.name}" + (" (OCR)" if args.ocr else ""),
        file=sys.stderr,
    )
    state = ingest_module.run(state)
    state = parse_module.run(state, parser=DoclingParser(force_ocr=args.ocr), file_bytes=body)
    state.get("extraction_payload", {}).pop("_file_bytes", None)

    if args.dump_text:
        text_path = args.pdf_path.with_suffix(args.pdf_path.suffix + ".txt")
        text_path.write_text(state["parsed_doc"]["text"], encoding="utf-8")
        print(f"[parsed text -> {text_path}]", file=sys.stderr)

    print(
        f"[2/3] graph: classify -> extract -> validate -> gate "
        f"(mode={os.environ.get('CCDP_LLM_MODE', 'auto')})",
        file=sys.stderr,
    )
    final = graph_runner.run_pipeline(state)

    print("[3/3] result:", file=sys.stderr)
    report = {
        "doc_id": final.get("doc_id"),
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
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
