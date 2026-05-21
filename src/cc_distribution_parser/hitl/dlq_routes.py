"""DLQ triage UI - list + replay/archive."""

from __future__ import annotations

from typing import Annotated, Any, Protocol

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse


class DlqStore(Protocol):
    def list_oldest_first(self) -> list[dict[str, Any]]: ...
    def replay(self, dlq_id: str) -> None: ...
    def archive(self, dlq_id: str) -> None: ...


def get_dlq_store() -> DlqStore:
    raise RuntimeError("DlqStore not injected.")


def build_router() -> APIRouter:
    router = APIRouter(prefix="/dlq", tags=["dlq"])

    @router.get("/", response_class=HTMLResponse)
    def list_(store: Annotated[DlqStore, Depends(get_dlq_store)]) -> str:
        items = store.list_oldest_first()
        rows = "\n".join(
            f"<tr><td>{i['id']}</td><td>{i.get('stage', '?')}</td>"
            f"<td>{i.get('error_class', '?')}</td>"
            f"<td>{i.get('retry_count', 0)}</td>"
            f'<td><form hx-post="/dlq/replay/{i["id"]}"><button>replay</button></form></td>'
            f'<td><form hx-post="/dlq/archive/{i["id"]}"><button>archive</button></form></td>'
            f"</tr>"
            for i in items
        )
        return (
            f"<h1>DLQ ({len(items)})</h1>"
            f"<table><thead><tr><th>id</th><th>stage</th><th>error</th>"
            f"<th>retries</th><th></th><th></th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    @router.post("/replay/{dlq_id}")
    def replay(dlq_id: str, store: Annotated[DlqStore, Depends(get_dlq_store)]) -> dict[str, str]:
        try:
            store.replay(dlq_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return {"status": "replayed", "id": dlq_id}

    @router.post("/archive/{dlq_id}")
    def archive(dlq_id: str, store: Annotated[DlqStore, Depends(get_dlq_store)]) -> dict[str, str]:
        store.archive(dlq_id)
        return {"status": "archived", "id": dlq_id}

    return router
