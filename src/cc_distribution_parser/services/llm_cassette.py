"""Cassette layer for deterministic LLM-call replay.

Per .claude/rules/testing.md §Golden-eval rule 6: "Replays use recorded
fixtures by default. Live Bedrock calls in CI burn money + are flaky. The
eval harness records Bedrock responses on first run, replays thereafter;
live mode is opt-in via EVAL_LIVE=1."

Modes (env: CCDP_LLM_MODE):
    replay  — read cassette only; raise CassetteMiss if absent.  CI default.
    record  — always call real send + overwrite cassette.        For refresh.
    auto    — read if present, else call real + write.           Local default.

Cassette key:
    sha256(path_label + model_id + system + user + response_model + temperature)

Storage:
    tests/eval/cassettes/<key>.json
    {
      "model_id": ...,
      "response_model": "CapitalCallV1",
      "temperature": "0.0",
      "parsed_dict": { ... pydantic model_dump(mode="json") ... },
      "raw_meta":    { ... usage + cost ... }
    }
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from cc_distribution_parser.observability.logging import get_logger

log = get_logger(__name__)

CassetteMode = Literal["replay", "record", "auto"]

DEFAULT_CASSETTE_DIR = pathlib.Path("tests/eval/cassettes")


class CassetteMiss(Exception):  # noqa: N818 — domain term
    """Raised in replay mode when no cassette exists for the request."""


def get_mode() -> CassetteMode:
    raw = os.environ.get("CCDP_LLM_MODE", "auto").lower()
    if raw not in {"replay", "record", "auto"}:
        log.warning("cassette.invalid_mode", value=raw, defaulting_to="auto")
        return "auto"
    return raw  # type: ignore[return-value]


def _cassette_key(
    *,
    path_label: str,
    model_id: str,
    system: str,
    user: str,
    response_model: type[BaseModel],
    temperature: float,
) -> str:
    h = hashlib.sha256()
    h.update(path_label.encode("utf-8"))
    h.update(b"\x00")
    h.update(model_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    h.update(b"\x00")
    h.update(response_model.__name__.encode("utf-8"))
    h.update(b"\x00")
    h.update(f"{temperature:.4f}".encode())
    return h.hexdigest()


def _load(path: pathlib.Path, response_model: type[BaseModel]) -> tuple[BaseModel, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    parsed = response_model.model_validate(payload["parsed_dict"])
    return parsed, payload["raw_meta"]


def _save(
    path: pathlib.Path,
    *,
    model_id: str,
    response_model: type[BaseModel],
    temperature: float,
    parsed: BaseModel,
    raw_meta: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": model_id,
        "response_model": response_model.__name__,
        "temperature": f"{temperature:.4f}",
        "parsed_dict": parsed.model_dump(mode="json"),
        "raw_meta": raw_meta,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def wrap(
    real_send: Callable[..., tuple[BaseModel, dict[str, Any]]],
    *,
    path_label: str,
    cassette_dir: pathlib.Path | None = None,
    mode: CassetteMode | None = None,
) -> Callable[..., tuple[BaseModel, dict[str, Any]]]:
    """Return a send-callable that consults the cassette before calling real_send.

    `path_label` distinguishes instructor vs tool_use cassettes — same prompt
    on different paths still keys to different files.
    """
    cassette_dir = cassette_dir or DEFAULT_CASSETTE_DIR
    effective_mode: CassetteMode = mode or get_mode()

    def _send(**kwargs: Any) -> tuple[BaseModel, dict[str, Any]]:
        model_id: str = kwargs["model_id"]
        system: str = kwargs["system"]
        user: str = kwargs["user"]
        response_model: type[BaseModel] = kwargs["response_model"]
        temperature: float = float(kwargs.get("temperature", 0.0))

        key = _cassette_key(
            path_label=path_label,
            model_id=model_id,
            system=system,
            user=user,
            response_model=response_model,
            temperature=temperature,
        )
        path = cassette_dir / f"{key}.json"

        if effective_mode == "replay":
            if not path.exists():
                raise CassetteMiss(
                    f"no cassette at {path} for {path_label} call to {model_id} "
                    f"(response_model={response_model.__name__}); "
                    f"set CCDP_LLM_MODE=auto or record to populate"
                )
            log.debug("cassette.replay", key=key, path_label=path_label)
            return _load(path, response_model)

        if effective_mode == "auto" and path.exists():
            log.debug("cassette.replay", key=key, path_label=path_label)
            return _load(path, response_model)

        log.info(
            "cassette.record",
            key=key,
            path_label=path_label,
            model_id=model_id,
            mode=effective_mode,
        )
        parsed, raw_meta = real_send(**kwargs)
        _save(
            path,
            model_id=model_id,
            response_model=response_model,
            temperature=temperature,
            parsed=parsed,
            raw_meta=raw_meta,
        )
        return parsed, raw_meta

    return _send
