-- Migration: 004_alter_corrections_add_status
-- Author:    gurub3174
-- Date:      2026-05-04
-- Reason:    v1.1.5 amendment — add operational status to corrections so the
--            correction lifecycle is queryable instead of inferred from joins
--            against extractions.superseded_by (architecture.md §5.2 v1.1.5).
--
--            Allowed values (enforced at the Pydantic / app layer):
--              'open'        — correction logged but not yet applied to a new
--                              extraction row (HITL submitted, awaiting commit)
--              'applied'     — correction folded into a new extractions row
--                              (the supersession is in place)
--              'rejected'    — reviewer changed their mind / flagged as wrong
--              'superseded'  — a later correction on the same field replaced
--                              this one before it was applied
--
--            Drives Phase 1.5 calibration: filter corrections to status='applied'
--            before scoring.
--
-- Reverts:   none
-- Costs:     N/A (additive; nullable for backfill safety)
-- Reviewed:  pending Code Reviewer pass-1 + pass-3

-- ============================================================================
-- UP
-- ============================================================================

ALTER TABLE corrections ADD COLUMN IF NOT EXISTS status VARCHAR;

CREATE INDEX IF NOT EXISTS idx_corrections_status ON corrections(status);

-- ============================================================================
-- DOWN
-- ============================================================================
-- Gated by .claude/rules/snowflake-migrations.md rule 7.
--
-- ALTER TABLE corrections DROP COLUMN IF EXISTS status;
