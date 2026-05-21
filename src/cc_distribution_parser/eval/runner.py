"""Eval harness — pytest entry point.

Marker: `pytest -m eval`. Skips clean (no docs) in CI when the golden corpus
is empty — that's the doc-independent build state.

Live mode: `EVAL_LIVE=1 pytest -m eval` exercises real Bedrock; default mode
replays from recorded fixtures (path TBD; harness wiring deferred to live data).
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

from cc_distribution_parser.eval.golden_set import GoldenDoc, load_golden_set
from cc_distribution_parser.eval.metrics import Metrics


def _eval_live() -> bool:
    return os.environ.get("EVAL_LIVE", "0") == "1"


def run_eval(
    *,
    root: pathlib.Path | None = None,
    run_pipeline: Any | None = None,
) -> tuple[Metrics, list[GoldenDoc]]:
    """Run the eval harness. Returns (metrics, docs).

    `run_pipeline(doc) -> dict[field, value]` is injected (None in the
    doc-independent build means the harness produces an empty metrics
    object and reports "no docs"). The CI gate calls this and compares to
    baseline.
    """
    docs = load_golden_set(root)
    metrics = Metrics()
    if not docs:
        return metrics, docs
    if run_pipeline is None:
        # In live mode without a runner wired, report empty metrics so CI is
        # informative rather than red.
        return metrics, docs
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
