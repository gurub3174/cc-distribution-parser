---
project: cc-distribution-parser
type: competitive-landscape-report
created: 2026-04-21
owner: market-scout
status: delivered-to-design-lead
tags: [market-research, document-extraction, financial-ie, hitl, vpc-llm]
---

# Competitive Landscape Report — Capital Call & Distribution Parser

Delivered to Design Lead. Companion raw notes: `wiki/raw/2026-04-21-market-scout-cc-distribution-parser.md`.

## Executive Summary

Top-line recommendations (each backed by detailed reasoning below):

- **Document parsing: adopt Docling as OSS default.** 58k GitHub stars, 100+ releases in 8 months, IBM-backed Granite-Docling-258M VLM (Apache 2.0) hits 97.9% complex-table accuracy. Wrap with `spacy-layout` if downstream spaCy usage is confirmed. Mainstream adoption tier.
- **Cloud IDP alternative: AWS Bedrock Data Automation is a serious hybrid option**, not a replacement — native blueprint-based extraction + A2I human review + Dec-2025 instruction optimization. For the 10-50 recurring GP templates specifically, BDA may cover 60-70% of layout+OCR for less code. Recommend **dual-path experiment** in phase 1 POC.
- **Orchestration: start with plain Python + Postgres queue + FastAPI.** LangGraph is overbuilt for this deterministic linear pipeline and its 2026 API instability is well-documented. Temporal is production-grade but overkill for 100-1000/mo solo-dev. Revisit when a non-linear flow or multi-worker parallelism emerges.
- **Schema-guided generation: Instructor + Pydantic + native Bedrock Converse structured output (Feb 2026 GA).** BAML adds complexity without payoff in Python-only codebase. Outlines solves a different problem (token-masking for high-throughput).
- **Few-shot retrieval: pgvector on Postgres.** Bedrock Knowledge Bases and Azure AI Search are 10x overkill at 10K-example scale. One database holds audit + embeddings + master data.
- **HITL UI: custom FastAPI + HTMX/React for phase 1.** Label Studio/Argilla/Prodigy are labeling-first; this project is review-first. The 2-schema, fixed-workflow spec fits a purpose-built UI in ~500 LOC that will outfit any retrofitted labeling tool.
- **LLM tracing: Arize Phoenix, not Langfuse (initially).** Self-hosted Langfuse requires 5 services (Postgres, ClickHouse, Redis, S3, app); Phoenix is a softer VPC bootstrap for a solo dev. Migrate if infra team/scale demands.
- **Entity resolution: rapidfuzz phase 1, Splink + embedding similarity phase 2.** LP/GP name variation is deterministic enough that Jaro-Winkler + master-data lookup handles most of it; save probabilistic record linkage for when master-data scales.
- **The DIY baseline is the recommendation.** See §4 Integration Recommendations.

---

## Q1. Document Parsing Stack for Mixed PDF+DOCX+Scanned

### Market map (categorized)

**OSS / self-hosted parsers:**
- **Docling** (docling-project, IBM-backed) — PDF + DOCX + PPTX + XLSX + HTML + images. Granite-Docling-258M VLM.
- **spacy-layout** (Explosion) — thin wrapper around Docling with spaCy Doc integration + layout spans.
- **Unstructured.io** (YC, OSS + managed) — PDF + DOCX + HTML; broad format coverage but weaker on complex tables.
- **Nougat** (Meta, 2023) — academic-paper OCR only; no active maintenance since 2024. Not a candidate.

**OSS / self-hosted with model downloads:**
- **Granite-Docling-258M** (IBM, Apache 2.0, Jan 2026) — 258M-param VLM; fits in 114ms/page on L4 GPU.

**Managed APIs:**
- **LlamaParse** (LlamaIndex) — $0.003/page; fast (~6s/doc); weaker on complex layouts; pay-per-doc.
- **Reducto** (Series A $24.5M Benchmark-led, 2025) — pixel-perfect cell-level traceability; strong on financial tables/charts; 250M+ pages processed; not self-hostable without enterprise deal.

**Cloud-native IDP (all VPC-compatible via their own cloud):**
- **AWS Textract** — 94.2% avg invoice accuracy; AnalyzeExpense for invoices; serverless integration.
- **AWS Bedrock Data Automation** — blueprint-based, instruction optimization (Dec 2025), 3000-page limit, native A2I human-review, F1/EM auto-metrics. **The sleeper candidate for this project.**
- **Azure Document Intelligence** — 30-min custom training; mortgage/check/pay-stub pre-built models; 93% field accuracy without training on common doc types.
- **Google Document AI** — 95.8% avg accuracy (highest in independent benchmark); few-shot learning with Gemini; weaker on DOCX input than PDF.

### Adoption tier + verdict

