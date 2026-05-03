---
project: cc-distribution-parser
type: product-spec
created: 2026-04-21
status: approved
author: design-lead
version: 1.0
---

# Product Spec — Capital Call & Distribution Parser

## Overview

An internal document-extraction pipeline for a fund administrator, parsing unstructured capital call and distribution notices (PDF + DOCX) into structured fields with human-in-the-loop verification. Designed as the MVP foundation of an internal **Canoe Intelligence replacement**.

**Dual-purpose project:**
- **Operational tool** — compresses manual extraction time, reduces audit exposure from transcription errors
- **AI engineering portfolio piece** — demonstrates enterprise-grade MVP with production practices (schema-guided LLM extraction, HITL flywheel, CI-enforced eval, observability, drift detection, prompt-injection defense)

## Personas

### Primary — Ops Reviewer (Phase 1: solo user)
Fund-administration operations analyst who currently extracts capital-call and distribution fields manually from GP-issued PDF/DOCX notices. Reviewer validates and corrects LLM extractions before they commit downstream.

Goals: reduce keystrokes per doc; reduce risk of transcription errors; maintain audit trail; zero silent misextractions.

Pain points today: 10-50 different GP templates means no single "rule" works; vocabulary varies (unfunded vs uncalled vs remaining); LP/GP names have many aliases; per-doc manual extraction takes meaningful time.

### Secondary — Eng/Admin (Phase 2)
Team of 2-5 reviewers with role-based access; need assignment, inter-annotator agreement sampling, per-user queue.

### Implicit — Auditor (all phases)
Every extraction must be auditable: which doc, which model, which prompt version, which few-shots, what confidence signals, who approved.

## Problem Statement

Capital call and distribution notices are semi-structured financial instructions (a wrong extracted dollar amount moves real money incorrectly). Each GP issues its own template, with high variation across GPs and subtle variation within a given GP's templates over time. Fields are often labeled inconsistently ("unfunded commitment" vs "uncalled capital" vs "remaining commitment"). Some fields are omitted entirely. LP and GP names vary in form (legal name, DBA, abbreviation). Manual extraction is slow and error-prone.

Existing tools (Canoe Intelligence, Hercules AI, Allvue, Formulary) are commercial. An internal alternative that the company can extend, that integrates with the company's master-data systems, and that produces an ongoing ground-truth corpus for future fine-tuning is strategically valuable.

## Constraints

| Constraint | Value |
|---|---|
| LLM deployment | **AWS Bedrock** (VPC-hosted) |
| Ground-truth labels (at start) | **<50 labeled docs** |
| Volume | **100-1000 docs/month, 10-50 distinct templates** |
| File formats | **PDF (text + scanned) + DOCX** |
| Reviewer model | **Solo MVP → 2-5 post-MVP** |
| Runtime | **Python service** (not Claude Code); Claude Code project structure per conventions |
| Cloud lock-in | AWS acceptable; Azure optional (Phase 1.5 A/B parser, if user confirms subscription) |
| Master-data access | **Exists but restricted/slow**; Phase 1 seam + CSV fallback |
| Timeline | **Phase 1 MVP: 5-6 weeks solo dev** (post-scope-cut per Critic review) |
| Language | English documents only in scope |

## Success Criteria

### Phase 1 MVP — Measurable Targets

| Metric | Target | Measurement |
|---|---|---|
| Field-level precision (post-HITL) | ≥ 98% on high-confidence fields | Per-field accuracy on committed extractions vs ground truth |
| Field-level precision (raw) | ≥ 95% on auto-validated fields after calibration study | Per-field accuracy on auto-committed extractions |
| Classification precision | ≥ 99% | Per-class F1 on golden eval |
| Speed per doc | < 2 min end-to-end | Wall-clock parse + classify + extract + present to reviewer |
| Cost per doc | < $0.10 | Per-doc LLM inference cost (Bedrock usage) |
| HITL efficiency | ≥ 70% of fields approved without correction (after phase-1 ramp) | Correction rate in audit log |
| **Silent-error rate** | ≈ 0 | No confidently-wrong extractions pass to commit |
| Time-to-labeled-500 | 3-6 months of production use | Cumulative HITL-approved exemplars |

### Non-targets (explicitly out of scope for Phase 1)
- Downstream booking into accounting systems
- Investor statement generation
- Email auto-routing beyond CC/Distro classification
- Multi-tenant admin UI
- Non-English documents
- Fine-tuning

## Functional Scope (Phase 1)

