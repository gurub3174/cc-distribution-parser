"""Bedrock per-token cost table.

Keyed by inference-profile model ID (the `us.anthropic.*` form used in
config/models.yaml). If a model isn't in the table, `compute_cost` returns 0
and logs a warning — cost telemetry is best-effort, not load-bearing.

Rates verified against Anthropic published pricing 2026-Q1. Bedrock charges
match Anthropic API for the Claude family. Update this table when model
prices change or new pinned IDs are added to config/models.yaml.
"""

from __future__ import annotations

from decimal import Decimal

from cc_distribution_parser.observability.logging import get_logger

log = get_logger(__name__)


# (input_per_million, output_per_million) in USD
_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (Decimal("1.00"), Decimal("5.00")),
    "us.anthropic.claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
}


def compute_cost(model_id: str, input_tokens: int, output_tokens: int) -> Decimal:
    rates = _PRICES.get(model_id)
    if rates is None:
        log.warning("bedrock_pricing.unknown_model", model_id=model_id)
        return Decimal("0")
    in_rate, out_rate = rates
    millions = Decimal(1_000_000)
    return (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / millions
