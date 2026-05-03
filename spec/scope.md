# Project Scope — CC Distribution Parser

> Set by the AI Design Team as the final deliverable of the design phase.
> Build Lead reads this at session start to determine tier engagement.
> **Last updated:** 2026-05-02 — repackaged from 2026-04-21 design + 2026-04-28 v1.1 lock for AI Build Team intake.

## Tier

**Internal**

(Prototype | **Internal** | Production)

## Tier rationale

The design commits to Phoenix-sidecar OTel tracing in MVP Sprint 1, golden-eval CI gating via DeepEval, four-layer silent-error defense (spotlighting + schema + reconciliation + HITL), and an audit trail with full per-extraction provenance — all of which exceed Prototype scope. It does NOT yet declare formal SLOs, model card, governance memo, or Langfuse — so Production-tier governance overhead would be premature. Internal tier matches the actual commitments. Graduate to Production when Phase 1.5 ships canon + master-data integration and external users (other fund-admin orgs) appear, per the v1.1 multi-tenant Phase 4 stretch.

## Critical context — v1.1 LOCKED 2026-04-28

Three changes from the 2026-04-21 design package were locked on 2026-04-28 and are LOAD-BEARING for the build:

1. **Storage: Snowflake + SQLite + S3** (was: single Postgres + pgvector + S3). Vector store moves to Snowflake Cortex `VECTOR`. Forward-compatible `tenant_id` / `user_id` column from day 1.
2. **Canonicalization deferred to Phase 1.5** (was: MVP Sprint 3). Rationale: measure where extraction fails before building the fixer.
3. **Phoenix observability promoted to Sprint 1** (was: Phase 1.5). OTel tracing is non-negotiable from first deploy.
4. **Multi-tenancy is now Phase 4 stretch** (was: permanent non-goal). MVP design uses a `user_id` column that is forward-compatible with future `tenant_id`.

The canonical architecture document is **`spec/architecture.md`** (= design-spec.md v1.1). The 2026-04-21 `architecture.md` is superseded on storage / canon timing / multi-tenant posture and Phoenix timing.

## Skills required (from build-team inventory)

Always:
- `tdd-pytest`
- `ruff-python`
- `git-workflow`

Tier-conditional (Internal):
- `trail-of-bits-security` — must apply OWASP LLM Top 10 lens; CC parser processes untrusted PDFs (prompt-injection rule from `~/.claude/ai-build-team/rules/prompt-injection.md` is mandatory)
- `deepeval-llm` — golden eval on PRs touching prompts / schemas / models (Acceptance Criterion 8)
- `ci-cd-pipeline` — required for Acceptance Criterion 8 (CI gate)
- `backend-patterns` — applies to FastAPI ingress + worker pattern + idempotent commit
- `python-refactoring` — applies during Sprint 3+ as parser surface stabilizes

