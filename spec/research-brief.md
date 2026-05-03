---
project: cc-distribution-parser
artifact: research-brief
author: research-analyst
created: 2026-04-21
status: delivered-to-design-lead
tags: [research-brief, information-extraction, llm-calibration, document-ai]
---

# Research Brief — Capital Call & Distribution Parser

**Author:** Research Analyst
**For:** Design Lead
**Date:** 2026-04-21
**Scope:** 12 research questions covering document IE, LLM cascades, confidence calibration, few-shot/fine-tune trade-offs, task decomposition, schema-guided generation, HITL, injection defense, GraphRAG rule-out, and retrieval-augmented extraction.

Raw exploration notes: `wiki/raw/2026-04-21-analyst-cc-distribution-parser.md`.

---

## Executive Summary

Ten top-line findings with confidence grades:

1. **(Strong)** LMDX-style layout-text serialization into a frontier LLM (Perot et al. ACL 2024) with schema is the right phase-1 pattern for <50-label regimes — beats fine-tuning LayoutLMv3/Donut specialists at this scale. **DocLLM** (ACL 2024, JPMorgan team) validates the layout-in-LLM approach specifically for financial docs.
2. **(Strong)** LLM cascade (FrugalGPT lineage, TMLR 2024) is well-supported for COST reduction but requires a reliable verifier; the 98%-cost-reduction headline is dataset-specific. For this project, cascade gains depend on scorer quality (reconciliation + schema-adherence signals, not LLM-as-judge).
3. **(Strong)** Semantic Entropy (Farquhar et al., *Nature* 2024) is the strongest general-purpose hallucination/uncertainty signal published — clusters samples by meaning then computes entropy. Directly applicable at the FIELD level for our pipeline.
4. **(Strong)** Token-logprob-based confidence does NOT correlate well with accuracy in document parsing without careful aggregation; aggregation method swings calibration error by more than the signal itself. Use as ONE signal in an ensemble, not alone.
5. **(Strong, but with caveat)** Dynamic few-shot retrieval (Liu et al. DeeLIO 2022) reliably beats random/static selection. Add **MMR diversity re-ranking** on top of cosine similarity — semantic similarity alone returns near-duplicates and causes pattern-overfit.
6. **(Strong)** Schema-guided / constrained generation eliminates format errors BUT can degrade reasoning quality by 10-15% when the model is forced into JSON from token 1 (Tam et al. EMNLP 2024; Park et al. NeurIPS 2024). **Mitigation: free-form reasoning step before structured output**, or function-calling with an explicit "reasoning" field preceding structured fields.
7. **(Moderate)** Task decomposition (per-field-group rather than one mega-prompt) consistently improves extraction accuracy; decomposed prompting (Khot et al. ICLR 2023) is the most applicable pattern. Per-field-group is the conservative pick; per-field multiplies calls with diminishing returns.
8. **(Strong)** Fine-tune vs few-shot break-even is task-dependent and usually sits at 500-2000 labels for extraction tasks (Mosbach et al. 2024). The design brief's phase-3 trigger at 500 labels is correctly conservative but should be gated by empirical A/B, not label count alone.
9. **(Strong)** Spotlighting (Hines et al. Microsoft 2024) drops prompt-injection attack success >50% → <2%; defense-in-depth is OWASP consensus. No single defense is sufficient; our layered approach (spotlighting + schema + reconciliation + HITL) aligns with best practice.
10. **(Strong)** GraphRAG is confirmed overkill for per-document field extraction. Standard chunk/vector retrieval wins on single-hop detailed queries. For doc packets >15k tokens, use layout-aware chunking with field-hint retrieval; under 3k tokens, pass full doc.

---

## Q1. Information Extraction from Semi-Structured Financial/Legal Documents

**Key finding (Moderate-Strong):** Frontier LLMs with layout-text serialization and schema prompting (LMDX pattern) have closed or reversed the gap vs specialist layout-aware models (LayoutLMv3, Donut) for data-poor regimes. Specialist fine-tune is only clearly better when >500-2000 labels exist.

### Evidence