| Tool | Stars / Evidence | Tier | Verdict |
|---|---|---|---|
| Docling | 58k stars, v2.90 (Apr 2026), 100+ releases, IBM-backed | Mainstream | **Recommended phase 1 OSS default** |
| spacy-layout | Active, wrapper on Docling; fits if spaCy is already in pipeline | Early-adopter | **Viable — adopt if spaCy canonicalization confirmed** |
| AWS Bedrock Data Automation | GA 2024 + Dec 2025 optimization; AWS-referenced customers | Mainstream (within AWS) | **Evaluate head-to-head with Docling in POC** |
| Azure Document Intelligence | Mature since 2019 (ex-Form Recognizer); strong Azure ecosystem | Mainstream | **Viable alternative if Azure is cloud-of-record** |
| AWS Textract | Mature, 2018-original; weaker for LLM-downstream vs BDA | Mainstream | **Viable for pure OCR; BDA supersedes for IDP** |
| Google Document AI | Mature; highest benchmark accuracy; GCP lock-in | Mainstream | **Viable alternative if Vertex is cloud-of-record** |
| Reducto | Series A 2025, 250M+ pages, strong on finance | Early-adopter | **Viable managed alternative; not self-hostable** |
| Unstructured.io | Broad format coverage; weaker on tables | Mainstream | **Viable but Docling outperforms on this data** |
| LlamaParse | Pay-per-page; weak on complex layouts | Mainstream | **Avoid for production — cost + accuracy tradeoff |
| Nougat | No maintenance since 2024 | Experimental | **Avoid — abandoned** |

**Recommended (phase 1):** Docling (+ spacy-layout if spaCy pipeline confirmed) as the default parse layer. **Run a controlled comparison to Bedrock Data Automation on 10-20 representative CC/Distro docs in POC.** If BDA hits ≥95% layout+field-localization accuracy, consider a hybrid: BDA for parsing + blueprint extraction on high-frequency templates, Docling + LLM for the long tail.

**Avoid:** LlamaParse (cost + accuracy), Nougat (abandoned), Unstructured.io (Docling dominates).

---

## Q2. Orchestration for Deterministic HITL Workflows

### Market map (categorized)

**LLM-native orchestration:**
- **LangGraph** (LangChain Inc.) — graph-based, checkpointers, `interrupt()` for HITL.
- **CrewAI** — role-based, agent-centric; not a good fit for deterministic doc IE.
- **PydanticAI** — Pydantic-centric agent framework; lighter weight than LangGraph.
- **BAML + orchestration** — BAML's structured-output DSL with a separate scheduler.

**General-purpose durable execution:**
- **Temporal** — strongest durability in the industry; OpenAI Agents SDK integration (Feb 2026 GA); $300M Series raised Feb 2026 at $5B.
- **Prefect** — Python-native data orchestration; HITL via pause/resume; lighter than Temporal.
- **Dagster** — asset-oriented; more dataops-focused; less natural for HITL.

**Queue-based / no framework:**
- **Celery / RQ / arq** — Python task queues; each HITL wait = a queued job.
- **Plain Postgres + FastAPI webhook** — jobs table with status column; polling or webhook.

### Adoption tier + verdict

| Tool | Evidence | Tier | Verdict |
|---|---|---|---|
| LangGraph | Dominant in 2025 LLM tutorials; 2026 complaints re: LangChain API churn, node-boundary checkpointing, scaling ceilings | Mainstream | **Viable but risky for solo dev — pin version if chosen** |
| Temporal | 1.86T executions in 2025, OpenAI-native, $5B valuation | Mainstream | **Overkill at 100-1000/mo; great skill to learn; revisit phase 3** |
| Prefect | Python-native, mature, active | Mainstream | **Viable — lighter than Temporal, real durability** |
| Plain Python + Postgres queue | No framework dependency | — | **Recommended phase 1** |
| BAML | DSL + codegen; cross-language | Early-adopter | **Avoid unless multi-language needed** |
| CrewAI / Dagster | Wrong shape for deterministic doc IE | — | **Avoid for this project** |

**Recommended (phase 1):** Plain Python + Postgres jobs table + FastAPI HITL endpoints. HITL wait is just a row with `status='awaiting_review'`; approve flips the row; a background worker (arq or even cron-driven Python) picks up approved rows and continues the pipeline. Idempotent writes + `SELECT FOR UPDATE SKIP LOCKED` handles worker crashes. Total LOC: ~200.

**Alternative if the user wants framework experience for job search:** LangGraph with `interrupt()` — but **pin LangGraph to a specific version** (e.g., `langgraph==0.2.x` range) and isolate the graph to a single module so the rest of the codebase is framework-agnostic. Budget time for quarterly LangGraph upgrades.

**Avoid:** BAML (DSL tax), CrewAI (wrong shape), Dagster (wrong shape).

---

## Q3. Retrieval for Dynamic Few-Shot (kNN over past extractions)

### Market map

**Managed cloud RAG:**
- **AWS Bedrock Knowledge Bases** — managed ingestion, hybrid search, rerankers, multiple backends (OpenSearch Serverless, Aurora pgvector, Pinecone).
- **Azure AI Search** — managed, integrated with SharePoint/OneDrive/Blob.
- **GCP Vertex AI Search** — equivalent in GCP.

**Self-hosted in-DB vector:**
- **pgvector on Postgres** — v0.8 (April 2025) shipped iterative index scans, 9x faster filtered queries; battle-tested.
- **pgvectorscale** (Timescale) — pgvector + DiskANN; for much larger scale.

**Framework libraries:**
- **Haystack** (deepset) — retrieval pipeline framework; broader than just vector store.
- **FAISS + SQLite** — minimum viable: FAISS for ANN + SQLite for metadata.

