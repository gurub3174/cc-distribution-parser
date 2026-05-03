"""initial — langgraph_checkpoints + hitl_queue_locks

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-03

Bootstrap SQLite ops state. Holds two tables:

- langgraph_checkpoints: checkpoint state for LangGraph SqliteSaver. Schema is
  managed by langgraph itself at runtime (langgraph.checkpoint.sqlite creates
  its own tables on first use); we declare it here only so a fresh deploy has
  the file with correct schema before LangGraph touches it.
- hitl_queue_locks: advisory locks on in-flight HITL reviews. Prevents two
  reviewers grabbing the same item.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # hitl_queue_locks: app-managed advisory locks.
    op.create_table(
        "hitl_queue_locks",
        sa.Column("extraction_id", sa.String(), primary_key=True),
        sa.Column("locked_by_user_id", sa.String(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_hitl_locks_expires_at",
        "hitl_queue_locks",
        ["expires_at"],
    )

    # _langgraph_bootstrap_marker: leading underscore signals "infrastructure, not data".
    # LangGraph's SqliteSaver auto-creates its own schema on first use; this marker only
    # ensures a fresh deploy has the database file present before LangGraph touches it.
    op.execute(
        "CREATE TABLE IF NOT EXISTS _langgraph_bootstrap_marker ("
        "id INTEGER PRIMARY KEY, note TEXT"
        ")"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS _langgraph_bootstrap_marker")
    op.drop_index("idx_hitl_locks_expires_at", table_name="hitl_queue_locks")
    op.drop_table("hitl_queue_locks")
