"""0002_phase1_extractions — documents + extractions + audit on SQLite

Revision ID: 0002_phase1_extractions
Revises: 0001_initial
Create Date: 2026-05-24

Phase-1 stand-in for the Snowflake schema in
src/cc_distribution_parser/db/snowflake_migrations/001_initial.sql +
002_add_documents_registry.sql + 003_alter_extractions_add_temperature_and_quality.sql.

Three tables added so the full pipeline (ingest -> parse -> classify ->
extract -> validate -> gate -> commit) can complete end-to-end on a dev
machine without Snowflake credentials. Production target stays Snowflake;
see .claude/rules/snowflake-migrations.md for the Phase-1.5 swap plan.

JSON fields are stored as TEXT — SQLite has json1 extension if downstream
queries need it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase1_extractions"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("original_s3_uri", sa.String(), nullable=False),
        sa.Column("docling_json_s3_uri", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ingested"),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("parser_metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_documents_file_hash_user", "documents", ["file_hash", "user_id"], unique=True
    )

    op.create_table(
        "extractions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("doc_id", sa.String(), nullable=False),
        sa.Column("class", sa.String(), nullable=False),
        sa.Column("payload_variant", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("prompt_hash", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("parser_version", sa.String(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0"),
        sa.Column("provenance_json", sa.Text(), nullable=True),
        sa.Column("extraction_quality_json", sa.Text(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("committed_by", sa.String(), nullable=True),
        sa.Column("committed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_extractions_doc_id", "extractions", ["doc_id"])

    op.create_table(
        "audit",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )
    op.create_index("idx_audit_target", "audit", ["target"])


def downgrade() -> None:
    op.drop_index("idx_audit_target", table_name="audit")
    op.drop_table("audit")
    op.drop_index("idx_extractions_doc_id", table_name="extractions")
    op.drop_table("extractions")
    op.drop_index("idx_documents_file_hash_user", table_name="documents")
    op.drop_table("documents")
