"""End-to-end pipeline runner.

Builds the LangGraph DAG with everything plugged in:
- Model IDs from Settings (mirrors config/models.yaml pins).
- LLM senders wrapped in cassette layer (replay/record/auto per CCDP_LLM_MODE).
- SQLite-backed commit executors (Phase-1 stand-in for Snowflake).
- LangGraph InMemorySaver as the checkpointer for interrupt()/resume.

Public API: `run_pipeline(state, *, llm_mode=None) -> DocState`.

This is the ONLY non-`workflow/` module allowed to call `build_graph(...)`.
Service code stays framework-free per `.claude/rules/framework-swap.md`
containment invariant #3.
"""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from cc_distribution_parser.config import get_settings
from cc_distribution_parser.observability.logging import bind_pipeline_context, get_logger
from cc_distribution_parser.services import commit_sqlite, llm_cassette
from cc_distribution_parser.services.llm_client import (
    _call_via_instructor,
    _call_via_tool_use,
)
from cc_distribution_parser.workflow.graph import build_graph
from cc_distribution_parser.workflow.types import DocState

log = get_logger(__name__)


def _cassette_senders(mode: str | None) -> dict[str, Any]:
    """Build the (instructor_send, tool_use_send) pair wrapped in cassettes.

    Same wrapped pair is used for classify + extract_cc + extract_distro +
    reclassify — they all share the underlying llm_client.call seam.
    """
    return {
        "instructor_send": llm_cassette.wrap(
            _call_via_instructor,
            path_label="instructor",
            mode=mode,  # type: ignore[arg-type]
        ),
        "tool_use_send": llm_cassette.wrap(
            _call_via_tool_use,
            path_label="tool_use",
            mode=mode,  # type: ignore[arg-type]
        ),
    }


def run_pipeline(
    state: DocState,
    *,
    llm_mode: str | None = None,
    sqlite_path: str | None = None,
) -> DocState:
    """Run the full LangGraph DAG to completion (or to the HITL interrupt).

    The DAG pauses at the `hitl` node whenever `gate_decision == "hitl"` —
    expected behavior while `auto_approve_threshold == 0.0` is locked. The
    returned state still has `extraction_payload` + `validation_report`
    populated, which is what the eval harness measures on.

    `llm_mode` overrides the CCDP_LLM_MODE env var if provided.
    `sqlite_path` overrides Settings.sqlite_path (useful for tests).
    """
    settings = get_settings()
    commit_sqlite.init_db(path=sqlite_path)
    canonical_doc_id = commit_sqlite.ensure_documents_row(dict(state), path=sqlite_path)
    # Dedup may have reconciled doc_id to an existing row's id. Keep state
    # aligned so downstream nodes (commit.assert_document_exists, etc.) use
    # the canonical id.
    if canonical_doc_id != state.get("doc_id"):
        log.info(
            "graph_runner.dedup",
            requested=state.get("doc_id"),
            canonical=canonical_doc_id,
        )
        state["doc_id"] = canonical_doc_id  # type: ignore[typeddict-unknown-key]

    fetch_one, execute = commit_sqlite.make_executors(path=sqlite_path)

    classifier_model = settings.bedrock_classifier_model_id
    extractor_model = settings.bedrock_extractor_model_id

    senders = _cassette_senders(llm_mode)

    graph = build_graph(
        checkpointer=InMemorySaver(),
        classify_kwargs={"model_id": classifier_model, **senders},
        extract_cc_kwargs={"model_id": extractor_model, **senders},
        extract_distro_kwargs={"model_id": extractor_model, **senders},
        reclassify_kwargs={"model_id": extractor_model, **senders},
        commit_kwargs={"fetch_one": fetch_one, "execute": execute},
    )

    thread_id = state.get("doc_id") or f"smoke-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    bind_pipeline_context(
        doc_id=state.get("doc_id", thread_id),
        pipeline_run_id=state.get("pipeline_run_id", thread_id),
    )

    log.info(
        "graph_runner.invoke",
        doc_id=state.get("doc_id"),
        llm_mode=llm_mode or llm_cassette.get_mode(),
    )

    result = graph.invoke(state, config=config)
    # LangGraph 1.x returns the final state dict (or the state at interrupt).
    # Both shapes carry the DocState fields we care about.
    if isinstance(result, dict):
        return result  # type: ignore[return-value]
    return state  # defensive fallback
