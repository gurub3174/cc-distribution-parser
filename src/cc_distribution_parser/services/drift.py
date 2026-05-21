"""Weekly drift report writer.

Per architecture.md §15.5: scheduled GH Action writes drift-reports/<week>.md.
> 20% WoW correction-rate increase = alert section.
"""

from __future__ import annotations

import pathlib
from datetime import UTC, date, datetime
from typing import Any


def render_report(
    *,
    week_starting: date,
    per_field_correction_rate: dict[str, float],
    prior_week: dict[str, float] | None,
    alert_threshold: float = 0.20,
) -> str:
    lines = [
        f"# Drift report - week of {week_starting.isoformat()}",
        f"_Generated {datetime.now(UTC).isoformat()}_",
        "",
        "## Per-field correction rates",
        "",
        "| Field | Current | Prior | Delta |",
        "|---|---|---|---|",
    ]
    alerts: list[str] = []
    for fld, current in sorted(per_field_correction_rate.items()):
        prior = (prior_week or {}).get(fld)
        prior_s = f"{prior:.3f}" if prior is not None else "-"
        delta = (current - prior) if prior is not None else None
        delta_s = f"{delta:+.3f}" if delta is not None else "-"
        lines.append(f"| {fld} | {current:.3f} | {prior_s} | {delta_s} |")
        if delta is not None and delta > alert_threshold:
            alerts.append(f"- {fld}: +{delta:.3f} vs prior week")

    if alerts:
        lines.append("")
        lines.append("## ALERTS")
        lines.extend(alerts)
    return "\n".join(lines) + "\n"


def write_report(
    *,
    week_starting: date,
    body: str,
    reports_dir: pathlib.Path | None = None,
) -> pathlib.Path:
    reports_dir = reports_dir or pathlib.Path("drift-reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{week_starting.isoformat()}.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_retry_spike(
    *,
    fallback_rate: float,
    threshold: float = 0.05,
    reports_dir: pathlib.Path | None = None,
) -> pathlib.Path | None:
    """If fallback rate exceeds threshold, write a retry-spike report.

    Returns the path written, or None if the rate is below threshold.
    """
    if fallback_rate < threshold:
        return None
    reports_dir = reports_dir or pathlib.Path("drift-reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = reports_dir / f"retry-spike-{ts}.md"
    path.write_text(
        f"# Retry-spike alert {ts}\n\n"
        f"Instructor fallback rate: {fallback_rate:.3f} "
        f"(threshold: {threshold:.3f})\n\n"
        f"Investigate per .claude/rules/structured-output-fallback.md.\n",
        encoding="utf-8",
    )
    return path


def collect_correction_rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate from a list of {field, total, corrected} rows to per-field rate."""
    out: dict[str, float] = {}
    for row in rows:
        total = int(row.get("total", 0) or 0)
        corrected = int(row.get("corrected", 0) or 0)
        out[str(row["field"])] = corrected / total if total else 0.0
    return out