### Adoption tier + verdict

| Tool | Evidence | Tier | Verdict |
|---|---|---|---|
| pgvector | Shipped since 2021, millions of deployments | Mainstream | **Recommended phase 1** |
| Bedrock Knowledge Bases | Mature within AWS | Mainstream | **Overkill at this scale; vendor lock-in** |
| Azure AI Search | Mature | Mainstream | **Overkill; vendor lock-in** |
| Haystack | Mature, 15k+ stars | Mainstream | **Framework tax; DIY is simpler at this scale** |
| FAISS + SQLite | Very mature | Mainstream | **Viable but loses SQL filtering — pgvector wins** |

**Recommended:** pgvector. The same Postgres already holding audit records holds embeddings. SELECT with `<=>` cosine distance returns in <10ms at 10K rows. Filters by template, GP, date range all come for free as SQL. One database, one backup story.

**Avoid/postpone:** Bedrock KB, Azure AI Search — revisit only if corpus grows past 100K labeled examples OR if reviewer wants hybrid BM25 + vector search at larger scale.

---

## Q4. HITL Review Platforms

### Market map

**Labeling-first open source:**
- **Label Studio** (Heartex, MIT) — multi-modal, active, most mature OSS labeling.
- **Argilla** (HF-acquired 2024) — LLM-friendly, CustomField for custom UI, active.
- **CVAT** — computer-vision-centric; not a fit.

**Labeling-first paid:**
- **Prodigy** (Explosion, $390/seat) — keyboard-first, active learning built-in, fully scriptable.

**DIY:**
- **FastAPI + HTMX / React + custom schema UI**
- **Streamlit** — fast to build, weak UX at scale.

### Adoption tier + verdict

| Tool | Evidence | Tier | Verdict |
|---|---|---|---|
| Label Studio | Mature, 18k+ stars, multi-modal | Mainstream | **Viable alternative phase 2** |
| Argilla | HF-owned, stable post-acquisition | Mainstream | **Viable alternative phase 2** |
| Prodigy | Paid, mature | Mainstream | **Viable if budget permits; keyboard UX wins** |
| Custom FastAPI + HTMX | Framework-level, mature | — | **Recommended phase 1** |
| Streamlit | Framework-level, mature | Mainstream | **Rapid-prototype only — UX ceiling too low for production** |

**Recommended (phase 1):** Custom FastAPI + HTMX (or minimal React). Justification:
- Only 2 schemas to support (CC, Distribution); 10 fields total.
- Fixed workflow: review → per-field approve/correct → bulk-approve-high-confidence → commit.
- Tri-state field absence model and arithmetic-invariant flags require first-class UI support that generic labeling tools don't natively provide.
- Per-field confidence color coding + provenance display (chunk ID, model, prompt version) is a 1-day add in HTMX; grafting into Label Studio is multi-week.

**Viable alternative:** Label Studio — if a second use case emerges, or multi-reviewer becomes a requirement. The investment is reusable beyond this project.

**Avoid:** Streamlit for production HITL UX (OK for eval-harness dashboards).

---

## Q5. Schema-Guided Generation Libraries

### Market map

**Wrapper libraries:**
- **Instructor** — Pydantic + 15+ providers (Bedrock, Azure, OpenAI, Anthropic, Gemini, etc.) via LiteLLM.
- **Outlines** — token-masking (FSM constrained decoding); forces schema compliance during generation.
- **BAML** (BoundaryML) — DSL + codegen; Schema-Aligned Parsing for robust recovery; multi-language clients.
- **LangChain output parsers** — ecosystem tax; not recommended standalone.

**Native provider features:**
- **AWS Bedrock Converse structured output** — `outputConfig.textFormat` parameter, GA Feb 2026; supports Claude 4.5+, Gemma, Mistral, etc.
- **Azure OpenAI structured outputs** — mature since late 2024.
- **Vertex Gemini function calling** — mature.

### Adoption tier + verdict

| Tool | Evidence | Tier | Verdict |
|---|---|---|---|
| Instructor | 8k+ stars, 15+ provider integrations | Mainstream | **Recommended** |
| Native Bedrock Converse | GA Feb 2026 | Mainstream | **Use underneath Instructor** |
| Native Azure OpenAI | Mature | Mainstream | **Use if Azure is cloud-of-record** |
| Outlines | Active, ~10k stars | Mainstream | **Overkill at 100-1000/mo; revisit if retry cost becomes dominant** |
| BAML | 4k+ stars, rapidly growing | Early-adopter | **Premature complexity for Python-only** |
| LangChain output parsers | — | Mainstream | **Avoid — ecosystem tax** |

**Recommended:** Instructor + Pydantic, using native Bedrock Converse / Azure structured output underneath. This gives retry-on-validation-failure at the library level while leveraging the provider's best-effort structured decoding. Pydantic integration is first-class; provider swap is a one-line change (LiteLLM). Matches the Design Brief's provider-abstraction requirement (R4).

**Avoid for this project:** BAML (DSL tax in Python-only codebase), LangChain output parsers.

---

## Q6. LLM Tracing + Evaluation (Self-Hostable / VPC)

### Market map

