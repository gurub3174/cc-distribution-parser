---
name: Auto-Approve Threshold Unlock Policy
applies-to: any change to auto_approve_threshold in config/models.yaml
status: load-bearing
enforcement: PENDING — CI lock-check workflow lands in Sprint 1 (.github/workflows/threshold-lock-check.yml). Until then this rule is honor-system + Code Reviewer pass.
references: spec/scope.md Eval Targets; spec/architecture.md §15.5; spec/critical-review.md C4 (R5)
---

# Auto-Approve Threshold Unlock Policy

The auto-approve threshold determines what fraction of HITL queue items bypass human review. **Locked at `0.0` (100% HITL) until a calibration study completes.** Critic C4 surfaced ritual-decay risk: rituals without forcing functions die silently. This file IS the forcing function.

## Lock state

```yaml
# config/models.yaml
auto_approve_threshold: 0.0   # LOCKED — see .claude/rules/threshold-unlock.md
```

The constant lives in versioned config. Changing it requires:

1. Calibration study (defined below) is complete with documented results.
2. New threshold value comes from the calibration study, not an estimate.
3. Change-log entry below is updated with the unlock event.
4. CI passes a check that compares the YAML value against the last documented value in this file — if the YAML changed but this file didn't, CI fails.

## Calibration study — gate to unlock

The study is run when at least **20 HITL-labeled extractions per class** (CC + Distribution = 40 total) are accumulated in `corrections`. Procedure:

1. Pull the labeled set from `corrections` join `extractions`.
2. For each soft signal (semantic-entropy, self-consistency, schema-confidence, reconciliation-score), compute precision/recall at every threshold from 0.0 to 1.0 in 0.05 increments.
3. Compute the threshold that achieves **P ≥ 0.99 on the auto-approved subset** AND maintains **R ≥ 0.40** (i.e., we can auto-approve at least 40% of high-confidence items without dropping precision below 0.99).
4. If no threshold satisfies both: stay at 0.0; document why; revisit at n=50.
5. If multiple thresholds satisfy both: pick the most conservative (highest threshold) to leave headroom.

## Unlock procedure

When ready to unlock:

1. Author the calibration-study report at `docs/calibration-study-<date>.md`.
2. Update the change-log section below: date, new threshold, citation to study, approver (human).
3. Update `config/models.yaml` in the same commit.
4. Add an integration test asserting the new threshold value.

The same commit must touch all three files. Code Reviewer rejects partial unlocks.

## Re-locking trigger

Auto-approve re-locks to `0.0` if either:

- HITL correction rate exceeds 5% on auto-approved items (sustained over 1 week).
- Drift report flags a 5+ pt F1 drop on the regression set.
- A silent-error event reaches commit (any wrong-money extraction).

Re-lock is automatic via CI check on metrics; calibration must repeat to unlock again.

## Change-log

| Date | Threshold | Reason | Approver | Study reference |
|---|---|---|---|---|
| 2026-05-03 | 0.0 | Initial lock — Acceptance Criterion 7 | gurub3174 | spec/scope.md |

## Anti-patterns

- "Just for testing" — raising the threshold in a non-prod environment without unlock procedure. There is no non-prod for this; the threshold rides on the same code path everywhere.
- Loosening the calibration-study P/R targets to clear the gate sooner. The targets ARE the gate; loosening defeats the purpose.
- Skipping the re-lock trigger because "the rate spike was a fluke." If it was a fluke, calibration will reconfirm in <1 day. If it wasn't, re-lock just saved a money-loss event.
