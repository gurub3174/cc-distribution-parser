# cc-distribution-parser

Extracts capital-call and distribution notices (PDF / scanned PDF / DOCX) into validated structured fields with HITL review. Internal Canoe Intelligence replacement; corpus-owning by design.

## Setup

```bash
uv venv
uv pip install -e ".[dev,eval]"
```

## Run

(project-specific — fill in once `src/cc_distribution_parser/` is populated)

## Test

```bash
uv run pytest tests/          # unit + integration
uv run pytest -m eval         # golden-eval (CI-gated)
```

## Lint + Format + Type-check

```bash
uv run ruff check .
uv run ruff format .
uv run pyright
```

## Project structure

- `src/cc_distribution_parser/` — Python source
- `tests/` — pytest tests (unit + integration + eval)
- `spec/` — design package from AI Design Team (PRD, TDD, sprint plan, scope, etc.)
- `wiki/` — project-local lessons-learned

## Build Team

This project is built with the AI Build Team. See `CLAUDE.md` for invocation instructions.