**Open-source self-hosted:**
- **Langfuse** — OSS, ClickHouse-acquired Jan 2026 ($400M deal). 1000+ self-hosted deployments. Needs Postgres + ClickHouse + Redis + S3 + app.
- **Arize Phoenix** — OSS, self-hostable, simpler deployment, strong agent-trace support.
- **OpenLLMetry** (Traceloop) — OTel-based; plug into any OTel backend.

**Proprietary with self-host tier:**
- **Braintrust** — self-hosting via enterprise agreement only.
- **LangSmith** — self-host tier exists; LangChain-coupled pricing.
- **Helicone** — proxy-based, simpler install.

### Adoption tier + verdict

| Tool | Evidence | Tier | Verdict |
|---|---|---|---|
| Arize Phoenix | OSS, ~4k stars, mature, simpler deploy | Mainstream | **Recommended phase 1** |
| Langfuse | OSS, 8k+ stars, ClickHouse-backed | Mainstream | **Viable phase 2 when infra team exists** |
| OpenLLMetry | OTel-native | Early-adopter | **Viable if already using OTel stack** |
| Braintrust | Proprietary | — | **Avoid — not truly self-hostable** |
| LangSmith | LangChain coupling | — | **Avoid unless already committed to LangChain** |
| Helicone | Proxy-based | Early-adopter | **Viable alternative — simpler than Langfuse** |

**Recommended (phase 1):** Arize Phoenix. Solo-dev VPC bootstrap wins: one container + one volume, local SQLite or Postgres backend, OTel-native. Migrate to Langfuse when/if infra team emerges and evaluation-framework polish becomes dominant.

**Avoid:** Braintrust (proprietary lock), LangSmith (LangChain tax).

---

## Q7. Fin-Services Doc IE Precedents

### Market map

**Direct competitors (CC/Distribution specifically):**
- **Canoe Intelligence** — the direct competitor; real-time CC+Distro extraction; Gen II partnership (2025); Schwab/Envestnet integrations; zero architecture transparency.
- **Hercules AI / Artemis** — explicit CC+Distro product marketed at fund admins; little technical detail public.
- **Allvue Systems** — broader private-markets platform; doc automation as one module.
- **Formulary** (Khosla-backed, $4.6M seed Jan 2026) — early-stage; AI-powered fund-manager software.

**Adjacent fin-services IE:**
- **Hebbia** — broader finance/legal doc analysis. **Published signals:** (a) OpenAI case study showing o1-based 92% accuracy vs 68% out-of-box RAG, (b) Matrix product runs o3-mini/o1/GPT-4o in *parallel* multi-agent, (c) their own "Financial AI Benchmark" drives model selection. 1B+ pages processed.
- **Ocrolus** — loan docs + bank statements; 99%+ accuracy claim; $80M Series C; built-in human review.
- **Kensho** (S&P Global) — macro scenario modeling, not doc extraction.
- **Reducto** — not fin-services specific but strong on financial tables.

**Less transparent:**
- **Eigen Technologies, Klarity, Intapp, Addepar, Rogo, Dloop** — mostly enterprise sales pages; no engineering blogs / conference talks surfaced.

### Key patterns from precedents (evidence → signal for our design)

| Pattern | Source | Signal for our project |
|---|---|---|
| Multi-model parallel cascade beats single-model RAG | Hebbia (OpenAI case study, 2025) | Validates Design Brief's cheap→expensive cascade |
| Proprietary benchmark drives model selection | Hebbia Financial AI Benchmark | Build domain golden eval early; don't rely on generic benchmarks |
| HITL integrated, not bolted on | Ocrolus, Canoe | Matches Design Brief; ship HITL in phase 1 not phase 2 |
| Per-metric cell-level traceability | Reducto | Matches Design Brief's provenance requirement (chunk ID, model, prompt version) |
| Context-aware doc AI unifies multiple doc types | Allvue | Supports polymorphic-schema decision in Design Brief |

**So-what:** Zero architecture transparency from direct competitors. Must build from first principles. Signals from adjacent precedents (Hebbia, Ocrolus, Reducto) validate the Design Brief's core choices: multi-model cascade, HITL, provenance, per-field confidence. **Ask the user whether their employer already uses Canoe** — if yes, this project is a Canoe-complement (e.g., pre-processing for templates Canoe struggles with) rather than a replacement, which changes phase-1 scope.

---

## Q8. Entity Resolution / Fuzzy Name Matching

### Market map

**Single-field string similarity:**
- **rapidfuzz** — Python+C++, MIT, 2.7k stars, mature. Levenshtein, Jaro-Winkler, ratio. Zero-config.
- **thefuzz** / **fuzzywuzzy** — legacy, superseded by rapidfuzz.
- **jellyfish** — older; rapidfuzz faster.

**Multi-field probabilistic record linkage:**
- **Splink** (UK Ministry of Justice) — DuckDB/Spark/Athena backends; unsupervised Fellegi-Sunter; 7M records in 2 min; 100M+ on Spark.
- **dedupe** (dedupeio) — requires manual labeling; memory-bound past 2M records; slower dev cycle.
- **recordlinkage** — Python, academic-style; lower adoption.
- **Zingg** — JVM-based; broader enterprise features; not Python-native.

