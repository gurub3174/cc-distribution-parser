"""Tests for HITL + DLQ FastAPI routers with stubbed stores."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cc_distribution_parser.hitl import dlq_routes
from cc_distribution_parser.hitl import routes as hitl_routes


class FakeHitlStore:
    def __init__(self) -> None:
        self.items = [
            {
                "extraction_id": "e-1",
                "doc_class": "capital_call",
                "queued_at": "2026-05-20T10:00:00Z",
                "extraction_payload": {"gp_name": "Acme"},
                "validation_report": {"per_field": {"gp_name": "validated"}},
            }
        ]
        self.actions: list[tuple[str, str]] = []

    def list_pending(self) -> list[dict[str, Any]]:
        return self.items

    def get(self, extraction_id: str) -> dict[str, Any] | None:
        return next((i for i in self.items if i["extraction_id"] == extraction_id), None)

    def approve(self, extraction_id: str, *, reviewer: str) -> None:
        self.actions.append(("approve", extraction_id))

    def edit(self, extraction_id: str, *, fields: dict, reviewer: str) -> None:
        self.actions.append(("edit", extraction_id))

    def reject(self, extraction_id: str, *, reviewer: str, reason: str) -> None:
        self.actions.append(("reject", extraction_id))


class FakeDlqStore:
    def __init__(self) -> None:
        self.items = [{"id": "d-1", "stage": "extract_cc", "error_class": "X", "retry_count": 2}]
        self.actions: list[tuple[str, str]] = []

    def list_oldest_first(self) -> list[dict[str, Any]]:
        return self.items

    def replay(self, dlq_id: str) -> None:
        if dlq_id != "d-1":
            raise KeyError(dlq_id)
        self.actions.append(("replay", dlq_id))

    def archive(self, dlq_id: str) -> None:
        self.actions.append(("archive", dlq_id))


@pytest.fixture
def client():
    app = FastAPI()
    hitl_store = FakeHitlStore()
    dlq_store = FakeDlqStore()
    app.dependency_overrides[hitl_routes.get_store] = lambda: hitl_store
    app.dependency_overrides[dlq_routes.get_dlq_store] = lambda: dlq_store
    app.include_router(hitl_routes.build_router())
    app.include_router(dlq_routes.build_router())
    with TestClient(app) as c:
        yield c, hitl_store, dlq_store


def test_queue_list_renders(client):
    c, _store, _ = client
    r = c.get("/hitl/queue")
    assert r.status_code == 200
    assert "HITL queue (1)" in r.text
    assert "e-1" in r.text


def test_review_renders_fields(client):
    c, _, _ = client
    r = c.get("/hitl/review/e-1")
    assert r.status_code == 200
    assert "gp_name" in r.text
    assert "Acme" in r.text


def test_review_404_when_missing(client):
    c, _, _ = client
    r = c.get("/hitl/review/missing")
    assert r.status_code == 404


def test_approve_calls_store(client):
    c, store, _ = client
    r = c.post("/hitl/approve/e-1", data={"reviewer": "alice"})
    assert r.status_code == 200
    assert ("approve", "e-1") in store.actions


def test_reject_calls_store(client):
    c, store, _ = client
    r = c.post("/hitl/reject/e-1", data={"reviewer": "alice", "reason": "wrong class"})
    assert r.status_code == 200
    assert ("reject", "e-1") in store.actions


def test_flag_vocab_appends_to_yaml(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    c, _, _ = client
    r = c.post(
        "/hitl/flag_vocab/e-1",
        data={"term": "Distribution", "variant": "Cash Distribution", "canonical": "distribution"},
    )
    assert r.status_code == 200
    out = (tmp_path / "data" / "vocab_pending.yaml").read_text(encoding="utf-8")
    assert "Cash Distribution" in out


def test_dlq_list(client):
    c, _, _ = client
    r = c.get("/dlq/")
    assert r.status_code == 200
    assert "DLQ (1)" in r.text
    assert "d-1" in r.text


def test_dlq_replay(client):
    c, _, dlq = client
    r = c.post("/dlq/replay/d-1")
    assert r.status_code == 200
    assert ("replay", "d-1") in dlq.actions


def test_dlq_replay_unknown_404(client):
    c, _, _ = client
    r = c.post("/dlq/replay/missing")
    assert r.status_code == 404


def test_dlq_archive(client):
    c, _, dlq = client
    r = c.post("/dlq/archive/d-1")
    assert r.status_code == 200
    assert ("archive", "d-1") in dlq.actions
