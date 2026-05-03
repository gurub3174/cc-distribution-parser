---
name: Snowflake DDL Migration Policy
applies-to: any change to src/cc_distribution_parser/db/snowflake_models.py or snowflake_migrations/
status: load-bearing
---

# Snowflake DDL Migration Policy

Snowflake holds **load-bearing money-document data**: extractions (with cost + audit trail), corrections, silver-pool exemplars (Cortex VECTOR(1024)), eval runs, drift reports, DLQ, audit. Schema changes here cascade to long-retention storage where backout is expensive.

## Rules

1. **Versioned forward-only files.** Every schema change ships as `snowflake_migrations/NNN_<verb>_<noun>.sql` where `NNN` is a zero-padded sequence (`001`, `002`, ...). Never edit a committed migration. Add a new one.
2. **One logical change per migration.** A migration adds one table, alters one column set, or seeds one canonical lookup. Bundling multiple changes makes rollback impossible.
3. **Forward AND down.** Every migration ships with both `-- UP` and `-- DOWN` sections. The down must restore the prior schema exactly. Test the down on a Snowflake clone before merging the up.
4. **Versioning columns are append-only contracts.** `model_id`, `prompt_hash`, `prompt_version`, `parser_version`, `schema_version` exist on `extractions` from migration 001. Removing or renaming any of them breaks regression analysis — treat as a major-version event with explicit data backfill plan.
5. **VECTOR dimension is a one-way door.** `few_shot_exemplars_silver.embedding VECTOR(1024)` is sized for Titan v2. Changing dimension means re-embedding the entire silver pool. Document the cost in the migration header before merging.
6. **Multi-tenancy seam stays open.** Every mutable table has `user_id VARCHAR` from migration 001 (forward-compatible with future `tenant_id`). Migrations that add new mutable tables MUST include `user_id`. CI fails if a new table omits it.
7. **No DROP TABLE in MVP migrations.** Phase 1 only adds + alters. Drops require explicit user approval recorded in the migration header.
8. **Long-retention awareness.** Snowflake's Time Travel + Fail-safe means data is recoverable for 1–90 days. This is not a license for casual destructive changes — recovery requires Snowflake admin engagement.

## Naming convention

```
001_initial.sql                       # bootstrap — all MVP tables
002_add_template_fingerprint.sql      # Phase 2 example
003_add_master_data_cache.sql         # Phase 1.5 example
```

## Change-log requirement

Each migration starts with a header:

```sql
-- Migration: 002_add_template_fingerprint
-- Author:    <git user>
-- Date:      YYYY-MM-DD
-- Reason:    Phase 2 — template-seen detection (architecture §8.3)
-- Reverts:   none
-- Costs:     N/A (additive)
-- Reviewed:  Code Reviewer pass-1 + pass-3
```

## Reference

- Project context: `spec/architecture.md` §6 (data model), §15.5 (rituals).
- Inherits from: central `~/.claude/ai-build-team/rules/code-style.md` (surgical changes principle).