**Embedding-based:**
- **sentence-transformers + cosine similarity** — handles semantic name variants that fuzz doesn't (e.g., "Pacific Ventures LP" ≈ "PVP Fund I").

### Adoption tier + verdict

| Tool | Evidence | Tier | Verdict |
|---|---|---|---|
| rapidfuzz | 2.7k stars, mature, MIT | Mainstream | **Recommended phase 1** |
| Splink | 2k+ stars, UK gov production usage | Mainstream | **Viable phase 2 if master-data scales** |
| dedupe | 4k+ stars but scaling limits | Mainstream | **Avoid for new projects — Splink superseded** |
| sentence-transformers + cosine | Embedding model ecosystem, mature | Mainstream | **Recommended phase 2 augment for semantic variants** |
| thefuzz, jellyfish | Legacy | — | **Avoid — rapidfuzz supersedes** |
| Zingg | JVM, not Python-native | Early-adopter | **Avoid — stack mismatch** |

**Recommended (phase 1):** rapidfuzz for name canonicalization + fuzzy match against master-data CSV. `process.extractOne(name, master_list, scorer=fuzz.token_set_ratio)` with threshold (typically 85-90) handles the majority of LP/GP variations. Route low-score matches to HITL.

**Phase 2 augments:** Add sentence-transformer embeddings for semantic variants (e.g., acronyms, re-orderings, legal-entity-type variations rapidfuzz misses). Add Splink only if master-data grows past ~100K entities.

**Avoid:** dedupe (scaling), thefuzz (superseded), Zingg (JVM).

---

## Q9. "No Framework / DIY" Baseline — What Do You Give Up?

### The DIY stack
```
Ingest       →  docling (+ spacy-layout)
Extract      →  Pydantic + Instructor + Bedrock Converse
Canonicalize →  spaCy matchers + rapidfuzz
Retrieve     →  pgvector on Postgres
HITL UI      →  FastAPI + HTMX (or minimal React)
Trace        →  Arize Phoenix
Queue        →  Plain Python worker (arq) + Postgres jobs table
```
Total top-level dependencies: ~7. Every one except Docling is 5+ years mature.

### What you give up vs full-framework stack (and at what cost)

| You give up | What mitigates it | Residual cost |
|---|---|---|
| LangGraph's checkpoint-on-node boundary | Postgres `SELECT FOR UPDATE SKIP LOCKED` + idempotent writes | Minimal — state is explicit in DB |
| Temporal's durability guarantees | Idempotent writes + retry with backoff + dead-letter | ~5% of Temporal's crash-recovery cases uncovered; acceptable at 100-1000/mo |
| Bedrock Knowledge Bases managed RAG | pgvector + one embedding call per upsert | Zero — scale doesn't justify managed |
| Label Studio's pre-built UI | ~500 LOC FastAPI + HTMX purpose-built UI | Requires some UX polish investment |
| Langfuse's polished trace UI | Arize Phoenix (80% feature parity, simpler deploy) | Minimal |
| BAML's schema-aligned parsing robustness | Instructor retry-on-validation-error + Bedrock native structured output | Negligible retry overhead at this volume |

### What you gain with DIY

- **Solo-dev cognitive load**: the whole stack fits in one architecture diagram; no framework internals to debug.
- **Interview narrative**: "I chose boring tech and understood every layer" is a stronger differentiator in 2026 than "I used LangGraph" (which everyone uses).
- **Upgrade freedom**: no framework-lock — can swap any piece (e.g., Bedrock → Azure) without framework-shaped changes.
- **No upstream churn pain**: LangGraph's documented API instability is a real tax; DIY is stable by construction.
- **Observability**: OTel → Phoenix → Postgres logs is the classic stack every production engineer can reason about.

**Recommendation: the DIY baseline IS the recommendation.** Upgrade individual components only when concrete evidence demands (e.g., Temporal if crash recovery becomes a real incident type; LangGraph if non-linear agent loops emerge).

---

## Tool Recommendation Matrix (master table)

