"""LangGraph DAG.

THE ONLY module allowed to import langgraph.* per
.claude/rules/framework-swap.md containment invariant #1.

Nodes (per architecture.md §8):
  parse -> classify -> route -> extract_cc/extract_distro/skip -> validate
  -> gate -> {auto_commit | hitl-interrupt | reclassify | commit-skip}

The hitl branch uses LangGraph's `interrupt()` to pause; SqliteSaver
persists state until a reviewer resumes via the FastAPI HITL routes.

For doc-independent CI, the graph builds and can be smoke-tested with
stub LLM senders. Live execution against Bedrock is `-m integration`.
"""

from __future__ import annotations

from typing import Any

# LangGraph 1.x imports — pinned per pyproject.toml lessons-learned 2026-05-03.
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from cc_distribution_parser.services import classify as classify_service
from cc_distribution_parser.services import commit as commit_service
from cc_distribution_parser.services import extract as extract_service
from cc_distribution_parser.services import gate as gate_service
from cc_distribution_parser.services import reclassify as reclassify_service
from cc_distribution_parser.services import validate as validate_service
from cc_distribution_parser.workflow.types import DocState


def _route_by_class(state: DocState) -> str:
    cls = state.get("doc_class")
    if cls == "capital_call":
        return "extract_cc"
    if cls == "distribution":
        return "extract_distro"
    return "commit_skip"


def _route_by_gate(state: DocState) -> str:
    decision = state.get("gate_decision")
    if decision == "auto_commit":
        return "commit"
    if decision == "reclassify":
        return "reclassify"
    return "hitl"  # default: human review


def _hitl_node(state: DocState) -> Command:
    """Pause for HITL review.

    The interrupt payload is what the FastAPI HITL UI receives. Resume value
    (a dict of approved/edited fields) is merged back into state by the
    routes layer in services/hitl.
    """
    payload = {
        "doc_id": state.get("doc_id"),
        "doc_class": state.get("doc_class"),
        "extraction_payload": state.get("extraction_payload"),
        "validation_report": state.get("validation_report"),
        "provenance": state.get("provenance"),
    }
    decision = interrupt(payload)  # blocks until UI resumes
    if isinstance(decision, dict):
        for k, v in decision.items():
            state[k] = v  # type: ignore[literal-required]
    return Command(goto="commit")


def _skip_node(state: DocState) -> DocState:
    """No-extract path for other_or_reject. Still emits an audit row at commit."""
    state["stage"] = "commit"
    return state


def build_graph(
    *,
    checkpointer: Any | None = None,
    extract_cc_kwargs: dict[str, Any] | None = None,
    extract_distro_kwargs: dict[str, Any] | None = None,
    classify_kwargs: dict[str, Any] | None = None,
    reclassify_kwargs: dict[str, Any] | None = None,
    commit_kwargs: dict[str, Any] | None = None,
) -> Any:
    """Compile and return the StateGraph.

    Kwargs let tests inject stub send functions / fake Snowflake executors.
    """
    extract_cc_kwargs = extract_cc_kwargs or {}
    extract_distro_kwargs = extract_distro_kwargs or {}
    classify_kwargs = classify_kwargs or {}
    reclassify_kwargs = reclassify_kwargs or {}
    commit_kwargs = commit_kwargs or {}

    def _classify(state: DocState) -> DocState:
        return classify_service.run(state, **classify_kwargs)

    def _cc(state: DocState) -> DocState:
        return extract_service.run_cc(state, **extract_cc_kwargs)

    def _distro(state: DocState) -> DocState:
        return extract_service.run_distro(state, **extract_distro_kwargs)

    def _reclassify(state: DocState) -> DocState:
        return reclassify_service.run(state, **reclassify_kwargs)

    def _commit(state: DocState) -> DocState:
        return commit_service.run(state, **commit_kwargs)

    g: StateGraph = StateGraph(DocState)
    g.add_node("classify", _classify)
    g.add_node("extract_cc", _cc)
    g.add_node("extract_distro", _distro)
    g.add_node("validate", validate_service.run)
    g.add_node("gate", gate_service.run)
    g.add_node("reclassify", _reclassify)
    g.add_node("hitl", _hitl_node)
    g.add_node("commit", _commit)
    g.add_node("commit_skip", _skip_node)

    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify",
        _route_by_class,
        {
            "extract_cc": "extract_cc",
            "extract_distro": "extract_distro",
            "commit_skip": "commit_skip",
        },
    )
    g.add_edge("extract_cc", "validate")
    g.add_edge("extract_distro", "validate")
    g.add_edge("validate", "gate")
    g.add_conditional_edges(
        "gate",
        _route_by_gate,
        {"commit": "commit", "reclassify": "reclassify", "hitl": "hitl"},
    )
    g.add_edge("reclassify", "validate")  # re-validate after escalation
    g.add_edge("commit", END)
    g.add_edge("commit_skip", "commit")

    return g.compile(checkpointer=checkpointer)
