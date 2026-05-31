# Sprint 8 — Handoff

> Read this at session start before invoking `/build`. Builds on Sprint 7 commit `d34da11`.

## Where Sprint 7 landed

- Live Bedrock end-to-end on 3 native CC PDFs. Cost ~$0.015/doc.
- Cassette layer committed; `pytest -m eval` runs in replay against 6 cassettes (no AWS in CI).
- Phase-1 SQLite commit backend wired through the LangGraph DAG.
- Baseline **F1 = 0.83** (P=0.70, R=1.00, 19 TP / 8 FP / 0 FN across 27 cells × 3 templates).
- Anti-fabrication prompt v0.1.1 ships audit markers in reasoning ("UNFUNDED FIELDS FABRICATED", "DOCUMENT IS A TEMPLATE") whenever the model can't anchor a field to source content.

## The 8 false positives that drive the precision drag

| Class | Count | Cells | Fix path |
|---|---|---|---|
| Unfunded ledger fabrication | 6 | `unfunded_before`/`unfunded_after` × 3 templates | **§A — FieldProvenance** |
| Template misclassification | 2 | `capital_call_amount` + `currency` on `free-form-cc-template` | **§B — Classifier template-detection** |

Eliminating both ⇒ F1 ≈ 1.0 on the current 3-doc corpus. The corpus will grow as ILPA + further drawdown notices land, so the gate has to actually fire (it currently doesn't because there's no baseline-vs-current comparison wired in CI yet — see §D).

---

## §A — FieldProvenance (Phase 1.5, biggest lift)

**Reference:** `spec/architecture.md` §7.6 + v1.1.5 amendment.

**Goal:** every extracted value points to a `chunk_id` in `parsed_doc_chunks`. Values that the model can't anchor become validation failures, routed to HITL via the existing gate. Fabrication stops being silent.

**Scope:**

1. **Schema (`src/cc_distribution_parser/schemas/`)** — bump `capital_call.py` to `schema_version = "capital_call@1.1.0"`. Add:
   ```python
   class FieldProvenance(BaseModel):
       chunk_id: str | None  # null = "no source chunk supports this value"
       span_start: int | None
       span_end: int | None
       confidence: float = Field(ge=0.0, le=1.0)
   class CapitalCallV1(BaseModel):
       ...
       field_provenance: dict[str, FieldProvenance]
   ```
   Add a `@model_validator(mode="after")` that fails the model when a field has a value but `field_provenance[field].chunk_id` is None — that's the fabrication catch.

2. **Prompts (`prompts/extract_cc.py`)** — bump to `extract_cc@0.2.0`. Two changes:
   - Render chunks in the user message with explicit ids: `[chunk_id=doc-abc:c0001 | page=1 | role=body] Notice text here…`
   - Instruct the model: "For every extracted value, emit `field_provenance.<field_name>` with the `chunk_id` you copied the value from. If no chunk supports the value, emit `chunk_id: null` AND set the field's value to null (Optional[T])."

3. **Schemas — make absence representable** — `unfunded_before: Optional[Decimal]`, `unfunded_after: Optional[Decimal]`, etc. Schema bump documents the broadened field shape. Update the unfunded-invariant validator to skip when either is None (with a `validation_report.absent_fields` flag).