| Tool | Category | Adoption Tier | Evidence | Verdict (phase 1) |
|---|---|---|---|---|
| **Docling** | Parse | Mainstream | 58k⭐, v2.90 (Apr 2026), IBM-backed, 97.9% table acc | **Recommended** |
| **spacy-layout** | Parse wrapper | Early-adopter | Explosion-maintained, Docling wrapper | **Recommended if spaCy in pipeline** |
| **AWS Bedrock Data Automation** | Cloud IDP | Mainstream | GA + Dec 2025 optimization, A2I-native | **Evaluate in POC** |
| **Azure Document Intelligence** | Cloud IDP | Mainstream | Mature since 2019, 30-min custom train | **Viable if Azure-native** |
| **Google Document AI** | Cloud IDP | Mainstream | 95.8% benchmark, few-shot with Gemini | **Viable if Vertex-native** |
| **AWS Textract** | Cloud OCR | Mainstream | Mature; BDA supersedes for IDP | **Avoid — BDA better** |
| **Reducto** | Managed parse | Early-adopter | $24.5M Series A, 250M+ pages | **Viable managed alt; not self-hostable** |
| **Unstructured.io** | Parse | Mainstream | Broad format coverage; weaker tables | **Avoid — Docling dominates** |
| **LlamaParse** | Managed parse | Mainstream | Pay-per-page, weak complex layouts | **Avoid** |
| **Nougat** | Parse | Experimental | No maintenance since 2024 | **Avoid** |
| **Plain Python + Postgres queue** | Orchestration | — | Mature pattern | **Recommended** |
| **LangGraph** | Orchestration | Mainstream | 2026 API instability documented | **Viable with version pinning** |
| **Temporal** | Orchestration | Mainstream | $5B val, OpenAI-native, 1.86T execs | **Overkill phase 1; revisit phase 3** |
| **Prefect** | Orchestration | Mainstream | Python-native data orchestration | **Viable alt to Temporal** |
| **BAML** | Structured gen | Early-adopter | DSL + codegen, rising | **Avoid for Python-only** |
| **Dagster / CrewAI** | Orchestration | Mainstream | Wrong shape for this project | **Avoid** |
| **pgvector** | Retrieval | Mainstream | v0.8 iterative scans, millions of deploys | **Recommended** |
| **Bedrock Knowledge Bases** | Retrieval | Mainstream | Managed within AWS | **Overkill at 10K scale** |
| **Azure AI Search** | Retrieval | Mainstream | Managed within Azure | **Overkill at 10K scale** |
| **Haystack** | Retrieval | Mainstream | 15k+⭐, framework | **Framework tax — DIY simpler** |
| **FAISS + SQLite** | Retrieval | Mainstream | Very mature | **pgvector wins on SQL filters** |
| **FastAPI + HTMX** | HITL UI | — | Mature, fast to build | **Recommended** |
| **Label Studio** | HITL UI | Mainstream | 18k+⭐, multi-modal | **Phase 2 alt** |
| **Argilla** | HITL UI | Mainstream | HF-owned, stable | **Phase 2 alt** |
| **Prodigy** | HITL UI | Mainstream | Paid; keyboard-first; active learning | **Viable if budget** |
| **Streamlit** | HITL UI | Mainstream | Fast prototype; weak UX ceiling | **Avoid for production** |
| **Instructor** | Structured gen | Mainstream | 8k+⭐, 15+ providers | **Recommended** |
| **Native Bedrock Converse** | Structured gen | Mainstream | GA Feb 2026 | **Use underneath Instructor** |
| **Native Azure OpenAI** | Structured gen | Mainstream | Mature since 2024 | **Use if Azure** |
| **Outlines** | Structured gen | Mainstream | Token-masking FSM | **Revisit if retry cost dominant** |
| **LangChain output parsers** | Structured gen | Mainstream | Ecosystem tax | **Avoid** |
| **Arize Phoenix** | Tracing | Mainstream | OSS, simpler deploy | **Recommended** |
| **Langfuse** | Tracing | Mainstream | OSS, ClickHouse-backed | **Viable phase 2** |
| **OpenLLMetry** | Tracing | Early-adopter | OTel-native | **Viable alt** |
| **Helicone** | Tracing | Early-adopter | Proxy-based, simpler | **Viable alt** |
| **Braintrust** | Tracing | Mainstream | Proprietary self-host tier | **Avoid — not truly self-hostable** |
| **LangSmith** | Tracing | Mainstream | LangChain coupling | **Avoid** |
| **rapidfuzz** | Entity resolution | Mainstream | MIT, mature, C++-fast | **Recommended** |
| **Splink** | Entity resolution | Mainstream | UK gov, DuckDB/Spark | **Phase 2 if master-data scales** |
| **sentence-transformers** | Entity resolution (sem) | Mainstream | Embedding-similarity | **Phase 2 augment** |
| **dedupe** | Entity resolution | Mainstream | Memory-bound past 2M | **Avoid — Splink supersedes** |
| **thefuzz / jellyfish** | Entity resolution | Legacy | Superseded | **Avoid** |
| **Zingg** | Entity resolution | Early-adopter | JVM-based | **Avoid — stack mismatch** |

---

## Integration Recommendations — Opinionated Phase-1 Stack

```
┌──────────────────────────────────────────────────────────────┐
│ INGEST                                                       │
│   PDF | DOCX | scanned-PDF                                   │
│   → docling (2.x) + spacy-layout if spaCy pipeline confirmed │
│   → (POC parallel: Bedrock Data Automation on 10-20 docs)    │
└──────────────────────────────────────────────────────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ CLASSIFY + EXTRACT                                           │
│   LLM: Bedrock Converse API (or Azure OpenAI) — native       │
│     structured output + tool use                             │
│   Wrapper: Instructor + Pydantic (provider swap via LiteLLM) │
│   Schema: polymorphic (CC schema | Distribution schema)      │
│   Few-shot retrieval: pgvector cosine kNN, k=3-5             │
└──────────────────────────────────────────────────────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ CANONICALIZE                                                 │
│   spaCy pattern matchers (vocabulary dictionary)             │
│   rapidfuzz for LP/GP name → master-data lookup (phase 1.5)  │
│   Decimal + date canonicalization (stdlib)                   │
└──────────────────────────────────────────────────────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ VALIDATE                                                     │
│   Pydantic validators for field types                        │
│   Custom validators for arithmetic invariants + date order   │
│   Tri-state assignment (absent / failed / low-conf)          │
└──────────────────────────────────────────────────────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ HITL                                                         │
│   Jobs table in Postgres (status: queued / in_review /       │
│     approved / rejected / committed)                         │
│   FastAPI + HTMX review UI (per-field approve,               │
│     keyboard-first, confidence-color)                        │
│   Worker (arq) polls approved rows and finalizes commit      │
└──────────────────────────────────────────────────────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ OBSERVE                                                      │
│   Arize Phoenix OTel traces — one trace per doc              │
│   Golden eval harness: pytest + local dataset                │
│   Cost attribution: log token counts per call → Postgres     │
└──────────────────────────────────────────────────────────────┘
```

