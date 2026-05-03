---
project: cc-distribution-parser
type: implementation-plan
created: 2026-04-21
updated: 2026-05-03 (v1.1.1 — repo structure reconciled to hybrid rules pattern + actual scaffold layout)
author: design-lead
status: approved
companion: design-spec.md
amendments:
  - 2026-04-28 (v1.1) — Snowflake + canon Phase 1.5 + Phoenix MVP + ops adds
  - 2026-05-03 (v1.1.1) — repo structure: `app/` → `src/cc_distribution_parser/`; `claude/` → `.claude/` (hidden); rules pattern → hybrid (central inheritance + project-specific .claude/rules/ + overrides.md). See `overrides.md` "Context — hybrid rules pattern" for rationale.
---

# Implementation Plan — Capital Call & Distribution Parser (Phase 1, ~5 weeks solo)

**v1.1 deltas from 2026-04-21 baseline** (full rationale in `design-spec.md` Appendix D):

- Storage: **Snowflake + SQLite + S3** (was: one Postgres + pgvector + S3)
- Canonicalization: **deferred to Phase 1.5** (was: MVP Sprint 3) — measure where extraction fails before building the fixer
- Tracing: **Phoenix sidecar promoted to MVP Sprint 1** (was: Phase 1.5)
- New MVP operational adds: **structlog bound-context contract** (Sprint 1), **first-class versioning columns** `prompt_hash` / `parser_version` / `schema_version` (Sprint 1), **tiered retry + DLQ** (Sprint 2)
- New Phase 1.5 lines: **prompt registry**, **CD automation**, plus the canonicalization layer pulled in from MVP
- New Phase 2 line: **experiment A/B infrastructure** (live-traffic split + treatment label, distinct from one-off A/B experiments)
- Multi-tenancy posture: **Phase 4 stretch** (was: out of scope permanently); MVP `user_id` column is forward-compatible

## Repo Structure (reconciled 2026-05-03 — hybrid rules pattern + src layout)

