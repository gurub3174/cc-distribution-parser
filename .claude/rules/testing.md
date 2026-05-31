---
name: Testing — patterns + golden-eval contract
applies-to: every test file, every CI workflow
status: load-bearing
references: spec/test-plan.md; spec/scope.md Acceptance Criterion 8
---

# Testing

Three layers: unit, integration, golden-eval. Each layer has a different cadence, cost, and gating policy.

## Layout

```
tests/
├── conftest.py              # shared fixtures
├── unit/                    # pure-function tests; <100ms each; no I/O
├── integration/             # multi-component, may hit local SQLite + MinIO; <5s each; no Bedrock, no Snowflake
├── eval/                    # marker=eval; golden set; replays through real or recorded Bedrock
└── security/
    └── injection_suite/     # red-team prompts; runs eval-time
```

## Markers (pyproject.toml)

```toml
[tool.pytest.ini_options]
markers = [
    "eval: golden-eval suite; CI-gated on PRs touching prompts/schemas/models",
    "integration: end-to-end with real Bedrock + Snowflake (skip in CI default)",
]
```

`pytest tests/` runs unit + (unmarked) integration. `pytest -m eval` runs the golden-eval suite. `pytest -m integration` is opt-in for live Bedrock/Snowflake runs.

## Unit-test rules

1. **No I/O.** Unit tests don't touch network, disk (beyond tmp_path), Snowflake, Bedrock, or LangGraph. If you need a connection, you're in the wrong layer.
2. **No mocks of own code.** Mock external boundaries (boto3 client, Snowflake connector); never mock our own service functions. Stubbing internal modules fakes the test.
3. **Fixture invariant — boundary state.** Test fixtures default to the boundary state where every multiplier/branch is neutral and every gate barely passes. Then per-test overrides flip exactly one thing. (See build-lead lesson 2026-05-01 "Test-fixture confidence threshold trap.")
4. **One concept per test.** No `test_extract_full_pipeline` that asserts 12 things. Split.

## Integration-test rules

1. **Local-only services.** SQLite (Alembic-migrated), MinIO (S3 emulator), in-process FastAPI. NOT Bedrock, NOT Snowflake.
2. **Test the seam.** A good integration test exercises a service-to-service contract (parse → extract handshake; extract → validate handshake). It is NOT an end-to-end "everything works" test.
3. **Bedrock + Snowflake go in `-m integration`.** Marker required. CI default skips them; engineers run them locally before merging changes that touch the integration boundary.

## Golden-eval rules

1. **Eval set lives in `data/golden_eval/`.** Each doc has a paired `<doc>.json` ground truth file.
2. **Per-field + per-template metrics.** F1 reported per (field × template). A blended F1 hides regressions on rare templates.
3. **Regression gate (initial, n<50):** `>5pt F1 drop` on any (field × template) cell fails the PR.
4. **Regression gate (mature, n≥50):** `>2pt F1 drop` fails.
5. **CI gating per Acceptance Criterion 8:** PRs touching `prompts/`, `schemas/`, `models.yaml`, OR `services/llm_client.py` MUST pass `pytest -m eval`. Path filter in `.github/workflows/golden-eval.yml`.
6. **Replays use recorded fixtures by default.** Live Bedrock calls in CI burn money + are flaky. The eval harness records Bedrock responses on first run, replays thereafter; live mode is opt-in via `EVAL_LIVE=1`.

## Security testing

1. **Spotlighting tests live in `tests/security/injection_suite/`.** Red-team prompts (50+ from OWASP LLM + project-specific).
2. **Test the security PROPERTY, not the input string.** When testing a wrap-based defense (Spotlighting wraps untrusted input in delimiters), the bad string IS in the output (wrapped). Assert that the bad string only appears INSIDE the wrap, never outside. (See build-lead lesson 2026-05-01 "Test the security property.")
3. **Schema-confusion tests.** Probe extraction with documents that look like CCs but have distribution-shaped numbers, and vice versa. Validates that the classifier + schema-validator handshake is genuinely independent.

## Coverage policy

- **Coverage as observation, not goal.** Aim for behavior coverage, not line coverage. A 100% line-coverage suite that doesn't test the unfunded-arithmetic invariant is worse than an 80% suite that does.
- **No coverage gate in CI.** Tracked in HTML reports for awareness; not enforced. (See build-team `code-style.md` — "test the right things, not all the things.")

## Anti-patterns

- **Test that passes whether the code is right or wrong.** Common with mocked-everywhere unit tests. Detect by: deliberately introduce a bug; if the test still passes, the test is fake.
- **Eval gate disabled "for one PR."** Eval gates rot when bypassed once. Re-enable before merge or open a tracked exemption.
- **Flaky integration test re-tried with `pytest --reruns`.** Find the flake source. Re-trying is admitting you don't know what the test is actually testing.