### Key integration decisions

1. **Bedrock-first, Azure fallback.** Pick one provider for phase 1. Abstract behind Instructor's provider interface so swap is a config change, not a rewrite. The Design Brief (R4) demands this.
2. **One Postgres database.** Holds: jobs queue, audit records, embeddings (pgvector), master-data cache, eval results. Single backup story. Single ops surface.
3. **POC parallel comparison in week 1.** Run 10-20 representative CC/Distro docs through both (a) docling + LLM + Instructor, and (b) Bedrock Data Automation blueprint. Compare field-level accuracy. **If BDA matches or beats open-source at ≥95%, pivot phase 1 to BDA-primary with docling as fallback for edge-case templates.** This is a high-value experiment before locking architecture.
4. **Skip LangGraph and Temporal in phase 1.** If orchestration complexity emerges (e.g., non-linear agent loops in phase 3 for template auto-detection), revisit. Do not adopt pre-emptively.
5. **Custom HITL UI, not Label Studio.** Accept the ~1-2 week UX investment. Revisit Label Studio only if a second use case emerges.

---

## Risks and Unknowns

### Tools where signals conflict

| Tool | Signal tension | Recommendation |
|---|---|---|
| **LangGraph** | High adoption BUT documented 2026 API instability and HITL-gap complaints | Only adopt with version pinning + isolation. Do NOT bet phase-1 architecture on it. |
| **Docling** | 58k⭐ + IBM but only 8 months old; benchmark numbers are self-reported | Validate empirically on your template mix in POC before locking |
| **BAML** | Rapid growth; genuine technical merit (Schema-Aligned Parsing) BUT adds DSL + codegen step | Premature for Python-only solo dev; revisit if cross-language needs emerge |
| **Bedrock Data Automation** | New (2024) and AWS-proprietary — vendor lock risk BUT solves huge chunk of problem | Abstract behind parse-layer interface; evaluate head-to-head with Docling in POC |
| **Argilla** | HF-acquired 2024; team continuity AND HF strategic alignment both uncertain | Don't bet phase-1 UI on it; Label Studio is safer if going OSS-labeling route |

### Emerging tools with insufficient history

- **Formulary** (Khosla seed, Jan 2026) — too early.
- **Granite-Docling-258M** (Jan 2026) — the VLM itself is new; Docling-the-library is the mature surface.
- **Native Bedrock structured output** (GA Feb 2026, 2 months old at time of writing) — watch for edge-case breakage. Instructor's retry-on-error is the safety net.

### Unknowns worth asking the user (Design Lead)

1. **Is the user's employer already using Canoe Intelligence?** If yes, reframe scope as Canoe-complement (preprocess templates Canoe struggles with, or build internal tool for a subset Canoe doesn't cover). If no, we have more greenfield.
2. **Cloud-of-record locked?** AWS Bedrock path unlocks BDA; Azure unlocks Document Intelligence's mortgage/invoice models. This steers parse-layer choice.
3. **Is there an existing internal web app for reviewers today?** If yes, the HITL UI decision becomes "embed or integrate," which may favor FastAPI endpoints behind their existing UI over a standalone app.
4. **Is "interview-grade" story dominant, or "ship value fast" dominant?** If interview-grade: include LangGraph + Temporal exposure as a phase-2 experiment. If ship-value: hold the DIY line through phase 2.
5. **Reviewer count and dispersion.** If solo reviewer (likely), custom UI wins. If 5+ reviewers with auth/permission layers, Label Studio's multi-user model matters.

---

## Self-Check (SOP Step 6)

- [x] Market map present and categorized (not a flat list) — Q1-Q9 each have OSS / managed / cloud categorizations
- [x] Adoption tier per entry (mainstream / early-adopter / experimental) with evidence — see master matrix
- [x] Production evidence per recommendation (not just GitHub stars) — release cadence, enterprise adoption, independent benchmarks cited
- [x] Tool Recommendation Matrix in table format — master matrix + per-question verdicts
- [x] "No framework / DIY" baseline option included — Q9 dedicated to it; DIY IS the recommendation
- [x] All 9 research questions answered — Q1 through Q9 each have a dedicated section

## Sources

