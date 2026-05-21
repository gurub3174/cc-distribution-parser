"""Smoke tests for the LangGraph DAG.

We don't run the graph end-to-end (the hitl interrupt makes that messy in
unit tests); we verify (a) the graph compiles, (b) routing functions return
the right node names, (c) langgraph imports stay isolated to workflow/.
"""

from __future__ import annotations

import pathlib

from cc_distribution_parser.workflow.graph import (
    _route_by_class,
    _route_by_gate,
    build_graph,
)


def test_graph_compiles():
    graph = build_graph()
    assert graph is not None


def test_route_by_class():
    assert _route_by_class({"doc_class": "capital_call"}) == "extract_cc"
    assert _route_by_class({"doc_class": "distribution"}) == "extract_distro"
    assert _route_by_class({"doc_class": "other_or_reject"}) == "commit_skip"
    assert _route_by_class({}) == "commit_skip"


def test_route_by_gate():
    assert _route_by_gate({"gate_decision": "auto_commit"}) == "commit"
    assert _route_by_gate({"gate_decision": "reclassify"}) == "reclassify"
    assert _route_by_gate({"gate_decision": "hitl"}) == "hitl"
    assert _route_by_gate({}) == "hitl"


def test_langgraph_imports_isolated_to_workflow_package():
    """Containment invariant #1 from .claude/rules/framework-swap.md.

    Looks for actual import statements (`import langgraph` / `from langgraph`)
    so mentions in comments / docstrings don't trip the check.
    """
    import re

    pattern = re.compile(r"^\s*(?:from\s+langgraph|import\s+langgraph)", re.MULTILINE)
    src_root = pathlib.Path(__file__).parents[2] / "src" / "cc_distribution_parser"
    offenders = []
    for path in src_root.rglob("*.py"):
        rel = path.relative_to(src_root)
        if rel.parts[0] == "workflow":
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(rel))
    assert offenders == [], f"langgraph imports leaked outside workflow/: {offenders}"
