---
project: cc-distribution-parser
type: design-brief
created: 2026-04-21
updated: 2026-04-21
status: confirmed
owner: user (fund-admin operator + AI engineer in-training)
---

# Design Brief — Capital Call & Distribution Parser

## Parsed Goal

Build a Python-based document-ingestion and information-extraction pipeline that:

1. Ingests unstructured **capital call notices** and **distribution notices** (PDFs, possibly scanned, possibly email-embedded) from fund General Partners.
2. Classifies each document as **Capital Call** or **Distribution**.
3. Extracts **10 pre-defined fields** with calibrated confidence scores.
4. Surfaces results to a human reviewer (HITL) before the extractions are committed downstream.
5. Captures human corrections as a ground-truth labeling flywheel that enables future fine-tuning.

## Dual Purpose

- **Skill-building for AI engineer job search** — target enterprise/production competency (system design, cost optimization, reliability, LLM ops, DevOps, security). Project deliverables include the standard `design-rationale.md` with Interview Angles per decision.
- **Real tool for employer (fund administrator)** — accelerate manual extraction, reduce keystrokes per doc, reduce audit exposure from transcription errors.

These goals are aligned. Staged **POC → MVP → Production → Enterprise** roadmap lets the tool deliver value early while maturing into interview-grade infrastructure.

## Domain Stakes

- Capital calls and distributions are **financial instructions**. Wrong dollar amount, wrong fund, wrong investor ID = real money moves incorrectly. This is a **low-tolerance-for-false-confidence** domain. The worst failure mode is silent misextraction — confident wrong answers.
- Documents are **semi-structured**: each GP re-uses their own template, but templates vary widely across GPs. Template-aware strategies often outperform pure "throw-it-at-an-LLM" approaches at this variance level.
- **PII + financial sensitivity** constrain LLM API choice (see confirmed constraints below).

## Confirmed Constraints