```
C:\projects\cc-distribution-parser\
├── CLAUDE.md                          # <200 lines: overview + slash-command pointers + $USERPROFILE note
├── CLAUDE.local.md                    # personal overrides (gitignored)
├── overrides.md                       # deviations from central build-team rules (see hybrid rules pattern)
├── mcp.json                           # external tool integrations (GitHub, optional)
├── .gitignore                         # .claude/rules/ ships; other .claude/ subfolders ignored
├── alembic.ini                        # SQLite ops-state migrations only (Snowflake DDL is raw SQL)
├── .github/workflows/
│   ├── ci.yml                         # ruff + pyright + pytest + pip-audit
│   ├── golden-eval.yml                # required check on PRs touching prompts/schemas/models (AC8)
│   └── drift-weekly.yml               # scheduled cron writes drift-reports/
├── .claude/
│   ├── settings.json                  # permissions, hooks, model selection (committed)
│   ├── rules/                         # PROJECT-SPECIFIC RULES ONLY (hybrid pattern)
│   │   ├── snowflake-migrations.md    # Snowflake DDL change policy
│   │   ├── framework-swap.md          # LangGraph swap playbook (Critic W3)
│   │   ├── structured-output-fallback.md  # Instructor tool_use fallback (Critic W6)
│   │   ├── threshold-unlock.md        # auto-approve unlock after calibration (Critic C4)
│   │   └── testing.md                 # test pyramid + golden-eval CI contract
│   # Generic rules (code-style, no-fabrication, prompt-injection, wiki-conventions, tier-engagement,
│   # settings-precedence) inherit centrally from ~/.claude/ai-build-team/rules/ — NOT duplicated.
│   # Project-specific deviations from those central rules live in `overrides.md`.
│   #
│   # The following .claude/ subfolders are gitignored — central inheritance handles them:
│   #   .claude/agents/    (build-team agents at ~/.claude/ai-build-team/team/agents/)
│   #   .claude/skills/    (skills at ~/.claude/skills/ or central plugin marketplace)
│   #   .claude/commands/  (commands inherited centrally)
│   #   .claude/hooks/     (hooks at ~/.claude/ai-build-team/hooks/)
├── src/cc_distribution_parser/        # Python src layout per pyproject.toml
│   ├── __init__.py
│   ├── main.py                        # FastAPI entrypoint (Sprint 1)
│   ├── config.py                      # env + settings (Sprint 1)
│   ├── parsing/
│   │   ├── base.py                    # ParserProtocol, ParsedDoc (Sprint 1)
│   │   └── docling_parser.py          # Phase 1 only (Sprint 1)
│   ├── schemas/
│   │   ├── capital_call.py            # CapitalCallV1 (reasoning-first); schema_version export
│   │   ├── distribution.py            # DistributionV1; schema_version export
│   │   └── parsed_doc.py              # ParsedDoc (parser_version included)
│   ├── prompts/
│   │   ├── classifier.py              # 3-class; version + compute_hash() exports
│   │   ├── extract_cc.py              # monolithic CC; version + compute_hash()
│   │   └── extract_distro.py          # monolithic Distro; version + compute_hash()
│   ├── services/                      # framework-free; def run(state: DocState) -> DocState
│   │   ├── parse.py
│   │   ├── classify.py
│   │   ├── extract.py                 # run_cc + run_distro
│   │   ├── validate.py
│   │   ├── gate.py
│   │   ├── commit.py
│   │   ├── few_shot_retrieval.py     # Snowflake Cortex VECTOR + MMR
│   │   ├── llm_client.py              # Instructor + Bedrock Converse + tiered retry
│   │   ├── retry.py                   # boto3 adaptive + tenacity + DLQ writer (Sprint 2)
│   │   └── queue_slo.py               # writes .hitl-queue-alert marker
│   ├── workflow/
│   │   ├── graph.py                   # LangGraph DAG — ONLY package allowed to import langgraph.*
│   │   └── types.py                   # DocState TypedDict (framework-free)
│   ├── db/
│   │   ├── snowflake_models.py        # Snowflake schema declarations
│   │   ├── snowflake_migrations/      # versioned forward-only DDL (001_initial.sql is bootstrapped)
│   │   ├── sqlite_models.py           # ops state SQLAlchemy models (langgraph checkpoints, hitl locks)
│   │   ├── sqlite_migrations/         # Alembic env.py + versions/ for SQLite
│   │   └── session.py                 # both connections
│   # canonicalization/, master_data/   # PHASE 1.5 — not in MVP
│   ├── hitl/
│   │   ├── routes.py                  # FastAPI + HTMX endpoints
│   │   ├── templates/                 # Jinja2 templates
│   │   ├── static/                    # Tailwind + Alpine.js
│   │   └── dlq_routes.py              # DLQ triage UI (Sprint 2)
│   ├── observability/
│   │   ├── logging.py                 # structlog bound-context contract (Sprint 1)
│   │   ├── tracing.py                 # OTel → Phoenix sidecar (Sprint 1)
│   │   └── cost.py                    # per-span cost aggregation
│   └── eval/
│       ├── golden_set.py              # load/save golden docs
│       ├── runner.py                  # pytest -m eval harness
│       └── metrics.py                 # per-field + per-template
├── data/
│   ├── golden_eval/                   # 20-30 labeled docs + ground truth
│   └── vocab_pending.yaml             # Phase 1.5 — HITL-flagged new variants
├── drift-reports/                     # weekly markdown reports (git-tracked; gitignored only at scaffold time, ungitignore once Sprint 6 lands)
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   ├── security/injection_suite/      # red-team prompts (eval-time)
│   └── eval/                          # marker=eval (replayed by CI)
├── docs/                              # any long-form design docs
├── pyproject.toml                     # deps + pinned versions
├── Dockerfile                         # local dev image (production hardened in Phase 1.5 CD)
├── docker-compose.yml                 # FastAPI app + Phoenix sidecar + MinIO; Snowflake = firm cloud
└── README.md
```

## Dependency Pinning (Phase 1 critical choices)

