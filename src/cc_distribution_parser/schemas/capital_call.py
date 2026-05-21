"""CapitalCallV1 - 9-field capital-call extraction schema.

Reasoning-first per Tam et al. EMNLP 2024 (arXiv:2408.02442) and
.claude/rules/structured-output-fallback.md rule 6: strict JSON-mode from
token 1 degrades reasoning 10-15%; the reasoning prefix preserves the chain
and is auditable in HITL provenance.

Field set is locked at v1.0.0; field additions require a new module +
schema_version bump + golden-eval regression sweep.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

schema_version = "capital_call@1.0.0"


class CapitalCallV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # REASONING FIRST — see module docstring.
    reasoning: str = Field(min_length=1)

    # 9 structured fields.
    gp_name: str = Field(min_length=1)
    fund_name: str = Field(min_length=1)
    investor_name: str = Field(min_length=1)
    notice_date: date
    due_date: date
    capital_call_amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unfunded_before: Decimal = Field(ge=0)
    unfunded_after: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def _unfunded_invariant(self) -> CapitalCallV1:
        # abs((before - call) - after) < 0.01 — the load-bearing CC check
        # per architecture.md. Phase 1 validates at extraction time AND
        # again in services/validate.py for defense in depth.
        diff = (self.unfunded_before - self.capital_call_amount) - self.unfunded_after
        if abs(diff) >= Decimal("0.01"):
            raise ValueError(
                f"unfunded invariant violated: "
                f"({self.unfunded_before} - {self.capital_call_amount}) - "
                f"{self.unfunded_after} = {diff}"
            )
        return self

    @model_validator(mode="after")
    def _dates_ordered(self) -> CapitalCallV1:
        if self.due_date < self.notice_date:
            raise ValueError("due_date must be >= notice_date")
        return self
