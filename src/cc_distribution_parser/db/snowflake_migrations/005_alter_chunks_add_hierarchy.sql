-- Migration: 005_alter_chunks_add_hierarchy
-- Author:    gurub3174
-- Date:      2026-05-04
-- Reason:    v1.1.5 amendment — populate parsed_doc_chunks from MVP onward (was:
--            "scaffolded for Phase 2 RAG retrieval" per architecture.md §5.2).
--            Add hierarchy + char-offset + summary-context columns so chunks
--            simultaneously support (a) Phase 2 RAG retrieval AND (b) MVP
--            field-level provenance markers (architecture.md §7.6 v1.1.5).
--
--            New columns:
--              read_order              — sequential ordering within the doc
--                                        (1-indexed; "document read order" per
--                                        v1.1.5 design discussion)
--              parent_chunk_id         — nullable; points to the ancestor chunk
--                                        (e.g., a leaf paragraph's parent_chunk_id
--                                        points to its enclosing section header)
--              hierarchy_level         — 0=root, 1=section, 2=subsection,
--                                        3=paragraph/table/leaf
--              char_offset_start/end   — absolute char position within the doc
--                                        text; load-bearing for the
--                                        FieldProvenance markers stored in
--                                        extractions.provenance_json.field_provenance
--              doc_summary_context     — the doc-level summary string that was
--                                        prepended to chunk text BEFORE
--                                        embedding. Stored per-chunk so re-embed
--                                        is reproducible (RAPTOR / Anthropic
--                                        contextual-retrieval pattern). NULL
--                                        until the embedding is computed
--                                        (Sprint 3 when Titan integration lands).
--              embedding_input_hash    — SHA256 of (doc_summary_context || chunk_text);
--                                        reproducibility check for Phase 2
--                                        re-embedding without rebuilding the
--                                        full pipeline.
--
--            Sprint 1 populates: read_order, parent_chunk_id, hierarchy_level,
--                                char_offset_start, char_offset_end, plus existing
--                                doc_id, page, layout_role, text, bbox.
--            Sprint 3 backfills: embedding, doc_summary_context, embedding_input_hash
--                                when Bedrock Titan v2 integration ships.
--
-- Reverts:   none
-- Costs:     N/A (additive; all nullable for sprint-phased backfill)
-- Reviewed:  pending Code Reviewer pass-1 + pass-3

-- ============================================================================
-- UP
-- ============================================================================

ALTER TABLE parsed_doc_chunks ADD COLUMN IF NOT EXISTS read_order           INTEGER;
ALTER TABLE parsed_doc_chunks ADD COLUMN IF NOT EXISTS parent_chunk_id      VARCHAR;
ALTER TABLE parsed_doc_chunks ADD COLUMN IF NOT EXISTS hierarchy_level      INTEGER;
ALTER TABLE parsed_doc_chunks ADD COLUMN IF NOT EXISTS char_offset_start    INTEGER;
ALTER TABLE parsed_doc_chunks ADD COLUMN IF NOT EXISTS char_offset_end      INTEGER;
ALTER TABLE parsed_doc_chunks ADD COLUMN IF NOT EXISTS doc_summary_context  VARCHAR;
ALTER TABLE parsed_doc_chunks ADD COLUMN IF NOT EXISTS embedding_input_hash VARCHAR;

CREATE INDEX IF NOT EXISTS idx_chunks_parent     ON parsed_doc_chunks(parent_chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_level      ON parsed_doc_chunks(hierarchy_level);
CREATE INDEX IF NOT EXISTS idx_chunks_read_order ON parsed_doc_chunks(doc_id, read_order);

-- ============================================================================
-- DOWN
-- ============================================================================
-- Gated by .claude/rules/snowflake-migrations.md rule 7.
--
-- ALTER TABLE parsed_doc_chunks DROP COLUMN IF EXISTS embedding_input_hash;
-- ALTER TABLE parsed_doc_chunks DROP COLUMN IF EXISTS doc_summary_context;
-- ALTER TABLE parsed_doc_chunks DROP COLUMN IF EXISTS char_offset_end;
-- ALTER TABLE parsed_doc_chunks DROP COLUMN IF EXISTS char_offset_start;
-- ALTER TABLE parsed_doc_chunks DROP COLUMN IF EXISTS hierarchy_level;
-- ALTER TABLE parsed_doc_chunks DROP COLUMN IF EXISTS parent_chunk_id;
-- ALTER TABLE parsed_doc_chunks DROP COLUMN IF EXISTS read_order;