```toml
# pyproject.toml highlights
[project.dependencies]
python = "^3.11"
fastapi = "^0.115"
uvicorn = "^0.30"
pydantic = "^2.8"

# Snowflake (warehouse: extractions, corrections, exemplars w/ Cortex VECTOR, eval, drift, dlq, audit)
snowflake-connector-python = "^3.10"
snowflake-sqlalchemy = "^1.6"          # if using SQLAlchemy on Snowflake
sqlalchemy = "^2.0"

# SQLite (operational state: langgraph checkpoints, hitl queue locks)
alembic = "^1.13"                      # migrations for SQLite ops state

# AWS
boto3 = "^1.34"                        # Bedrock SDK; configure adaptive retry mode (Sprint 2)

# Document parsing
docling = "~2.0"                       # Phase 1 primary parser
spacy = "^3.7"
spacy-layout = "~0.2"

# LLM stack
instructor = "^1.4"                    # schema-guided wrapper
tenacity = "^9.0"                      # app-layer retry on transient failures (Sprint 2)

# Orchestration
langgraph = "~0.2.0"                   # W1 — minor-compatible pin
langgraph-checkpoint-sqlite = "~0.1"   # SQLite checkpointer (was: -postgres)

# Observability
structlog = "^24.1"                    # bound-context logging (Sprint 1)
opentelemetry-api = "^1.26"
opentelemetry-sdk = "^1.26"
opentelemetry-exporter-otlp = "^1.26"  # spans → Phoenix
arize-phoenix = "^5.0"                 # Phoenix sidecar (Sprint 1, promoted from Phase 1.5)

# Testing + CI
pytest = "^8.3"
pytest-asyncio = "^0.24"
pip-audit = "^2.7"
```

## Sprint 0 — Setup (2-3 days)

