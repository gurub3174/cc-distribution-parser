---
project: cc-distribution-parser
type: design-rationale
created: 2026-04-21
author: design-lead
status: final
purpose: Teaching + interview-prep layer for the architecture decisions
---

# Design Rationale — Capital Call & Distribution Parser

This document converts the architectural decisions into durable learning and interview-prep material. Four parts:

1. **Part 1 — Architectural Decisions** with Interview Angle per decision
2. **Part 2 — Research Dossier** (load-bearing evidence graded by how much the design rests on it)
3. **Part 3 — POC → Enterprise Roadmap** (staged practice adoption)
4. **Part 4 — Interview Competency Map** (decisions → AI engineering competencies + skill level)

---

## Part 1 — Architectural Decisions with Interview Angles

Each decision is framed: **WHAT** → **WHY** → **TRADE-OFF** → **ALTERNATIVE REJECTED** → **REVISIT TRIGGER** → **INTERVIEW ANGLE** (sample question + strong-answer ingredients + competency tags + skill level).

---

### Decision 1 — Monolithic extraction (Phase 1), per-field-group decomposition (Phase 1.5 A/B)

**What:** Single Sonnet call per doc per schema in Phase 1; A/B against decomposed in Phase 1.5.

**Why:** Research on decomposition (Khot 2023 DecomP) is strong for reasoning tasks; extraction-specific evidence is thin (Analyst Research Gap #2). Decomposition is 4-5× cost (LLM calls × input tokens). Shipping monolithic then A/B is rigorous and cheap.

**Trade-off:** Monolithic may be weaker on specific field groups (date locale, name canonicalization). We measure per-field accuracy and decompose only the groups that underperform, rather than blanket-decomposing.

**Alternative rejected:** Ship decomposed Phase 1. Cost-prohibitive without empirical justification; locks in the expensive path before measurement.

**Revisit trigger:** Phase 1.5 A/B results; monolithic baseline accuracy per field group.

**Interview Angle:**
> "How do you decide whether to decompose a multi-field LLM extraction task into per-field or per-field-group prompts?"

Strong answer covers:
- The cost multiplier (per-call pricing × input token re-broadcast)
- Research support for decomposition in reasoning tasks (DecomP) vs thin extraction-specific evidence
- The scientific order (ship monolithic baseline → measure per-field accuracy → decompose targeted weak groups)
- Prompt caching as a mitigator (shared system prompt across decomposed sub-prompts)
- Why "always decompose" is overfitting to general LLM advice

**Competency tags:** `system-design` `cost-optimization` `eval-driven-development`
**Skill level:** Mid → Senior (cost-awareness is the senior differentiator)

---

### Decision 2 — CC schema splits `unfunded` into `before_call` and `after_call`

**What:** `CapitalCallV1` has both `unfunded_before_call: Optional[Decimal]` and `unfunded_after_call: Optional[Decimal]`; reconciliation invariant enforces `abs((before - call) - after) < 0.01` when both present.

**Why:** User's domain input specified the invariant `Unfunded(before) − Capital_call = Unfunded(after)`. With only one `unfunded_commitment` field, the invariant collapses to something different and weaker. The user's invariant is the **highest-value silent-error detector** because it catches wrong `capital_call_amount` extractions that would otherwise pass schema + confidence checks.

**Trade-off:** Extractor must look for two unfunded values; some notices state only one — they'll have Optional nulls which is fine.

**Alternative rejected:** Single `unfunded_commitment` (initial design). Caught by Design Critic as a clarification-propagation failure.

**Revisit trigger:** If in production, the invariant fires but isn't useful (e.g., notices too often have only one value), reconsider whether the check is costing more review friction than it saves.

**Interview Angle:**
> "Give an example of a domain invariant you introduced to catch silent LLM extraction errors. Why is this better than confidence scoring alone?"

Strong answer covers:
- LLM confidence scores are miscalibrated post-RLHF (Kadavath 2022 caveat)
- Structured domain invariants are HARD signals: they pass or fail deterministically
- Invariants catch plausible-wrong extractions that pass schema + soft-signal checks
- Specific example: `unfunded_before − call = unfunded_after` catches wrong `capital_call_amount` because the ratio check is independent of the amount extraction
- Design process: sourced from domain-expert input, not invented from LLM knowledge

**Competency tags:** `domain-modeling` `reliability` `hallucination-mitigation`
**Skill level:** Senior (catching this failure mode requires either domain immersion or rigorous review process)

---

### Decision 3 — Single parser (Docling) Phase 1 behind `ParserProtocol`; BDA + Azure DI as Phase 1.5 A/B

**What:** Ship Docling only in Phase 1 with a swappable interface. Phase 1.5 adds Bedrock Data Automation as second implementation; evaluate on 10-30 labeled docs; decide to route / swap / add third.

**Why:** User's own sequencing: "AFTER collecting data and building initial infrastructure…" Shipping three parsers day 1 is 8-14 days with zero empirical basis for which is best. Phase 1.5 A/B preserves the interview narrative of rigorous empirical comparison.

**Trade-off:** Phase 1 locks in Docling-compatible downstream code paths. Phase 1.5 A/B may require adjusting normalization if BDA's blueprint output structures fields differently.

**Alternative rejected:** Three parallel parsers Phase 1. Critic C2.

**Revisit trigger:** Phase 1.5 A/B results on the labeled set; template-specific parser routing considered.

**Interview Angle:**
> "You're adopting a new parser/tool category. You have options X, Y, Z. How do you decide between building one vs all three vs abstracting a pluggable interface?"

Strong answer covers:
- Pluggable interface is cheap to design (Protocol + normalized output type)
- Shipping all three without empirical basis is YAGNI
- The right pattern: ship one + interface + plan the A/B for when labels exist
- The wrong pattern: pre-optimize the A/B without data
- How to normalize vendor-specific outputs into a common contract (preserve `raw_vendor_output` for audit)

**Competency tags:** `system-design` `YAGNI` `abstraction-discipline`
**Skill level:** Mid → Senior

---

### Decision 4 — AWS Bedrock Converse + Instructor + Pydantic + reasoning-first schema

**What:** Every LLM call uses Bedrock Converse structured output, wrapped with Instructor for retry-on-validation, targeting Pydantic schemas where the first field is always `reasoning: str` (free-form before structured fields).

**Why:**
- **Reasoning-first:** Tam EMNLP 2024 and Park NeurIPS 2024 show that strict JSON-mode from token 1 degrades reasoning 10-15% on complex tasks. The mitigation is free-form thinking before structured emission, which is well-established.
- **Native Bedrock Converse:** GA Feb 2026; production-grade structured output.
- **Instructor:** industry-standard Pydantic + provider-abstraction wrapper; 8k+⭐; provider swap is one line.
- **Pydantic:** type safety + automatic validator hook for domain reconciliation.

**Trade-off:** Reasoning field is ~200-500 output tokens per call (cost + latency). Worth it for reasoning quality on ambiguous extractions (date locale, currency inference, name disambiguation).

**Alternative rejected:** Outlines (token-masking FSM) — compile-time issues on complex schemas; Instructor retry is simpler. LangChain output parsers — ecosystem tax. BAML — Python-only codebase, DSL tax.

**Revisit trigger:** If reasoning field token cost dominates, drop it on simpler sub-prompts (Currency, enum Type) while keeping it on harder ones.

**Interview Angle:**
> "How do you structure prompt outputs to get structured data AND high reasoning quality from a modern LLM?"

Strong answer covers:
- The documented 10-15% reasoning degradation when JSON-mode is enforced from token 1 (Tam 2024)
- Mechanistic explanation: constrained decoding distorts probability distribution via renormalization (Park 2024)
- Mitigation pattern: reasoning field FIRST in the schema, then structured fields
- Provider-level function calling / tool use over library-level token-masking for flat schemas
- Pydantic retry-on-validation as the safety net for edge cases

**Competency tags:** `prompt-engineering` `structured-generation` `reliability`
**Skill level:** Senior

---

### Decision 5 — Hard-signal tri-state confidence (Phase 1); soft signals Phase 1.5

**What:** Per-field status is `absent` / `validated_high_conf` / `failed_or_violation` based on hard signals: Pydantic pass, reconciliation pass, master-data hit. Soft signals (min-logprob, self-consistency, semantic entropy) deferred to Phase 1.5 after calibration study.

**Why:**
- **Analyst Q3:** no single confidence signal is reliable for structured extraction. Hard signals are the most reliable layer; soft signals are ensemble enhancements.
- **Critic C3:** soft signals depend on Phase-1.5 calibration study (empirical weights). Phase 1 hard-only removes the calibration-study blocker and cuts ~1 week build time.
- **User domain input:** fields may be absent; tri-state distinguishes absent from failed from low-confidence.

**Trade-off:** No "probably correct but uncertain" tier in Phase 1 — everything is either rock-solid-validated or HITL. Conservative for cold start.

**Alternative rejected:** Verbalized confidence (miscalibrated post-RLHF). Mean logprob (aggregation swings > signal). Single hard signal (too coarse).

**Revisit trigger:** Phase 1.5 calibration study on 20 HITL-labeled docs; empirical ensemble weights unlock soft-signal gating.

**Interview Angle:**
> "How would you detect low-confidence LLM extractions that need human review?"

Strong answer covers:
- Why direct "how confident 0-100?" probing is miscalibrated post-RLHF
- Why token logprobs alone don't correlate with correctness (aggregation swings matter more than the signal)
- The hard/soft signal hierarchy: schema-adherence + domain invariants + master-data checks are hardest; token-level and sample-diversity signals are softer
- Semantic entropy (Farquhar Nature 2024) as the strongest published soft signal — cluster samples by meaning then compute entropy
- Self-consistency (Wang 2023) as a cheaper soft signal
- Ensemble approach with weights tuned on a calibration study (domain-specific because extraction-specific calibration is under-researched — Analyst Gap #1)
- Tri-state classification (absent / validated / failed) for actionable downstream routing

**Competency tags:** `LLM-ops` `reliability` `calibration` `production-ML`
**Skill level:** Senior → Staff

---

### Decision 6 — LangGraph orchestration (pinned `0.2.x` + isolated in `app/workflow/`)

**What:** LangGraph for per-doc workflow with HITL `interrupt()` + `PostgresSaver` checkpointing. Graph is isolated in one module; node functions are thin adapters over framework-free service functions.

**Why:**
- User preference for interview-grade durable-execution exposure
- Native HITL wait pattern via `interrupt()`
- PostgresSaver gives us crash-recoverable state for free

**Trade-off:** LangGraph's 2026 API churn is documented (Scout). We accept quarterly upgrade work as cost. Mitigation stack:
- Minor-compatible pin (`~=0.2.0`)
- Node adapters over framework-free services (swappable)
- `claude/rules/framework-swap.md` playbook
- Quarterly changelog review

**Alternative rejected:** Plain Python + Postgres queue (Scout Q2 recommendation) — rejected for user preference. Temporal — overkill at 100-1000/mo. Prefect, Dagster, BAML — wrong shape or thinner interview signal.

**Revisit trigger:** If LangGraph ships breaking changes affecting the node model, execute the framework swap per playbook. Also revisit in Phase 2 if non-linear agent loops emerge (Phase 2 active learning).

**Interview Angle:**
> "Why did you choose LangGraph over plain Python or Temporal? Would you choose it again?"

Strong answer covers:
- Checkpoint-on-node-boundary is a real feature for HITL pipelines
- But plain Python + Postgres can do the same with ~200 LOC
- Trade-off accepted because the interview signal + exposure to durable execution framework was part of the project's purpose
- Risk managed via isolation (node adapters over framework-free services) + version pinning
- Would I choose again? Depends on project purpose: for a purely operational tool, plain Python would likely win on simplicity; for a learning project with enterprise ambitions, LangGraph earns its complexity
- The framework-agnostic service layer is the key discipline — if you can't swap your orchestrator, you picked the wrong abstraction

**Competency tags:** `system-design` `framework-evaluation` `abstraction-discipline` `interview-signal`
**Skill level:** Senior

---

### Decision 7 — One Postgres for everything (jobs + audit + embeddings + master-data cache + eval); Alembic from day 1

**What:** Single Postgres database with pgvector extension hosts all persistence: LangGraph checkpoints, extraction audit, embeddings, master-data CSV cache, eval runs, drift reports metadata.

**Why:**
- Scout Q3: pgvector beats Bedrock Knowledge Bases / Azure AI Search / Haystack / FAISS+SQLite at 10K-example scale.
- Single backup story. Single ops surface.
- SQL filters over embeddings (WHERE class = ..., WHERE template = ...) come free.
- Alembic migrations from day 1 handle the coupling risk (O2).

**Trade-off:** Schema changes affect five logical surfaces at once. Mitigated by Alembic + schema-compat policy (backward-compatible changes OK; breaking changes require coordinated migration).

**Alternative rejected:** Dedicated vector DB (Pinecone/Weaviate/Chroma) — second system to maintain, unjustified at scale. Bedrock KB — vendor lock + managed overkill.

**Revisit trigger:** If corpus grows past 1M exemplars, consider pgvectorscale or dedicated vector DB. Realistically Phase 4+.

**Interview Angle:**
> "When would you use a dedicated vector database vs Postgres with pgvector?"

Strong answer covers:
- pgvector scaling ceiling (1M-10M rows depending on vector dimensions and query patterns)
- Wins of one-DB simplicity: backups, migrations, SQL filters, ACID across vectors and metadata
- When to upgrade: corpus size, query patterns (e.g., if every retrieval needs sophisticated metadata filtering + recent-window time bias, a dedicated system might help)
- The pg_vector v0.8 (April 2025) iterative index scan + 9× faster filtered queries improvement is often the tipping factor
- Cost: managed vector DBs charge per-query + storage; pgvector is free with Postgres

**Competency tags:** `data-infrastructure` `cost-optimization` `YAGNI`
**Skill level:** Mid → Senior

---

### Decision 8 — Custom FastAPI + HTMX HITL UI (solo-first, multi-user schema-ready)

**What:** Purpose-built ~500-800 LOC review UI. FastAPI + HTMX + Tailwind + Alpine.js. Solo auth Phase 1; DB schema has `user_id` on every mutable row for Phase 2 multi-user.

**Why:**
- Scout Q4: Label Studio / Argilla are labeling-first tools; this is a review-first workflow.
- HAX guidelines (CHI 2019) applied: G2 reliability bands, G11 provenance on demand, G17 global controls.
- Tri-state + invariant-failure flags need first-class UI support that generic labeling tools don't provide.

**Trade-off:** 1-2 weeks of UX polish. Amortizes across future fund-admin extraction use cases.

**Alternative rejected:** Label Studio — labeling-first grafting = multi-week plugin work. Argilla — HF-acquisition team continuity uncertainty. Prodigy — paid; keyboard UX strong but overkill for solo MVP. Streamlit — UX ceiling too low for production.

**Revisit trigger:** If multi-tenant or 10+ reviewers, reconsider Label Studio or Argilla for their auth/permission models.

**Interview Angle:**
> "When do you build a custom review UI vs use Label Studio/Argilla?"

Strong answer covers:
- Labeling-first vs review-first workflows are different shapes
- Custom UI wins when the schema is fixed (not exploratory) AND the workflow has specialized states (tri-state, invariant flags) that generic tools don't support natively
- ~500 LOC is the break-even for custom; grafting custom logic into a generic tool is often 3-5× that
- Multi-reviewer auth models are the usual reason to choose Label Studio / Argilla
- HAX guidelines (Amershi et al. CHI 2019) ground UX decisions in research

**Competency tags:** `UX-for-ML` `build-vs-buy` `solo-productivity`
**Skill level:** Mid → Senior

---

### Decision 9 — Dynamic few-shot + MMR diversity re-ranking + compact few-shot format

**What:** Retrieve top-20 HITL-approved exemplars by cosine similarity → MMR re-rank (λ=0.5) → return top 5 as few-shot context. Each few-shot is stored as (extraction-table + 200-token doc synopsis), not full source doc.

**Why:**
- Analyst Q5: Liu DeeLIO 2022 shows dynamic kNN few-shot beats static/random (+41.9% ToTTo, +45.5% NQ).
- MMR (Carbonell & Goldstein 1998) diversification prevents near-duplicate retrieval that overfits to one template.
- Compact format keeps few-shot context at ~500 tokens per exemplar instead of 2000-10000; key to cost math (W2).
- Silver/gold pool split (W3) prevents feedback-loop poisoning from single-reviewer mistakes.

**Trade-off:** Compact synopsis may lose some signal vs full doc text. Mitigated by structuring the synopsis as "here's what this exemplar looked like + here are the correct extractions."

**Alternative rejected:** Static hand-curated few-shots (scales poorly as pool grows). Full-doc few-shots (cost prohibitive per W2 math). Random-retrieval few-shots (weaker signal per Liu 2022).

**Revisit trigger:** If per-field accuracy plateaus, experiment with structured few-shots that include field-location hints.

**Interview Angle:**
> "How do you design a dynamic few-shot retrieval system that avoids near-duplicate bias?"

Strong answer covers:
- Cosine-only kNN returns near-duplicates because embeddings cluster tightly for same-template docs
- MMR re-ranking tunes the diversity/relevance balance via λ parameter
- The compact exemplar format (structured extraction + synopsis) vs full-doc is a cost decision with minimal accuracy impact for structured extraction
- Feedback-loop risk when HITL-approved extractions become few-shots — silver/gold pool split protects against single-reviewer-mistake propagation
- Cold-start: hand-pick 3-5 diverse exemplars until you have 20+ HITL-approved

**Competency tags:** `retrieval` `RAG` `few-shot-learning` `cost-optimization`
**Skill level:** Mid → Senior

---

### Decision 10 — Spotlighting + 5-layer guardrail stack for prompt injection defense

**What:** Document text wrapped in `<untrusted_document>` tags with explicit system-prompt instruction to treat contents as data. Combined with schema enforcement, Pydantic retry, domain reconciliation, and HITL as final gate.

**Why:**
- Analyst Q10: Hines et al. Microsoft 2024 showed spotlighting drops injection attack success from >50% to <2% on GPT-family.
- OWASP LLM01:2025 defense-in-depth consensus.
- Documents are adversary-authored in principle (GPs generate them); injection is a realistic if low-probability vector.

**Trade-off:** Near-zero cost to implement. No meaningful downside.

**Alternative rejected:** Single-layer defense (fragile). LLM-as-judge injection detection (DeepMind 2025 shows insufficient alone).

**Revisit trigger:** Red-team eval results; if injection attacks succeed in practice, add classifier-based detection (preliminary confidence but growing).

**Interview Angle:**
> "How do you defend against prompt injection in a document-processing pipeline?"

Strong answer covers:
- Indirect prompt injection is the OWASP #1 LLM risk (LLM01:2025)
- Spotlighting with explicit delimiters + system-prompt hardening is the single highest-ROI defense (Hines 2024 data)
- Structured output enforcement prevents the model from emitting free-form content that exfiltrates
- Domain reconciliation catches semantic injection (injected text claiming a different amount)
- HITL is the final line of defense for financial-value fields
- Red-team eval suite included in golden set — don't just implement defenses, test them

**Competency tags:** `security` `LLM-safety` `adversarial-ML`
**Skill level:** Senior

---

### Decision 11 — CI-enforced golden eval + scheduled drift report + calibration-deadline lock on auto-approve (Ritual Health)

**What:** Four rituals, each with automatic trigger + fallback + enforcement mechanism:
1. Golden eval replay = GH Actions required check on PRs touching prompts/schemas/models
2. HITL queue SLO = UI banner + git-status marker file when items >3 days old
3. Drift report = weekly scheduled GH Action writes `drift-reports/YYYY-MM-DD.md`
4. Calibration-study deadline = `auto_approve_threshold: 0.0` locked in config with comment

**Why:** Prior sessions' lesson-learned (LinkedIn-builder and job-search-pipeline both flagged this exact pattern): longitudinal rituals die silently without automatic triggers. Confidence: high, confirmed across three sessions.

**Trade-off:** Some rigidity — e.g., threshold can't be raised without unlocking; forces disciplined process. This is the intended feature, not a bug.

**Alternative rejected:** Documentation-only rituals ("remember to run the eval"). Known to decay.

**Revisit trigger:** If a ritual's enforcement is too aggressive (e.g., CI gate blocks too many legitimate PRs), tune thresholds. But never remove the gate.

**Interview Angle:**
> "How do you prevent the quality rituals you set up from decaying in production?"

Strong answer covers:
- Rituals that depend on human memory die in 3 weeks (Amershi G17 isn't enough — guidelines need enforcement)
- The three enforcement mechanisms: (1) mechanical (CI required check), (2) visible (UI banner / git status), (3) blocking (config locked until condition met)
- Specific example: auto-approve threshold locked at 0.0 until calibration study runs
- Writing the trigger + fallback + enforcement for each ritual forces gaps to surface (gaps are always there; writing exposes them)
- Prior-incident calibration: learned this pattern from earlier projects where rituals died

**Competency tags:** `production-ML` `MLOps` `process-design` `quality-engineering`
**Skill level:** Senior → Staff (this is what separates operators from builders)

---

## Part 2 — Research Dossier

### Strongly load-bearing papers (the design falls if these are wrong)

**LMDX** — Perot et al. ACL Findings 2024 ([arXiv:2309.10952](https://arxiv.org/abs/2309.10952))
- **Finding:** Layout-coord + schema prompting into PaLM 2-S / Gemini Pro zero/few-shot SOTA on VRDU, CORD.
- **How we use it:** Justifies the phase-1 extraction pattern (layout-text serialization + frontier LLM + schema + few-shot).
- **What breaks if wrong:** If frontier + layout-text doesn't match specialist fine-tunes, our Phase-1 accuracy target fails and we need phase-3 fine-tuning earlier. Likelihood: moderate; VLM benchmarks suggest the gap is closing for frontier LLMs.

**DocLLM** — Wang et al. ACL 2024 ([arXiv:2401.00908](https://arxiv.org/abs/2401.00908))
- **Finding:** Layout-aware LLM extension beats 14/16 benchmarks on structured doc IE. JPMorgan co-authored (financial-domain).
- **How we use it:** Validates layout-aware approach for financial-doc IE specifically.
- **What breaks if wrong:** Same failure mode as LMDX. Direct financial-domain evidence makes this more reliable.

**Tam et al. "Let Me Speak Freely?"** — EMNLP 2024 ([arXiv:2408.02442](https://arxiv.org/abs/2408.02442))
- **Finding:** JSON-mode from token 1 degrades reasoning 10-15% on complex tasks.
- **How we use it:** Directly motivates reasoning-first schema design.
- **What breaks if wrong:** If reasoning-first doesn't help, we're paying ~200-500 tokens/call for nothing. Negative impact is small cost, not correctness.

**Hines et al. "Spotlighting"** — Microsoft 2024 ([arXiv:2403.14720](https://arxiv.org/abs/2403.14720))
- **Finding:** Delimiter + marking + encoding drops injection attack success >50% → <2%.
- **How we use it:** Primary prompt-injection defense.
- **What breaks if wrong:** Injection defense is layered (5 layers); spotlighting is layer 1. Failure degrades but doesn't break defense.

**Liu et al. DeeLIO 2022** ([arXiv:2101.06804](https://arxiv.org/abs/2101.06804))
- **Finding:** Similarity-based kNN few-shot beats random by 41.9% (ToTTo), 45.5% (NQ).
- **How we use it:** Justifies dynamic few-shot architecture.
- **What breaks if wrong:** Extraction tasks may show smaller gains than text generation; effect direction still holds.

### Moderately load-bearing (design adapts if these are wrong)

**Khot et al. DecomP** — ICLR 2023 ([arXiv:2210.02406](https://arxiv.org/abs/2210.02406))
- **Finding:** Modular sub-prompt decomposition improves reasoning task accuracy.
- **How we use it:** Justifies Phase 1.5 A/B for per-field-group decomposition.
- **What breaks if wrong:** Phase 1 ships monolithic anyway; this only affects the decomposition experiment.

**Farquhar et al. Semantic Entropy** — Nature 2024 ([doi:10.1038/s41586-024-07421-0](https://www.nature.com/articles/s41586-024-07421-0))
- **Finding:** Cluster-by-meaning entropy is strongest published uncertainty signal.
- **How we use it:** Phase 1.5 soft-signal in confidence ensemble.
- **What breaks if wrong:** Phase 1 doesn't use it; only affects Phase 1.5 calibration outputs.

**Kadavath et al.** — Anthropic 2022 ([arXiv:2207.05221](https://arxiv.org/abs/2207.05221))
- **Finding:** Large models well-calibrated on MC/T-F in right format; direct verbalized confidence miscalibrates after RLHF.
- **How we use it:** Justifies NOT using "how confident 0-100?" probing.
- **What breaks if wrong:** Design is conservative; if verbalized confidence worked, we'd be leaving an easy signal on the table.

### Supporting (design references these but doesn't depend on them)

**FrugalGPT** — Chen et al. TMLR 2024; **RouteLLM** — Ong et al. 2024; **Mosbach et al. 2024** (fine-tune vs few-shot break-even); **Amershi HAX** — CHI 2019; **Greshake 2023** (prompt injection formalization); **OWASP LLM01:2025**; **GraphRAG rule-out** (Edge 2024 + "When to use Graphs in RAG" 2025).

---

## Part 3 — POC → Enterprise Roadmap (practice adoption by stage)

Practices staged by when to adopt. **Now** = Phase 1. **Soon** = Phase 1.5. **Later** = Phase 2+. **Never** = not for this project.

| Practice | Stage | Cost | Benefit |
|---|---|---|---|
| Pydantic schema-enforced output | **Now** | Low | Eliminates format errors; free reliability |
| Dynamic few-shot retrieval | **Now** | Low (pgvector + embeddings) | Compounds value of HITL corrections |
| MMR diversity re-ranking | **Now** | Low | Prevents near-duplicate bias |
| Reasoning-first schema | **Now** | Low (~200 tokens/call) | Preserves reasoning quality |
| Spotlighting | **Now** | Zero | Prompt-injection defense layer 1 |
| Prompt caching (Anthropic) | **Now** | Zero | ~80% input cost reduction |
| Compact few-shot format | **Now** | Low | Major cost reduction vs full-doc few-shots |
| Polymorphic schema by class | **Now** | Low | Cleaner than union schema |
| Hard-signal tri-state validation | **Now** | Low | Rock-solid base layer |
| Prompt + model version pinning in provenance | **Now** | Zero | Audit + regression tracking |
| CI-enforced golden eval on prompt/schema PRs | **Now** | Low | Prevents silent regression |
| Drift report weekly scheduled job | **Now** | Low | Catches drift without dashboards |
| Calibration-deadline auto-approve lock | **Now** | Zero | Prevents over-trust ritual decay |
| Structured logs + OTel-to-stdout | **Now** | Low | 80% of observability value |
| Alembic migrations from day 1 | **Now** | Low | Prevents schema-change pain later |
| Tool-agnostic parser interface (single impl) | **Now** | Low | Phase 1.5 A/B ready |
| Custom purpose-built HITL UI | **Now** | Medium (1-2 weeks) | Review-first UX; reusable |
| LangGraph for durable HITL orchestration | **Now** | Medium (framework tax) | User pref + interview signal |
| Monolithic per-schema extraction | **Now** | Low | Baseline to A/B decomposition against |
| Calibration study (20 HITL-labeled docs) | **Soon** | Medium | Unlocks soft-signal ensemble |
| Soft-signal confidence ensemble (min-logprob, self-consistency, semantic entropy) | **Soon** | Medium | Tunes auto-approve threshold |
| Monolithic-vs-decomposed A/B | **Soon** | Medium | Empirical decomposition decision |
| Parser A/B (Docling vs BDA) | **Soon** | Medium | Empirical parser decision |
| Cascade (Haiku first → Sonnet on disagreement) | **Soon** if cost > target | Medium | Cost reduction with agreement gating |
| Master-data integration wired | **Soon** when access arrives | Medium | Improves LP/GP accuracy ceiling |
| Arize Phoenix deployed | **Soon** | Medium | Dashboards when logs aren't enough |
| Multi-reviewer auth + assignment | **Later** (Phase 2) | Medium | When team expands |
| Inter-annotator agreement sampling | **Later** (Phase 2) | Medium | Label quality control at team scale |
| Gold/silver pool split active | **Later** (Phase 2) | Low | Unlocked by multi-reviewer |
| Active learning sampling | **Later** (Phase 2) | Medium | Max info gain per reviewer-minute |
| Hybrid BM25 + dense retrieval + RRF | **Later** (Phase 2) | Low | Exact-match boost for financial terminology |
| Multi-collection retrieval | **Later** (Phase 2) | Low | Cross-surface context |
| Per-GP-template fine-tune | **Later** (Phase 3) | High (GPU + labels) | Cost + accuracy for top templates |
| Template-specific extractors | **Later** (Phase 3) | High | Specialist performance |
| Cross-fund analytics / GraphRAG reconsideration | **Later** (Phase 3+) | High | Only if multi-hop queries emerge |
| Multi-tenancy | **Later** (Phase 4) | Very high | If serving other fund admins |
| SLA + on-call | **Later** (Phase 4) | Very high | Production-hardening |
| LangGraph for linear deterministic workflows | **Never** (for a truly trivial tool — but OK here) | — | Would be overkill at smaller scale |
| GraphRAG | **Never** for per-doc field extraction | — | Wins on multi-hop global synthesis, not our use case |
| Dedicated vector DB (Pinecone/Weaviate) | **Never** at <1M exemplars | — | pgvector suffices for years |
| Full LangChain ecosystem | **Never** | — | Framework tax; Instructor + Bedrock is tighter |

---

## Part 4 — Interview Competency Map

Each decision maps to competencies + skill levels. Use this to prepare for interviews by decision.

| Decision | Primary competencies | Secondary | Skill level |
|---|---|---|---|
| D1 Monolithic → decomposed A/B | `system-design`, `cost-optimization`, `eval-driven-development` | `prompt-engineering` | Mid → Senior |
| D2 Unfunded before/after + invariant | `domain-modeling`, `reliability`, `hallucination-mitigation` | `eval-design` | Senior |
| D3 ParserProtocol + Docling-only Phase 1 | `system-design`, `YAGNI`, `abstraction-discipline` | `build-vs-buy` | Mid → Senior |
| D4 Bedrock Converse + Instructor + reasoning-first | `prompt-engineering`, `structured-generation`, `reliability` | `LLM-ops` | Senior |
| D5 Hard-signal tri-state + soft-signal ensemble later | `LLM-ops`, `reliability`, `calibration`, `production-ML` | `eval-design` | Senior → Staff |
| D6 LangGraph with isolation | `system-design`, `framework-evaluation`, `abstraction-discipline` | `interview-signal` | Senior |
| D7 One Postgres + Alembic | `data-infrastructure`, `cost-optimization`, `YAGNI` | `scaling-decisions` | Mid → Senior |
| D8 Custom HITL UI | `UX-for-ML`, `build-vs-buy`, `solo-productivity` | `research-grounded-design` | Mid → Senior |
| D9 Dynamic few-shot + MMR + compact format | `retrieval`, `RAG`, `few-shot-learning`, `cost-optimization` | `ML-engineering` | Mid → Senior |
| D10 Spotlighting + 5-layer injection defense | `security`, `LLM-safety`, `adversarial-ML` | `defense-in-depth` | Senior |
| D11 CI-enforced rituals | `production-ML`, `MLOps`, `process-design`, `quality-engineering` | `organizational-design` | Senior → Staff |

### Competency coverage summary

| Competency | Decisions touching it |
|---|---|
| **System design** | D1, D3, D6, D7 |
| **LLM-ops / production-ML** | D5, D11 |
| **Cost optimization** | D1, D7, D9 |
| **Reliability / hallucination mitigation** | D2, D4, D5, D10 |
| **Prompt engineering** | D4, D5, D9 |
| **Retrieval / RAG** | D9, D7 |
| **Security** | D10 |
| **MLOps / quality engineering** | D11 |
| **Domain modeling** | D2 |
| **UX for ML** | D8 |
| **Framework evaluation / YAGNI** | D1, D3, D6 |
| **Eval-driven development** | D1, D5, D11 |

### Skill-level targets

- **Mid:** can explain any decision at the "what + why" level
- **Senior:** can explain the trade-offs accepted, the alternatives rejected, and the revisit triggers
- **Staff:** can explain how the decision interacts with organizational / process / ritual-decay considerations (D11), how to generalize the lesson beyond this project, and how you'd do it differently at 10× scale

---

## Using This Document

1. **Pre-interview prep:** Pick 3-5 decisions most relevant to the role. Memorize Interview Angle + strong-answer ingredients. Practice aloud.
2. **During implementation:** Use the POC → Enterprise roadmap (Part 3) to decide what to build now vs defer.
3. **After Phase 1 ships:** Update Part 2 (research dossier) with "what actually broke when we ran this." Update Part 3 with promotions/demotions based on experience.
4. **Next project:** Copy the decision-framing structure (WHAT/WHY/TRADE-OFF/ALTERNATIVE/REVISIT/INTERVIEW). It's a durable pattern for any architectural project.
