"""structlog bound-context contract.

Every log line emitted by this service MUST carry `doc_id` and
`pipeline_run_id` once they are known. The bound-context processor enforces
this — if a log call happens after `bind_pipeline_context` but a required
key is missing, the processor raises in dev (`strict=True`) or annotates
with `_missing_context` in prod.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

REQUIRED_CONTEXT_KEYS = ("doc_id", "pipeline_run_id")


class RequiredContextProcessor:
    """Fails loud (dev) or annotates (prod) when required keys are missing.

    Reason: log-line drift across the pipeline is silent — a missing
    `doc_id` makes a Phoenix trace impossible to join. Catch at emit time.
    """

    def __init__(self, *, strict: bool) -> None:
        self.strict = strict

    def __call__(
        self,
        _logger: Any,
        _name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        if not event_dict.get("_pipeline_bound"):
            return event_dict
        missing = [k for k in REQUIRED_CONTEXT_KEYS if k not in event_dict]
        if missing:
            if self.strict:
                raise RuntimeError(f"bound-context missing required keys: {missing}")
            event_dict["_missing_context"] = missing
        return event_dict


def configure_logging(*, strict: bool = False, level: int = logging.INFO) -> None:
    """Idempotent setup. Call once at process start."""
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            RequiredContextProcessor(strict=strict),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_pipeline_context(*, doc_id: str, pipeline_run_id: str, **extra: Any) -> None:
    """Bind doc_id + pipeline_run_id for the current async/thread context.

    All downstream log calls in this context inherit these. The
    `_pipeline_bound` marker tells RequiredContextProcessor to enforce.
    """
    structlog.contextvars.bind_contextvars(
        doc_id=doc_id,
        pipeline_run_id=pipeline_run_id,
        _pipeline_bound=True,
        **extra,
    )


def clear_pipeline_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
