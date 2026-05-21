"""Per-field x per-template F1 + regression-gate logic.

A blended F1 hides regressions on rare templates per .claude/rules/testing.md.
We compute precision/recall/F1 at the cell level (field x template_id) so the
gate fires when ANY cell regresses, not just the average.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CellMetric:
    field: str
    template_id: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class Metrics:
    by_cell: dict[tuple[str, str], CellMetric] = field(default_factory=dict)

    def add(self, *, field_name: str, template_id: str, tp: int, fp: int, fn: int) -> None:
        key = (field_name, template_id)
        self.by_cell[key] = CellMetric(
            field=field_name, template_id=template_id, tp=tp, fp=fp, fn=fn
        )


def regression_gate(
    *,
    current: Metrics,
    baseline: Metrics,
    n_docs: int,
) -> list[str]:
    """Return list of regression messages. Empty list = gate passes.

    Rule 3/4 in .claude/rules/testing.md: >5pt drop fails initially; >2pt at n>=50.
    """
    threshold = 0.02 if n_docs >= 50 else 0.05
    regressions: list[str] = []
    for key, cur in current.by_cell.items():
        base = baseline.by_cell.get(key)
        if not base:
            continue
        drop = base.f1 - cur.f1
        if drop > threshold:
            field_, tmpl = key
            regressions.append(
                f"{field_} x {tmpl}: f1 {base.f1:.3f} -> {cur.f1:.3f} (drop {drop:.3f})"
            )
    return regressions
