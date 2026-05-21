"""Tests for cc_distribution_parser.services.llm_client.

The Bedrock send paths are stubbed via the `instructor_send` /
`tool_use_send` keyword args so no live AWS is touched.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel

from cc_distribution_parser.services import llm_client


class FakeResp(BaseModel):
    reasoning: str
    value: int


def setup_function(_func):
    llm_client.reset_fallback_metrics()


def _instr_ok(**kwargs) -> tuple[BaseModel, dict[str, Any]]:
    return FakeResp(reasoning="ok", value=1), {
        "input_tokens": 10,
        "output_tokens": 5,
        "cached_tokens": 0,
        "cost_usd": "0.001",
    }


def _instr_fail(**kwargs):
    raise llm_client.InstructorRetriesExhausted("budget")


def _tool_ok(**kwargs) -> tuple[BaseModel, dict[str, Any]]:
    return FakeResp(reasoning="ok-fallback", value=2), {
        "input_tokens": 20,
        "output_tokens": 6,
        "cached_tokens": 0,
        "cost_usd": "0.002",
    }


def test_call_uses_instructor_path_by_default():
    parsed, meta = llm_client.call(
        model_id="us.anthropic.claude-sonnet-4-6-20250929-v1:0",
        system="sys",
        user="usr",
        response_model=FakeResp,
        prompt_version="v1",
        prompt_hash="h1",
        instructor_send=_instr_ok,
        tool_use_send=_tool_ok,
    )
    assert isinstance(parsed, FakeResp)
    assert parsed.value == 1  # type: ignore[attr-defined]
    assert meta.used_fallback is False
    assert meta.input_tokens == 10
    assert meta.cost_usd == Decimal("0.001")


def test_call_falls_back_to_tool_use_on_instructor_exhausted():
    parsed, meta = llm_client.call(
        model_id="us.anthropic.claude-sonnet-4-6-20250929-v1:0",
        system="sys",
        user="usr",
        response_model=FakeResp,
        prompt_version="v1",
        prompt_hash="h1",
        instructor_send=_instr_fail,
        tool_use_send=_tool_ok,
    )
    assert isinstance(parsed, FakeResp)
    assert parsed.value == 2  # type: ignore[attr-defined]
    assert meta.used_fallback is True
    assert meta.retry_count == llm_client.MAX_INSTRUCTOR_RETRIES


def test_call_rejects_loose_model_id():
    with pytest.raises(ValueError, match="loose model id"):
        llm_client.call(
            model_id="sonnet",
            system="s",
            user="u",
            response_model=FakeResp,
            prompt_version="v",
            prompt_hash="h",
            instructor_send=_instr_ok,
            tool_use_send=_tool_ok,
        )


def test_fallback_rate_metric_tracked():
    llm_client.call(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        system="s",
        user="u",
        response_model=FakeResp,
        prompt_version="v",
        prompt_hash="h",
        instructor_send=_instr_ok,
        tool_use_send=_tool_ok,
    )
    llm_client.call(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        system="s",
        user="u",
        response_model=FakeResp,
        prompt_version="v",
        prompt_hash="h",
        instructor_send=_instr_fail,
        tool_use_send=_tool_ok,
    )
    assert llm_client.get_fallback_rate() == 0.5
