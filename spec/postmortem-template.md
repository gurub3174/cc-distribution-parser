---
project: cc-distribution-parser
type: postmortem-template
created: 2026-04-21
status: empty-template-fill-after-phase-1-ships
---

# Postmortem — Capital Call & Distribution Parser — Phase 1

**Fill this template AFTER Phase 1 ships.** Compare what happened against what was designed.

## Metadata

- **Phase 1 ship date:**
- **Actual calendar duration:** (vs design estimate 5-6 weeks)
- **Actual focus-hours invested:**
- **Stack at ship:** (list any changes from architecture.md)
- **Phase-1 release gate passed?** Y/N. If N, which AC failed?

## What went well

List 3-5 concrete things that worked.

1.
2.
3.

## What didn't go well

List 3-5 concrete things that were painful or wrong.

1.
2.
3.

## What surprised us

Things the design didn't predict (good or bad).

1.
2.

## Accuracy against design predictions

| Predicted metric | Target | Actual | Notes |
|---|---|---|---|
| Field-level precision (post-HITL) | ≥98% | | |
| Field-level precision (raw, auto-validated after calibration) | ≥95% | | |
| Classification precision | ≥99% | | |
| Speed per doc | <2 min | | |
| Cost per doc | <$0.10 | | |
| HITL correction rate | ≥70% approve-without-correct | | |
| Silent-error rate | ≈0 | | |
| Time to 30 golden docs labeled | End of sprint 6 | | |

## Accuracy against risk register predictions

| Risk | Did it materialize? | Mitigation worked? | Notes |
|---|---|---|---|
| R1 Sparse-data cold start | | | |
| R2 HITL fatigue / ritual decay | | | |
| R3 Template drift | | | |
| R4 LLM provider deprecation | | | |
| R5 Over-trust | | | |
| R6 Prompt injection | | | |
| R7 Silent regression on prompt change | | | |
| R8 Scope creep | | | |

## Critic findings — outcome

| Critic finding | How did it play out? |
|---|---|
| C1 Unfunded before/after invariant | (did it catch errors? how many?) |
| C2 Single parser Phase 1 | (did Phase-1.5 A/B happen? what did it show?) |
| C3 Timeline realism | (did the 6-week estimate hold with scope cuts?) |
| C4 Ritual decay triggers | (did rituals stick? which failed silently?) |
| W1 LangGraph churn | (how many breaking changes in first 6 months?) |
| W2 Token economics | (actual per-doc cost?) |
| W3 Silver/gold pool | (phase-1 silver-only acceptable?) |
| W4 Reclassification path | (how many reclassifications happened?) |
| W5 Master-data access | (did it arrive? what's the accuracy ceiling?) |
| W6 Bedrock Converse stability | (any semantic breakage?) |
| W7 Golden eval size | (did n=20-30 catch regressions?) |

## Assumptions — held vs broken

| Assumption | Held? | Evidence |
|---|---|---|
| 5-6 weeks solo-dev sufficed | | |
| User has Bedrock capacity | | |
| Docling handles scanned PDFs acceptably | | |
| Prompt caching hit rate ≥80% | | |
| Compact few-shots retain enough signal | | |
| Reviewer clears queue on cadence | | |

## What would we do differently

Concrete changes we'd make if starting over.

1.
2.
3.

## What should Phase 1.5 prioritize

Based on Phase 1 learnings, what's the top Phase 1.5 priority? (Calibration study? Decomposition A/B? Parser A/B? Master-data wiring?)

## Evidence of actual use

- Number of docs processed through pipeline in first month:
- Number of docs processed in first three months:
- HITL reviewer hours saved (estimated vs manual baseline):
- Dollar cost of inference in first three months:
- Any production incidents:

## Lessons learned (feed into wiki/lessons-learned)

Things that should propagate to future projects via the design team's lessons system.

For Design Lead:

For Market Scout:

For Research Analyst:

For Design Critic:

User preferences / process-preferences updates:

## Sign-off

- [ ] Postmortem reviewed with self (solo-dev)
- [ ] Postmortem reviewed with any stakeholders (if applicable)
- [ ] Lessons captured in wiki
- [ ] Phase 1.5 plan drafted