| Constraint | Answer | Architectural consequence |
|---|---|---|
| LLM deployment | **AWS Bedrock** (VPC-hosted) | Claude on Bedrock + Bedrock Data Automation + Titan/Cohere embeddings + Textract fallback. |
| Ground-truth data | **<50 labeled docs** currently | Fine-tuning deferred to phase 3+; phase 1 relies on zero/few-shot with frontier models; HITL loop is the labeling pipeline |
| Volume & variety | **100-1000 docs/mo, 10-50 templates** | Cascade (cheap → expensive) justified for phase 1.5; template-aware extraction for recurring formats |
| Master-data access | **Exists but access is restricted/slow/ops-dependent** | Reference-data lookup (fund master, investor master) designed as **optional integration seam**. Phase 1 works without it; phase 2 connects when access resolved. |
| Runtime | **Python service, NOT Claude Code** (per-project override of Claude-Code-only convention) | Docling, LangGraph, Bedrock SDKs all require Python. Convention override is explicit and deliberate. |
| Project location | `C:\projects\cc-distribution-parser\` | Per user conventions — sidesteps apostrophe-path issue |
| Structure | Claude Code project template (CLAUDE.md + `claude/{rules,commands,skills,agents,hooks}` + `mcp.json` + Python code as siblings) | Mandatory per user conventions |
| Product vision | **Greenfield internal Canoe replacement** — MVP is phase-1 basics, vision extends to full coverage | Scope MVP tightly; design with extension seams for the full vision (multi-reviewer, fine-tuning, active learning, template-specific extractors) |
| MVP philosophy | **Enterprise-adjacent MVP without over-engineering** — LangGraph included (pinned + isolated); embeddings + vector store included for continuous-improvement narrative; fine-tuning + full-GraphRAG OUT | LangGraph orchestrates the pipeline; pgvector stores embeddings + few-shot exemplars; hybrid BM25+dense retrieval; metadata-filtered search via SQL on pgvector |
| Reviewer model | **Solo (me) for MVP → 2-5 post-MVP** | Custom FastAPI + HTMX UI with auth-ready extension seams. Multi-reviewer features (assignment, IAA sampling) in phase 2. |

## Pushback Acknowledged Up Front

User opened with a rich tool list. Rough initial verdicts (to be confirmed/reversed by Market Scout + Research Analyst):

| Technique | Initial verdict | Reasoning |
|---|---|---|
| Docling parsing | ✅ Strong fit, but survey AWS Textract + Bedrock Data Automation + Azure Document Intelligence as alternatives | PDF + layout-aware is the whole point; native cloud services may already cover 60% of the problem |
| HITL review | ✅ Non-negotiable | Financial domain demands it |
| Cheap → expensive LLM cascade | ✅ Proven cost pattern | FrugalGPT lineage + disagreement gating |
| Deterministic rules for known-format fields | ✅ Critical | Many CC/Distro fields (fund names, dates, amounts with labels) are regex-first |
| **Schema-guided generation** (function calling / Pydantic / Instructor / BAML) | ✅ **Locked for phase 1** | Eliminates format errors; near-zero cost to add; critical at sparse-data scale |
| **Dynamic few-shot retrieval** (kNN over prior extractions) | ✅ **Locked for phase 1** | Compounds value of every HITL correction; works even at 20-30 labels |
| Self-consistency / ensemble voting | 🟡 Phase 2 | 3× cost buys better calibration but not required initially |
| Weak supervision / programmatic labeling (Snorkel-style) | 🟡 Phase 2 | Accelerates fine-tune path; adds complexity; defer |
| LangGraph orchestration | 🟡 Likely fit, evaluate alternatives (Prefect, Temporal, plain state machine, BAML) | Deterministic workflow ≠ auto-need for LangGraph |
| RAG over prior extractions | 🟡 Used ONLY for few-shot retrieval, not "live learning" | Learning = HITL flywheel → periodic fine-tune, not live retrieval |
| GraphRAG | 🔴 Likely overkill | 10-field per-doc extraction doesn't need KG navigation |
| Fine-tuning | 🟡 Deferred to phase 3 | No ground truth yet; build the flywheel first |
| GPU-intensive synthesis | 🔴 Unclear need | Frontier models via Bedrock beat self-hosted at this volume |

Every verdict must be grounded with market + research evidence before locking the architecture.

## Success Criteria (working target — refine during Architecture phase)

- **Field-level precision:** ≥ 98% on high-confidence fields after HITL, ≥ 95% raw (industry bar for financial IE)
- **Classification precision:** ≥ 99% (CC vs Distribution is binary and easy for LLMs)
- **Speed per doc:** < 2 min end-to-end
- **Cost per doc:** < $0.10 target
- **HITL efficiency:** ≥ 70% of fields approved without correction after phase 1 ramp
- **Silent-error rate:** ≈ 0 — system MUST flag low-confidence extractions, never confidently extract wrong values
- **Time-to-labeled-500:** target reaching 500 labeled examples within 3-6 months of production use (unlocks fine-tuning option)

## Scope

**In scope (phase 1):**
- **Polymorphic document ingestion** — PDF (text + scanned) + DOCX (tooling TBD per Scout)
- Classification (Capital Call vs Distribution vs Other/Reject)
- **Polymorphic extraction** — 9 CC fields OR 8 Distribution fields based on classification
- **Schema-guided generation** (Pydantic-validated output, per doc-type schema)
- **Dynamic few-shot retrieval** over labeled corpus (per doc-type)
- **Domain vocabulary dictionary** + canonicalization layer (variant → canonical)
- **Tri-state field status** (absent / failed / low-conf)
- **Reconciliation validators** (arithmetic invariants, date ordering)
- HITL review workflow that doubles as labeling pipeline
- Audit trail with per-extraction provenance (chunk ID, model ID, prompt version, confidence)
- Template detection and fingerprint cache for recurring GPs (optimization, not gating)
- **Reference-data lookup seam** (phase 1: code path + mock; phase 1.5-2: wired to real master data)
- Golden eval set + continuous eval harness
- Cost attribution per doc

**Future scope (phase 2):**
- Reference-data lookup **populated** (master-data integration wired up)
- Self-consistency / ensemble voting
- Weak supervision / bootstrap labeling
- Active learning sampling (send most-ambiguous docs to HITL first)
- Reviewer efficiency UX improvements

**Future scope (phase 3+):**
- Fine-tuning on accumulated labels
- Template-specific extractors
- Model distillation to cheaper serving tier

**Out of scope:**
- Downstream booking into accounting systems
- Investor statement generation
- Email auto-routing / classification beyond CC/Distro
- Multi-tenant admin UI
- Non-English documents (flag as assumption)

## Sparse-Data Architecture Requirements (Phase 1)

Because we start at <50 labeled docs, the following patterns are design requirements, not optional:

1. **Schema-guided generation** — extraction output conforms to a Pydantic schema enforced at decode time (via function calling, JSON mode, or Instructor/Outlines library). Eliminates ~30% of zero-shot failures that are format errors, not semantic.
2. **Dynamic few-shot retrieval** — at inference, retrieve the k=3-5 most-similar prior extractions by embedding similarity and inject as in-context examples. Storage: every HITL-approved extraction becomes a future few-shot exemplar.
3. **Task decomposition** — extract fields in per-field or per-field-group prompts rather than one mega-prompt. Each sub-task is easier; failures attribute to the step that caused them.
4. **Confidence calibration via structured signals** — use schema-adherence, logprob-based signals, rule-agreement, and (phase 2) self-consistency disagreement. NOT direct "how confident 0-100?" probing (LLMs miscalibrate that).
5. **Chunk-level RAG within document** — for long docs, retrieve relevant chunks before extraction (not full-doc dump). Reduces tokens and noise.

## MLOps & Reliability Requirements (Phase 1)

Locked-in production discipline — not optional even for POC:

1. **Prompt + model versioning** — every extraction record `{prompt_version, model_id, temperature, timestamp, few_shots_used[]}`. Required for audit + regression tracking.
2. **Golden eval set** — reserve a small (start 10, grow to 50+) labeled set that NEVER touches prompting/tuning. Every change replays it.
3. **Continuous eval harness** — automated run on golden set with every prompt/model change. Per-field accuracy deltas reported.
4. **Drift detection** — track HITL correction rate per field per week; alert on increase. Template drift, model-version drift both surface through this metric.
5. **Provider abstraction layer** — thin wrapper around Bedrock/Azure/Vertex so the LLM provider is swappable without re-platforming.
6. **Cost attribution per doc** — log token usage per call; per-doc cost rollup. Required for ROI proof and unit-economics-based decision-making.
7. **Prompt injection defense** — add `claude/rules/prompt-injection.md`; treat document text as untrusted input in system prompts; post-hoc reconciliation validators catch manipulation attempts.

## Financial Domain Considerations (user-validated from operator experience)

### Locked-in from user's domain input (2026-04-21)

1. **LP/GP name variation is HIGH** — many aliases, legal vs DBA, abbreviations. Free-form LLM extraction is unreliable here. **Master-data lookup priority elevated from phase-2-nice-to-have → phase-1 strongly desired.** Even a read-only CSV export of your fund/investor master gets most of the win. Phase-1 design MUST include the lookup seam; phase 1.5 wires it up; phase 2 formalizes.
2. **Vocabulary variation on commitment terms** — "unfunded commitment" vs "uncalled capital" vs "remaining commitment" vs "funded" vs "contributed" — many variants for the same semantic field. Design includes:
   - **Domain vocabulary dictionary** (variant → canonical) injected into extraction prompts as hints
   - **Post-extraction canonicalization layer** (spaCy pattern matchers or regex table) normalizing variants
3. **Fields may be omitted in-doc** — schema allows optional/nullable; HITL surfaces three distinct states per field:
   - `absent_in_doc` (doc legitimately doesn't contain it)
   - `extraction_failed` (doc has it but parser couldn't locate it)
   - `extracted_low_confidence` (found but uncertain)
   Each routes differently: absent = accept-as-null; failed = re-run with stronger model; low-conf = HITL queue.
4. **Mixed file formats: PDF + DOCX** — pipeline needs polymorphic ingest layer. DOCX text is often cleaner than PDF text; scanned-PDF requires OCR. Three code paths. **Parser must not assume PDF-first.**
5. **Templates vary greatly** — confirms **general LLM extraction is the primary pipeline; template matching is a cost optimizer, not the core strategy.** Don't over-invest in template caching until volume per template justifies it.

### Standing domain concerns

1. **Number canonicalization** — `$1,234,567.89`, `1.23M`, `(1,234,567.89)` (accounting negative), foreign thousand-separators → canonical `Decimal`.
2. **Date disambiguation** — `01/02/2026` context-resolution (GP-template locale inference).
3. **Multi-currency handling** — distributions often include FX-converted lines; extract per-currency, not just total.
4. **Reconciliation checks** — arithmetic invariants per schema:
   - **CC:** `Commitment - Unfunded (after) = cumulative called`; `Unfunded (before) - Capital call amount = Unfunded (after)`
   - **Distribution:** `Distribution amount` consistency if per-investor breakdown present
   - Date ordering: call_date ≤ due_date; distribution_date ≤ payment_date
   Violations auto-flag for HITL regardless of individual field confidence. Cheap silent-error catch.
5. **Document versioning / superseding notices** — detect when a doc is a corrected version of a prior notice. Don't double-book. (Open question for user workflow.)
6. **Signature / authorization** — low-priority verification pass; flag for later.

## HITL / Labeling Flywheel Design Requirements

The labeling pipeline IS the strategic asset. Design requirements:

1. **Active learning sampling (phase 2)** — uncertainty sampling routes ambiguous docs to HITL first. Max info gain per reviewer-minute.
2. **Inter-annotator agreement (if multi-reviewer)** — sample 5-10% double-review to measure label quality.
3. **Correction attribution** — track which fields, models, templates get corrected most. Surfaces weak prompts and weak rules directly.
4. **Golden set promotion workflow** — reviewers can flag "clean, representative example" → eligible for promotion to golden eval set (with second-reviewer sign-off).
5. **Reviewer UX priorities** — keyboard-first, bulk-approve high-confidence fields, attention routed to flagged fields only. Per-doc review time is the KPI.
6. **Ritual health (pre-mortem concern)** — reviewing must happen in the reviewer's existing workflow, not a context-switch. If reviewers stop using it, the flywheel stops silently. Design for automatic triggers and visible queue state.

## Risk Register (pre-mortem seeds for Design Critic)

| # | Risk | Likelihood | Impact | Phase-1 mitigation |
|---|---|---|---|---|
| R1 | Sparse-data cold start → poor initial accuracy | High | Medium | Low auto-approve threshold initially; expect high HITL burden for 2-3 months; measure convergence |
| R2 | HITL fatigue / ritual decay | Medium | High | Integrate into existing workflow; visible queue; correction-rate dashboard |
| R3 | Template drift | Medium | Medium | Drift detection via HITL correction rate; template fingerprints expire |
| R4 | LLM provider deprecation | Medium | Low | Provider abstraction layer; re-eval cadence |
| R5 | Over-trust (auto-approve threshold too high too early) | Medium | Very High | Start threshold low; require eval evidence before raising |
| R6 | Prompt injection via document text | Low | High | Untrusted-input sandbox; post-hoc reconciliation validators |
| R7 | Silent regression on prompt change | Medium | High | Continuous eval harness gates deployments |
| R8 | Scope creep toward "universal doc parser" | High | Medium | 10 fields, 2 classes, phase 1. Critic enforces. |

## Extraction Schemas (polymorphic by document type — locked)

**Decision:** Classification happens first, then extraction applies the correct schema per doc type. This is cleaner than a union schema (no permanent-null fields per doc type) and matches the real domain structure.

### Capital Call schema (9 fields)

| # | Field | Type | Notes |
|---|---|---|---|
| 1 | Fund name / ID | string, optional | Cross-checks against fund master in phase 2 |
| 2 | GP / Manager name | string, required | High-variation; normalization + master-data lookup critical |
| 3 | LP / Investor name | string, required | High-variation; normalization + master-data lookup critical |
| 4 | Capital call date | date, required | Document date — distinguish from due date |
| 5 | Due date | date, required | When LP must wire funds |
| 6 | Commitment (total) | Decimal + currency, optional | Arithmetic-checked with unfunded |
| 7 | Capital call amount | Decimal + currency, required | The called amount for this notice |
| 8 | Unfunded commitment | Decimal + currency, optional | Arithmetic-checked |
| 9 | Currency | ISO-4217 string, required | Normalized per-field and across doc |

**Arithmetic invariant:** `Commitment - Unfunded (after call) = cumulative called`. `Unfunded (before) - Capital call amount = Unfunded (after)`. Post-extraction reconciliation enforces; violation → auto-flag for HITL regardless of individual field confidence.

### Distribution schema (8 fields)

| # | Field | Type | Notes |
|---|---|---|---|
| 1 | Fund name / ID | string, optional | Cross-checks against fund master in phase 2 |
| 2 | GP / Manager name | string, required | Shared normalization w/ CC |
| 3 | LP / Investor name | string, required | Shared normalization w/ CC |
| 4 | Distribution date | date, required | Effective date |
| 5 | Payment date | date, required | When LP actually receives funds |
| 6 | Distribution amount | Decimal + currency, required | Total distributed |
| 7 | Distribution type | enum: income \| return_of_capital \| realized_gain \| other | Tax-relevant classification |
| 8 | Currency | ISO-4217 string, required | |

### Shared infrastructure (both schemas)

- Currency normalization and multi-currency handling (per-currency lines if FX conversions present)
- Name normalization (LP/GP canonicalization before master-data lookup)
- Date disambiguation (MM/DD vs DD/MM from GP-template locale)
- **Field-absence tri-state:** every field distinguishes `absent_in_doc` / `extraction_failed` / `extracted_low_confidence` — HITL surfaces each differently

## Open Questions for Architecture Phase

1. **The 10 fields — exact list needed.** User supplies during Architecture phase.
2. **Which 3-5 fund GPs generate the most volume?** — Template-aware extraction starts there.
3. **Does your company have an existing web UI or workflow tool the reviewer uses today?** — Determines HITL as new web app vs handoff into existing tooling.
4. **Cloud preference** — AWS Bedrock, Azure OpenAI, or GCP Vertex? (Affects Bedrock Knowledge Bases vs Azure AI Search vs Vertex + Native services.)
5. **Who's the production operator?** — You alone, a team, an ops/IT group?
6. **Budget ceiling** — is there a real dollar cap per month on LLM inference for this tool?
7. **Document ingestion source** — email attachment, SFTP drop, manual upload, API?
8. **Downstream handoff** — where do approved extractions go? (CSV export, API, database write?)
9. **Superseding-notice handling** — how does your current workflow treat corrected CC/Distribution notices?
10. **Multi-currency prevalence** — what fraction of docs have non-USD or FX-converted lines?

## Pipeline Plan (SOP Step 2.5)

- ✅ **Market Scout** — REQUIRED. Tooling landscape spans: docling + **spacy-layout** + AWS Textract + Bedrock Data Automation + Azure Document Intelligence (PDF AND DOCX handling); orchestration frameworks (LangGraph, Prefect, Temporal, plain state machine, BAML); RAG in VPC contexts (Bedrock Knowledge Bases, Azure AI Search, pgvector, Haystack); HITL platforms (Argilla, Label Studio, Prodigy); schema-guided generation libraries (Instructor, Outlines, BAML, native function calling); LLM tracing/eval tools self-hostable (Braintrust, Langfuse, Phoenix, LangSmith self-host); fin-services IE precedents (Hebbia, Eigen, Kensho, Ocrolus, Klarity, Intapp).
- ✅ **Research Analyst** — REQUIRED. Literature covers IE from semi-structured docs (LayoutLM, Donut, LMDX, DocLLM), LLM cascades (FrugalGPT and successors), confidence calibration (Kadavath, SelfCheckGPT, FActScore), task decomposition, dynamic few-shot, HITL design + active learning, prompt injection defense, few-shot vs fine-tune performance curves at sparse-data scale.
- ✅ **Design Critic** — REQUIRED. Financial-domain production deployment = highest-risk context; silent-error-tolerance = 0; pre-mortem on the 8 risks above.

## Pipeline Flow (preview — Architecture finalizes)

```
Doc arrives (PDF | DOCX | scanned-PDF)
      │
      ▼
