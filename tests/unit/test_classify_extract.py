"""Tests for classify + extract services with stubbed LLM client."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from cc_distribution_parser.services import classify as classify_service
from cc_distribution_parser.services import extract as extract_service
from cc_distribution_parser.workflow.types import DocState

SONNET = "us.anthropic.claude-sonnet-4-6-20250929-v1:0"
HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _meta() -> dict[str, Any]:
    return {"input_tokens": 1, "output_tokens": 1, "cached_tokens": 0, "cost_usd": "0.0001"}


def _state_with_parsed(text: str) -> DocState:
    return {
        "doc_id": "d-1",
        "user_id": "u-1",
        "parsed_doc": {"text": text},
    }


def test_classify_persists_versioning_columns():
    def stub_send(*, response_model, **_kw):
        obj = response_model(reasoning="r", label="capital_call", confidence=0.9)
        return obj, _meta()

    state = _state_with_parsed("a capital call notice")
    out = classify_service.run(state, model_id=HAIKU, instructor_send=stub_send)
    assert out["doc_class"] == "capital_call"
    assert out["model_id"] == HAIKU
    assert out["prompt_version"].startswith("classifier@")
    assert out["prompt_hash"]


def test_extract_cc_persists_payload_and_schema_version():
    def stub_send(*, response_model, **_kw):
        obj = response_model(
            reasoning="r",
            gp_name="Acme",
            fund_name="Fund IV",
            investor_name="Alpha",
            notice_date=date(2026, 5, 1),
            due_date=date(2026, 5, 15),
            capital_call_amount=Decimal("100"),
            currency="USD",
            unfunded_before=Decimal("500"),
            unfunded_after=Decimal("400"),
        )
        return obj, _meta()

    state = _state_with_parsed("capital call body")
    out = extract_service.run_cc(state, model_id=SONNET, instructor_send=stub_send)
    assert out["schema_version"] == "capital_call@1.0.0"
    assert out["extraction_payload"]["gp_name"] == "Acme"


def test_extract_distro_persists_payload_and_schema_version():
    def stub_send(*, response_model, **_kw):
        obj = response_model(
            reasoning="r",
            gp_name="Acme",
            fund_name="Fund IV",
            investor_name="Alpha",
            notice_date=date(2026, 5, 1),
            payment_date=date(2026, 5, 15),
            distribution_amount=Decimal("100"),
            currency="USD",
            distribution_type="income",
        )
        return obj, _meta()

    state = _state_with_parsed("distribution body")
    out = extract_service.run_distro(state, model_id=SONNET, instructor_send=stub_send)
    assert out["schema_version"] == "distribution@1.0.0"
    assert out["extraction_payload"]["distribution_type"] == "income"
