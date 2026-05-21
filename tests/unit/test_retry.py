"""Tests for cc_distribution_parser.services.retry."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from cc_distribution_parser.schemas.capital_call import CapitalCallV1
from cc_distribution_parser.services.retry import (
    NonRecoverableError,
    TransientError,
    is_validation_error,
    with_app_retry,
    write_to_dlq,
)


def test_with_app_retry_retries_transient():
    calls = {"n": 0}

    @with_app_retry
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientError("temporary")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 2


def test_with_app_retry_does_not_retry_validation_error():
    calls = {"n": 0}

    @with_app_retry
    def bad_validation() -> CapitalCallV1:
        calls["n"] += 1
        # construct an invalid object to raise ValidationError
        return CapitalCallV1(
            reasoning="x",
            gp_name="x",
            fund_name="x",
            investor_name="x",
            notice_date=date(2026, 1, 1),
            due_date=date(2026, 1, 2),
            capital_call_amount=Decimal("100"),
            currency="USD",
            unfunded_before=Decimal("0"),
            unfunded_after=Decimal("0"),  # invariant violated by construction
        )

    with pytest.raises(ValidationError):
        bad_validation()
    assert calls["n"] == 1  # not retried


def test_with_app_retry_does_not_retry_non_recoverable():
    calls = {"n": 0}

    @with_app_retry
    def fatal() -> None:
        calls["n"] += 1
        raise NonRecoverableError("auth")

    with pytest.raises(NonRecoverableError):
        fatal()
    assert calls["n"] == 1


def test_is_validation_error_predicate():
    try:
        CapitalCallV1(  # type: ignore[call-arg]
            reasoning="x"
        )
    except ValidationError as e:
        assert is_validation_error(e)


def test_write_to_dlq_inserts_row_via_execute():
    captured: dict[str, Any] = {}

    def fake_execute(sql: str, params: tuple) -> None:
        captured["sql"] = sql
        captured["params"] = params

    dlq_id = write_to_dlq(
        doc_id="d-1",
        stage="extract_cc",
        error_class="InstructorRetriesExhausted",
        error_message="boom",
        retry_count=2,
        payload={"x": 1},
        user_id="u-1",
        execute=fake_execute,
    )
    assert isinstance(dlq_id, str) and len(dlq_id) > 10
    assert "INSERT INTO dlq" in captured["sql"]
    assert captured["params"][1] == "d-1"
    assert captured["params"][2] == "extract_cc"


def test_write_to_dlq_bounds_error_message_size():
    captured: dict[str, Any] = {}

    def fake_execute(sql, params):
        captured["params"] = params

    write_to_dlq(
        doc_id="d",
        stage="parse",
        error_class="X",
        error_message="A" * 5000,
        retry_count=0,
        payload=None,
        user_id="u",
        execute=fake_execute,
    )
    assert len(captured["params"][4]) == 2000
