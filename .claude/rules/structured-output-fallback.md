---
name: Structured Output Fallback Policy
applies-to: src/cc_distribution_parser/services/llm_client.py and any extractor
status: forward-contract — enforced from Sprint 2 once llm_client.py lands
references: spec/critical-review.md W6 (R10); spec/architecture.md §5
---

# Structured Output Fallback Policy

Bedrock Converse went GA Feb 2026. As of project start, the structured-output stack (Bedrock Converse + Instructor + Pydantic schemas) is ~2 months old. Critic W6 surfaced edge-case risk: silent semantic breakage where the model returns syntactically-valid JSON that violates the schema in a way Instructor's retry can't recover.

## Rules

1. **Pinned exact model IDs.** Never use loose model identifiers (`claude-sonnet-4`, `sonnet`). Use full pinned IDs (`claude-sonnet-4-6`). Listed in `config/models.yaml`. Provenance records `model_id` on every extraction.
2. **Instructor retry budget = max 2.** First call + 1 retry on Pydantic `ValidationError`. Beyond that, fall back (rule 3). Do NOT raise the budget — retries on validation errors burn tokens without changing model behavior.
3. **`tool_use` fallback on validation failure.** If Converse + Instructor exhausts retries, retry once via Bedrock Converse `toolConfig` (forced tool use). Tools have a different output path than freeform text — empirically catches a class of failures that JSON-mode doesn't.
4. **Validation failures count toward retry-rate alert.** If `>5%` of LLM calls hit the fallback over a 1-hour window, write `drift-reports/retry-spike-<ts>.md`. Do not silently absorb the rate change — it's the canary for W6.
5. **Schema validation failures are NEVER transient retries.** Tenacity's `retry_if_exception_type` excludes `pydantic.ValidationError`. Validation failure → Instructor retry (rule 2) → fallback (rule 3) → DLQ. Never bounces through tenacity.
6. **Reasoning-first schemas.** Every Pydantic schema for extraction puts a `reasoning: str` field BEFORE the structured fields. Tam et al. EMNLP 2024 (`arXiv:2408.02442`): strict JSON-mode from token 1 degrades reasoning 10-15%. The reasoning prefix preserves the chain.

## Implementation contract

```python
# src/cc_distribution_parser/services/llm_client.py
def call(
    model_id: str,
    system: str,
    user: str,
    response_model: type[BaseModel],
    prompt_cache_keys: list[str] | None = None,
) -> tuple[BaseModel, CallMetadata]:
    try:
        return _call_via_instructor(...)   # rule 2
    except InstructorRetriesExhausted as exc:
        _record_fallback_metric(exc)        # rule 4
        return _call_via_tool_use(...)      # rule 3
```

## What changes if Bedrock Converse stabilizes (post-Phase-1)

If the retry-rate metric stays under 1% for 3 consecutive months:

- Keep the fallback; remove the alert threshold sensitivity.
- Document the stabilization in this file with the date + measured rate.
- The fallback stays even at low rate — cheap insurance.

## What changes if Bedrock Converse degrades

If retry-rate sustains >10% over 1 week:

- Open an RFC for swapping Instructor implementation (e.g., direct Bedrock JSON mode + Pydantic + manual retry loop).
- Do NOT increase Instructor's retry budget. Adding retries to a degraded primary just burns money.

## Anti-patterns

- Catching `ValidationError` and forging an "OK" response with empty fields. Silent fabrication.
- Retrying validation errors with exponential backoff. Won't help — the model gives the same answer.
- Removing the reasoning prefix because "we don't use it downstream." We do — it's auditable in HITL provenance and proves the chain wasn't crushed by JSON-mode.
