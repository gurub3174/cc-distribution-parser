"""DistributionV1 — 8-field distribution extraction schema.

Reasoning-first per Tam et al. 2024 + .claude/rules/structured-output-fallback.md
rule 6.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

schema_version = "distribution@1.0.0"

DistributionType = Literal["income", "return_of_capital", "realized_gain", "other"]


class DistributionV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reasoning: str = Field(min_length=1)

    gp_name: str = Field(min_length=1)
    fund_name: str = Field(min_length=1)
    investor_name: str = Field(min_length=1)
    notice_date: date
    payment_date: date
    distribution_amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    distribution_type: DistributionType