Project-specific (added to `.claude/skills/` only if introduced; central inheritance is preferred per `~/.claude/ai-build-team/templates/project/CLAUDE.md`):
- LangGraph `0.2.x` workflow conventions (pinned per Critic W3; isolated to `app/workflow/` per Scout finding on 2026 API churn)
- Bedrock Converse + Instructor + Pydantic schema-guided extraction pattern
- Snowflake Cortex `VECTOR` for few-shot retrieval (replaces pgvector per v1.1)
- HTMX + FastAPI HITL review UI (custom, ~500-800 LOC per Scout's HITL platform verdict)

## Agent roster engagement

| Agent | Engagement | Rationale |
|---|---|---|
| Build Lead | Full | Always full |
| Code Reviewer | Full | Internal tier — full Pass 1-3 (correctness + style + security smells); STRIDE deferred to Production graduation |
| AI Engineer | Light | Internal tier — eval foundations only (DeepEval pytest in `tests/evals/`, CI smoke gates); full observability stack (Langfuse + model card + governance memo + deployment config) deferred to Production |
| Pattern Scout | On | Always on; high value on this project (existing OSS for Docling, Bedrock patterns, HITL UIs) |

## Out of scope (Phase 1)

Explicitly excluded by the design — guards against scope creep at build time:

- Downstream booking into accounting systems
- Investor statement generation
- Email auto-routing beyond CC/Distro classification
- Multi-tenant admin UI (multi-tenant **DB schema** seam IS in scope; admin UI is not)
- Non-English documents
- Fine-tuning of any model
- BDA + Azure DI parsers (Phase 1.5 A/B once Docling baseline + golden-eval exist; Critic C2)
- Per-field-group decomposition (Phase 1.5 A/B; Critic C3)
- Soft-signal confidence ensemble (Phase 1.5; Critic C3)
- Master-data live integration (Phase 1.5 wiring; CSV fallback in Phase 1)
- Auto-approve threshold > 0.0 — locked at 0.0 (100% HITL) until calibration study (Acceptance Criterion 7)

## Deployment intent

**Internal-only.** AWS Bedrock VPC-hosted; single-tenant in MVP; solo reviewer Phase 1 → 2-5 reviewers Phase 2.

## Eval targets

Lifted from `spec/product-spec.md` § Success Criteria (Phase 1 release gate):

| Metric | Target |
|---|---|
| Field-level precision (post-HITL) | ≥ 98% on high-confidence fields |
| Field-level precision (raw, post-calibration) | ≥ 95% on auto-validated fields |
| Classification precision | ≥ 99% per-class F1 |
| End-to-end speed per doc | < 2 min wall-clock |
| Per-doc LLM cost | < $0.10 |
| HITL efficiency (post-ramp) | ≥ 70% of fields approved without correction |
| **Silent-error rate** | **≈ 0** — no confidently-wrong extractions reach commit |
| Time-to-labeled-500 | 3-6 months of production use |

Acceptance gates (release criteria — `product-spec.md` lines 122-134):

1. Pipeline processes PDF + DOCX + scanned-PDF end-to-end with no uncaught exceptions on 30 test docs
2. Golden eval harness passes (per-field F1 baseline + per-template baseline captured)
3. HITL UI: upload → review → approve → commit loop works end-to-end; SLO banner functions
4. All 8 Risk Register items (`spec/design-brief.md`) have mitigations implemented OR documented-as-accepted
5. All required `~/.claude/ai-build-team/rules/` modules are referenced in `CLAUDE.md` (prompt-injection + no-fabrication mandatory)
6. Drift-reports workflow writes a report file and surfaces in `git status`
7. Auto-approve threshold is `0.0` (100% HITL) in committed config, with lock comment referencing architecture §15.5 ritual plan
8. CI pipeline runs `pytest -m eval` on PRs touching prompts / schemas / models
9. `CLAUDE.md` under 200 lines; project inherits rules from central build team
10. `spec/implementation-plan.md` Sprint-0 deliverables all checked in

## Governance gates

Not applicable at Internal tier. When graduating to Production (post-Phase-1.5):

- NIST AI RMF compliance pass (AI Engineer full engagement)
- Model card per Mitchell 2019 — per-prompt-version + per-model-version
- Langfuse production observability (replaces or augments Phoenix sidecar)
- Incident-disclosure plan for silent-error escapes
- STRIDE security review (Code Reviewer Pass 4)

## Pointers to canonical artifacts

All in `spec/` (copies of design-team `team/output/cc-distribution-parser/` artifacts; design-team output remains canonical):

- `spec/architecture.md` — = `design-spec.md` v1.1 (the 2026-04-28 LOCKED reconciliation)
- `spec/implementation-plan.md` — sprint breakdown with Snowflake + canon Phase 1.5 + Phoenix Sprint 1 (header updated 2026-04-28)
- `spec/test-plan.md` — acceptance criteria → validation tests
- `spec/design-rationale.md` — per-decision Why/Tradeoff/Alternative + Interview Competency Map
- `spec/product-spec.md` — PRD; some sections superseded by v1.1 (storage, multi-tenant framing) per design-spec.md `supersedes-on:`
- `spec/design-brief.md` — original problem framing + risk register + locked invariants
- `spec/critical-review.md` — Design Critic findings (C1-C4 already incorporated; W1-W7 + O1-O3 traced in architecture §15.5)
- `spec/postmortem-template.md` — fill at Phase 1 ship

## Wiki anchor

- **Central wiki:** `~/.claude/ai-design-team/wiki/` — topic notes for `document-ai-extraction`, `llm-confidence-calibration`, `llm-cost-optimization`, `prompt-injection-defense` are listed as **compilation candidates** in `wiki/index.md` (not yet compiled — raw notes available as fallback).
- **Raw notes:** `~/.claude/ai-design-team/wiki/raw/2026-04-21-{market-scout,analyst}-cc-distribution-parser.md` — useable as-is until compilation.
- **Project-local wiki:** `wiki/` — populated during build with project-specific lessons.
