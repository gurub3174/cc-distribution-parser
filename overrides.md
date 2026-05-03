# Project Overrides — cc-distribution-parser

Project-specific **deviations** from build-team defaults. For project-specific **rules** (not deviations), see `.claude/rules/`.

## Format

```markdown
## Override: <short title>
**Default (from build team):** <what build team's rule says>
**Override:** <what this project does instead>
**Why:** <reason>
**Reference:** <which build-team rule file is being overridden>
```

## Context — hybrid rules pattern (2026-05-03 reconciliation)

Three patterns were considered for where rules live:
- **A — pure central + single overrides.md** (initial 2026-05-02 scaffold choice). Drawback: project-specific rules like Snowflake DDL policy or LangGraph swap playbook don't fit "deviations" semantics; one mega-file loses contextual loading.
- **B — hybrid (current).** Generic rules (`code-style`, `no-fabrication`, `prompt-injection`, `wiki-conventions`) inherit from `~/.claude/ai-build-team/rules/`. Project-specific rules live in `.claude/rules/` — they're not overrides of anything, they encode this project's own decisions. `overrides.md` is **only** for deviations from central rules.
- **C — pure per-project** per `~/.claude/ai-design-team/wiki/user/conventions.md` (2026-04-20). Drawback: duplicates central rules across every project, drift risk.

This project uses **B**. Surfaced explicitly per the user's "conventions are guidelines, not religion" feedback. Effect on `~/.claude/ai-design-team/wiki/user/conventions.md`: the per-project-claude/rules convention is **partially superseded** — generic rules centralize, project-specific stays local.

## Overrides

## Override: prompt-injection elevated to non-negotiable
**Default (from build team):** `~/.claude/ai-build-team/rules/prompt-injection.md` — wrap untrusted text in `<untrusted_source>` blocks.
**Override:** ALL PDF/DOCX extraction MUST use Spotlighting per Hines et al. 2024 (`arXiv:2403.14720`). Delimiter + system-prompt marking required at every extraction call. No exceptions for Phase 1; multi-layer defense (spotlighting + schema + reconciliation invariants + HITL gate) is the load-bearing silent-error mitigation.
**Why:** CC parser processes externally-sourced money-moving documents. Injection success rate must drop below 2% (paper claim) and HITL is the final layer — bypass at any layer is a money-loss event.
**Reference:** central `prompt-injection.md`; project `spec/architecture.md` §11 (defense-in-depth); `spec/critical-review.md` C1-C4 + W2.

## Override: no-fabrication adds CC-specific arithmetic invariant
**Default (from build team):** `~/.claude/ai-build-team/rules/no-fabrication.md` — extracted content must be grounded in source; cite or refuse.
**Override:** Capital Call schema additionally enforces `unfunded_before_call - capital_call_amount = unfunded_after_call` when both fields are present. Validator rejects extractions that satisfy schema but violate this invariant. Enforced at the validator step (NOT just at HITL review) so silent commits cannot pass through.
**Why:** This invariant is the single highest-value silent-error detector in the design (Critic C1, design-spec.md §3). Schema-only enforcement misses arithmetic-consistent hallucinations.
**Reference:** central `no-fabrication.md`; project `spec/architecture.md` §6 (validation); `spec/design-brief.md` (locked invariant from user clarification).

## Override: LangGraph pinned exact, isolated to `app/workflow/`
**Default (from build team):** No specific LangGraph pin in central rules.
**Override:** LangGraph pinned to `~=0.2.0` (exact `0.2.x`). All LangGraph code lives in `src/cc_distribution_parser/workflow/` and nowhere else. No LangGraph imports in `core/`, `models/`, `parsers/`, `hitl/`.
**Why:** Market Scout 2026-04-21 finding — LangGraph carries 2026 API-churn risk. Critic W3 mandated isolation so a future swap (Temporal, Prefect, plain-Python state machine) is a one-directory rewrite.
**Reference:** `spec/market-research.md`; `spec/critical-review.md` W3; `spec/architecture.md` §4.

## Override: Snowflake replaces pgvector for vector store
**Default (from build team):** No vector store default.
**Override:** Few-shot exemplar retrieval uses Snowflake Cortex `VECTOR` type with cosine similarity. SQLite stores LangGraph PostgresSaver checkpoints (Phase 1 single-host); S3 holds doc binaries. Postgres + pgvector is NOT a fallback — design-spec v1.1 LOCKED this on 2026-04-28.
**Why:** v1.1 lock — Snowflake exists in tenant; one fewer service to operate; aligned with future master-data integration which lives in Snowflake.
**Reference:** `spec/architecture.md` §4.3 (storage); `spec/scope.md` Critical Context.

## Override: Auto-approve threshold locked at 0.0 (100% HITL) until calibration study
**Default (from build team):** No central HITL threshold rule.
**Override:** `auto_approve_threshold = 0.0` in committed config. Lock comment in source must reference `spec/architecture.md` §15.5 ritual plan. Threshold can ONLY be raised after a calibration study; CI must fail if the value is changed without an accompanying threshold-unlock change-log entry.
**Why:** Acceptance Criterion 7. Silent-error tolerance is ≈ 0; raising threshold without measured calibration is the single fastest path to the failure mode the design exists to prevent.
**Reference:** `spec/scope.md` Eval Targets; `spec/architecture.md` §15.5.
