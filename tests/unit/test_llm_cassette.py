"""Unit tests for the cassette layer."""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import BaseModel

from cc_distribution_parser.services.llm_cassette import (
    CassetteMiss,
    _cassette_key,
    get_mode,
    wrap,
)


class _Echo(BaseModel):
    value: str


def _real_send_factory(call_log: list[dict]):
    def _send(**kwargs):
        call_log.append(kwargs)
        return _Echo(value="from-live"), {
            "input_tokens": 10,
            "output_tokens": 20,
            "cached_tokens": 0,
            "cost_usd": "0.001",
        }

    return _send


def _kwargs(user: str = "u1") -> dict:
    return {
        "model_id": "us.anthropic.claude-sonnet-4-6-20250929-v1:0",
        "system": "sys",
        "user": user,
        "response_model": _Echo,
        "temperature": 0.0,
        "prompt_cache_keys": [],
    }


def test_auto_mode_records_then_replays(tmp_path: pathlib.Path) -> None:
    log: list[dict] = []
    real = _real_send_factory(log)
    sender = wrap(real, path_label="instructor", cassette_dir=tmp_path, mode="auto")

    parsed1, meta1 = sender(**_kwargs())
    assert parsed1.value == "from-live"
    assert len(log) == 1
    assert any(p.suffix == ".json" for p in tmp_path.iterdir())

    parsed2, meta2 = sender(**_kwargs())
    assert parsed2.value == "from-live"
    assert len(log) == 1, "second auto-mode call must hit cassette, not real"
    assert meta1 == meta2


def test_replay_mode_misses_raise(tmp_path: pathlib.Path) -> None:
    log: list[dict] = []
    real = _real_send_factory(log)
    sender = wrap(real, path_label="instructor", cassette_dir=tmp_path, mode="replay")
    with pytest.raises(CassetteMiss):
        sender(**_kwargs())
    assert log == [], "replay must NOT fall through to real send"


def test_record_mode_overwrites(tmp_path: pathlib.Path) -> None:
    log: list[dict] = []
    real = _real_send_factory(log)
    auto = wrap(real, path_label="instructor", cassette_dir=tmp_path, mode="auto")
    auto(**_kwargs())
    assert len(log) == 1
    record = wrap(real, path_label="instructor", cassette_dir=tmp_path, mode="record")
    record(**_kwargs())
    assert len(log) == 2, "record mode must always call real, not replay"


def test_key_distinguishes_path_label(tmp_path: pathlib.Path) -> None:
    log: list[dict] = []
    real = _real_send_factory(log)
    instructor = wrap(real, path_label="instructor", cassette_dir=tmp_path, mode="auto")
    tool_use = wrap(real, path_label="tool_use", cassette_dir=tmp_path, mode="auto")
    instructor(**_kwargs())
    tool_use(**_kwargs())
    assert len(log) == 2, "instructor vs tool_use must key to different cassettes"


def test_key_distinguishes_temperature() -> None:
    a = _cassette_key(
        path_label="instructor",
        model_id="m",
        system="s",
        user="u",
        response_model=_Echo,
        temperature=0.0,
    )
    b = _cassette_key(
        path_label="instructor",
        model_id="m",
        system="s",
        user="u",
        response_model=_Echo,
        temperature=0.5,
    )
    assert a != b


def test_cassette_payload_round_trips_pydantic(tmp_path: pathlib.Path) -> None:
    log: list[dict] = []
    real = _real_send_factory(log)
    sender = wrap(real, path_label="instructor", cassette_dir=tmp_path, mode="auto")
    sender(**_kwargs())
    cassette_path = next(tmp_path.iterdir())
    payload = json.loads(cassette_path.read_text(encoding="utf-8"))
    assert payload["parsed_dict"] == {"value": "from-live"}
    assert payload["response_model"] == "_Echo"
    assert payload["model_id"].startswith("us.anthropic")


def test_get_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CCDP_LLM_MODE", "replay")
    assert get_mode() == "replay"
    monkeypatch.setenv("CCDP_LLM_MODE", "WeIrD")
    assert get_mode() == "auto"  # falls back on invalid value
    monkeypatch.delenv("CCDP_LLM_MODE", raising=False)
    assert get_mode() == "auto"