Polymorphic parser (docling + spacy-layout / Textract / Doc Intelligence)
      │
      ▼
Classifier (cheap model, schema-guided: CC | Distribution | Other/Reject)
      │
      ▼
Template detector (fingerprint cache — optional optimization)
      │
      ▼
Route to polymorphic schema based on class:
      │
  ┌───┴────────┐
  ▼            ▼
[CC schema  [Distribution
 extractor]  schema extractor]
  │            │
  └─────┬──────┘
        │
        ▼
Extraction (schema-guided + dynamic few-shot + domain vocab hints)
        │
        ▼
Canonicalization layer (variant → canonical; number/date/currency/name)
        │
        ▼
Reconciliation validators (arithmetic invariants, date ordering)
        │
        ▼
[optional] Master-data lookup (phase 1: seam / phase 2: wired)
        │
        ▼
Confidence scoring + tri-state (absent / failed / low-conf)
        │
  ┌─────┴──────────────┐
  ▼                    ▼
High-confidence   Low-confidence / flagged
(auto-commit)     (HITL queue)
  │                    │
  └─────────┬──────────┘
            ▼
  Labeled output → provenance store + eval replay
            │
            ▼
  Labeling flywheel → phase-3 fine-tune trigger
```

## Next Step

Launch Market Scout + Research Analyst in parallel with the expanded research scope above.