- [Procycons — PDF Extraction Benchmark 2025 (Docling/Unstructured/LlamaParse)](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/)
- [Reducto — Document Parser Comparison](https://llms.reducto.ai/document-parser-comparison)
- [Iterathon — Docling Production Deployment Guide 2026](https://iterathon.tech/blog/docling-production-deployment-guide-2026)
- [Docling GitHub Releases](https://github.com/docling-project/docling/releases)
- [BusinessWareTech — AWS Textract vs Google/Azure/GPT-4o Invoice Benchmark](https://www.businesswaretech.com/blog/research-best-ai-services-for-automatic-invoice-processing)
- [AI:Productivity — Best OCR Tools 2026 (Google vs AWS vs Azure vs ABBYY)](https://aiproductivity.ai/blog/best-ocr-tools-2026/)
- [AWS — Scalable IDP using Amazon Bedrock Data Automation](https://aws.amazon.com/blogs/machine-learning/scalable-intelligent-document-processing-using-amazon-bedrock-data-automation/)
- [AWS — Bedrock Data Automation blueprint instruction optimization](https://aws.amazon.com/about-aws/whats-new/2025/12/bedrock-data-automation-optimization-document-blueprints/)
- [LangChain — Durable Execution (LangGraph)](https://docs.langchain.com/oss/python/langgraph/durable-execution)
- [Medium — LangGraph vs Temporal for AI Agents (Mar 2026)](https://medium.com/data-science-collective/langgraph-vs-temporal-for-ai-agents-durable-execution-architecture-beyond-for-loops-a1f640d35f02)
- [Temporal — Durable Execution Solutions](https://temporal.io/)
- [ZenML — We Tested 8 LangGraph Alternatives](https://www.zenml.io/blog/langgraph-alternatives)
- [ema.ai — Top 10 LangGraph Alternatives 2026](https://www.ema.ai/additional-blogs/addition-blogs/langgraph-alternatives-to-consider)
- [techsy.io — 8 Best LLM Structured Output Libraries Ranked 2026](https://techsy.io/en/blog/best-llm-structured-output-libraries)
- [techsy.io — LLM Structured Outputs: Every Provider Guide 2026](https://techsy.io/en/blog/llm-structured-outputs-guide)
- [Instructor — Bedrock Integration](https://python.useinstructor.com/integrations/bedrock/)
- [AWS — Structured data response with Bedrock: Prompt Engineering and Tool Use](https://aws.amazon.com/blogs/machine-learning/structured-data-response-with-amazon-bedrock-prompt-engineering-and-tool-use/)
- [Boundary — Comparing BAML vs Pydantic](https://docs.boundaryml.com/guide/comparisons/baml-vs-pydantic)
- [Atlan — Enterprise RAG Platforms Comparison 2026](https://atlan.com/know/enterprise-rag-platforms-comparison/)
- [AWS Prescriptive — Vector Database Comparison](https://docs.aws.amazon.com/prescriptive-guidance/latest/choosing-an-aws-vector-database-for-rag-use-cases/vector-db-comparison.html)
- [John Snow Labs — Top 6 Annotation Tools for HITL LLMs 2026](https://www.johnsnowlabs.com/top-6-annotation-tools-for-hitl-llms-evaluation-and-domain-specific-ai-model-training/)
- [Labellerr — 8 Best Text Annotation Tools 2026](https://www.labellerr.com/blog/text-annotation-labeling-tools/)
- [Braintrust — Langfuse Alternatives 2026](https://www.braintrust.dev/articles/langfuse-alternatives-2026)
- [Langfuse — Self-Hosting Documentation](https://langfuse.com/self-hosting)
- [ClickHouse — Welcomes Langfuse acquisition](https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability)
- [Firecrawl — Best LLM Observability Tools 2026](https://www.firecrawl.dev/blog/best-llm-observability-tools)
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz)
- [Splink (MOJ) GitHub](https://github.com/moj-analytical-services/splink)
- [Robin Linacre — Deduplicating 7M records in 2 min with Splink](https://medium.com/data-science-collective/deduplicating-7-million-records-in-two-minutes-with-splink-4b1a87035a85)
- [Hercules AI — Capital Call and Distribution Notices](https://www.hercules.ai/capital-call-and-distribution-notices)
- [Akin — 2026 Perspectives in Private Equity: AI & Technology](https://www.akingump.com/en/insights/articles/2026-perspectives-in-private-equity-ai-and-technology)
- [OpenAI — Hebbia case study](https://openai.com/index/hebbia/)
- [Canoe Intelligence — Solutions](https://canoeintelligence.com/solutions/canoe-intelligence/)
- [Gen II + Canoe Partnership](https://gen2fund.com/news/gen-ii-revolutionizes-private-equity-data-digitalization-through-strategic-partnership-with-canoe-intelligence/)
- [Fortune — Formulary $4.6M seed (Jan 2026)](https://fortune.com/2026/01/20/khosla-formulary-private-fund-administration-venture-capital-private-equity-seed-round/)
- [Reducto — AI Financial Document Processing](https://reducto.ai/industries/finance)
- [Fortune — Reducto Series A $24.5M](https://fortune.com/2025/04/25/exclusive-reducto-ai-document-parsing-startup-raises-24-5-million-series-a-led-by-benchmark/)
- [Ocrolus Platform](https://www.ocrolus.com/platform/)
- [Argilla — Joining Hugging Face](https://argilla.io/blog/argilla-joins-hugggingface/)
- [Explosion — spacy-layout GitHub](https://github.com/explosion/spacy-layout)
- [AWS — Converse API Tool Use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-examples.html)
