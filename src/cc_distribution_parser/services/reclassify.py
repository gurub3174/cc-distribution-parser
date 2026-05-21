"""Reclassify path — Sonnet escalation on reconciliation failure.

Per Critic W4 (R5): when validate flags an invariant violation, escalate
to a stronger model with a tighter prompt rather than immediately HITL.
This is a single-shot retry — failure goes to HITL.
"""

from __future__ import annotations

from typing import Any

from cc_distribution_parser.observability.logging import get_logger
from cc_distribution_parser.services import classify as classify_service

log = get_logger(__name__)


def run(state: Any, *, model_id: str, **send_seams: Any) -> Any:
    """Re-run classification with the escalation model. Same DocState shape.

    The escalation model is Sonnet (config/models.yaml::models.reclassifier),
    not Haiku — the rationale per W4 is that the original failure was likely a
    weak-model misread.
    """
    log.warning(
        "reclassify.escalation",
        doc_id=state.get("doc_id"),
        original_class=state.get("doc_class"),
    )
    return classify_service.run(state, model_id=model_id, **send_seams)