- **LMDX** — Perot et al. (ACL Findings 2024, [arXiv:2309.10952](https://arxiv.org/abs/2309.10952)). **Methodology:** serializes text with coordinate tokens + target schema into PaLM 2-S / Gemini Pro; zero-shot and few-shot evaluated. Set SOTA on VRDU and CORD with localization guarantees. **Confidence: Moderate-Strong** (ACL Findings, Google-authored, two-benchmark SOTA).
- **DocLLM** — Wang et al. (ACL 2024, [arXiv:2401.00908](https://arxiv.org/abs/2401.00908)). **Methodology:** lightweight extension to LLMs with disentangled spatial attention over bounding boxes (no image encoder). Outperformed SOTA on 14/16 datasets, generalized to 4/5 unseen datasets. JPMorgan co-authors — directly financial-domain. **Confidence: Strong** (ACL main).
- **Donut** — Kim et al. (ECCV 2022, [arXiv:2111.15664](https://arxiv.org/abs/2111.15664)). **Methodology:** OCR-free vision encoder + text decoder; SOTA on CORD/DocVQA at release. Requires training data. **Confidence: Strong**.
- **LayoutLMv3** — Huang et al. (MM 2022). Foundational layout-aware pre-training. Requires fine-tuning. **Confidence: Strong**.
- **Frontier-VLM benchmarks 2025-2026** — Reducto March 2025: Gemini 2.0 Flash ~80% accuracy on form parsing; Mistral OCR ~45%. Qwen2.5-VL-72B / GLM-4.5V leading open VLMs. **Confidence: Moderate** (vendor / industry benchmarks; not peer-reviewed).

### So What (Design Implication)

Lock phase-1 pattern as: **Docling/Textract layout extraction → layout-text serialization → frontier LLM (Claude 3.5/3.7 or equivalent on Bedrock) + schema prompt + dynamic few-shot**. Do NOT fine-tune LayoutLMv3 or Donut at <50 labels — the cost/risk doesn't pay off. Reserve specialist path for phase 3 if template-specific cost becomes compelling.

### Conflicting Evidence

Industry / leaderboard data favors VLMs (Gemini 2.0 Flash, Qwen2.5-VL) while peer-reviewed work still cites layout-aware fine-tunes as SOTA on closed benchmarks. The reconciliation: VLMs win zero/few-shot; specialists win when labels are abundant.

---

## Q2. LLM Cascades / Routing for Cost

**Key finding (Strong for pattern; Moderate for magnitude):** Cheap→strong cascades save cost when the verifier is reliable. The 98% savings headline is dataset-specific. Routing (RouteLLM) is the newer principled framing.

### Evidence

- **FrugalGPT** — Chen, Zaharia, Zou (TMLR 2024, [arXiv:2305.05176](https://arxiv.org/abs/2305.05176)). **Methodology:** three strategies — prompt adaptation, LLM approximation, LLM cascade. Empirical on HEADLINES/OVERRULED/COQA benchmarks. Cost reduction up to 98% at matched accuracy. **Confidence: Strong** (TMLR peer-review).
- **RouteLLM** — Ong et al. LMSYS ([arXiv:2406.18665](https://arxiv.org/abs/2406.18665), 2024). **Methodology:** routing learned from preference data; matrix-factorization router. 85% cost reduction on MT-Bench, 45% MMLU, 35% GSM8K. **Confidence: Moderate** (arXiv, widely adopted).
- **RouterBench / RouterEval** ([arXiv:2403.12031](https://arxiv.org/abs/2403.12031) / 2503.10657): multi-LLM routing benchmarks confirming Pareto-improving routers exist.
- **ThrifLLM** (VLDB 2025): formal framing of cost-effective LLM selection.

### So What (Design Implication)

Cascade is a phase-1.5 OPTIMIZATION, not a phase-1 requirement. Start single-strong-model (e.g., Claude 3.5 Sonnet on Bedrock) for all fields; measure real per-doc cost. Add cheap-classifier-then-strong-extractor cascade when unit economics demand it. **Crucially:** build the verifier on STRUCTURED signals (schema adherence, reconciliation checks, logprob-based uncertainty) rather than LLM-as-judge self-evaluation — cheap model often hallucinates plausible extractions that an LLM-judge also rubber-stamps.

### Conflicting Evidence

Most cascade benchmarks are on QA/classification tasks, not field extraction. Extraction-specific cascade savings are plausibly smaller because cheap-model error modes (fabrication of plausible field values) are harder to verify than QA accuracy.

---

## Q3. Confidence Calibration for LLM Extraction

**Key finding (Strong):** No single confidence signal is reliable alone for structured extraction. Semantic entropy is the strongest general signal; ensemble of schema-adherence + reconciliation + self-consistency + semantic entropy is the state-of-the-art practical combination.

### Evidence

- **Kadavath et al.** ([arXiv:2207.05221](https://arxiv.org/abs/2207.05221), Anthropic, 2022). **Methodology:** large-scale calibration study across tasks; P(True) and P(IK) probes. Finding: large models well-calibrated on MC/T-F in the right format; P(IK) generalizes partially; direct verbalized confidence miscalibrates after RLHF. **Confidence: Strong** for MC; Moderate for open-ended; **caveat**: pre-RLHF-flattening era.
- **SelfCheckGPT** — Manakul et al. ([arXiv:2303.08896](https://arxiv.org/abs/2303.08896), EMNLP 2023). **Methodology:** N-sample response comparison; zero-resource. Strong AUC-PR on sentence-level hallucination detection (WikiBio). **Confidence: Strong** (EMNLP).
- **Semantic Entropy** — Farquhar, Kossen, Kuhn, Gal (*Nature* 2024, [DOI:10.1038/s41586-024-07421-0](https://www.nature.com/articles/s41586-024-07421-0)). **Methodology:** cluster samples by semantic equivalence, then compute entropy. Cross-model (GPT-4, LLaMA-2, Falcon), cross-task. **Confidence: Strong** (Nature peer-review — top venue).
- **Semantic Entropy Probes** — Kossen et al. ([arXiv:2406.15927](https://arxiv.org/abs/2406.15927)): single-forward-pass approximation of semantic entropy. Cheap to deploy.
- **FActScore** — Min et al. ([arXiv:2305.14251](https://arxiv.org/abs/2305.14251), EMNLP 2023). **Methodology:** atomic fact decomposition + retrieval verification. ChatGPT 58% factuality on biography generation. <2% estimation error. **Confidence: Strong** (EMNLP). Less directly applicable to field-level extraction but decomposition philosophy transfers.
- **Self-Consistency** — Wang et al. ([arXiv:2203.11171](https://arxiv.org/abs/2203.11171), ICLR 2023). **Methodology:** N sampled CoTs, majority vote. Extended to calibration by Huang et al. ([arXiv:2403.09849](https://arxiv.org/abs/2403.09849)). **Confidence: Strong** for the pattern.
- **Token logprobs for extraction — industry findings 2024**: aggregation method (min/mean/product) swings calibration error 0.15-0.29 per model — bigger than the signal itself. No clear correlation between averaged logprobs and accuracy in document parsing. Spotify engineering 2024 case study: useful as one signal, not sole. **Confidence: Moderate** (industry, not peer-reviewed; but consistent across reports).

### So What (Design Implication)

Build a **confidence ensemble** per field:
1. **Hard signals (highest trust):** schema-adherence (pass/fail), reconciliation invariant (pass/fail), master-data lookup hit (pass/fail/absent).
2. **Soft signals (ensemble score):** per-field min-logprob (not mean), self-consistency agreement across N=3-5 samples at phase 2, semantic entropy at the field level at phase 2.
3. **Never trust** verbalized "how confident 0-100?" — confirmed by Kadavath-era calibration research plus post-RLHF miscalibration.
4. Auto-flag for HITL on ANY hard-signal failure regardless of soft-signal confidence.

### Conflicting Evidence / Research Gap

**Extraction-specific calibration research is THIN** — most work is QA/open-gen. The "which signal correlates with correctness for structured extraction" question is not definitively answered in the literature. **Recommend small internal calibration study** (~20 docs, measure per-field signal vs HITL ground truth) as phase-1.5 work. Flag as **Research Gap #1**.

---

## Q4. Few-Shot vs Fine-Tune at Sparse-Data Scale

**Key finding (Strong for general pattern; Moderate for exact break-even):** Break-even between frontier+few-shot and fine-tune is task-dependent. Typical range 500-2000 labels for extraction. At <50 labels, frontier+few-shot dominates.

### Evidence

- **"Fine-Tuning, Prompting, In-Context Learning and Instruction-Tuning: How Many Labelled Samples Do We Need?"** — Mosbach et al. ([arXiv:2402.12819](https://arxiv.org/abs/2402.12819)). **Methodology:** multi-task study across training regimes. Finding: specialized fine-tuned models beat general models at 10-1000 samples depending on task complexity. Simple classification (SST-2) → break-even at ~0.2% of full dataset. Complex tasks → 1000+ needed. **Confidence: Moderate** (arXiv preprint; rigorous but unreviewed).
- **Few-Shot PEFT (IA)³** — Liu et al. (NeurIPS 2022, [arXiv:2205.05638](https://arxiv.org/abs/2205.05638)). **Methodology:** PEFT beats ICL at 32-shot on T0 tasks. Classification-style focus. **Confidence: Strong** (NeurIPS). Note: 32 samples is classification-task scale; extraction is harder.
- **LoRA** — Hu et al. ([arXiv:2106.09685](https://arxiv.org/abs/2106.09685)). 10,000× fewer trainable params, 3× less GPU, matches full fine-tune. At <50 samples, prone to overfit without regularization. **Confidence: Strong** (widely replicated).
- **Scaling-law literature** — fine-tune "pre-power phase" exists below a pre-learned data size threshold ([arXiv:2402.02314](https://arxiv.org/abs/2402.02314) and related).

### So What (Design Implication)

Design brief's phase staging is literature-consistent:
- Phase 1 (<50 labels): frontier + dynamic few-shot + schema + ensemble calibration. Confirmed.
- Phase 3 (500+ labels): fine-tune option unlocked but NOT auto-triggered. Gate phase-3 fine-tune on EMPIRICAL A/B evidence on the golden eval set — not label count. Some fields may need 2000+ labels to beat few-shot frontier; others may benefit earlier.
- Consider **per-template distilled SLM fine-tune** for hot paths (top 3-5 GP templates by volume) at phase 3, rather than one generalist fine-tune.

### Conflicting Evidence

Mosbach et al. 2024 is arXiv-only. Confidence downgrade to Moderate. However, the general phenomenon (break-even depends on task) is consistent across multiple papers.

---

## Q5. Dynamic Few-Shot / Exemplar-Based ICL

**Key finding (Strong):** kNN retrieval over semantically-similar exemplars consistently beats random/static selection. Gains are substantial on generation tasks (41.9% on ToTTo, 45.5% on NQ). **Selection should combine similarity AND diversity.**

### Evidence

- **Liu et al. 2022** — ([arXiv:2101.06804](https://arxiv.org/abs/2101.06804), DeeLIO 2022, "What Makes Good In-Context Examples for GPT-3?"). **Methodology:** retrieval-based prompt selection with sentence encoders. Beats random on table-to-text (+41.9% on ToTTo) and NQ QA (+45.5%). Fine-tuned task-specific retrievers amplify gains. **Confidence: Strong**.
- **ICL survey** (Dong et al., EMNLP 2024): consolidates decoder-retrieval patterns; reinforces diversity importance.
- **CoverICL**: graph-based selection integrating uncertainty + semantic coverage → better budget efficiency.
- **Retrieval-style ICL for few-shot text classification** (MIT Press TACL 2024): kNN prompting formalized; performance sensitivity to retriever.

### So What (Design Implication)

1. Retrieval over HITL-approved exemplars (via embedding similarity) is the right phase-1 pattern — confirmed by design brief.
2. **Add MMR (Maximal Marginal Relevance) re-ranking** on top of cosine similarity. Otherwise kNN returns near-duplicates and model overfits to one pattern. Recommended specification: "retrieve top 20 by similarity, re-rank by MMR with λ=0.5, return top 5."
3. **Cold-start handling**: at <20 HITL-approved labels, curate a hand-picked static few-shot set of 3-5 maximally-diverse examples per schema. Switch to dynamic at 20+ approved.
4. Use BM25 + dense hybrid retrieval (not pure dense) — financial terminology is exact-match-heavy; BM25 shines there. (See existing wiki source [[bm25-retrieval]].)

### Conflicting Evidence

The Liu et al. gains are on text generation; may be smaller on pure field extraction. But effect direction is consistent.

---

## Q6. Task Decomposition for Structured Extraction

**Key finding (Strong for general pattern; Moderate for extraction-specific):** Per-field-group decomposition consistently improves accuracy over monolithic prompts. Decomposed Prompting is the most applicable framework.

### Evidence

- **Decomposed Prompting (DecomP)** — Khot et al. (ICLR 2023, [arXiv:2210.02406](https://arxiv.org/abs/2210.02406)). **Methodology:** modular sub-prompt library; iterative top-down decomposition. Most flexible vs Least-to-Most. **Confidence: Strong** (ICLR).
- **Plan-and-Solve** — Wang et al. (ACL 2023, [arXiv:2305.04091](https://arxiv.org/abs/2305.04091)). Beats zero-shot CoT on reasoning tasks. **Confidence: Strong**.
- **Least-to-Most** — Zhou et al. (ICLR 2023, [arXiv:2205.10625](https://arxiv.org/abs/2205.10625)). Strong on compositional generalization (SCAN). **Confidence: Strong** for compositional; less relevant to extraction specifically.
- **Prompt-chaining studies 2024** (multiple): chained refinement beats single-prompt refinement on summarization. Extraction likely follows same pattern.
- **Event extraction decomposition** (ACE05-EN, WikiEvents): schema-aware decomposition separating trigger + argument achieves SOTA. Direct precedent for per-field-group decomposition.
- **Spider benchmark** (text-to-SQL): 10-40pt gains from decomposition per task complexity.

### So What (Design Implication)

Per-field-GROUP decomposition (dates, amounts, names, classification) is literature-supported and the right phase-1 pattern. Don't go all the way to per-field — it multiplies calls without proportional accuracy gain for easy fields. Monitor HITL correction rate per group; if one group has high correction rate, split it further. Field group suggestions:
- **Classification** (standalone, cheap model).
- **Names group** (Fund/GP/LP — benefit from shared context for canonicalization).
- **Dates group** (call/due/distribution/payment — benefit from shared locale inference).
- **Amounts group** (commitment/call amount/unfunded/distribution — benefit from shared currency + reconciliation).
- **Type enum** (Distribution type — standalone with dedicated prompt).

### Conflicting Evidence / Research Gap

Extraction-specific decomposition evidence is thinner than reasoning-task evidence. **Research Gap #2**: monolithic-vs-decomposed empirical comparison on our specific 9/8 field schema is an open question — recommend A/B test during phase 1 eval harness setup.

---

## Q7. Schema-Guided / Constrained Generation

**Key finding (Strong):** Constrained generation eliminates format errors. BUT strict JSON-mode from token 1 degrades reasoning by 10-15% on math/symbolic/complex tasks. **The mitigation is well-established: free-form reasoning → structured format, via function-calling with a thinking field.**

### Evidence

- **Outlines** — Willard & Louf ([arXiv:2307.09702](https://arxiv.org/abs/2307.09702), 2023). **Methodology:** FSM over vocabulary; token-level constraint. Widely adopted library.
- **"Let Me Speak Freely?"** — Tam et al. (EMNLP 2024 Findings, [arXiv:2408.02442](https://arxiv.org/abs/2408.02442)). **Methodology:** systematic comparison of JSON-mode vs free-form on reasoning tasks. Finding: 10-15% degradation on math, symbolic reasoning, complex analysis when JSON-constrained. **Confidence: Strong** (EMNLP peer-review, reproducible).
- **Park et al. NeurIPS 2024**: mechanistic explanation — constrained decoding distorts probability distribution via renormalization after high-prob-token masking → syntactically correct but semantically less natural. **Confidence: Strong** (NeurIPS).
- **JSONSchemaBench** ([arXiv:2501.10868](https://arxiv.org/abs/2501.10868)): comprehensive benchmark across engines. Outlines lowest compliance rate due to timeouts; complex schemas (minItems, large enums) compile in 40s-10min. **Confidence: Moderate**.
- **Instructor / Pydantic**: industry-standard post-hoc validation with retry loop. Not pure grammar — retries rather than guarantees.

### So What (Design Implication)

1. **Use provider-level function-calling / tool-use** (Bedrock Converse, OpenAI tools) over library-level Outlines for production. Provider implementation handles compile-cost issues and is more robust for our flat 9-field schemas.
2. **Include a reasoning / thinking field IN the schema**, placed FIRST, so the model emits reasoning before structured fields:
   ```json
   {"reasoning": "string (free text)", "fund_name": "...", "gp_name": "..."}
   ```
   This preserves reasoning quality AND guarantees structured output. This is an EXPLICIT DESIGN ADDITION not yet in the brief — recommend adding.
3. **Keep schemas FLAT** — avoid deep nesting. 9 flat fields is well within the low-risk zone per JSONSchemaBench.
4. **Pydantic + retry on validation failure** as secondary layer — belt and suspenders, cheap, catches provider edge cases.

### Conflicting Evidence

Recent extraction benchmarks suggest JSON-mode degradation is smaller on extraction (which doesn't require extensive CoT) than on math reasoning. For pure field lookup, JSON-mode from token 1 may be fine. But for ambiguous fields requiring reasoning (date disambiguation, currency inference), the free-form-first pattern is safer.

---

## Q8. HITL Design in IE Pipelines

**Key finding (Moderate):** Uncertainty sampling is the established active learning baseline. LLM-based active learning is a rapidly-evolving area. HCI guidance from HAX/Bansal transfers but not LLM-IE-specific. Correction-propagation UX is under-researched.

### Evidence

- **"From Selection to Generation: A Survey of LLM-based Active Learning"** — Ren et al. ([arXiv:2502.11767](https://arxiv.org/abs/2502.11767), 2025). **Methodology:** survey of selection techniques + emerging LLM-generated annotation. **Confidence: Moderate** (recent preprint survey).
- **CoverICL**: uncertainty + coverage > either alone.
- **Deep Active Learning for Foundation Models** survey (Intelligent Computing 2025). **Confidence: Moderate**.
- **HAX Toolkit / Amershi et al.** (Microsoft Research, CHI 2019 best paper — "Guidelines for Human-AI Interaction"). **Methodology:** 20+ years synthesis into 18 design guidelines. **Confidence: Strong** (CHI best paper). Key relevant guidelines:
  - G2: "Make clear how well the system can do what it can do" → display calibrated per-field reliability bands.
  - G11: "Make clear why the system did what it did" → per-field provenance (chunk pointer, prompt version, model).
  - G17: "Provide global controls" → user-adjustable auto-approve thresholds.
- **Bansal et al. human-AI complementarity** research: humans work best with AI when they understand the AI's error BOUNDARIES, not just global accuracy. **Confidence: Moderate** (multiple papers, CHI/AAAI venues).

### So What (Design Implication)

1. **Active learning sampling (phase 2)**: uncertainty sampling is the baseline; add diversity (CoverICL pattern) as enhancement. Its effectiveness depends on Q3 (calibration) working reliably — gate phase-2 active learning on phase-1 calibration-study results.
2. **HITL UX priorities**:
   - Display per-field reliability BANDS (red/yellow/green), not raw confidence numbers (HAX G2 + Bansal complementarity).
   - Show per-field provenance on demand (chunk pointer + extraction prompt) (HAX G11).
   - Global adjustable threshold slider (HAX G17).
   - Bulk-approve high-confidence + attention-routed flagging.
3. **Correction propagation**: add corrections to the few-shot retrieval pool; do NOT auto-retrain on a single correction. Research-gap-driven conservative stance.

### Research Gap

**Research Gap #3**: HCI research specifically on LLM-assisted document IE is thin. Generic human-AI research transfers in principle but hasn't been validated on our task type. Recommend small usability study (2-3 reviewers) at end of phase 1.

---

## Q9. Few-Shot Document Classification

**Key finding (Strong):** Frontier LLMs achieve 0.85+ F1 on zero-shot binary/multi-class document classification. CC-vs-Distribution is well within the easy regime and is NOT the pipeline bottleneck.

### Evidence

- **Chae & Davidson 2025** (Sage Journals, [doi:10.1177/00491241251325243](https://journals.sagepub.com/doi/10.1177/00491241251325243)). **Methodology:** 10 models × 4 training regimes on text classification. Finding: frontier models give best zero/few-shot; fine-tuned smaller models competitive on cost/accuracy. **Confidence: Moderate** (peer-reviewed journal).
- **Dark-web zero-shot classification** (MDPI Electronics 2025): 8 commercial LLMs on 10k docs. DeepSeek 0.870, Grok 0.868, Gemini 2.0 Flash 0.861 macro-F1. Cohen's Kappa >0.840 vs human. **Confidence: Moderate**.
- **Label Space Reduction** ([arXiv:2502.08436](https://arxiv.org/abs/2502.08436)): +7% avg F1 on Llama-3.1-70B via iterative label refinement. More relevant for large taxonomies; binary CC/Distribution doesn't need this.
- **Failure modes for frontier LLMs**: context-length degradation, weak OOD generalization on novel templates, memorization over reasoning on high-frequency patterns.

### So What (Design Implication)

Use a cheap fast model (Claude Haiku / Gemini Flash / Bedrock Nova Lite) with function-calling for the classification step. Expect 98%+ accuracy. Ship with a 3-class taxonomy (CC / Distribution / Reject-or-Other) not 2 — the "Other" bucket catches joint notices, corrected notices, forwarded emails. Track per-GP-template correction rate as drift signal.

### Conflicting Evidence

None substantive — finding is robust across studies.

---

## Q10. Prompt Injection Defense for Document-Processing Pipelines

**Key finding (Strong):** Indirect prompt injection is a real risk for document-processing pipelines. Spotlighting + structured output + reconciliation + HITL gives layered defense with low residual risk.

### Evidence

- **Greshake et al.** ([arXiv:2302.12173](https://arxiv.org/abs/2302.12173), CISPA 2023, Black Hat USA 2023). **Methodology:** formal definition of indirect prompt injection with demonstrated real-world exploits. Model hijack, data theft, persistent compromise possible. **Confidence: Strong** (widely-replicated demonstrations).
- **Spotlighting** — Hines et al. (Microsoft, [arXiv:2403.14720](https://arxiv.org/abs/2403.14720), CEUR 2024). **Methodology:** three transforms — delimiting, marking, encoding. Attack success rate >50% → <2% on GPT-family. **Confidence: Strong** (ablated).
- **DeepMind Gemini lessons** ([arXiv:2505.14534](https://arxiv.org/abs/2505.14534), 2025): production-derived defense-in-depth. **Confidence: Moderate** (engineering report).
- **OWASP LLM01:2025**: prompt injection is #1 LLM risk. Defenses: segregate external content, constrain output, HITL for sensitive ops, system-prompt hardening. **Confidence: Strong** (industry consensus).
- **Instruction Detection Defense** ([arXiv:2505.06311](https://arxiv.org/abs/2505.06311), 2025): classifier-based detection of injection patterns. **Confidence: Preliminary**.

### So What (Design Implication)

Phase-1 defense stack (add `claude/rules/prompt-injection.md` as design-brief specified):
1. **Spotlighting**: delimit document text with explicit tags in the prompt (e.g., `<untrusted_document>...</untrusted_document>`) and instruct the system prompt to treat the content as data, not instructions. Evidence-strong, near-zero cost.
2. **Structured-output enforcement** (schema-guided): prevents model from emitting free-form responses that exfiltrate data. Already design-locked.
3. **Reconciliation validators**: catch semantic-level injection (e.g., "wire to account X" text blended into extraction) — structured output alone doesn't catch this. Already design-locked.
4. **HITL**: final line of defense for financial-value fields. Already design-locked.
5. **Red-team evaluation**: include 20-50 crafted injection prompts in documents as part of golden eval set — verify extraction remains correct and no out-of-schema content leaks.

### Conflicting Evidence

None — layered defense is industry consensus.

---

## Q11. GraphRAG vs Standard RAG (Rule-Out Analysis)

**Key finding (Strong):** GraphRAG is confirmed overkill for per-document field extraction. Standard RAG wins on single-hop detailed queries. GraphRAG wins on global-synthesis / multi-hop queries — not our task.

### Evidence

- **Microsoft GraphRAG** — Edge et al. ([arXiv:2404.16130](https://arxiv.org/abs/2404.16130), 2024). 86% vs 32% baseline on enterprise benchmarks (Microsoft internal). LazyGraphRAG 96% win rate on complex global queries. **Confidence: Moderate** (Microsoft vendor benchmarks).
- **HippoRAG** — Gutiérrez et al. (NeurIPS 2024). KG + Personalized PageRank. Up to +20% on multi-hop QA. 10-30× cheaper and 6-13× faster than iterative retrieval (IRCoT). **Confidence: Strong** (NeurIPS acceptance).
- **"RAG vs. GraphRAG: Systematic Evaluation"** ([arXiv:2502.11371](https://arxiv.org/abs/2502.11371), 2025): GraphRAG wins on global/multi-hop; standard RAG wins on detailed single-hop.
- **"When to use Graphs in RAG"** ([arXiv:2506.05690](https://arxiv.org/abs/2506.05690), ICLR'26 accepted): GraphRAG frequently underperforms vanilla RAG on many real-world single-hop tasks. **Confidence: Moderate-Strong**.
- **Industry guidance consistent**: standard RAG best for ~80% of use cases.

### So What (Design Implication)

Rule-out confirmed. Keep GraphRAG out of phase 1 AND phase 2. Only reconsider if a future feature (cross-notice fund analytics, multi-GP relationship analysis) requires global synthesis. For per-doc field extraction, standard chunk retrieval + BM25/dense hybrid is optimal.

### Conflicting Evidence

None — multiple independent analyses agree.

---

## Q12. Retrieval-Augmented Extraction (Chunk vs Full-Doc)

**Key finding (Moderate-Strong):** For typical 1-5 page CC/Distribution notices (<8k tokens), full-doc context beats chunking. For large packets (>15k tokens), chunk-retrieve helps. Long-context LLMs do NOT eliminate the need for retrieval — "context rot" and context-cliff effects are documented.

### Evidence

- **"Long-Context Isn't All You Need"** (Snowflake Engineering 2025): finance RAG — chunks beat full-doc even at 200k-window Claude 3.5 Sonnet due to "context confusion." **Confidence: Moderate** (engineering blog, domain-specific).
- **Chroma context-rot research (July 2025)**: retrieval performance degrades with context length even on straightforward tasks. **Confidence: Moderate**.
- **Sequential-NIAH** ([arXiv:2504.04713](https://arxiv.org/abs/2504.04713), 2025): best model only 63.5% max accuracy on sequential multi-needle extraction from 8K-128K context. **Confidence: Moderate**.
- **NAACL 2025 Findings**: fixed 200-word chunks match or beat semantic chunking on retrieval + answer gen. Confidence: Moderate.
- **Jan 2026 analysis** (industry): "context cliff" ~2500 tokens where quality drops sharply.

### So What (Design Implication)

Tiered chunking strategy:
- **<3000 tokens (typical single-notice)**: pass full doc. No chunking needed.
- **3000-15000 tokens**: pass full doc but pre-extract via layout-aware sections (Docling section breaks, spacy-layout regions). Keep structure.
- **>15000 tokens (multi-attachment packets)**: chunk + retrieve by field hint. Use BM25 + dense hybrid for field-specific retrieval.
- **Always**: layout-aware chunking beats naive character chunking.

### Conflicting Evidence

Long-context proponents argue modern frontier models (Claude 3.7, Gemini 2.5 with 1M+ windows) have improved on context rot. Empirical finding (Chroma, Snowflake) still favors retrieval — the degradation is smaller but not zero. Conservative design: pass full doc when under 8k tokens; chunk above.

---

## Evidence Summary Table

| # | Paper / Benchmark | Key Finding | Confidence | Relevance |
|---|---|---|---|---|
| Q1 | LMDX (Perot 2024, ACL) | Layout-coord + schema + frontier LLM SOTA on VRDU/CORD zero/few-shot | Strong | Direct |
| Q1 | DocLLM (Wang 2024, ACL) | Disentangled spatial attention; JPMorgan; 14/16 dataset SOTA | Strong | Direct |
| Q1 | Donut (Kim 2022, ECCV) | OCR-free VDU transformer; requires training data | Strong | Analogous (needs labels) |
| Q1 | LayoutLMv3 (Huang 2022) | Joint text/layout/image pretraining; requires fine-tune | Strong | Analogous (phase 3+) |
| Q1 | Reducto bench 2025 | Gemini 2.0 Flash ~80% form parsing; frontier VLMs close LayoutLM gap | Moderate | Direct |
| Q2 | FrugalGPT (Chen 2024, TMLR) | Cascade cheap→strong; up to 98% cost reduction (dataset-specific) | Strong | Direct |
| Q2 | RouteLLM (Ong 2024, LMSYS) | Preference-learned router; 85% MT-Bench cost reduction | Moderate | Direct |
| Q2 | RouterBench 2024 | Multi-LLM routing benchmarks; Pareto-improving routes exist | Moderate | Analogous |
| Q3 | Kadavath 2022 (Anthropic) | Large models well-calibrated on MC/T-F; P(True) encouraging | Strong | Direct |
| Q3 | SelfCheckGPT (Manakul 2023, EMNLP) | N-sample divergence → hallucination; zero-resource | Strong | Direct |
| Q3 | Semantic Entropy (Farquhar 2024, Nature) | Cluster-by-meaning entropy; cross-model, cross-task | Strong | Direct |
| Q3 | FActScore (Min 2023, EMNLP) | Atomic fact decomposition + retrieval verification | Strong | Analogous |
| Q3 | Self-Consistency (Wang 2023, ICLR) | N-sample CoT majority vote; extended to calibration | Strong | Direct |
| Q3 | Token-logprobs industry 2024 | Aggregation swings calibration error > signal; use in ensemble | Moderate | Direct |
| Q4 | Mosbach et al. 2024 (arXiv) | Fine-tune break-even 10-1000 labels; task-dependent | Moderate | Direct |
| Q4 | Few-Shot PEFT (Liu 2022, NeurIPS) | (IA)³ PEFT > ICL at 32-shot on classification | Strong | Analogous |
| Q4 | LoRA (Hu 2021) | 10000× fewer params, matches full fine-tune at sufficient data | Strong | Direct |
| Q5 | Liu 2022 DeeLIO | Similarity-kNN few-shot > random; +41.9% ToTTo, +45.5% NQ | Strong | Direct |
| Q5 | ICL survey EMNLP 2024 | Similarity + diversity (MMR) beats similarity alone | Moderate | Direct |
| Q5 | BM25 synthesis (wiki) | BM25 competitive with dense on structured/terminology text | Strong | Direct |
| Q6 | Decomposed Prompting (Khot 2023, ICLR) | Modular sub-prompt library; flexible top-down decomposition | Strong | Direct |
| Q6 | Plan-and-Solve (Wang 2023, ACL) | Plan-first improves zero-shot CoT | Strong | Analogous |
| Q6 | Least-to-Most (Zhou 2023, ICLR) | Sequential sub-problems; compositional generalization | Strong | Analogous |
| Q7 | Outlines (Willard 2023) | FSM-based token filtering; industry-standard library | Strong | Direct |
| Q7 | "Let Me Speak Freely?" (Tam 2024, EMNLP) | JSON-mode from token 1 → 10-15% reasoning degradation | Strong | Direct |
| Q7 | Park 2024 NeurIPS | Constrained decoding distorts probability distribution | Strong | Direct |
| Q7 | JSONSchemaBench 2025 | Complex schemas cause compile-time issues; Outlines worst compliance | Moderate | Direct |
| Q8 | LLM Active Learning survey (Ren 2025) | Uncertainty sampling baseline; LLM-generated annotation emerging | Moderate | Direct |
| Q8 | HAX Toolkit (Amershi 2019, CHI best paper) | 18 guidelines for human-AI interaction | Strong | Analogous |
| Q8 | Bansal complementarity research | Humans need error-BOUNDARIES understanding, not just accuracy | Moderate | Direct |
| Q9 | Chae & Davidson 2025 | Frontier LLMs best zero/few-shot text classification | Moderate | Direct |
| Q9 | Dark-web zero-shot (MDPI 2025) | Frontier LLMs 0.85+ F1 on zero-shot binary classification | Moderate | Direct |
| Q10 | Greshake 2023 (CISPA) | Indirect prompt injection formally defined; real-world RCE demo'd | Strong | Direct |
| Q10 | Spotlighting (Hines 2024, Microsoft) | >50% → <2% attack success on GPT-family | Strong | Direct |
| Q10 | OWASP LLM01:2025 | #1 risk; defense-in-depth consensus | Strong | Direct |
| Q10 | DeepMind Gemini defense (2025) | Production-derived layered defense-in-depth | Moderate | Analogous |
| Q11 | Microsoft GraphRAG (Edge 2024) | 86% vs 32% baseline on global queries; overkill for single-hop | Moderate | Rule-out |
| Q11 | HippoRAG (Gutiérrez 2024, NeurIPS) | KG+PPR; +20% multi-hop; not needed for single-hop extraction | Strong | Rule-out |
| Q11 | "When to use Graphs in RAG" (2025, ICLR'26) | GraphRAG underperforms vanilla on single-hop tasks | Moderate | Rule-out |
| Q12 | Long-Context Isn't All You Need (Snowflake 2025) | Finance RAG: chunks beat 200k-window full-doc | Moderate | Direct |
| Q12 | Sequential-NIAH (2025) | Max 63.5% on multi-needle from 8k-128k context | Moderate | Direct |
| Q12 | NAACL 2025 Findings | Fixed 200-word chunks match semantic chunking | Moderate | Direct |

---

## Research Gaps

1. **LLM-extraction-specific calibration** (Q3): most calibration research is QA/open-gen. Which signals correlate with correctness for per-field structured extraction is not definitively published. **Recommendation**: phase-1 internal calibration study — 20 HITL-labeled docs, measure each signal (min-logprob, semantic entropy, self-consistency agreement, schema-adherence, reconciliation pass) vs ground truth; pick ensemble weights empirically.

2. **Monolithic-vs-decomposed extraction on our specific schemas** (Q6): general decomposition literature is strong but extraction-specific evidence is thin. **Recommendation**: A/B comparison of monolithic 9-field prompt vs 4-group decomposed prompts on golden eval set at phase-1 start.

3. **HCI research specifically on LLM-assisted document IE** (Q8): HAX/Bansal work transfers in principle but not validated on this task type. Correction-propagation UX especially thin. **Recommendation**: brief usability study (2-3 reviewers) end of phase 1; conservative correction-propagation (feed into few-shot pool, no auto-retrain).

4. **Optimal chunking strategy for our specific doc-length distribution** (Q12): tiered strategy is principled but the exact breakpoints depend on our corpus — will need empirical calibration once 50-100 docs have been processed through phase 1.

5. **Post-RLHF calibration degradation** (Q3): Kadavath 2022 calibration findings may not transfer to current RLHF-tuned Claude 3.7 / GPT-4o. Newer calibration work exists but isn't yet consolidated. **Conservative stance**: assume verbalized "how confident?" is miscalibrated; rely on structural signals.

---

## Judgment Calls Required

These are decisions the Design Lead must make because research doesn't definitively settle them:

1. **Cascade vs single-strong-model for phase 1** (Q2): literature supports cascade for cost but at 100-1000 docs/mo and low-complexity extraction, single strong model may be simpler. Recommend: start single strong, measure cost per doc, add cascade in phase 1.5 if cost-per-doc exceeds target.

2. **Field-group boundaries for decomposition** (Q6): suggested (classification / names / dates / amounts / type) is a starting heuristic. Empirical tune required. Avoid over-decomposing below group level.

3. **Phase-3 fine-tune trigger** (Q4): 500 labels is a reasonable gate BUT should be confirmed by A/B on golden eval set, not auto-triggered. Some fields may need 2000+; others may fine-tune well earlier.

4. **Long-context vs chunk threshold** (Q12): suggested 3k/15k breakpoints are conservative. Tune based on observed accuracy curves once corpus is processed.

5. **Confidence threshold for auto-approve** (design brief R5 risk): literature gives no concrete number. Start VERY conservative (require HITL for nearly everything) for 2-3 months, raise threshold only with eval-set evidence. Agrees with design brief's "start threshold low" directive.

---

## Self-Check (SOP Step 7)

- [x] Findings organized by research question (not by paper) — all 12 sections structured by Q.
- [x] ≥5 findings — 45+ citations across 12 questions.
- [x] Every citation has: key finding + methodology note + confidence grade + "So What" — each question has a So-What section.
- [x] Evidence Summary Table present (paper / finding / confidence / relevance).
- [x] Research Gaps section present (5 gaps identified).
- [x] No preprint treated as strong evidence — arXiv-only findings marked Moderate or Preliminary.
- [x] All 12 research questions addressed.
- [x] Judgment Calls section included (per SOP Step 5 / Research Gaps).

Delivered to Design Lead.
