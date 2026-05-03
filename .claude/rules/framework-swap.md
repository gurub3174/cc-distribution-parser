---
name: LangGraph Swap Playbook
applies-to: any LangGraph version change OR consideration of replacing LangGraph
status: load-bearing
references: spec/critical-review.md W3; spec/architecture.md §4
---

# LangGraph Swap Playbook

LangGraph is pinned `~=0.2.0` (minor-compatible). Market Scout's 2026-04-21 finding: LangGraph carries 2026 API-churn risk. Critic W3 (R4 in risk register) mandated isolation so a future swap is a one-directory rewrite.

## Containment invariants

These hold at all times. CI fails if any are violated:

1. **All LangGraph imports live in `src/cc_distribution_parser/workflow/`.** No other package imports `langgraph.*`.
2. **`workflow/types.py::DocState` is a plain `TypedDict`.** Importable anywhere; carries zero LangGraph dependencies.
3. **Service functions in `src/cc_distribution_parser/services/` are framework-free.** Each service is `def run(state: DocState) -> DocState` — pure, testable without spinning up a graph.
4. **Checkpointer choice is configurable.** `langgraph.checkpoint.sqlite.SqliteSaver` is the MVP default; the choice is wired through `app/config.py`, never hardcoded into nodes.

## Acceptable upgrade — minor version (0.2.x → 0.2.y)

1. Bump pin in `pyproject.toml`.
2. Run `pytest tests/integration/` — must pass.
3. Run `pytest -m eval` — must pass with no F1 regression.
4. Update `~/.claude/ai-build-team/wiki/lessons-learned/build-lead.md` if any API friction surfaced.

## Major upgrade decision (0.2.x → 0.3.x or 1.x)

LangGraph minor versions have historically introduced breaking changes. Treat every minor bump as a **decision**, not a maintenance task.

1. Read the LangGraph changelog. Identify breaking changes touching `StateGraph`, `Command`, `interrupt`, `Checkpoint`, or conditional-edge APIs.
2. Spike the upgrade on a feature branch. Run integration + eval suites.
3. If migration is non-trivial: open a swap RFC (`docs/rfc-langgraph-X.Y.md`) and route through Build Lead for user decision before committing.

## Full-swap playbook (LangGraph → alternative)

Triggers — any of:

- LangGraph project goes unmaintained (no commits 6 months) OR licensing changes.
- A breaking minor consumes more than 3 days of remediation.
- A measured production incident traces to a LangGraph bug with no upstream fix.

Replacement candidates (Market Scout 2026-04-21):

| Candidate | When it wins |
|---|---|
| **Plain Python state machine** | If the workflow is fundamentally linear (parse → classify → extract → validate → gate → commit) with one `interrupt()` for HITL. Removes one dependency entirely. |
| **Temporal** | If we need durable retries across hours/days, multi-node workers, and SLA visibility. Heavier but battle-tested. |
| **Prefect 3** | If we want a Python-native scheduler with a visual DAG view. Lighter than Temporal, less mature than LangGraph for agent loops. |

Swap procedure:

1. Implement the new orchestrator in `src/cc_distribution_parser/workflow/` — same `DocState` IO contract.
2. Run integration suite + eval suite — both must pass with no behavior diff.
3. Single PR replaces `workflow/graph.py` only. Service layer untouched.
4. Update `claude/rules/framework-swap.md` with the post-mortem of the swap.

## Anti-patterns

- **LangGraph imports leaking into `services/`.** Catches as a Code Reviewer pass-3 finding.
- **Hand-rolling retry/state-machine logic in services because "the graph is overkill."** Either the graph IS overkill (then swap) or services should stay pure (then leave retry to the graph or to `services/retry.py`).
- **Pinning `langgraph` to a major-version range (`>=0.2,<2.0`).** Defeats the whole point — locks in churn risk.
