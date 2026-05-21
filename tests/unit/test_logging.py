"""Tests for cc_distribution_parser.observability.logging."""

from __future__ import annotations

import pytest

from cc_distribution_parser.observability.logging import (
    RequiredContextProcessor,
    bind_pipeline_context,
    clear_pipeline_context,
    configure_logging,
)


def setup_function(_func):
    clear_pipeline_context()


def test_processor_passes_when_not_pipeline_bound():
    proc = RequiredContextProcessor(strict=True)
    out = proc(None, "info", {"event": "hello"})
    assert "_missing_context" not in out


def test_processor_passes_when_bound_keys_present():
    proc = RequiredContextProcessor(strict=True)
    out = proc(
        None,
        "info",
        {
            "_pipeline_bound": True,
            "doc_id": "d1",
            "pipeline_run_id": "r1",
            "event": "hello",
        },
    )
    assert "_missing_context" not in out


def test_processor_raises_strict_when_missing():
    proc = RequiredContextProcessor(strict=True)
    with pytest.raises(RuntimeError):
        proc(None, "info", {"_pipeline_bound": True, "event": "hello"})


def test_processor_annotates_non_strict_when_missing():
    proc = RequiredContextProcessor(strict=False)
    out = proc(None, "info", {"_pipeline_bound": True, "event": "hello"})
    assert "_missing_context" in out
    assert set(out["_missing_context"]) == {"doc_id", "pipeline_run_id"}


def test_configure_logging_idempotent_does_not_raise():
    configure_logging()
    configure_logging()  # second call should not crash


def test_bind_and_clear_roundtrip():
    bind_pipeline_context(doc_id="d1", pipeline_run_id="r1")
    clear_pipeline_context()
    # if context were leaking, a subsequent emit would carry doc_id;
    # we just assert no exception was raised.