**Deliverables (status as of 2026-05-03):**
- [x] Project scaffolded at `C:\projects\cc-distribution-parser\` with full directory structure above
- [x] `CLAUDE.md` written (<200 lines) with project overview, slash-command pointers
- [x] **Hybrid rules pattern applied:** `.claude/rules/{snowflake-migrations,framework-swap,structured-output-fallback,threshold-unlock,testing}.md` written; generic rules inherit from `~/.claude/ai-build-team/rules/`; `overrides.md` carries deviations
- [x] `pyproject.toml` with pinned deps per §Dependency Pinning
- [x] `docker-compose.yml` spins up FastAPI app + **Phoenix sidecar** + MinIO (S3 emulator); Snowflake is firm-managed
- [x] First Snowflake DDL migration script written (`src/cc_distribution_parser/db/snowflake_migrations/001_initial.sql`) — covers all MVP tables incl. versioning columns + multi-tenancy seam (`user_id`)
- [x] Alembic initialized for **SQLite ops-state schema** (langgraph_checkpoints marker + hitl_queue_locks)
- [x] GitHub Actions stubbed (`ci.yml`, `golden-eval.yml`, `drift-weekly.yml`)
- [ ] Snowflake account/warehouse access verified — **deferred (needs creds)**
- [ ] Python virtualenv + install succeeds — pending `uv sync`
- [ ] `pytest --collect-only` runs cleanly — pending venv

**Tasks:**
1. `git init` + initial scaffold commit ✅
2. Scaffold directory per repo-structure above ✅
3. Write `CLAUDE.md` ✅ (done at scaffold time; revised 2026-05-03 for hybrid rules pattern)
4. Write `.claude/rules/*.md` per hybrid pattern (5 project-specific rule files, NOT a duplicated generic-rules tree) ✅
5. Configure `pyproject.toml` + pin deps ✅
6. Write `docker-compose.yml` for FastAPI + Phoenix sidecar + MinIO ✅
7. Write Snowflake DDL bootstrap script (all MVP tables + versioning columns + `user_id` seam) ✅
8. Initialize Alembic for SQLite ops state; create `2026_05_03_0001_initial.py` migration ✅
9. Stub GitHub Actions workflows ✅
10. **Deferred (needs Snowflake creds):** validate environment — `pytest --collect-only`, Snowflake connection test, `docker compose up`
11. **Deferred (needs Snowflake creds):** apply `001_initial.sql` to firm Snowflake

**Sprint 0 exit criteria:** all check-marked items above complete + tasks 10-11 unblocked when Snowflake creds available.

## Sprint 1 — Ingestion + Parse + Storage + Observability (5-7 days)

**Deliverables:**
- [ ] FastAPI ingress endpoint accepts PDF + DOCX uploads; stores blob to S3 + `jobs` row in SQLite ops state
- [ ] `ParserProtocol` interface defined
- [ ] `DoclingParser` implemented; emits `ParsedDoc` (parser_version included)
- [ ] Parse-only worker processes queue; 5 test docs parse successfully
- [ ] Snowflake schema applied (all MVP tables) with first-class versioning columns on `extractions`: `model_id`, `prompt_hash`, `prompt_version`, `parser_version`, `schema_version`
- [ ] **structlog bound-context contract** — `doc_id` + `pipeline_run_id` bound at ingress, inherited by every downstream stage; required fields enforced via custom processor
- [ ] **Phoenix sidecar wired** — OTel spans emitted from `parse` stage; visible in Phoenix UI at `localhost:6006`; spans carry full versioning fields (model_id, prompt_version, prompt_hash, parser_version, schema_version)
- [ ] Per-doc cost attribution scaffolded (zero for parse stage; ready for LLM calls in Sprint 2)

**Tasks:**
1. `app/schemas/parsed_doc.py` — `ParsedDoc` Pydantic model (includes `parser_version`)
2. `app/parsing/base.py` — `ParserProtocol`
3. `app/parsing/docling_parser.py` — wrap docling + spacy-layout; sets `parser_version` from docling version + own wrapper version
4. `app/main.py` — FastAPI app with `/upload` endpoint
5. `app/db/snowflake_models.py` — schema declarations for all MVP tables (with versioning columns)
6. `app/db/sqlite_models.py` — ops-state schema for langgraph + hitl locks
7. `app/services/parse.py` — service function wrapping the parser
8. S3 wiring (local: MinIO in docker-compose; prod: real S3)
9. **`app/observability/logging.py`** — structlog config with bound-context processors; required-fields validator; JSON output to stdout
10. **`app/observability/tracing.py`** — OTel SDK config; OTLP exporter pointing to Phoenix sidecar; helper to attach versioning fields to every span
11. End-to-end test: upload → parse → SQLite job row + Snowflake `extractions` placeholder row + Phoenix trace visible

## Sprint 2 — Classification + Extraction (Monolithic) + LLM Client + Retry/DLQ (5-7 days)

**Deliverables:**
- [ ] `llm_client.py` — Instructor + Bedrock Converse wrapper with prompt caching
- [ ] **Tiered retry stack:** boto3 configured with `mode='adaptive', max_attempts=5` for transport-layer (Bedrock 5xx, throttle); tenacity wrapper at app-layer for transient failures (3 attempts, exponential backoff); Pydantic `ValidationError` does NOT trigger transport retry (handled by Instructor max-2)
- [ ] **DLQ writer** — `app/services/retry.py` writes to Snowflake `dlq` table after retry budgets exhausted; captures `error_class`, `error_message`, `retry_count`, `payload_json`
- [ ] 3-class classifier works end-to-end; `prompt_hash` computed from rendered prompt and persisted on extraction row
- [ ] Monolithic CC extractor works end-to-end; `prompt_hash` persisted
- [ ] Monolithic Distribution extractor works end-to-end; `prompt_hash` persisted
- [ ] Reasoning-first schemas emit structured output
- [ ] Spotlighting wrapper applied to doc text
- [ ] Vocab-dictionary hints injected into extractor system prompt (zero-cost — fits in cached portion)
- [ ] Cost attribution logged per call; rolls up to `extractions.provenance_json.cost_usd`

**Tasks:**
1. `app/services/llm_client.py` — Instructor wrapper around Bedrock Converse (model IDs from `config/models.yaml`); computes + persists `prompt_hash` on every call
2. `app/services/retry.py` — boto3 adaptive config + tenacity decorators for transient errors + DLQ writer; explicit transient/validation split
3. `app/prompts/classifier.py` — 3-class system + user prompt with 3-5 hard-coded few-shots; exports `version` + `compute_hash()`
4. `app/services/classify.py` — run classifier, return `DocClassification`
5. `app/prompts/extract_cc.py` — monolithic CC extractor prompt (reasoning-first schema, vocab hints, spotlighting wrapper); exports `version` + `compute_hash()`
6. `app/prompts/extract_distro.py` — monolithic Distribution extractor prompt
7. `app/schemas/capital_call.py` + `distribution.py` with Pydantic schemas (unfunded before/after fields); exports `schema_version`
8. `app/services/extract.py::run_cc` + `run_distro`
9. Implement Anthropic prompt caching on system prompt + schema + vocab hints
10. Integration test: parse → classify → extract CC → returns `CapitalCallV1`; row in Snowflake has populated `prompt_hash`, `parser_version`, `schema_version`, `model_id`, `prompt_version`
11. Negative-path test: simulate Bedrock 429 → boto3 retries; simulate Pydantic validation fail → Instructor max-2; simulate non-recoverable → DLQ row written

## Sprint 3 — Few-Shot Retrieval (2-3 days)

> **Canonicalization deferred to Phase 1.5 per v1.1 lock.** MVP relies on LLM-via-prompt-instruction + Pydantic coercion for number/date/currency normalization. The full deterministic layer (rapidfuzz + spaCy vocab + master-data integration) lands in Phase 1.5 once we have data on where extraction actually fails.

**Deliverables:**
- [ ] `few_shot_exemplars_silver` populated from seed data (hand-curated 5-10 entries per class, embedded with Titan v2 1024-d)
- [ ] Snowflake Cortex `VECTOR_COSINE_SIMILARITY` retrieval works (top-20 candidate)
- [ ] MMR re-ranking implemented (λ=0.5, returns top-5)
- [ ] Titan embeddings integrated via Bedrock
- [ ] Compact few-shots (extraction table + 200-tok synopsis) stored, not full docs

**Tasks:**
1. Seed `few_shot_exemplars_silver` with 5-10 hand-crafted CC + Distribution examples
2. `app/services/few_shot_retrieval.py` — embed query doc (Titan v2), Cortex cosine, MMR re-rank, top 5
3. Wire few-shot retrieval into the extractor prompts
4. Integration test: extract with retrieved few-shots; provenance records `few_shot_ids`

## Sprint 4 — Validation + Gate + HITL Queue (5-7 days)

**Deliverables:**
- [ ] Domain reconciliation validators (CC unfunded invariant PRIMARY: `abs((unfunded_before − call) − unfunded_after) < 0.01`; date ordering; currency format)
- [ ] Hard-signal tri-state classification per field (`validated` / `absent` / `failed`)
- [ ] Gate node routes to auto-commit or HITL based on hard signals (auto-approve threshold locked at 0.0)
- [ ] Reclassify-on-reconciliation-fail path via Sonnet escalation
- [ ] LangGraph graph compiled with **SQLite checkpointer** (`langgraph.checkpoint.sqlite.SqliteSaver`)
- [ ] HITL queue writes to Snowflake; LangGraph `interrupt()` works; SQLite holds the workflow checkpoint

**Tasks:**
1. `app/services/validate.py` — Pydantic + domain validators including the CC unfunded invariant
2. Hard-signal tri-state logic (`validated` / `absent` / `failed_or_violation`)
3. `app/services/gate.py` — route to auto-commit or HITL
4. `app/services/reclassify.py` — Sonnet-escalation path (W4)
5. `app/workflow/graph.py` — LangGraph DAG with all nodes + conditional edges; SqliteSaver checkpointer
6. End-to-end test: upload → full pipeline → HITL queue row in Snowflake for low-confidence doc; SQLite checkpoint persists workflow state

## Sprint 5 — HITL UI (5-7 days)

**Deliverables:**
- [ ] FastAPI + HTMX review UI with queue view and review view
- [ ] Per-field approve/reject + inline edit
- [ ] Bulk-approve-all-validated keyboard shortcut (`a`)
- [ ] Reclassify button (W4)
- [ ] Flag-as-new-vocab action — appends to `data/vocab_pending.yaml` for Phase 1.5 use (O1)
- [ ] Queue SLO banner (C4)
- [ ] On-demand provenance drawer (`p`) — shows model_id, prompt_version, prompt_hash, few_shot_ids, tokens, cost
- [ ] Solo auth with multi-user schema ready (`user_id` on every mutable row)
- [ ] Audit log captures every edit
- [ ] **DLQ triage page** — lists `dlq` rows oldest-first; replay or archive actions

**Tasks:**
1. `app/hitl/routes.py` — queue list + review detail endpoints
2. Jinja2 templates for queue view + review view
3. Tailwind + Alpine.js setup
4. HTMX partials for per-field approve/reject (optimistic update)
5. Bulk-approve keyboard shortcut + server-side bulk endpoint
6. Reclassify button → resume LangGraph workflow with new class
7. "Flag as new vocab variant" → append to `data/vocab_pending.yaml`
8. SLO checker service: `app/services/queue_slo.py` counts queue items >3 days old; writes `.hitl-queue-alert` marker file if SLO violated
9. Provenance drawer rendering from `extractions.provenance_json` + first-class versioning columns
10. Session-based auth (single user); confirm DB schema has `user_id` on every mutable row
11. Audit logging middleware
12. `app/hitl/dlq_routes.py` — DLQ triage page

## Sprint 6 — Eval Harness + CI Gates + Drift + Docs (4-6 days)

**Deliverables:**
- [ ] Golden eval set (20-30 docs across 5+ templates, labeled)
- [ ] `pytest -m eval` harness computes per-field + per-template metrics
- [ ] GitHub Action `golden-eval.yml` runs on PRs touching prompts/schemas/models
- [ ] Regression gate: >5pt F1 drop = fail until n≥50; then >2pt
- [ ] Drift weekly cron writes markdown to `drift-reports/`
- [ ] Retry-rate alerter: if Bedrock retry rate >5% over an hour, write a `drift-reports/retry-spike-<ts>.md` file
- [ ] `auto_approve_threshold: 0.0` locked in `config/models.yaml` with calibration-study unlock comment
- [ ] README + basic docs
- [ ] `claude/rules/*` all written (no TODO stubs)
- [ ] All Phase 1 release-gate criteria in `product-spec.md` met (now also incl. Phoenix sidecar visible + versioning columns populated — see `design-spec.md` §10)

**Tasks:**
1. Golden eval set curation (stretch to find 20-30 labeled docs; document if <20)
2. `app/eval/runner.py` + `metrics.py`
3. `pytest.ini` marker config
4. `.github/workflows/golden-eval.yml` — required check, runs on paths
5. `.github/workflows/drift-weekly.yml` — scheduled weekly job
6. `config/models.yaml` with pinned model IDs + `auto_approve_threshold: 0.0`
7. `claude/rules/threshold-unlock.md` documenting the calibration-study deadline
8. Complete all stub rule files
9. README with project overview + quickstart (incl. Snowflake setup, Phoenix sidecar bring-up)
10. Phase 1 release gate checklist review against `design-spec.md` §10

## Timeline Summary

| Sprint | Duration | Cumulative |
|---|---|---|
| Sprint 0: Setup | 2-3 days | ~3 days |
| Sprint 1: Ingest + Parse + Storage + Observability (Phoenix + structlog + versioning cols) | 5-7 days | ~10 days |
| Sprint 2: Classify + Extract + LLM client + Retry/DLQ | 5-7 days | ~17 days |
| Sprint 3: Few-Shot Retrieval (canon deferred) | **2-3 days** | ~20 days |
| Sprint 4: Validation + HITL Queue | 5-7 days | ~27 days |
| Sprint 5: HITL UI (incl. DLQ triage) | 5-7 days | ~34 days |
| Sprint 6: Eval + CI + Drift + Docs | 4-6 days | ~40 days |

**Total: 28-40 working days ≈ 5-6 calendar weeks at full-time, 7-9 weeks evenings/weekends.**

Net effect of v1.1 vs 2026-04-21 baseline: +0.5 day Sprint 1 (Phoenix + versioning cols), +0.5 day Sprint 2 (retry/DLQ), −2 days Sprint 3 (canon deferred). Total holds ~5 weeks full-time.

## Interface Contracts

### Service functions (all framework-free; `app/services/*`)
All service functions follow the signature:
```python
def run(state: DocState) -> DocState:
    """Pure function: reads from state, writes mutations, returns state."""
```

`DocState` is a TypedDict in `app/workflow/types.py` — owned by workflow module but importable anywhere.

### Prompt files (all in `app/prompts/`)
Each prompt module exports:
- `SYSTEM_PROMPT: str` — cached portion
- `USER_TEMPLATE: str` — per-doc formatted
- `FEW_SHOT_TEMPLATE: str` — per-exemplar formatted
- `version: str` — written to provenance + `extractions.prompt_version`
- `compute_hash(rendered: str) -> str` — SHA256 of the actual rendered prompt; written to `extractions.prompt_hash`

### Schema modules (all in `app/schemas/`)
Each schema module exports the Pydantic class plus:
- `schema_version: str` — written to `extractions.schema_version` (catches schema-shape changes in regression analysis)

### LLM client
```python
class LLMClient:
    def call(
        self,
        model_id: str,
        system: str,
        user: str,
        response_model: type[BaseModel],
        prompt_cache_keys: list[str] | None = None,
    ) -> tuple[BaseModel, CallMetadata]: ...
```

`CallMetadata` includes `prompt_hash`, `input_tokens`, `output_tokens`, `cached_tokens`, `cost_usd`, `latency_ms`, `retry_count` for log + span emission.

### Retry stack
```python
# app/services/retry.py
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
       retry=retry_if_exception_type(TransientError))
def with_app_retry(fn, *args, **kwargs):
    """Tenacity wrapper for transient app-layer failures (NOT validation errors)."""
    ...

def write_to_dlq(doc_id, stage, error, payload):
    """Snowflake INSERT into dlq table. Called when both retry budgets exhausted."""
    ...
```

### ParserProtocol (already in architecture §3)
```python
class ParserProtocol(Protocol):
    name: str
    version: str   # surfaces as parsed_doc.parser_version → extractions.parser_version
    def parse(self, file_path: Path) -> ParsedDoc: ...
```

## Dependencies Between Sprints

- Sprint 1 blocks on Sprint 0 (scaffold + Snowflake DDL + Phoenix sidecar)
- Sprint 2 blocks on Sprint 1 (`ParsedDoc` for extractor input + observability/retry foundations)
- Sprint 3 blocks on Sprint 2 (extractor consumes the few-shots; embedding infra needed)
- Sprint 4 blocks on Sprints 2 + 3 (validators run on extractor output)
- Sprint 5 can start in parallel with late Sprint 4 (HITL UI consumes the queue table; doesn't need validate logic finalized)
- Sprint 6 blocks on all prior (eval needs end-to-end pipeline)

Parallelism with solo dev is limited; sprints are largely sequential.

## Phase 1.5 (3-5 weeks post-MVP)

Per `design-spec.md` §8.2 — separate sprint plan written at start of Phase 1.5. Workstreams:

- **Calibration study** — 20 HITL-labeled docs → soft-signal weights → `claude/rules/confidence-weights.yaml` → unlock lower auto-approve threshold
- **Canonicalization layer** (deferred from MVP per v1.1) — full deterministic normalization: `app/canonicalization/` (numbers + dates + currency + names via rapidfuzz + spaCy vocab Matcher), `app/master_data/` (rapidfuzz against bootstrap CSV → real master-data when access resolved), new `canonicalize` LangGraph node between `extract_*` and `validate`. Adds `master_data_cache` Snowflake table.
- **Parser A/B** — Docling vs Bedrock Data Automation on labeled docs; per-parser scorecard; route by template family if warranted; Azure DI added if firm Azure subscription confirmed
- **Monolithic-vs-decomposed extraction A/B** — lock winner in `config/extractor.yaml`; decompose only field groups where monolithic underperforms
- **Prompt registry** (new) — refactor `app/prompts/` into a versioned registry: each prompt exports `version` + `hash` + `schema_version_target` + change-log entry; CI fails if a prompt file changes without a hash bump (pairs with the §6.2 first-class `prompt_hash` column)
- **CD automation** (new) — deployment automation for the FastAPI service (blue/green, rollback)
- **Cost cascade (optional)** — Haiku first-pass extraction → Sonnet on disagreement, if MVP unit cost exceeds target
- **Golden eval grown to 50+** — regression gate tightens from `>5pt` to `>2pt` F1 drop

## Phase 2 (4-8 weeks)

Per `design-spec.md` §8.3 — separate sprint plan at Phase 2 start. Workstreams:

- **Multi-reviewer + IAM RBAC** — `reviewer` / `approver` / `admin` roles; reviewer assignment; inter-annotator agreement sampling
- **Template-seen detection** — new `template_fingerprint` LangGraph node + `template_registry` Snowflake table
- **Active-learning sampling** — uncertainty + diversity over the queue
- **Soft-signal ensemble live** — semantic entropy + self-consistency added to the gate per Phase 1.5 calibration weights
- **Hybrid retrieval** — BM25 + dense via reciprocal-rank fusion
- **Document-chunk RAG activation** — `parsed_doc_chunks` becomes a retrieval target for weak-field secondary calls
- **Experiment A/B infrastructure** (new) — split live traffic between two prompts/models, log `treatment_label` column on `extractions`, compare via SQL. Distinct from one-off A/B experiments — this is the generic infrastructure for continuous experimentation.

## Phase 3 + Phase 4

Per `design-spec.md` §8.4 + §8.5 — distilled per-template SLMs (Phase 3, A/B-gated), template-specific extractor routing (Phase 3), cross-fund analytics (Phase 3), production hardening + multi-tenancy commercialization stretch + vector-store upgrade (Phase 4).
