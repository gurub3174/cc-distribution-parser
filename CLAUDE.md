# cc-distribution-parser

> Extracts capital-call and distribution notices (PDF / scanned PDF / DOCX) into validated structured fields with HITL review. Internal Canoe Intelligence replacement; corpus-owning by design.

Built by the user with the AI Build Team (`~/.claude/ai-build-team/`).

## Bash Workaround

User profile contains an apostrophe. Use `$USERPROFILE`:
```bash
cd "$USERPROFILE/.claude/ai-build-team" && <command>
```

## Project Tier

**Internal** (source of truth: `spec/scope.md`). Build Lead reads this at session start and modulates engagement per the tier matrix in `~/.claude/ai-build-team/rules/tier-engagement.md`.

## v1.1 LOCKED context (2026-04-28)

Three deltas from the 2026-04-21 design package — all load-bearing:

1. **Storage:** Snowflake + SQLite + S3 (was: Postgres + pgvector). Vector store = Snowflake Cortex `VECTOR`. `tenant_id` / `user_id` column forward-compatible from day 1.
2. **Canonicalization:** deferred to Phase 1.5 (was: MVP Sprint 3). Measure failure modes first.
3. **Phoenix observability:** promoted to Sprint 1 (was: Phase 1.5). OTel non-negotiable from first deploy.
4. **Multi-tenancy:** Phase 4 stretch (was: permanent non-goal).

Canonical architecture: `spec/architecture.md` (= design-spec.md v1.1).

## Build Team Reference

This project links to the central AI Build Team. Don't duplicate team infrastructure.

- **Team home:** `~/.claude/ai-build-team/`
- **Agents:** `~/.claude/ai-build-team/team/agents/`
- **Wiki:** `~/.claude/ai-build-team/wiki/`
- **Rules:** `~/.claude/ai-build-team/rules/` (inherits `code-style`, `no-fabrication`, `prompt-injection`, `wiki-conventions`, `tier-engagement`, `settings-precedence`)
- **Skills:** `~/.claude/ai-build-team/skills/`
- **Hooks:** `~/.claude/ai-build-team/hooks/`

## Invocation

From this project root:
- **`/consult-build-lead`** — lightweight conversation with Build Lead, full project context loaded
- **`/build [feature]`** — heavyweight pipeline with specialist delegation per tier
- **`/grill-me spec/architecture.md`** — Socratic interview drilling on a design or plan; scores reasoning across 5 competency dimensions
- **`/research <question>`** — timeboxed external evidence brief (academic / market / both); produces Top-3 with confidence grades + So What

All four fail loudly if `spec/scope.md` is missing.

## Project Conventions

**Hybrid pattern** (reconciled 2026-05-03):
- **Generic rules** inherit from `~/.claude/ai-build-team/rules/` (`code-style`, `no-fabrication`, `prompt-injection`, `wiki-conventions`, `tier-engagement`, `settings-precedence`).
- **Project-specific rules** live in `.claude/rules/` — they encode this project's own decisions (Snowflake DDL policy, LangGraph swap playbook, structured-output fallback, threshold unlock, testing patterns).
- **Deviations from central rules** go in `overrides.md` (e.g., elevating prompt-injection to mandatory Spotlighting).

See `overrides.md` for the rationale (Pattern A vs B vs C tradeoff).

**Note on convention divergence:** `~/.claude/ai-design-team/wiki/user/conventions.md` (2026-04-20) mandates a full per-project `claude/rules/` tree. The hybrid pattern partially supersedes that — surfaced explicitly per "conventions are guidelines, not religion."

## Source Layout

`src/cc_distribution_parser/` — Python src layout. Subpackages (per `spec/implementation-plan.md` §Repo Structure):
- `parsing/` — `ParserProtocol` + `DoclingParser` (Phase 1; BDA + Azure DI A/B in Phase 1.5)
- `schemas/` — Pydantic schemas (`CapitalCallV1` 9-field, `DistributionV1` 8-field, `ParsedDoc`); each module exports `schema_version`
- `prompts/` — versioned prompt modules; each exports `version`, `compute_hash()`, `SYSTEM_PROMPT`, `USER_TEMPLATE`
- `services/` — framework-free business logic; each `def run(state: DocState) -> DocState`
- `workflow/` — LangGraph DAG (isolated per Critic W3; pinned `~=0.2.0`); ONLY package allowed to import `langgraph.*`
- `db/` — Snowflake (warehouse) + SQLite (ops state) + S3; raw-SQL Snowflake migrations + Alembic SQLite migrations
- `hitl/` — FastAPI + HTMX review UI (HAX-grounded)
- `observability/` — structlog (bound-context contract) + OTel → Phoenix sidecar
- `eval/` — golden-eval harness (`pytest -m eval`); CI-gated per AC8

## Tests

```bash
uv run pytest tests/
uv run pytest -m eval     # golden-eval suite (CI-gated per Acceptance Criterion 8)
```

## Lint + Type

```bash
uv run ruff check .
uv run ruff format .
uv run pyright
```

## Spec (design team output)

`spec/` holds the design package. Read-only during build phase:

- `scope.md` — **tier + agent roster + skills required** (Build Lead reads this first)
- `architecture.md` — TDD-style technical design (= design-spec.md v1.1; the CANONICAL doc)
- `product-spec.md` — PRD-style consolidation (some sections superseded by v1.1)
- `design-brief.md` — original problem framing + risk register + locked invariants
- `implementation-plan.md` — sprint breakdown (Snowflake + canon Phase 1.5 + Phoenix Sprint 1)
- `test-plan.md` — acceptance → validation tests
- `design-rationale.md` — teaching + interview prep layer (Interview Competency Map)
- `critical-review.md` — Design Critic findings (C1-C4 incorporated)
- `postmortem-template.md` — fill at Phase 1 ship

## Wiki

- **Project-local:** `wiki/` — project-specific lessons-learned. Cross-link to central via wikilinks.
- **Central:** `~/.claude/ai-design-team/wiki/` — topic notes for `document-ai-extraction`, `llm-confidence-calibration`, `llm-cost-optimization`, `prompt-injection-defense` are pending compilation. Raw notes available at `~/.claude/ai-design-team/wiki/raw/2026-04-21-{market-scout,analyst}-cc-distribution-parser.md`.
