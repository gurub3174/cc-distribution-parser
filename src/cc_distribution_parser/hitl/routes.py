"""HITL FastAPI routes.

Endpoints:
- GET /hitl/queue            — list pending items
- GET /hitl/review/{id}      — review detail
- POST /hitl/approve/{id}    — approve as-is
- POST /hitl/edit/{id}       — submit edited fields
- POST /hitl/reject/{id}     — reject (sends to triage)
- POST /hitl/bulk_approve    — bulk-approve all "validated" items
- POST /hitl/flag_vocab/{id} — append to data/vocab_pending.yaml

The store is injected so unit tests can stub Snowflake.
"""

from __future__ import annotations

import pathlib
from typing import Annotated, Any, Protocol

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse


class HitlStore(Protocol):
    def list_pending(self) -> list[dict[str, Any]]: ...
    def get(self, extraction_id: str) -> dict[str, Any] | None: ...
    def approve(self, extraction_id: str, *, reviewer: str) -> None: ...
    def edit(self, extraction_id: str, *, fields: dict[str, Any], reviewer: str) -> None: ...
    def reject(self, extraction_id: str, *, reviewer: str, reason: str) -> None: ...


def get_store() -> HitlStore:
    raise RuntimeError("HitlStore not injected. Override via app.dependency_overrides.")


def build_router() -> APIRouter:
    router = APIRouter(prefix="/hitl", tags=["hitl"])

    @router.get("/queue", response_class=HTMLResponse)
    def queue(store: Annotated[HitlStore, Depends(get_store)]) -> str:
        items = store.list_pending()
        rows = "\n".join(
            f"<tr><td>{i['extraction_id']}</td>"
            f"<td>{i.get('doc_class', '?')}</td>"
            f"<td>{i.get('queued_at', '?')}</td>"
            f'<td><a href="/hitl/review/{i["extraction_id"]}">review</a></td></tr>'
            for i in items
        )
        return _wrap_html(
            f"<h1>HITL queue ({len(items)})</h1>"
            f"<table><thead><tr><th>id</th><th>class</th>"
            f"<th>queued</th><th></th></tr></thead><tbody>{rows}</tbody></table>"
        )

    @router.get("/review/{extraction_id}", response_class=HTMLResponse)
    def review(extraction_id: str, store: Annotated[HitlStore, Depends(get_store)]) -> str:
        item = store.get(extraction_id)
        if not item:
            raise HTTPException(status_code=404, detail="not found")
        payload = item.get("extraction_payload") or {}
        rep = item.get("validation_report") or {}
        fields_html = "\n".join(
            f'<div class="field"><label>{k}</label>'
            f'<input name="{k}" value="{v}" />'
            f'<span class="state">{rep.get("per_field", {}).get(k, "?")}</span></div>'
            for k, v in payload.items()
        )
        return _wrap_html(
            f"<h1>review {extraction_id}</h1>"
            f'<form hx-post="/hitl/edit/{extraction_id}">'
            f"{fields_html}"
            f'<button type="submit">save</button></form>'
            f'<form hx-post="/hitl/approve/{extraction_id}"><button>approve</button></form>'
        )

    @router.post("/approve/{extraction_id}")
    def approve(
        extraction_id: str,
        store: Annotated[HitlStore, Depends(get_store)],
        reviewer: Annotated[str, Form()] = "system",
    ) -> dict[str, str]:
        store.approve(extraction_id, reviewer=reviewer)
        return {"status": "approved", "extraction_id": extraction_id}

    @router.post("/reject/{extraction_id}")
    def reject(
        extraction_id: str,
        store: Annotated[HitlStore, Depends(get_store)],
        reviewer: Annotated[str, Form()] = "system",
        reason: Annotated[str, Form()] = "",
    ) -> dict[str, str]:
        store.reject(extraction_id, reviewer=reviewer, reason=reason)
        return {"status": "rejected", "extraction_id": extraction_id}

    @router.post("/flag_vocab/{extraction_id}")
    def flag_vocab(
        extraction_id: str,
        term: Annotated[str, Form()],
        variant: Annotated[str, Form()],
        canonical: Annotated[str, Form()] = "",
    ) -> dict[str, str]:
        path = pathlib.Path("data/vocab_pending.yaml")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(
                f"- extraction_id: {extraction_id}\n"
                f"  term: {term!r}\n"
                f"  variant: {variant!r}\n"
                f"  canonical: {canonical!r}\n"
            )
        return {"status": "flagged"}

    return router


_HTMX_CDN = "https://unpkg.com/htmx.org@1.9.10"
_TAILWIND_CDN = "https://cdn.jsdelivr.net/npm/tailwindcss@2.2/dist/tailwind.min.css"


def _wrap_html(body: str) -> str:
    return (
        "<!DOCTYPE html><html><head><title>HITL</title>"
        f'<script src="{_HTMX_CDN}"></script>'
        f'<link href="{_TAILWIND_CDN}" rel="stylesheet">'
        f'</head><body class="p-4">{body}</body></html>'
    )
