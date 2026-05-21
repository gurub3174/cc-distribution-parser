"""SQLAlchemy models for SQLite ops state.

Two tables: `jobs` (FastAPI ingress writes a row per upload; tracked separately
from Snowflake `documents` to keep ingestion ack independent of warehouse
availability) and `hitl_queue_locks` (advisory locks so two reviewers can't
grab the same item concurrently).

LangGraph's own checkpoint table is managed by `SqliteSaver` and is not
mirrored here — keep their schema isolated.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Alembic's env.py imports this for autogenerate.
metadata = Base.metadata


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    doc_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(UTC),
    )


class HitlQueueLock(Base):
    __tablename__ = "hitl_queue_locks"

    extraction_id: Mapped[str] = mapped_column(String, primary_key=True)
    locked_by: Mapped[str] = mapped_column(String)
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=900)
