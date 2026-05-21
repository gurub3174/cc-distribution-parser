"""Tests for eval harness — golden_set + metrics + runner."""

from __future__ import annotations

import json
import pathlib

from cc_distribution_parser.eval.golden_set import load_golden_set
from cc_distribution_parser.eval.metrics import Metrics, regression_gate
from cc_distribution_parser.eval.runner import run_eval


def test_load_golden_set_empty_when_dir_absent(tmp_path: pathlib.Path):
    assert load_golden_set(tmp_path / "missing") == []


def test_load_golden_set_picks_up_paired_files(tmp_path: pathlib.Path):
    (tmp_path / "alpha.pdf").write_bytes(b"%PDF-fake")
    (tmp_path / "alpha.json").write_text(
        json.dumps(
            {
                "template_id": "ilpa-cc-v1",
                "doc_class": "capital_call",
                "ground_truth": {"gp_name": "Acme"},
            }
        ),
        encoding="utf-8",
    )
    # orphan json without paired doc — ignored
    (tmp_path / "orphan.json").write_text(json.dumps({"template_id": "x"}), encoding="utf-8")
    docs = load_golden_set(tmp_path)
    assert [d.name for d in docs] == ["alpha"]
    assert docs[0].template_id == "ilpa-cc-v1"
    assert docs[0].ground_truth["gp_name"] == "Acme"


def test_metrics_f1_zero_on_empty_cell():
    m = Metrics()
    m.add(field_name="x", template_id="t", tp=0, fp=0, fn=0)
    cell = m.by_cell[("x", "t")]
    assert cell.f1 == 0.0


def test_metrics_f1_known_value():
    m = Metrics()
    m.add(field_name="x", template_id="t", tp=8, fp=2, fn=2)
    cell = m.by_cell[("x", "t")]
    assert abs(cell.precision - 0.8) < 1e-9
    assert abs(cell.recall - 0.8) < 1e-9
    assert abs(cell.f1 - 0.8) < 1e-9


def test_regression_gate_under_threshold_passes_initial():
    base = Metrics()
    cur = Metrics()
    base.add(field_name="x", template_id="t", tp=10, fp=0, fn=0)  # f1 = 1.0
    cur.add(field_name="x", template_id="t", tp=8, fp=2, fn=0)  # f1 ~ 0.89
    out = regression_gate(current=cur, baseline=base, n_docs=20)
    # drop ~0.11 > 0.05 → fail
    assert any("x x t" in msg for msg in out)


def test_regression_gate_above_threshold_fails_mature():
    base = Metrics()
    cur = Metrics()
    base.add(field_name="x", template_id="t", tp=10, fp=0, fn=0)
    cur.add(field_name="x", template_id="t", tp=9, fp=0, fn=1)  # f1=0.947
    # 5.3pt drop; n>=50 threshold = 2pt → fails
    out = regression_gate(current=cur, baseline=base, n_docs=50)
    assert out


def test_run_eval_no_docs_returns_empty_clean(tmp_path: pathlib.Path):
    metrics, docs = run_eval(root=tmp_path)
    assert docs == []
    assert metrics.by_cell == {}


def test_run_eval_with_docs_and_pipeline(tmp_path: pathlib.Path):
    (tmp_path / "alpha.pdf").write_bytes(b"%PDF-fake")
    (tmp_path / "alpha.json").write_text(
        json.dumps(
            {
                "template_id": "t1",
                "doc_class": "capital_call",
                "ground_truth": {"gp_name": "Acme", "fund_name": "Fund"},
            }
        ),
        encoding="utf-8",
    )

    def fake_pipeline(_doc):
        return {"gp_name": "Acme", "fund_name": "Wrong"}

    metrics, docs = run_eval(root=tmp_path, run_pipeline=fake_pipeline)
    assert len(docs) == 1
    cell_gp = metrics.by_cell[("gp_name", "t1")]
    cell_fund = metrics.by_cell[("fund_name", "t1")]
    assert cell_gp.tp == 1
    assert cell_fund.fp == 1
