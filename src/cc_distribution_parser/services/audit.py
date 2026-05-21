"""Append-only audit log writer.

Every HITL action (approve, reject, edit, bulk-approve, reclassify, vocab-flag)
and every config change emits an audit row. Reused by commit.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any


def write_audit(
    *,
    actor: str,
    action: str,
    target: str | None,
    metadata: dict[str, Any] | None,
    execute: Any,
) -> str:
    audit_id = str(uuid.uuid4())
    execute(
        "INSERT INTO audit (id, actor, action, target, ts, metadata_json) "
        "VALUES (%s, %s, %s, %s, %s, PARSE_JSON(%s))",
        (
            audit_id,
            actor,
            action,
            target or "",
            datetime.now(UTC),
            json.dumps(metadata or {}),
        ),
    )
    return audit_id
