"""HITL queue SLO checker.

Per architecture.md §15.5 ritual: any HITL item > 3 days old triggers an
SLO violation. Writes a `.hitl-queue-alert` marker file that shows up in
`git status` — visible-by-default forcing function (Critic C4).
"""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime, timedelta
from typing import Any

ALERT_FILE = ".hitl-queue-alert"
SLO_DAYS = 3


def find_aged_items(*, items: list[dict[str, Any]], now: datetime | None = None) -> list[str]:
    """Return extraction_ids older than SLO_DAYS.

    `items` is a list of {extraction_id, queued_at: datetime}.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=SLO_DAYS)
    aged = []
    for it in items:
        qa = it["queued_at"]
        if not isinstance(qa, datetime):
            continue
        if qa.tzinfo is None:
            qa = qa.replace(tzinfo=UTC)
        if qa < cutoff:
            aged.append(it["extraction_id"])
    return aged


def write_alert_marker(aged_ids: list[str], *, repo_root: pathlib.Path | None = None) -> bool:
    """Write the alert marker if aged_ids is non-empty; remove it otherwise.

    Returns True if a marker was written (SLO violated).
    """
    repo_root = repo_root or pathlib.Path.cwd()
    marker = repo_root / ALERT_FILE
    if aged_ids:
        marker.write_text(
            f"# HITL queue SLO violated at {datetime.now(UTC).isoformat()}\n"
            f"# {len(aged_ids)} item(s) > {SLO_DAYS} days:\n"
            + "\n".join(f"- {i}" for i in aged_ids)
            + "\n",
            encoding="utf-8",
        )
        return True
    if marker.exists():
        marker.unlink()
    return False