4. **Services**:
   - `extract.py` — render chunks with ids into `USER_TEMPLATE` (use the `chunks` list already in `DocState`).
   - `validate.py` — surface `validation_report.absent_fields: list[str]` and `validation_report.fabricated_fields: list[str]` (chunk_id null but value not null — should never happen post-fix, surface as a hard error).
   - `gate.py` — if `len(absent_fields) > 0`, force `hitl` regardless of confidence (sanity: don't auto-approve absences).

5. **Eval** — change `eval/runner.py` ground-truth comparison: when label is `null`, prediction `null` = TP; prediction non-null = FP. Same as today, but now the model can actually produce `null`. Expected F1 lift on unfunded fields: 0.0 → 1.0 (all 3 templates label them null; model should match).

6. **Migration** — `005_alter_extractions_add_field_provenance.sql` already exists per v1.1.5 amendment. Phase-1 SQLite mirror needs the same JSON column (`extraction_quality_json` is reserved-shape per CLAUDE.md amendment §3 — that's where `field_provenance` lives).

**Entry criteria:** all 6 unfunded-related cassettes get re-recorded against the new prompt. F1 baseline updated in wiki.

**Sequencing risk:** the chunked-context prompt is bigger (more input tokens). Sonnet 4.6 should still fit ILPA-shape docs in context, but multi-page funds-of-funds notices may push it. Sprint 8 should burn one cassette on a >5-page doc to verify.

**Tests to write first (TDD):**
- `tests/unit/test_extract_provenance.py` — given stub LLM returning `field_provenance.gp_name.chunk_id="doc:c0001"`, validate passes; given `chunk_id=None` + value="Acme", validate fails with "fabricated_fields=['gp_name']".
- `tests/unit/test_gate_provenance.py` — if `absent_fields` non-empty, gate returns `hitl` regardless of confidence.
- Integration: smoke-test the 3 existing PDFs; verify `unfunded_before` extractions now show `field_provenance.unfunded_before.chunk_id == None` and the field value is `null`.

**Estimated effort:** 2-3 days. The schema bump + prompt change + service plumbing is straightforward; the chunked-context formatting needs taste (whitespace + token budget).

---

## §B — Classifier template-detection (cheap, high-leverage)

**Goal:** `sample_capital_call_letter.pdf` (and any future placeholder template) gets classified `other_or_reject`, not `capital_call`.

**Scope:**

1. **`prompts/classifier.py`** — bump to `classifier@0.1.1`. Add to SYSTEM_PROMPT:
   ```
   Template detection: A document that contains placeholder text like 'ABC, LLC',
   'XYZ', 'Fund Name', 'Investor Name', '$_____', '[DATE]', or empty signature
   lines, AND no real entity/amount/date data, is a TEMPLATE — classify as
   other_or_reject. Real capital calls have specific names, amounts, and dates.
   ```
2. **Re-record** the classify cassette for `sample_capital_call_letter.pdf`.
3. **Ground truth** — `data/golden_eval/sample_capital_call_letter.json` already labels `doc_class: "other_or_reject"`. The classifier just needs to match.
4. **Eval** — add a `doc_class` row to the ground-truth comparison (currently the eval only measures per-field accuracy; classifier accuracy is implicit). Small extension to `eval/runner.py`:
   ```python
   pred_class = prediction.get("_doc_class")  # or pull from final state
   if doc.doc_class != pred_class:
       metrics.add(field_name="_doc_class", template_id=doc.template_id, tp=0, fp=1, fn=1)
   ```

**Estimated effort:** half a day. Mostly prompt + one eval-runner extension.

**Why this matters:** if the classifier routes templates to `other_or_reject`, the extract node never runs on them → no $0.01-fabrication FPs → 2 cells go to F1=1.0.

---

## §C — OCR (Sprint 7 carry-forward, BLOCKED on parser choice)

**Sprint 7 finding:** `DoclingParser.force_ocr` flag was unwired. Sprint 8 handoff wired it through `PdfPipelineOptions(do_ocr=True, force_full_page_ocr=True)`, but ILPA scans STILL produce 0 text. Root cause: docling's layout model classifies the entire ILPA page as a `Picture` region (not a text region), and OCR doesn't fire on Picture content even with `force_full_page_ocr` set. Verified across RapidOCR + EasyOCR engines.

**Recommended Sprint 8 path:**

1. **Bypass docling for image-only PDFs** — add a sibling parser `src/cc_distribution_parser/parsing/ocr_parser.py` that uses `pdf2image` + `pytesseract` (or `easyocr` directly) when docling's text-extraction returns empty. Routing logic in `services/parse.py`: try docling first; if `len(parsed.text) == 0` and `parser_metadata.contains_images`, retry through the OCR parser.

   OR

2. **Swap parser entirely for image-only PDFs to Azure DI / Bedrock BDA** — per `spec/scope.md:67` ("BDA + Azure DI A/B in Phase 1.5"). Both are Phase 1.5 deliverables already in scope. Bedrock BDA has the advantage of staying in the existing AWS account.

**Decision needed:** which? Build Lead recommendation is **option 1 (pdf2image + tesseract)** as a tactical fix — keeps docling as the primary parser, adds a fallback. Cost: ~1 day + tesseract install on dev machines. Option 2 is the strategic long-term move but is multi-day + needs Bedrock BDA model access.

**Tests to write first:** integration test that `ilpa_notice.pdf` produces `len(parsed.text) > 100` and contains the literal string "Capital Call Notice" (or whatever lands in the ILPA template).

**Estimated effort:** 1 day for option 1; 3+ days for option 2.

---

## §D — Sprint 7 follow-ups that didn't make it (read before opening any of A–C)

1. **Regression gate not wired in CI yet.** The baseline F1 lives in `~/.claude/ai-build-team/wiki/lessons-learned/build-lead.md` as a markdown table. The CI workflow at `.github/workflows/golden-eval.yml` runs `pytest -m eval` but doesn't compare current F1 against baseline. Need a small `tools/check_baseline_regression.py` that reads the wiki table OR a dedicated `baseline_metrics.json` and fails CI on >5pt drop per cell. **Without this, the gate is theater** (lesson 2026-05-03 — "A rule that names itself a forcing function MUST ship with the forcing function").

2. **Consolidation pass on `wiki/lessons-learned/build-lead.md`** — at 22 entries, over the 20 soft cap. Sprint 8 session 0 should consolidate before adding new entries.

3. **Cassette TTL policy.** Sprint 7 ships 6 cassettes; every prompt change invalidates them. Need a cleanup ritual: when a prompt's `version` bumps, the matching cassettes get deleted. Either automate (cassette key includes prompt_version explicitly) or document the ritual in `.claude/rules/testing.md`. Currently cassette keys hash `(model_id, system, user, response_model, temperature)` — prompt changes the `system` so the key changes automatically; orphan cassettes are dead weight. A pre-commit hook that prunes orphans (cassettes not touched in the last eval run) would handle this. ~1 hour fix.

4. **`auto_approve_threshold` is still locked at 0.0.** The unlock procedure in `.claude/rules/threshold-unlock.md` requires 20 labeled extractions per class (40 total) from the `corrections` table. Sprint 7 ships 3 labeled docs. The calibration study is at least Sprint 10+ before there's enough HITL data to attempt.

5. **`.ccdp-ops.sqlite` is local-only state** — already gitignored as of Sprint 7. But Phase 1.5 should plan its migration to Snowflake (the Phase-1 stand-in was always tactical; `.claude/rules/snowflake-migrations.md` change-log gets an entry when the swap happens).

---

## Sprint 8 ordering recommendation

If picking only one: **§A (FieldProvenance)**. Biggest precision lift, surfaces the silent-error class as a hard validation failure, eliminates 6/8 FPs.

If picking three: **§B → §D.1 → §A**.
- §B first (cheap, high-leverage, doesn't depend on schema work)
- §D.1 second (wires the regression gate so §A can be measured against a captured baseline)
- §A last (the big one; benefits from §B + §D.1 already in place)

**Don't pick §C first.** OCR is a tooling rabbit-hole; the 3-doc corpus already lets us measure prompt/schema improvements without it. ILPA docs are a "corpus diversification" goal, not a "blocker for shipping Phase 1."

---

## Carry-forward decisions for the user (Sprint 8 entry)

1. **Schema bump policy.** §A requires bumping `schema_version` from `1.0.0` to `1.1.0`. Per `spec/design-brief.md`, schema versions are major events. Is this OK to ship in one PR, or do you want it split (schema bump in one PR, prompt rewrite in the next)?
2. **OCR path** (§C). Option 1 (pdf2image + tesseract) or option 2 (Bedrock BDA) — needs your call before any §C work starts.
3. **Wiki consolidation timing.** Run the consolidation before Sprint 8 starts, or as Sprint 8 wraps?

---

## Files / paths a Sprint 8 agent should grep first

- `src/cc_distribution_parser/schemas/capital_call.py` — §A schema bump target.
- `src/cc_distribution_parser/prompts/extract_cc.py` — §A prompt rewrite + §B is in a sibling file.
- `src/cc_distribution_parser/prompts/classifier.py` — §B target.
- `src/cc_distribution_parser/services/validate.py` — §A validator changes.
- `src/cc_distribution_parser/services/gate.py` — §A gate changes.
- `src/cc_distribution_parser/eval/runner.py` — §A & §B comparison logic.
- `src/cc_distribution_parser/parsing/docling_parser.py` — §C: `_run_docling` and `_build_artifacts` need a sibling OCR path.
- `tests/eval/cassettes/` — invalidate + re-record on every prompt/schema bump.
- `spec/architecture.md` §7.6, §15.5 — the design-team spec for FieldProvenance.
- `.claude/rules/no-fabrication.md` — applies to §A; check what it says before designing the validator.
- `.claude/rules/structured-output-fallback.md` — already enforced; the new prompt must keep reasoning-first + spotlight wrap.