### Features
- **Upload intake** — PDF or DOCX via HTTP upload (FastAPI endpoint); emails/SFTP/API integrations = Phase 2
- **Document parsing** — Docling with `spacy-layout` (Phase 1.5 adds BDA + optional Azure DI)
- **Classification** — 3-class: `capital_call` | `distribution` | `other_or_reject`
- **Extraction** — polymorphic by class, 9-field CC schema or 8-field Distribution schema; reasoning-first; schema-guided via Bedrock Converse + Instructor + Pydantic
- **Canonicalization** — number, date, currency, name, vocabulary variant normalization
- **Master-data lookup** — rapidfuzz against a fund/GP/LP CSV; real master integration Phase 1.5+
- **Validation** — Pydantic types + domain reconciliation (unfunded before/after invariant primary); hard-signal tri-state per field
- **HITL review** — custom FastAPI + HTMX review UI; per-field approve/reject; bulk-approve-validated; reclassify button; flag-as-new-vocab
- **Audit trail** — every extraction + every correction with full provenance
- **Eval harness** — golden set (20-30 docs across 5+ templates, growing); `pytest -m eval`; per-field + per-template metrics
- **CI gate** — golden eval replay required on PRs touching prompts / schemas / models
- **Drift detection** — weekly drift report file; correction-rate tracking
- **Observability** — structured logs + OTel spans; per-doc cost attribution
- **Prompt injection defense** — spotlighting + schema + reconciliation + HITL (5 layers)

### Extraction Schemas

**Capital Call (9 fields):** reasoning, fund_name, fund_id, gp_name, lp_name, capital_call_date, due_date, commitment_total, capital_call_amount, **unfunded_before_call**, **unfunded_after_call**, currency

Arithmetic invariant: `unfunded_before_call − capital_call_amount = unfunded_after_call` (when both present).

**Distribution (8 fields):** reasoning, fund_name, fund_id, gp_name, lp_name, distribution_date, payment_date, distribution_amount, distribution_type (enum: income / return_of_capital / realized_gain / other), currency

## Non-Functional Requirements

- **Security**: PII + financial data stays in AWS tenant; encrypted at-rest (S3 + RDS) + in-transit (TLS 1.3); secrets via AWS Secrets Manager; audit append-only
- **Compliance**: 7-year default retention; WORM-style audit immutability via append-only + `superseded_by`
- **Reliability**: LangGraph PostgresSaver checkpointing; idempotent commit step; `SELECT FOR UPDATE SKIP LOCKED` worker pattern
- **Observability**: per-span cost + tokens + model version + prompt version captured; per-doc rollup
- **Recoverability**: full provenance enables replay of any extraction; Alembic migrations reversible
- **Extensibility**: `ParserProtocol`, `Instructor` provider abstraction, multi-user DB schema from day 1
- **Portability**: AWS-primary with provider-swap seams (LLM via Instructor, parser via Protocol, observability via OTel)

## Stakeholders

- **Product owner / Operator (user)** — AI engineer in-training at the fund admin company; solo dev + solo reviewer for MVP
- **End reviewer (same person, Phase 1)** → team of 2-5 (Phase 2)
- **Compliance / Audit** — reviews audit trail on demand
- **Fund admin IT** — gates master-data access (currently restricted/slow)

## Acceptance Criteria (Phase 1 release gate)

1. Pipeline processes PDF + DOCX + scanned-PDF end-to-end with no uncaught exceptions on 30 test docs
2. Golden eval harness passes (per-field F1 at baseline, per-template baseline captured)
3. HITL UI: upload → review → approve → commit loop works end-to-end; SLO banner functions
4. All 8 Risk Register items (Design Brief) have mitigations implemented OR documented-as-accepted
5. All 5 rule files in `claude/rules/` exist and are referenced in `CLAUDE.md`
6. Drift-reports workflow writes a report file and surfaces in git status
7. Auto-approve threshold is `0.0` (100% HITL) in committed config, with lock comment referencing §15.5 ritual plan
8. CI pipeline runs `pytest -m eval` on PRs touching prompts / schemas / models
9. CLAUDE.md under 200 lines; `claude/rules/` modular
10. `implementation-plan.md` sprint-0 deliverables all checked in

## Roadmap

See `architecture.md §15` for the phased roadmap (Phase 1 5-6 weeks / Phase 1.5 2-4 weeks / Phase 2 4-8 weeks / Phase 3 quarters / Phase 4 open).

## Open Questions

See `architecture.md §16` — none block Phase 1 start.
