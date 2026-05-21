"""Classifier service.

Renders prompt → llm_client.call → DocClassification → DocState.
The actual Bedrock path is stubbed; tests inject the LLM sender.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel

from cc_distribution_parser.prompts import classifier as classifier_prompt
from cc_distribution_parser.services import llm_client
from cc_distribution_parser.services.spotlighting import wrap
from cc_distribution_parser.workflow.types import DocClass, DocState


class DocClassification(BaseModel):
    reasoning: str
    label: DocClass
    confidence: float


def render_prompts(text: str) -> tuple[str, str, str]:
    """Return (system, user, prompt_hash). Caller persists prompt_hash."""
    system = classifier_prompt.SYSTEM_PROMPT
    user = classifier_prompt.USER_TEMPLATE.format(document=wrap(text))
    rendered = system + "\n\n" + user
    return system, user, classifier_prompt.compute_hash(rendered)


def run(state: DocState, *, model_id: str, **send_seams: Any) -> DocState:
    text = state["parsed_doc"]["text"]
    system, user, prompt_hash = render_prompts(text)
    parsed, meta = llm_client.call(
        model_id=model_id,
        system=system,
        user=user,
        response_model=DocClassification,
        temperature=0.0,
        prompt_version=classifier_prompt.version,
        prompt_hash=prompt_hash,
        **send_seams,
    )
    classification = cast(DocClassification, parsed)
    state["doc_class"] = classification.label
    state["classification_confidence"] = classification.confidence
    state["model_id"] = meta.model_id
    state["prompt_hash"] = meta.prompt_hash
    state["prompt_version"] = meta.prompt_version
    state["temperature"] = meta.temperature
    state["stage"] = "classify"
    return state
