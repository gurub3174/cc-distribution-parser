-- Migration: 002_add_documents_registry
-- Author:    gurub3174
-- Date:      2026-05-04
-- Reason:    v1.1.5 amendment — foundational doc-level registry for re-parseability
--            and dedup. Closes implicit gap in 001_initial.sql where
--            extractions.doc_id referenced "a ParsedDoc UUID" with no documents
--            table. Going forward, every ingested file gets a documents row at
--            the FastAPI ingress; extractions.doc_id and parsed_doc_chunks.doc_id
--            are now informational FKs to documents.id (Snowflake parses but
--            does not enforce FK; integrity is in app/services/parse.py and
--            app/services/commit.py per 001_initial.sql convention).
--
--            Blob storage: Docling parsed-JSON blob lives in S3 (consistent with
--            architecture.md §5.1 — S3 already holds original docs + ParsedDoc
--            cache, KMS encryption + 7-year-lifecycle policy already configured).
--            The documents row carries pointers (original_s3_uri,
--            docling_json_s3_uri); we don't query inside the blob — we fetch it
--            for re-parse — so a Snowflake external-stage layer is an
--            optimization, not an MVP requirement.
--
-- Reverts:   none
-- Costs:     N/A (additive)
-- Reviewed:  pending Code Reviewer pass-1 + pass-3

-- ============================================================================
-- UP
-- ============================================================================

CREATE TABLE IF NOT EXISTS documents (
    id                      VARCHAR PRIMARY KEY,                  -- UUID
    file_hash               VARCHAR NOT NULL,                     -- SHA256 hex of original file bytes (dedup key)
    original_filename       VARCHAR NOT NULL,                     -- as uploaded
    gp_source               VARCHAR,                              -- nullable: GP name when known (filename pattern / email metadata / HITL backfill)
    mime_type               VARCHAR NOT NULL,                     -- application/pdf | application/vnd.openxmlformats-officedocument.wordprocessingml.document
    byte_size               INTEGER NOT NULL,
    original_s3_uri         VARCHAR NOT NULL,                     -- s3://bucket/raw/{user_id}/{doc_id}.{ext}
    docling_json_s3_uri     VARCHAR,                              -- s3://bucket/parsed/{user_id}/{doc_id}.json (nullable until parsed)
    parser_version          VARCHAR,                              -- nullable until parsed; matches extractions.parser_version
    parser_metadata_json    VARIANT,                              -- {page_count, language, contains_tables, contains_images, ocr_used, parse_duration_ms, ...}
    status                  VARCHAR NOT NULL,                     -- 'ingested' | 'parsed' | 'failed_parse'
    ingested_at             TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP(),
    ingested_by             VARCHAR,                              -- nullable for system/batch ingest
    user_id                 VARCHAR NOT NULL                      -- multi-tenancy seam (forward-compatible with tenant_id Phase 4)
    -- Informational note: extractions.doc_id and parsed_doc_chunks.doc_id reference documents.id.
    -- Snowflake parses but does not enforce FK; integrity enforced in
    -- app/services/parse.py (writes documents row) and app/services/commit.py
    -- (asserts documents row exists before inserting extractions row).
);

CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_user_id   ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_gp_source ON documents(gp_source);
CREATE INDEX IF NOT EXISTS idx_documents_status    ON documents(status);

-- ============================================================================
-- DOWN
-- ============================================================================
-- Drops gated by .claude/rules/snowflake-migrations.md rule 7 (no DROP in MVP
-- migrations without explicit user approval recorded in this header).
--
-- DROP TABLE IF EXISTS documents;
