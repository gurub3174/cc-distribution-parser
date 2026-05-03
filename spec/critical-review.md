---
project: cc-distribution-parser
type: critical-review
author: design-critic
created: 2026-04-21
---

# Critical Review — Capital Call & Distribution Parser Architecture

## Executive Summary

The architecture is substantially evidence-grounded and honest about its trade-offs, which is commendable at this level of complexity. But it is **not a 4-6 week solo-dev MVP** — it is a 10-14 week build being described as a 4-6 week one, with at least three load-bearing components that will each consume weeks. The biggest concrete flaw is a **clarification-propagation failure**: the user specified a TWO-variable unfunded invariant (`Unfunded(before) - Capital_call = Unfunded(after)`) but the schema extracts only ONE `unfunded_commitment` field, so the invariant cannot be checked. The second biggest flaw is **Phase-1 shipping three parser implementations** when the user's own clarification was "after collecting data… be tool-agnostic" — parser A/B belongs in Phase 1.5, not day 1. Ritual decay (HITL, eval, calibration, drift review) is under-designed per prior-session pattern. LangGraph is kept for interview signal despite Scout's direct rejection — defensible but thin evidence-justification. **Verdict: YELLOW** — fundamentally sound, but needs scope cuts and schema surgery before implementation.

## Clarification-Propagation Check (per 2026-04-10 Critic lesson)

Walked every user clarification from the Design Brief §"Financial Domain Considerations" and §"Pushback Acknowledged" through the architecture components:

| User clarification | Status | Notes |
|---|---|---|
| Name variance HIGH; master-data lookup priority elevated to phase 1 | ✅ Propagated | §6 rapidfuzz + seam + CSV mock. |
| Vocabulary variation ("unfunded" / "uncalled" / "remaining"…) | ✅ Propagated | §6 spaCy matcher + vocab dictionary; also in §5 prompt hints. |
| Fields may be omitted; tri-state `absent` / `failed` / `low-conf` | ✅ Propagated | §7 ensemble layer. |
| Mixed PDF + DOCX + scanned-PDF; three code paths; no PDF-first assumption | ⚠️ Partial | §3 ParsedDoc has `source_format` enum but no per-format handling described (e.g., scanned-PDF requires OCR fallback which is buried in Docling's internals, not surfaced architecturally). |
| Templates vary greatly → LLM-primary, template-matching is optimizer | ✅ Propagated | §3 phase-1 plan; template routing deferred to phase 2. |
| **CC reconciliation invariant: `Unfunded(before) − Capital_call = Unfunded(after)`** | ❌ **NOT PROPAGATED** | See C1. Schema (§5) has a single `unfunded_commitment` field, not before/after. The architecturally-stated invariant in §7 quietly collapses to `commitment_total − unfunded_commitment` — a different check that CANNOT catch the error the user's specified invariant catches. |
| Tool-agnostic parser layer (user: "AFTER collecting data and building initial infra") | ❌ **NOT PROPAGATED** | See C2. Architecture ships three parsers in Phase 1, contrary to the user's sequence. |
| Master-data access "restricted/slow" — may never arrive | ⚠️ Partial | §6 has a mock CSV seam but no stated fallback if master never arrives (name-accuracy ceiling is silently capped). |

Three findings from this lens alone (C1, C2, W5). The lesson keeps paying.

## Prior-Session Calibration (per 2026-04-10 Critic lesson)

Prior lesson applied: **"deferred maintenance = never done" / ritual decay within 3 weeks.** This architecture has FOUR rituals without automatic triggers or health checks: HITL review cadence, golden-eval replay on prompt changes, drift correction-rate review, phase-1.5 calibration study. All four will decay. Surfaced in W2. Calibration pattern continues to pay.

---

## Critical (must address before implementation)

### C1. CC schema cannot check the user's stated unfunded-invariant

**Issue:** The user explicitly gave this reconciliation rule in the Design Brief ("Financial Domain Considerations" §"Standing domain concerns" #4):

> `Unfunded (before) − Capital call amount = Unfunded (after)`

This requires extracting **two** unfunded values — the pre-call and post-call balances. The architecture's `CapitalCallV1` schema has **one** `unfunded_commitment: Optional[Decimal]` field. §7 then states the invariant as "`commitment_total − unfunded_commitment` consistent with cumulative-called ledger if available" — that is a DIFFERENT invariant (commitment-against-cumulative, not before-vs-after), and the "if available" makes it silently skipped when the ledger isn't present.

The user's invariant catches **the most common silent error** in capital-call extraction: getting the capital-call-amount wrong. If you extract `capital_call_amount` incorrectly but correctly extract both unfunded values, `Unfunded(before) − Capital_call ≠ Unfunded(after)` fails immediately. With only one unfunded field, a wrong capital-call-amount extraction sails through because the architecturally-checked invariant has no independent redundancy.

This is a pure clarification-propagation failure — the user said the words, the words are in the brief, the implementation doesn't reflect them.

**Why it matters for THIS project:** Financial domain; silent-error-rate target ≈ 0. The whole point of reconciliation invariants is redundancy over the LLM's extraction. The strongest invariant the user specified has been dropped. This is also the check most likely to catch the exact class of error that passes schema validation and confidence thresholds (plausible-looking wrong number).

**Severity:** Critical.

**Concrete alternative / mitigation:**

1. Split `unfunded_commitment` into two schema fields: `unfunded_before_call: Optional[Decimal]` and `unfunded_after_call: Optional[Decimal]`. Both are optional because any given notice might state only one — but both should be extracted when present.
2. Add a §7 reconciliation validator: `if unfunded_before_call and unfunded_after_call and capital_call_amount: assert abs((unfunded_before_call - capital_call_amount) - unfunded_after_call) < 0.01`. Violation → HITL auto-flag regardless of per-field confidence.
3. Add the prompt hint to the "Amounts" sub-prompt: "Capital-call notices often state two unfunded values — the commitment remaining before this call, and the commitment remaining after this call. Extract both when present."
4. Keep the existing commitment-vs-cumulative invariant as a second, independent check.

**Evidence from reports:** Design Brief §"Financial Domain Considerations", standing concern #4 (quoted above). Also Design Brief §"Extraction Schemas": "Commitment − Unfunded (after call) = cumulative called; Unfunded (before) − Capital call amount = Unfunded (after)". Research Brief Q3 "So What": "Hard signals (highest trust): reconciliation invariant (pass/fail)" — the architecture is supposed to rely on hard signals as the highest-trust layer. Dropping one is load-bearing.

---

### C2. Shipping three parser implementations in Phase 1 contradicts the user's own sequencing and is the single biggest time-sink in the MVP

**Issue:** The architecture (§3) explicitly states: "Wire BedrockDataAutomationParser and AzureDocumentIntelligenceParser as alternate implementations **from day 1**." The user's direction (quoted in §3 "WHY") was the opposite: "**After collecting the data and building the initial infrastructure** we should have the parse function be tool agnostic so that we can swap between BDA and Azure Doc intelligence and analyze the initial accuracy of all models to evaluate cost and tradeoffs."

Three parser implementations with different SDKs (Docling vs AWS Bedrock Data Automation vs Azure Document Intelligence — the last requiring an Azure subscription that the user has not confirmed they have) behind a single `ParserProtocol`, PLUS a normalization layer from three distinct vendor outputs into a unified `ParsedDoc`, is **8-14 days of solo-dev work** by itself. The normalization layer alone is non-trivial: BDA emits blueprint-structured output, Docling emits DoclingDocument structure, Azure DI emits Form Recognizer structure. Normalizing these into one `ParsedDoc` without information loss (§3 claims `raw_vendor_output` preserves it for audit, but downstream code only sees the normalized form) requires careful schema negotiation — and field-localization accuracy downstream is deeply dependent on which parser's structural hints are preserved through normalization.

Shipping ONE parser in Phase 1, then adding the A/B harness in Phase 1.5 when you actually have labeled docs to compare on, is both what the user asked for and the YAGNI call. The §3 TRADE-OFF ACCEPTED ("2-3× the initial parser code") is understating — it's 3× the SDK learning, 3× the error-handling surface, 3× the auth/secrets/rate-limit configuration, and potentially a cloud-subscription dependency (Azure) the user may not have.

**Why it matters for THIS project:** 4-6 week solo-dev MVP. Budgeting 2 weeks to the parser when one parser works gives those 2 weeks back to the 10 other components that need them. The "empirical parser comparison" interview narrative is preserved by the Phase 1.5 A/B study — shipping three parsers in Phase 1 adds zero interview value over shipping one-then-adding-two.

**Severity:** Critical.

**Concrete alternative / mitigation:**

1. **Phase 1:** ship `ParserProtocol` interface + ONE implementation (DoclingParser). Do NOT build BDA or Azure DI parsers yet.
2. **Phase 1.5 A/B:** once you have 10-30 labeled docs, add `BedrockDataAutomationParser` as a second implementation, run the comparison, THEN decide whether Azure DI is worth a third implementation (probably not — you're AWS-native; Azure adds a whole cloud subscription).
3. Keep §3's interface and `raw_vendor_output` audit field — those are cheap design-now/build-later seams.
4. Update the §15 Week-1 POC experiment: instead of "docling + LLM vs BDA," do "docling + LLM on 10-20 docs, measure baseline." The BDA comparison slips to week 6-8 once initial labels exist.

**Evidence from reports:** User's own direction quoted verbatim in §3 "WHY." Scout Q1: "recommend dual-path experiment in phase 1 POC" — but Scout also says "Validate empirically on your template mix in POC before locking," which implies a sequence, not parallel shipping. The three-parser-day-1 interpretation is an overreach of Scout's guidance.

---

### C3. 4-6 week solo-dev timeline is not credible for this scope

**Issue:** The architecture claims Phase 1 ships in 4-6 weeks solo. Count the components: 3 parsers (C2) + LangGraph workflow with 9 nodes + 3-class classifier + 4-5-sub-prompt polymorphic extractor × 2 schemas + dynamic few-shot with MMR re-ranking over pgvector + 6-step canonicalization layer + Pydantic + reconciliation validators + confidence ensemble with hard+soft signals + tri-state + FastAPI + HTMX + Tailwind + Alpine HITL UI with per-field bands + provenance drawer + bulk-approve + keyboard nav + audit logging + Postgres schema for jobs+audit+embeddings+master-data-cache+eval-runs + S3 ingestion + Arize Phoenix OTel tracing + per-span attributes + cost attribution + drift dashboard + golden eval harness + `pytest -m eval` + CI + pip-audit + Bedrock Converse + Instructor + Titan embeddings + rapidfuzz + spaCy matchers + prompt-injection defense + `claude/rules/*` + drift-baseline.

Each of those is independently a day or more. The design's own §15 says "Week-1 POC experiment: docling + LLM vs Bedrock Data Automation on 10-20 docs" — that means week 1 is not infrastructure, it's bake-off. So the architecture-build must happen in weeks 2-6, i.e., **5 weeks for ~30 listed components**.

The user is a solo AI engineer in-training whose primary focus is AI engineering, not DevOps. The list above includes non-trivial DevOps (Postgres schema migrations, S3 ingestion, Phoenix container, OTel instrumentation, FastAPI + HTMX UI, Alpine.js state management, CI pipeline, pip-audit + dependabot, secrets-manager wiring). That's the half of the stack that eats solo devs.

**Why it matters for THIS project:** The whole project value is the staged POC → MVP → Production narrative. If Phase 1 actually takes 10-14 weeks, the interview story still works but the "4-6 week MVP" timeline is a planning error that propagates: the user will either (a) defer pieces under pressure and ship an incomplete MVP while thinking it's complete, (b) burn out, or (c) rewrite the timeline mid-project and lose planning credibility.

**Severity:** Critical (planning risk, not technical risk).

**Concrete alternative / mitigation:**

Right-size Phase 1 to what actually fits 4-6 weeks solo. Cut from Phase 1 and move to Phase 1.5:
- Two of three parsers (C2).
- Confidence ensemble "soft signals" — ship Phase 1 with HARD signals only (schema-adherence + reconciliation + master-data hit). Min-logprob and the phase-2 signals come later. Tri-state becomes simpler: `absent / high-conf-or-validated / failed-or-invariant-violation`. Less expressive, ship-able.
- Arize Phoenix — replace with structured Python logging + OTel-to-stdout in Phase 1. Phoenix is a day to set up and a week to operationalize dashboards. The observability story holds via logs for the MVP; Phoenix is a Phase 1.5 add.
- Drift detection dashboard — log HITL correction rate; defer the dashboard.
- Per-field-group decomposition — ship Phase 1 with MONOLITHIC per-schema extraction (one prompt per class). The decomposition A/B is already listed as Phase 1.5 in §12 — treat Phase 1 as the monolithic baseline, not the "already decomposed" version.
- Hybrid BM25+dense retrieval — already Phase 2 per §9; confirm it stays there.

Revised Phase 1 (realistic 5-6 weeks):
- Ingress + Postgres + S3 + polymorphic parser (Docling only) + 3-class classifier + monolithic polymorphic extractor + canonicalization + hard-signal reconciliation/validation + custom HITL UI (tri-state, not soft-confidence bands) + golden-eval harness + prompt-injection spotlighting + cost logging + LangGraph orchestration (pinned, isolated) + rapidfuzz + vocab dictionary.

This is still ambitious for solo but is plausible.

**Evidence from reports:** No direct contradiction from Scout/Analyst — this is an overengineering/timeline finding. Scout §9 is effectively this argument at the orchestration layer: "The DIY baseline IS the recommendation… choose boring tech and understand every layer." The architecture took the DIY-spirit partially (rejecting Bedrock KB, LangSmith, BAML) but not for the decomposition / confidence-ensemble / triple-parser choices.

---

### C4. Ritual decay — four unscheduled rituals, prior pattern holds

**Issue:** The architecture depends on four ongoing rituals none of which have an automatic trigger, a failure alert, or a documented fallback:

1. **HITL review** — queue exists, solo reviewer mode, but nothing prompts the user to clear the queue, nothing tracks review-age SLO, nothing alerts when queue backs up. §8 says "keyboard-first, bulk-approve" — UX affordances, not triggers.
2. **Golden-eval replay on prompt/model change** — §12 says "Triggers: every prompt change, every model version change, every schema change." What MECHANISM enforces this? A CI gate on a git hook? A pytest run on `main`? A Design Lead reminder? Left unstated, it becomes a manual ritual that dies by week 6.
3. **Drift review (HITL correction-rate per field per week)** — §13 says "regression alert on > 20% week-over-week increase." Alert routed where? Email to the solo dev? A daily cron? A dashboard the user doesn't open? No.
4. **Phase-1.5 calibration study (20 docs)** — blocked on the user manually labeling 20 docs, then running a calibration analysis, then editing a config. This is weeks of elapsed-time work with no forcing function.

The prior LinkedIn-builder review and job-search-pipeline review both surfaced this exact pattern (rituals → decay). Confidence: very high. This is the highest-probability silent-failure path in this architecture.

**Why it matters for THIS project:** The confidence ensemble — the core safety mechanism — depends on the calibration study happening. If it doesn't, the ensemble weights stay at the pre-study defaults and the auto-approve threshold stays "conservative" (= everything goes to HITL = reviewer fatigue = R2 in Design Brief). Meanwhile eval replay is what catches silent regression on prompt changes, which §7 acknowledges happens during iteration. Without triggers, the user will iterate on prompts without replaying the golden set, silently regressing accuracy.

**Severity:** Critical.

**Concrete alternative / mitigation:**

1. **Git pre-commit hook OR CI required-check** on prompts/schema changes: `pytest -m eval` must run and pass (within 2pt delta) before merge. Make it mechanical, not social.
2. **HITL queue SLO + UI banner.** If the HITL queue has >N items older than M days, show a banner on every `/design` session startup and on the HITL UI home page. Pick simple defaults (e.g., N=5, M=3) and tune.
3. **Drift alert:** a scheduled job (cron or GH Action) that queries Postgres weekly, computes week-over-week correction rate per field, writes a file `drift-report-YYYY-MM-DD.md` to the repo. Alert = file exists with >20% delta. Forcing: user sees the file in git status.
4. **Calibration study has a calendar deadline.** Pick a date (e.g., 6 weeks after Phase 1 ships). Block the auto-approve threshold from being raised until the study runs. Make the block visible in the config file ("`auto_approve_threshold: 0.0  # locked until calibration study complete — see docs/calibration.md`").
5. Add a §15.5 "Ritual Health" subsection to the architecture explicitly listing each ritual + trigger + fallback. The act of writing it forces the gaps to surface.

**Evidence from reports:** Design Brief Risk Register R2 "HITL fatigue / ritual decay — Medium/High." Prior critical-reviews (LinkedIn CRITICAL 3, job-search C2+W1) — same pattern, same fix class.

---

## Warning (should address; design may work without)

### W1. LangGraph adoption overrides Scout's direct recommendation based only on "interview narrative" — thin justification for accepting 2026 churn risk

**Issue:** Market Scout §Q2 is unambiguous: "Plain Python + Postgres queue + FastAPI HITL endpoints. HITL wait is just a row with `status='awaiting_review'`... Total LOC: ~200." And: "LangGraph is overbuilt for this deterministic linear pipeline and its 2026 API instability is well-documented." The architecture (§2) accepts LangGraph anyway, citing (a) "user-requested for interview-grade exposure" and (b) "fit to the workflow — HITL interrupts." Reason (b) is exactly what Scout addresses with the 200-LOC alternative. Reason (a) is the actual driver.

Interview narrative is a real consideration — the project IS dual-purpose per the Design Brief. But the architecture's TRADE-OFF section says "We accept quarterly upgrade work as cost" — quarterly upgrade work on a solo-dev production tool processing financial data is NOT a cheap cost. And LangGraph is one of many credible 2026 frameworks — the interview signal is not uniquely strong there. Temporal has stronger signal (OpenAI-native integration, Feb 2026) and is rejected as "overkill."

**Why it matters for THIS project:** C3 already argues the timeline is tight. LangGraph's `PostgresSaver` + checkpointing + `interrupt()` + state schema typing + upgrade work + the "isolation to one module" discipline is at least a full week of learn + integrate + debug. Scout's 200-LOC plain-Python alternative is 1-2 days. That's 3-4 days back for the timeline.

**Severity:** Warning (not Critical because isolation mitigates blast radius, and the user explicitly asked for this).

**Concrete alternative / mitigation:**

Option A (ship with Scout's recommendation): Plain Python + Postgres queue in Phase 1. Add LangGraph as a Phase 1.5 EXPERIMENT — swap the orchestration module to LangGraph and compare lines-of-code, upgrade pain, and debug experience. This is actually a STRONGER interview story: "I evaluated LangGraph against plain Python on a real production pipeline and here's what I learned." That's a more nuanced signal than "I used LangGraph."

Option B (keep LangGraph, tighten the mitigation): Pin to `langgraph==0.2.x` but NOT to a minor version (don't pin to `0.2.47` — that will bit-rot fast). Use the ACTUAL LangGraph API surface only within `app/workflow/graph.py`; import `ParsedDoc`, `DocClass`, etc. from framework-agnostic modules; make the graph node functions thin adapters over framework-agnostic service functions. Document an explicit "framework swap" playbook (1-2 pages) and add a quarterly calendar event to review LangGraph's changelog. If the changelog has breaking changes in the architecture's node model, execute the swap rather than the upgrade. This turns the framework choice into a managed risk.

**Evidence from reports:** Scout Q2 (quoted), Scout's "Recommended phase 1: Plain Python + Postgres jobs table + FastAPI HITL endpoints." Scout's master matrix lists LangGraph as "Viable with version pinning" — viable, not recommended, for THIS project.

---

### W2. Per-field-group decomposition × dynamic few-shot × reasoning-first schema — token economics assertion is unverified

**Issue:** §5 "TRADE-OFF ACCEPTED" states: "5 sub-prompts per doc vs 1 = ~5× inference cost at the extraction step. At 100-1000 docs/mo and Sonnet pricing, total monthly extraction cost ~$20-200." Let's check:

Per sub-prompt:
- Reasoning field emitted first = ~200-500 output tokens (Tam et al. cites this)
- Top-5 few-shots retrieved via MMR — each few-shot is a prior HITL-approved extraction with the SOURCE DOC text (needed for grounding) + the extracted values. A CC notice is 1-5 pages ≈ 2000-10,000 input tokens. Five few-shots = 10,000-50,000 tokens of few-shot context.
- Vocab dictionary hints = ~500-2000 tokens.
- Current doc text = 2000-10,000 input tokens.
- Output structured fields = ~100-300 tokens.

Per sub-prompt input: ~15,000-65,000 tokens. Output: ~300-800 tokens. Sonnet 3.5 pricing (mid-2026): ~$3/M input, ~$15/M output. Per sub-prompt: $0.045-0.195 input + $0.004-0.012 output = $0.05-0.21. Per doc with 5 sub-prompts: $0.25-$1.05. Monthly at 1000 docs: **$250-$1050**.

The architecture's $20-200/month claim requires either (a) few-shots being short extraction-only examples without source doc text — which defeats the point of in-context grounding, or (b) the doc text being passed only ONCE somehow — but per-group decomposition means each sub-prompt needs SOME doc context. The cheap path (pass `ParsedDoc.sections` subset relevant to the group) is doable but is not described in §5.

Even at the optimistic floor, the per-doc cost target from Design Brief ("< $0.10 target") is blown by 2.5-10×. This is a quiet but real problem: the architecture exceeds its own success criterion.

**Why it matters for THIS project:** Cost is an MVP go/no-go for self-hosted/solo production tools. If actual per-doc cost is $0.50-$1.00 instead of $0.10, monthly cost at 1000 docs is $500-$1000, which a solo dev + fund admin budget may not sustain indefinitely. Also, Phase-1.5 cascade (Haiku first-pass → Sonnet on disagreement) will NOT save you here — the cost is in the INPUT (doc + few-shots), not the output.

**Severity:** Warning.

**Concrete alternative / mitigation:**

1. **Show the math in the architecture.** Replace the "$20-200/mo" claim with a per-sub-prompt token budget table: input tokens = doc_section_tokens + few_shot_tokens_per + vocab_tokens + system_tokens. Make assumptions explicit.
2. **Share doc context across sub-prompts.** Pass the parsed doc ONCE via Bedrock Converse session or as a cached prefix (Anthropic prompt caching is GA — exploit it). Few-shots vary per sub-prompt, but the current doc is the big tokens-and-it's-constant.
3. **Shrink few-shots.** Five full-doc few-shots is indefensible at this cost. Use structured few-shots: just the EXTRACTION TABLE + a 200-token synopsis of the source doc. Store source doc pointer + extraction; don't re-hydrate full source in few-shots.
4. **Re-test the decomposition claim.** Per W2.3, Research Gap #2 is already "monolithic-vs-decomposed on our schemas." Ship Phase 1 monolithic (per C3), run the A/B in Phase 1.5. If decomposition wins by <2pt and costs 3-5× more, monolithic wins on cost.

**Evidence from reports:** Research Brief Q6 "So What": "Don't go all the way to per-field." Q6 "Research Gap #2": "monolithic-vs-decomposed empirical comparison on our specific 9/8 field schema is an open question." The architecture has already internalized this as a Phase 1.5 A/B — but ships DECOMPOSED as the Phase 1 default, which is the expensive side of the unproven A/B.

---

### W3. HITL-approved extractions feed the few-shot pool with no quality gate — feedback-loop risk

**Issue:** §8 + §9: "Append approved extraction to few-shot store." Reviewer makes a mistake → mistake is stored as a future few-shot → MMR kNN retrieves it → future extractions pattern-match on the mistake → more mistakes slip past HITL with higher confidence → mistakes feed back. No mechanism to detect or break this loop.

In a solo-reviewer Phase 1 this is especially risky: there is no inter-annotator check. If the reviewer has a systematic blind spot (e.g., always picks the wrong unfunded value on a specific GP template), that blind spot becomes the template's self-reinforcing pattern.

**Why it matters for THIS project:** Compounding error in a financial domain. The Design Brief explicitly says "Capture human corrections as a ground-truth labeling flywheel that enables future fine-tuning" — if the flywheel is poisoned, the fine-tune training data is poisoned.

**Severity:** Warning.

**Concrete alternative / mitigation:**

1. Separate two pools: `few_shot_exemplars_silver` (any HITL-approved) and `few_shot_exemplars_gold` (double-reviewed OR matches golden-eval-set entries). Phase 1 retrieval uses SILVER. Phase 2 (multi-reviewer) unlocks GOLD and retrieval prioritizes GOLD.
2. Add a `few_shot_provenance` column: which extractions produced this few-shot's values? If value_X was derived from few-shot_Y, down-weight Y in later retrievals for value_X (feedback-loop attenuation).
3. Audit: periodically sample approved extractions and flag outliers (extractions where ALL few-shots retrieved came from the same template — sign of echo-chamber retrieval).
4. MMR diversity re-ranking already helps (prevents k-near-duplicates) but doesn't prevent systematic error. Explicit gold/silver split is the real fix.

**Evidence from reports:** Design Brief §"HITL Flywheel" #5 mentions inter-annotator agreement as Phase 2 — that's the structural safety. Architecture should note that Phase 1's flywheel is provisional until Phase 2 multi-reviewer lands, and should not promote single-reviewer-approved extractions directly into a "trusted examples" pool without the gate.

---

### W4. Classification → polymorphic schema routing has no feedback path on misclassification

**Issue:** §4 + §5: Haiku classifies as "capital_call" → `CapitalCallExtractor` runs with CC schema → extractor returns best-effort CC fields. If Haiku was WRONG (doc was actually a distribution), the CC extractor extracts null/garbage for the fields that don't exist in the doc. §7's reconciliation will fail (dates don't match call/due pattern, amounts don't reconcile) and the doc routes to HITL — but as a "failed extraction" not a "reclassify" signal. The reviewer has to notice "oh this is actually a distribution, someone please reroute this," which is extra friction and a documented annoyance in every labeling tool.

There's no feedback loop that says "if CC extractor systematically fails reconciliation for docs from GP X, maybe Haiku is misclassifying GP X's template."

**Why it matters for THIS project:** §9 Research Brief "So What" cites 3-class (CC / Distribution / Other) accuracy at 98%+ expected. At 1000 docs/month, 2% = 20 misclassified docs/month = 20 extra HITL items that the reviewer has to reclassify-and-reroute manually.

**Severity:** Warning.

**Concrete alternative / mitigation:**

1. **Reclassify-on-reconciliation-fail:** If the extraction step's reconciliation invariants ALL fail, re-run classification with Sonnet (not Haiku) and an explicit "previous classification was X; re-evaluate given reconciliation failed" prompt. If Sonnet disagrees, route to HITL with "likely misclassified" flag.
2. **HITL UI reclassify button:** Let the reviewer one-click "actually this is a Distribution" → skill re-runs the pipeline with the corrected class. Add `reclassified_from` audit field so the signal isn't lost.
3. **Drift metric:** track per-template reclassification rate. If GP template T has >5% reclassification, the classifier is unreliable on T and deserves a dedicated few-shot example in the classifier prompt.

**Evidence from reports:** Research Brief Q9 cites 0.85+ F1 on zero-shot classification, 98%+ expected here. The 2% residual is exactly where this feedback path earns its keep. §16 Open Question #3 asks about reconciliation invariants catching silent errors — reclassification IS a silent-error class.

---

### W5. Master-data lookup's "restricted access" fallback is unspecified — name-field accuracy ceiling could be silently capped

**Issue:** Design Brief constraints table: "Master-data access: Exists but access is restricted/slow/ops-dependent." Architectural seam at §6: "Phase 1: mock master list (CSV). Phase 1.5: wired to real master." What if access NEVER arrives? The architecture is silent. Fund-admin IT shops notoriously drag on cross-team data access (the user's own operator experience flagged this).

Without real master-data: name canonicalization falls back to rapidfuzz against whatever CSV the user manually maintains. LP/GP name variation (user-flagged as HIGH) gets partial-match — some variants don't map. HITL has to correct manually. No ceiling is stated; the architecture quietly assumes Phase 1.5 works.

**Why it matters for THIS project:** The user SAID name variance is the single hardest field class. Master-data was elevated from phase-2 to phase-1 because of this. If the dependency fails, the accuracy target (≥95% raw per Design Brief) for LP/GP fields is unreachable — silently.

**Severity:** Warning.

**Concrete alternative / mitigation:**

1. **Make the fallback explicit.** Architecture §6 should add a "If master access never arrives" section: manually-maintained CSV of ~100-500 most-frequent LPs/GPs, updated from HITL corrections, with an explicit "accuracy-ceiling accepted" caveat.
2. **Bootstrap the fallback CSV from HITL.** Every HITL-corrected LP/GP name goes into a running canonical-name table. At 100+ unique names, the fallback IS a working master-list for your corpus (not the fund's whole master, but yours).
3. **Surface the dependency clearly.** The §15 Phase 1.5 section currently lists "Master-data integration wired (when access resolved)" — change to "Master-data integration wired IF access resolved by week N; else switch to CSV-maintained fallback with accuracy-ceiling note in eval report."

**Evidence from reports:** Design Brief constraints table (quoted) + user's domain input #1.

---

### W6. Bedrock Converse structured output is 2 months old (GA Feb 2026) — edge-case risk underestimated

**Issue:** Scout Q5 flags it as Mainstream but under "Emerging tools with insufficient history" explicitly notes: "Native Bedrock structured output (GA Feb 2026, 2 months old at time of writing) — watch for edge-case breakage. Instructor's retry-on-error is the safety net." The architecture uses Bedrock Converse structured output as foundational in §4 (classification), §5 (all 4-5 extraction sub-prompts), plus Instructor-wrapped on top. The safety net is: Instructor retries on Pydantic validation failure, `max=2` retries implied in §11.

The failure mode Scout is worried about is not "malformed JSON" (Instructor catches that). It's "edge-case semantic quirks" — e.g., Converse silently truncates nested reasoning fields, or emits enum values with case differences, or decays accuracy on long-context extraction. Those don't trigger Pydantic validation failure; they produce plausible-but-wrong extractions that go unretried.

**Why it matters for THIS project:** Every LLM call in the hot path uses this surface. If Bedrock Converse has a quiet breakage in month 3, the blast radius is the entire production pipeline, and the signal is "accuracy dropped on the golden eval" — not a loud error.

**Severity:** Warning.

**Concrete alternative / mitigation:**

1. **Golden eval replay cadence** (already covered in C4 ritual-health) catches silent regression IF it runs on schedule.
2. **Bedrock model version pinning:** in the Instructor config, pin to exact model IDs (e.g., `anthropic.claude-3-5-sonnet-20240620`) so AWS side-grade doesn't silently change behavior. Architecture §14 says model version is captured in provenance; confirm model pinning too.
3. **Instructor fallback to tool-use:** if native structured output breaks, Instructor's `tool_use` mode is the well-understood alternative. Document the fallback in `claude/rules/` and budget a few hours for a proactive swap when/if Bedrock Converse ships a breaking change.
4. **Alert on retry-rate spike.** If Instructor's retry rate jumps from ~1% baseline to 5%+, structured output is degrading. Log retry-rate and include in the drift dashboard.

**Evidence from reports:** Scout Q5 + "Emerging tools" section.

---

### W7. Golden eval set starting at 10 docs cannot represent 10-50 templates

**Issue:** §12: "Start: 10-20 hand-picked labeled docs, diverse across templates/GPs." Design Brief says 10-50 templates. 10 docs / 10-50 templates = under-1 coverage per template. The eval is guaranteed to miss template-specific regressions (e.g., prompt change that fixes Template A while breaking Template B — replay on 10 docs won't catch the Template B regression because Template B isn't in the eval set).

**Why it matters for THIS project:** §12 "Regression gate: any per-field F1 drop > 2pts fails deploy." At 10 docs, a 2pt F1 drop is 0.2 extractions — statistical noise. The gate doesn't work.

**Severity:** Warning (not Critical because the risk manifests as false-negatives on the eval, not as immediate production failure).

**Concrete alternative / mitigation:**

1. Raise the Phase 1 target to 20-30 labeled docs across at least 5 distinct templates. That's still aggressive given <50 labels exist total, but it's the minimum credible eval set.
2. Per-template accuracy alongside per-field: track accuracy by `(template_fingerprint, field)` so regression on a specific template is visible even if overall F1 holds.
3. Raise the regression gate threshold (`>5pt` not `>2pt`) until eval size ≥ 50 — statistical power is too low for tight thresholds at small n.
4. Prioritize the Phase 1.5 growth from 10→50 as a calendar-bound goal, not a lag indicator.

**Evidence from reports:** Analyst Research Gap #1 mentions extraction calibration is thin but this is a different issue — sample size for regression detection. §16 Open Question #8 flags "<20 labels means noisy empirical weights" — same shape of problem, one level deeper (eval-set noise vs confidence-weight noise).

---

## Observation (minor / nice-to-have)

### O1. Vocabulary dictionary maintenance is an undescribed workflow

§6: "Vocabulary canonicalization — spaCy Matcher with a domain-vocab table mapping variants (`'uncalled capital' → 'unfunded_commitment'`)." Where does the table live? Who updates it? When a new variant appears in HITL corrections, what's the workflow to add it? Architecture §6 TRADE-OFF says "Correction-attribution dashboard drives updates" but the dashboard is in §13 and doesn't describe how corrections flow back to the vocab table. Likely fine in practice (solo dev edits the table manually), but worth one paragraph in §6 describing the loop.

**Mitigation:** Add to §6: the vocab table is a YAML/CSV file in `claude/rules/vocab-dictionary.yaml`; after HITL reviewer corrects a new variant, a cron job or manual script writes the proposed addition to a PR; user reviews and merges. Or even simpler: reviewer flags a correction as "new vocab variant" in HITL UI → it's auto-appended to the file.

### O2. "One Postgres" coupling migration pain

§1: jobs + audit + embeddings + master-data cache + eval results all in one DB. This is fine at Phase 1 scale, but a schema migration (e.g., changing the `extractions` table structure) requires coordinating across five domains simultaneously. Use Alembic from day 1 for structured migrations; document schema-compatibility policy (backward-compatible changes OK; breaking changes require all components re-deployed together).

**Mitigation:** Add a paragraph to §9 noting the migration strategy.

### O3. Reasoning field token cost across sub-prompts

Each extraction sub-prompt emits 200-500 tokens of reasoning before structured output. Across 4-5 sub-prompts per doc × 1000 docs/mo = 4M-10M tokens of reasoning overhead per month. Sonnet output pricing ~$15/M = $60-150/month purely on reasoning. Not catastrophic but worth knowing the number.

**Mitigation:** Track reasoning token count in provenance; if it's dominating cost, experiment with shorter reasoning prompts ("reason briefly in 2-3 sentences") or drop reasoning for the easier groups (Currency, Type) where full reasoning is overkill.

---

## Assumption Audit

| Assumption | Classification | Evidence (or lack) | If wrong... |
|---|---|---|---|
| 4-6 weeks solo-dev suffices for Phase 1 scope | **Dangerous** | No evidence; scope is ~30 components | Timeline slips 2-8 weeks; user ships incomplete MVP or burns out (C3) |
| Three parser implementations in Phase 1 are affordable | **Dangerous** | Contradicts user's own sequencing | 2 weeks lost to parser glue instead of pipeline value (C2) |
| User has an Azure subscription (for Azure DI parser) | **Unvalidated** | Never asked | Third parser silently drops; architecture story shrinks |
| Docling is stable enough for production financial IE at 8 months old | **Plausible** | 58k stars, IBM-backed, 100+ releases (Scout Q1) | Phase 1 hits a Docling bug; swap to BDA earlier than planned (expensive but not fatal) |
| Bedrock Converse structured output is stable at 2 months GA | **Plausible** | GA Feb 2026 | Quiet semantic breakage in month 3 (W6); golden eval catches it IF run (C4) |
| LangGraph's 2026 API churn cost is "quarterly upgrade" only | **Plausible (optimistic)** | Scout flagged instability | More-than-quarterly disruption; isolation+pinning cap the blast radius (W1) |
| The user's master-data access will arrive by Phase 1.5 | **Unvalidated** | Design Brief says "restricted/slow/ops-dependent" | Name-accuracy ceiling silently capped (W5) |
| Golden eval of 10 docs gates regressions credibly | **Dangerous** | Statistical power is insufficient at n=10 | Silent prompt regressions ship (W7) |
| Reviewer (solo = user) will clear HITL queue on a cadence | **Dangerous** | No ritual trigger (C4) | Queue backs up, pipeline stalls silently |
| `$20-200/mo` extraction cost at 1000 docs/mo | **Dangerous** | Back-of-envelope shows $250-$1050 (W2) | Per-doc cost target exceeded by 2.5-10× |
| Decomposition beats monolithic on THESE schemas | **Plausible** | Strong general literature (Q6); thin extraction-specific evidence | Phase 1.5 A/B reverses the default; Phase 1 build was expensive and wrong |
| HITL-approved extractions are "trusted enough" as few-shots | **Plausible (optimistic)** | No quality gate described (W3) | Single-reviewer mistakes propagate into pattern-matching |
| `Unfunded(before) − Capital call = Unfunded(after)` invariant is dropped intentionally | **Dangerous** | Contradicts user's explicit statement (C1) | Most-likely silent error class goes uncaught |
| Haiku classifier errors are recoverable via HITL alone | **Plausible** | No reclassification feedback path (W4) | Per-template misclassification accumulates |
| Phase 1.5 calibration study will actually happen | **Dangerous** | No forcing function (C4) | Confidence ensemble stays at literature defaults indefinitely |
| User's Anthropic/AWS usage caps accommodate the build + production | **Unvalidated** | Not asked | Rate-limits / cap-hits silently degrade throughput |
| The reviewer UX (bulk-approve, keyboard nav, per-field bands) is learnable by a solo reviewer quickly | **Plausible** | Scout backed custom UI choice; user is the reviewer and the dev | Slight learning curve; not load-bearing |
| Phoenix (instead of Langfuse) is sufficient for Phase 1 observability | **Plausible** | Scout Q6 | Phase-2 migration to Langfuse if infra team arrives — bounded future work |

**Dangerous assumptions = 7.** They cluster around: timeline, scope (three parsers, decomposition-first, 10-doc eval), rituals, clarification-propagation failures, and cost math. These are the highest-impact fixes.

---

## Overengineering Assessment

| Component | Simpler alternative | Complexity savings |
|---|---|---|
| Three parser implementations in Phase 1 | One parser (Docling); add BDA in Phase 1.5 A/B; drop Azure DI unless user confirms Azure subscription | ~8-14 days solo-dev; one cloud dependency avoided |
| Per-field-group decomposition (4-5 sub-prompts) as Phase 1 default | Monolithic per-schema extraction in Phase 1; A/B against decomposed in Phase 1.5 (already listed) | 3-5× extraction cost reduction; ~1 week build; consistent with Research Gap #2 recommendation |
| Soft-signal confidence ensemble (min-logprob, eventual semantic entropy, self-consistency) in Phase 1 | Hard signals only in Phase 1 (schema-adherence, reconciliation, master-data hit); soft signals in Phase 1.5 after calibration study | Removes calibration-study blocker; simpler tri-state (`absent / validated / failed`); ~1 week build |
| Arize Phoenix in Phase 1 | Structured Python logging + OTel-to-stdout in Phase 1; Phoenix as Phase 1.5 when dashboards actually consumed | ~3-5 days setup + ongoing Docker-container care avoided |
| LangGraph (user-requested, accept risk) | Plain Python + Postgres queue (Scout Q2 recommendation); evaluate LangGraph as Phase 1.5 experiment | ~3-5 days learn/integrate; quarterly upgrade-tax avoided; STRONGER interview narrative ("I compared X to Y on a real pipeline") |
| Drift dashboard | Weekly drift report as markdown file in git; dashboard Phase 2 | ~2-3 days; forcing-function improves |
| Embedding reasoning-first field on Currency & Distribution-Type sub-prompts | Skip reasoning field for simple enum sub-prompts; keep on Names/Dates/Amounts | ~10-20% token savings on those groups |
| Full `schemas/` + `fingerprint cache` + `master_data_cache` + audit + eval tables simultaneously in one DB | Alembic migrations from day 1 + explicit schema-compatibility policy | Doesn't remove work, but prevents the coupling becoming migration hell (O2) |

**Combined Phase 1 scope cut if all simplifications accepted:** roughly 3-4 weeks of solo-dev work saved. That's the difference between "4-6 weeks" being fictional and "4-6 weeks" being plausible.

---

## AI-Specific Risks

| Risk | Present? | Severity | Mitigation in design? | Residual concern |
|---|---|---|---|---|
| Prompt injection via adversarial doc text | Yes (adversary-authored notices) | Medium | §11: spotlighting + schema + reconciliation + HITL | Acceptable (layered defense per Analyst Q10). Should include an injection test in the golden eval set (noted in §12 research-brief mapping but not explicit in §12 architecture). |
| Hallucination propagation (chained LLM calls: classify → extract) | Yes | Medium | Reclassify feedback path missing (W4); HITL as final gate | W4 unresolved |
| Context window overflow (multi-page notices + 5 few-shots + vocab) | Yes | Medium | Tiered chunking in Analyst Q12; §9 does "layout-aware chunking" but only "phase 2 addition" for hybrid BM25; current full-doc-in-few-shots is expensive (W2) | W2 unresolved |
| Token cost explosion | Yes | Warning | §5 claims $20-200/mo without math | W2 challenges the claim directly |
| Model deprecation / version churn | Yes | Low | Provider abstraction via Instructor; model IDs in provenance | Confirm: pin exact model IDs (W6 mitigation) |
| Eval-production gap | Yes | Warning | Golden eval harness + drift via HITL correction rate | n=10 is too small (W7); rituals decay (C4) |
| HITL reviewer fatigue (solo) | Yes | Warning | Keyboard-first UI, bulk-approve | Queue-size alert missing (C4); over-trust threshold escalation not bounded (open Q7) |
| Cold-start miscalibration (confidence ensemble weights on <20 labels) | Yes | Warning | §7 TRADE-OFF acknowledges; says "start conservative" | No literature-default fallback if calibration study delayed (open Q8) |
| Few-shot feedback loop (HITL mistakes propagate) | Yes | Warning | None (W3) | W3 unresolved |
| Bedrock Converse + Instructor stack young (2 months GA) | Yes | Warning | Instructor retry on validation | Semantic errors slip past validation (W6) |

---

## Evidence Grounding Audit

| Decision | Evidence quality | Grounded? | Notes |
|---|---|---|---|
| LMDX-style layout + frontier LLM (§1, §5) | Strong (Perot ACL 2024; DocLLM JPMorgan) | ✅ Well-grounded | Direct, peer-reviewed, financial-domain. |
| Schema-guided generation + reasoning-first (§4, §5) | Strong (Tam EMNLP 2024; Park NeurIPS 2024) | ✅ Well-grounded | Tam finding directly motivates reasoning-first design. |
| Dynamic few-shot + MMR (§5, §9) | Strong (Liu DeeLIO 2022) | ✅ Well-grounded | Gains on generation tasks; extraction-specific effect-size is moderate. |
| Per-field-group decomposition as Phase 1 DEFAULT (§5) | Moderate (DecomP ICLR 2023 strong for general; extraction-specific thin, per Research Gap #2) | ⚠️ Partial | Ships decomposed despite research-brief flagging monolithic-vs-decomposed as an open question. Should monolithic be the Phase 1 default with A/B in Phase 1.5? Analyst explicitly recommends A/B (W2, C3). |
| Confidence ensemble over single signal (§7) | Strong (Farquhar Nature 2024; Kadavath 2022) | ✅ Well-grounded | But soft-signal weight TUNING on n=20 is the gap (Phase 1.5 calibration study — ritual risk C4). |
| Spotlighting for injection defense (§11) | Strong (Hines Microsoft 2024) | ✅ Well-grounded | Defense-in-depth is consensus. |
| pgvector over managed RAG at this scale (§9) | Strong (Scout Q3 + independent benchmarks) | ✅ Well-grounded | |
| LangGraph with isolation + pinning (§2) | Mixed — Scout DIRECTLY rejected LangGraph for this project (Q2); architecture overrides for "interview narrative" | ⚠️ **Partial — user-directed, contradicts research** | The "interview narrative" justification is valid but doesn't need three parsers + LangGraph. Pick one "interview signal" component, not two (C2 + W1). |
| Custom HITL UI (§8) | Strong (Scout Q4; HAX CHI 2019) | ✅ Well-grounded | |
| Arize Phoenix (§13) | Strong (Scout Q6 for self-hosted simplicity) | ✅ Well-grounded | But overkill for Phase 1 solo-dev (overengineering) |
| GraphRAG ruled out (§9) | Strong (Analyst Q11) | ✅ Well-grounded | |
| 4-6 week timeline (§15) | **None** | ⚠️ Unsupported | No reference to similar-scope projects; not grounded (C3). |
| `$20-200/mo` extraction cost (§5) | **None — not shown** | ⚠️ Unsupported | Back-of-envelope math contradicts the claim (W2). |
| CC invariant `Unfunded(before) − Capital_call = Unfunded(after)` | **User directive — not implemented in schema or validator** | ⚠️ **Missing** | Clarification-propagation failure (C1). |
| Tool-agnostic parser SHIPPED Phase 1 | **Contradicts user's own sequencing** | ⚠️ **Misinterpreted** | User said "after collecting data" — architecture ships three parsers day 1 (C2). |

**Evidence gaps worth naming:**
- Three decisions are **user-directed and contradict research or clarifications** (LangGraph vs Scout Q2; three parsers vs user's sequencing; dropped unfunded-before/after invariant). Two are defensible (LangGraph for interview signal — W1), one is not (dropped invariant — C1), one is interpretation-of-user-intent (parsers — C2).
- Two quantitative claims in the architecture (timeline, cost) are stated without derivation. Both are wrong or under-supported.

---

## Lens Coverage Check

| Lens | Findings |
|---|---|
| Pre-Mortem (Step 2) | C3 (timeline collapse), C4 (ritual decay in 6 months), W3 (feedback loop), W4 (misclassification accumulation), W6 (silent Bedrock breakage) |
| Assumption Audit (Step 3) | C2 (three parsers assumption), C3 (timeline assumption), W5 (master-data), W7 (eval-set size), 7 Dangerous in the audit table |
| Overengineering (Step 4) | C2 (parsers), C3 (stack breadth), W1 (LangGraph), O-table items (Phoenix, ensemble soft signals, decomposition) |
| AI-Specific (Step 5) | W2 (token economics), W3 (feedback loop), W4 (misclassification), W6 (Bedrock Converse edge cases), ensemble-cold-start (C4) |
| Evidence Grounding (Step 6) | C1 (invariant not implemented), C2 (contradicts user sequencing), W1 (contradicts Scout), W2 (cost claim not shown), W7 (eval statistical power) |
| Clarification-Propagation (cumulative lesson) | C1 (primary), C2 (primary), W5 (partial) |
| Prior-Session Calibration (cumulative lesson) | C4 (carries LinkedIn+job-search pattern forward) |

Findings draw from all six lenses plus both cumulative-lesson sources. **No single-lens clustering** — e.g., pre-mortem alone provides only 2 of 4 criticals; clarification-propagation supplies the other 2.

---

## Self-Check

- [x] ≥3 risks with severity ratings — 4 Critical + 7 Warning + 3 Observation = 14 items, capped below 10 Warning+Critical per SOP
- [x] Each risk has a concrete alternative — C1-C4 and W1-W7 each carry explicit mitigation steps with file/schema/cadence specifics
- [x] Assumption Audit present — 18 assumptions classified; 7 Dangerous flagged
- [x] Overengineering Assessment present — 8 components with simpler alternatives + complexity-savings estimates
- [x] Items from multiple lenses — findings draw from Pre-Mortem, Assumption, Overengineering, AI-Specific, Evidence Grounding, plus both cumulative-lesson streams (clarification-propagation, prior-session calibration)
- [x] Past-review calibration applied — LinkedIn ritual-decay CRITICAL 3 and job-search C2/W1 directly inherited into current C4; clarification-propagation lesson directly surfaced C1 and C2
- [x] No theoretical-risk-without-impact — every item has a THIS-project-specific plausibility described (1000 docs/mo, financial domain, solo dev, 4-6 week timeline)
- [x] No alternative-free criticism — every Critical and Warning includes a named replacement or mitigation specific enough to execute

---

## Verdict for Design Lead

**YELLOW** — architecture is fundamentally sound; three categories of surgery required before implementation:

1. **Schema fix (C1):** split unfunded into before/after; add the validator. ~1 day.
2. **Scope cuts (C2, C3, W1):** drop 2 of 3 parsers, move decomposition + soft-signal ensemble + Phoenix to Phase 1.5, reconsider LangGraph. Recovers ~3-4 weeks of timeline credibility.
3. **Ritual triggers (C4):** hard-wire golden-eval CI gate, HITL queue SLO, drift weekly file, calibration-study calendar deadline. ~2 days of spec work, prevents 6-month silent failure.

Plus six Warnings (W2-W7) that are fixable with targeted edits to the architecture doc. After those edits, this is a defensible Phase 1 architecture and an interview-strong project.
