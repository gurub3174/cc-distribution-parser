---
type: lessons-learned
project: cc-distribution-parser
sprint: 0
created: 2026-05-03
tags: [sprint-0, scaffold, build-lead]
---

# Sprint 0 — Scaffold Lessons

## Hybrid rules pattern (`.claude/rules/` + central inheritance + `overrides.md`)

**What:** Generic rules (`code-style`, `no-fabrication`, `prompt-injection`, `wiki-conventions`, `tier-engagement`, `settings-precedence`) inherit from `~/.claude/ai-build-team/rules/`. Project-specific rules (`snowflake-migrations`, `framework-swap`, `structured-output-fallback`, `threshold-unlock`, `testing`) live in `.claude/rules/`. `overrides.md` ONLY captures deviations from central rules (e.g., elevating prompt-injection to mandatory Spotlighting).

**Why this project chose it:** The two existing patterns each broke a property we needed.
- Pure per-project (per `~/.claude/ai-design-team/wiki/user/conventions.md` 2026-04-20) duplicates 4 generic rules across every project — drift risk.
- Pure central + single `overrides.md` (build-team default 2026-04-30) jams substantial project-specific rules into a "deviations" file where they don't semantically fit (Snowflake DDL policy isn't a deviation of anything — it's an original rule).

**Effect:** Six central rule files inherited; 5 project-specific rule files committed to `.claude/rules/`; `.gitignore` updated to ship `.claude/rules/` only (other `.claude/` subfolders stay ignored). See `overrides.md` "Context — hybrid rules pattern" for the full A/B/C tradeoff.

**For future projects:** This is the first project using the hybrid. Companion projects (`job-search-pipeline`, `job-search-network`) still use the older per-project pattern. If hybrid B holds across 2–3 projects, promote it to `~/.claude/ai-design-team/wiki/user/conventions.md` and supersede the older convention.

## Spec-drift catch — `implementation-plan.md` was 2026-04-28 baseline

The implementation plan listed a `claude/rules/{code-style,testing,no-fabrication,prompt-injection}.md` Sprint 0 task — written before the build-team central-inheritance pattern existed. Surfaced as part of SOP step 0 (per build-lead lesson 2026-05-01 "Diff CLAUDE.md against spec amendments"). Resolution: bumped implementation-plan.md to v1.1.1 with a 2026-05-03 amendment recording the hybrid reconciliation.

**Pattern:** Specs drift between design-phase end and build-phase start. The drift catch is cheap if done at scaffold time; expensive if discovered mid-Sprint-1 when code already commits to the wrong pattern.

## Code Reviewer pass — caught the Dockerfile install-order trap

`pip install -e .` was placed BEFORE `COPY src ./src`, resolving an empty package. Caught as BLOCKING in pass-1. Trivial fix (swap two lines), but would have failed CI on the first `docker compose build`. Record this as a project-specific Dockerfile gotcha; surface to AI Engineer when Phase 1.5 CD work hardens the production image.

## Forward-contracts for Sprint 2+ rules

`.claude/rules/structured-output-fallback.md` describes `services/llm_client.py::call()` which doesn't exist until Sprint 2. Marked `status: forward-contract — enforced from Sprint 2` in frontmatter. Useful as design-up-front for OWASP-LLM-defensive properties (the security property is defined before the code that needs to enforce it).

## Snowflake creds deferred → Sprint 0 split

Sprint 0 deliverables 10-11 (validate environment + apply DDL) are blocked on Snowflake creds. All other Sprint 0 work landed: scaffold, rules, deps, docker-compose, DDL bootstrap, Alembic init, GitHub Actions, hybrid pattern reconciliation.
