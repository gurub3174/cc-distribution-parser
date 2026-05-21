"""Tests for cc_distribution_parser.observability.tracing."""

from __future__ import annotations

from unittest.mock import MagicMock

from cc_distribution_parser.observability.tracing import (
    VERSIONING_ATTRS,
    attach_versioning_attrs,
)


def test_versioning_attrs_canonical_set():
    assert set(VERSIONING_ATTRS) == {
        "model_id",
        "prompt_hash",
        "prompt_version",
        "parser_version",
        "schema_version",
        "temperature",
    }


def test_attach_only_canonical_keys():
    span = MagicMock()
    attach_versioning_attrs(
        span,
        model_id="m1",
        prompt_hash="h",
        prompt_version="v",
        parser_version="docling@2",
        schema_version="cc@1",
        temperature=0.0,
        unknown_key="dropped",
    )
    keys_set = {call.args[0] for call in span.set_attribute.call_args_list}
    assert "unknown_key" not in keys_set
    assert "model_id" in keys_set


def test_attach_skips_none_values():
    span = MagicMock()
    attach_versioning_attrs(span, model_id=None, prompt_hash="h")
    keys_set = {call.args[0] for call in span.set_attribute.call_args_list}
    assert "model_id" not in keys_set
    assert "prompt_hash" in keys_set
