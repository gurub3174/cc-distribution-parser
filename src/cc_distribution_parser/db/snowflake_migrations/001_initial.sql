-- Migration: 001_initial
-- Author:    gurub3174
-- Date:      2026-05-03
-- Reason:    Bootstrap MVP schema (architecture.md §5.2 / §6.2)
-- Reverts:   none (use down section)
-- Costs:     N/A (initial schema)
-- Reviewed:  pending Code Reviewer pass-1 + pass-3
--
-- This migration creates ALL MVP tables: extractions, corrections,
-- few_shot_exemplars_silver (Cortex VECTOR(1024)), parsed_doc_chunks,
-- eval_runs, drift_reports, dlq, audit. master_data_cache and template_registry
-- are deferred to Phase 1.5 / Phase 2 per architecture.md §5.2.
--
-- Forward-compatible multi-tenancy seam: every mutable table carries user_id
-- (will be aliased to tenant_id in Phase 4 stretch per spec/scope.md).
--
-- Run with the schema configured in env (CCDP.PUBLIC default).

-- ============================================================================
-- UP
-- ============================================================================

-- extractions: final per-doc extraction. WORM via insert + superseded_by pointer.
CREATE TABLE IF NOT EXISTS extractions (
    id                  VARCHAR PRIMARY KEY,                  -- UUID
    doc_id              VARCHAR NOT NULL,                     -- ParsedDoc UUID
    class               VARCHAR NOT NULL,                     -- 'capital_call' | 'distribution' | 'other'
    payload_variant     VARCHAR NOT NULL,                     -- mirror of class for analytics
    payload_json        VARIANT NOT NULL,                     -- CapitalCallV1 | DistributionV1
    -- First-class versioning columns (architecture.md §6.2; .claude/rules/snowflake-migrations.md rule 4)
    model_id            VARCHAR NOT NULL,                     -- exact pinned ID
    prompt_hash         VARCHAR NOT NULL,                     -- SHA256 hex of rendered prompt
    prompt_version      VARCHAR NOT NULL,                     -- human-readable label
    parser_version      VARCHAR NOT NULL,                     -- from ParsedDoc.parser_version
    schema_version      VARCHAR NOT NULL,                     -- from app/schemas/*.py
    provenance_json     VARIANT,                              -- few_shot_ids, signals, tokens, cost_usd
    user_id             VARCHAR NOT NULL,                     -- multi-tenancy seam (forward-compatible with tenant_id Phase 4)
    committed_by        VARCHAR,                              -- nullable: locked at threshold=0.0 today (every row has a HITL reviewer); see .claude/rules/threshold-unlock.md
    committed_at        TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP(),
    superseded_by       VARCHAR                               -- WORM: points to newer extraction.id if revised
    -- NOTE: Snowflake parses but does not enforce FOREIGN KEY constraints (informational only).
    -- Referential integrity for corrections.extraction_id and silver.extraction_id is enforced
    -- in app/services/commit.py — do not rely on the DB to reject orphans.
);
CREATE INDEX IF NOT EXISTS idx_extractions_doc_id      ON extractions(doc_id);
CREATE INDEX IF NOT EXISTS idx_extractions_prompt_hash ON extractions(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_extractions_user_id     ON extractions(user_id);

-- corrections: HITL correction log, append-only. Drives drift reports + future calibration.
CREATE TABLE IF NOT EXISTS corrections (
    id                  VARCHAR PRIMARY KEY,                  -- UUID
    extraction_id       VARCHAR NOT NULL REFERENCES extractions(id),
    field               VARCHAR NOT NULL,                     -- e.g., 'capital_call_amount'
    old_value           VARIANT,                              -- as extracted
    new_value           VARIANT,                              -- as corrected by reviewer
    reason_code         VARCHAR,                              -- enum: 'wrong_value' | 'wrong_class' | 'absent_extracted' | ...
    user_id             VARCHAR NOT NULL,                     -- reviewer
    ts                  TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);
CREATE INDEX IF NOT EXISTS idx_corrections_extraction_id ON corrections(extraction_id);

-- few_shot_exemplars_silver: HITL-approved extractions enter this pool, retrieved via Cortex VECTOR.
CREATE TABLE IF NOT EXISTS few_shot_exemplars_silver (
    id                  VARCHAR PRIMARY KEY,                  -- UUID
    extraction_id       VARCHAR NOT NULL REFERENCES extractions(id),
    class               VARCHAR NOT NULL,                     -- 'capital_call' | 'distribution'
    doc_embedding       VECTOR(FLOAT, 1024),                  -- Cortex VECTOR; sized for Titan v2; see snowflake-migrations.md rule 5
    field_values_json   VARIANT NOT NULL,                     -- compact extraction table
    synopsis_200tok     VARCHAR(2000) NOT NULL,               -- ~200-token doc summary
    user_id             VARCHAR NOT NULL,
    approved_at         TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);
CREATE INDEX IF NOT EXISTS idx_silver_class ON few_shot_exemplars_silver(class);

-- parsed_doc_chunks: scaffolded for Phase 2 RAG retrieval (parsed_doc_chunks weak-field secondary calls).
CREATE TABLE IF NOT EXISTS parsed_doc_chunks (
    id                  VARCHAR PRIMARY KEY,
    doc_id              VARCHAR NOT NULL,
    page                INTEGER NOT NULL,
    layout_role         VARCHAR,                              -- 'header' | 'body' | 'table' | 'footer' (spacy-layout)
    text                VARCHAR,
    bbox                VARIANT,                              -- {x, y, w, h}
    embedding           VECTOR(FLOAT, 1024),
    user_id             VARCHAR NOT NULL,
    created_at          TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON parsed_doc_chunks(doc_id);

-- eval_runs: golden-set replay history; powers the regression gate.
CREATE TABLE IF NOT EXISTS eval_runs (
    id                      VARCHAR PRIMARY KEY,
    run_at                  TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP(),
    commit_sha              VARCHAR NOT NULL,                 -- git SHA of the eval-time tree
    prompt_hash             VARCHAR NOT NULL,                 -- joins to extractions.prompt_hash
    per_field_f1_json       VARIANT NOT NULL,                 -- {field: f1}
    per_template_f1_json    VARIANT NOT NULL,                 -- {template_id: f1}
    pass                    BOOLEAN NOT NULL,
    regression_details_json VARIANT                            -- if pass=false, what regressed
);
CREATE INDEX IF NOT EXISTS idx_eval_runs_commit_sha ON eval_runs(commit_sha);

-- drift_reports: weekly correction-rate snapshots (counterpart to drift-reports/*.md files).
CREATE TABLE IF NOT EXISTS drift_reports (
    id                              VARCHAR PRIMARY KEY,
    week_starting                   DATE NOT NULL,
    per_field_correction_rate_json  VARIANT NOT NULL,
    alerts_json                     VARIANT,                   -- list of triggered alerts
    created_at                      TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);

-- dlq: dead-letter for non-recoverable failures after both retry budgets exhausted (architecture.md §6.3).
CREATE TABLE IF NOT EXISTS dlq (
    id                  VARCHAR PRIMARY KEY,
    doc_id              VARCHAR NOT NULL,
    stage               VARCHAR NOT NULL,                     -- 'parse' | 'classify' | 'extract_cc' | ...
    error_class         VARCHAR NOT NULL,                     -- e.g., 'BedrockThrottlingException'
    error_message       VARCHAR,                              -- redacted; never log secrets
    retry_count         INTEGER NOT NULL,
    last_attempt_at     TIMESTAMP_TZ NOT NULL,
    payload_json        VARIANT,                              -- minimal redacted payload for triage
    user_id             VARCHAR NOT NULL,
    created_at          TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);
CREATE INDEX IF NOT EXISTS idx_dlq_doc_id ON dlq(doc_id);
CREATE INDEX IF NOT EXISTS idx_dlq_stage  ON dlq(stage);

-- audit: system-level append-only event log.
CREATE TABLE IF NOT EXISTS audit (
    id                  VARCHAR PRIMARY KEY,
    actor               VARCHAR NOT NULL,                     -- user_id or 'system'
    action              VARCHAR NOT NULL,                     -- 'extraction.commit' | 'hitl.approve' | 'config.threshold_change' | ...
    target              VARCHAR,                              -- e.g., extraction id, doc_id, config key
    ts                  TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP(),
    metadata_json       VARIANT
);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit(action);
CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit(actor);

-- ============================================================================
-- DOWN
-- ============================================================================
-- Run in reverse dependency order. Drops are gated by .claude/rules/snowflake-migrations.md rule 7
-- (no DROP in MVP migrations); included here for symmetry — DO NOT execute on prod without
-- explicit user approval recorded in the migration header.
--
-- DROP TABLE IF EXISTS audit;
-- DROP TABLE IF EXISTS dlq;
-- DROP TABLE IF EXISTS drift_reports;
-- DROP TABLE IF EXISTS eval_runs;
-- DROP TABLE IF EXISTS parsed_doc_chunks;
-- DROP TABLE IF EXISTS few_shot_exemplars_silver;
-- DROP TABLE IF EXISTS corrections;
-- DROP TABLE IF EXISTS extractions;
