"""Marker=eval smoke test.

Runs `pytest -m eval`. Doc-independent build ships zero golden docs; the
harness reports "no docs" and the gate passes vacuously. Once real golden
docs land in data/golden_eval/, this test surfaces them.
"""

from __future__ import annotations

import pathlib

import pytest

from cc_distribution_parser.eval.runner import run_eval


@pytest.mark.eval
def test_golden_eval_harness_runs_clean():
    metrics, docs = run_eval(root=pathlib.Path("data/golden_eval"))
    # Either no docs (doc-independent build) OR every doc produced metrics.
    if docs:
        assert metrics.by_cell, "harness produced no metrics despite finding docs"
    else:
        assert metrics.by_cell == {}
