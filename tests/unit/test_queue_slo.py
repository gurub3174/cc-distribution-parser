"""Tests for cc_distribution_parser.services.queue_slo."""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime, timedelta

from cc_distribution_parser.services.queue_slo import (
    ALERT_FILE,
    SLO_DAYS,
    find_aged_items,
    write_alert_marker,
)


def test_find_aged_items_picks_only_over_threshold():
    now = datetime(2026, 5, 21, 12, 0, tzinfo=UTC)
    items = [
        {"extraction_id": "fresh", "queued_at": now - timedelta(days=1)},
        {
            "extraction_id": "borderline",
            "queued_at": now - timedelta(days=SLO_DAYS) - timedelta(hours=1),
        },
        {"extraction_id": "old", "queued_at": now - timedelta(days=10)},
    ]
    aged = find_aged_items(items=items, now=now)
    assert set(aged) == {"borderline", "old"}


def test_write_alert_marker_creates_file(tmp_path: pathlib.Path):
    written = write_alert_marker(["e1", "e2"], repo_root=tmp_path)
    assert written is True
    marker = tmp_path / ALERT_FILE
    assert marker.exists()
    body = marker.read_text(encoding="utf-8")
    assert "e1" in body and "e2" in body


def test_write_alert_marker_removes_when_clean(tmp_path: pathlib.Path):
    marker = tmp_path / ALERT_FILE
    marker.write_text("stale", encoding="utf-8")
    written = write_alert_marker([], repo_root=tmp_path)
    assert written is False
    assert not marker.exists()
