"""Tests for cc_distribution_parser.services.drift."""

from __future__ import annotations

import pathlib
from datetime import date

from cc_distribution_parser.services.drift import (
    collect_correction_rates,
    render_report,
    write_report,
    write_retry_spike,
)


def test_render_report_includes_alerts_above_threshold():
    body = render_report(
        week_starting=date(2026, 5, 18),
        per_field_correction_rate={"gp_name": 0.40, "fund_name": 0.10},
        prior_week={"gp_name": 0.10, "fund_name": 0.10},
        alert_threshold=0.20,
    )
    assert "Drift report" in body
    assert "ALERTS" in body
    assert "gp_name" in body


def test_render_report_no_alerts_when_below_threshold():
    body = render_report(
        week_starting=date(2026, 5, 18),
        per_field_correction_rate={"x": 0.12},
        prior_week={"x": 0.10},
    )
    assert "ALERTS" not in body


def test_write_report_creates_dated_file(tmp_path: pathlib.Path):
    path = write_report(
        week_starting=date(2026, 5, 18),
        body="# stub\n",
        reports_dir=tmp_path,
    )
    assert path.exists()
    assert path.name == "2026-05-18.md"


def test_write_retry_spike_under_threshold_returns_none(tmp_path: pathlib.Path):
    out = write_retry_spike(fallback_rate=0.02, threshold=0.05, reports_dir=tmp_path)
    assert out is None
    assert list(tmp_path.iterdir()) == []


def test_write_retry_spike_writes_when_over(tmp_path: pathlib.Path):
    out = write_retry_spike(fallback_rate=0.10, threshold=0.05, reports_dir=tmp_path)
    assert out is not None
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "Retry-spike" in body
    assert "0.100" in body


def test_collect_correction_rates_handles_zero_total():
    rates = collect_correction_rates(
        [
            {"field": "x", "total": 10, "corrected": 2},
            {"field": "y", "total": 0, "corrected": 0},
        ]
    )
    assert rates["x"] == 0.2
    assert rates["y"] == 0.0
