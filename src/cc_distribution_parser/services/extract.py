"""Extractor services for capital_call + distribution.

Two entry points: `run_cc` and `run_distro`. Each renders the appropriate
prompt + few-shots, calls the LLM client, persists prompt_hash + schema_version.
"""

from __future__ import annotations

from typing import Any, cast

from cc_distribution_parser.prompts import extract_cc as cc_prompt
from cc_distribution_parser.prompts import extract_distro as distro_prompt
from cc_distribution_parser.schemas.capital_call import CapitalCallV1
from cc_distribution_parser.schemas.capital_call import schema_version as cc_schema_version
from cc_distribution_parser.schemas.distribution import DistributionV1
from cc_distribution_parser.schemas.distribution import (
    schema_version as distro_schema_version,
)
from cc_distribution_parser.services import llm_client
from cc_distribution_parser.services.spotlighting import wrap
from cc_distribution_parser.workflow.types import DocState


def _render_user(prompt_module: Any, text: str, vocab_hints: list[str]) -> str:
    return prompt_module.USER_TEMPLATE.format(
        few_shots="",  # Sprint 3 wires this in
        wrapped_document=wrap(text),
        vocab_hints=", ".join(vocab_hints) if vocab_hints else "(none)",
    )


def run_cc(state: DocState, *, model_id: str, **send_seams: Any) -> DocState:
    text = state["parsed_doc"]["text"]
    user = _render_user(cc_prompt, text, [])
    rendered = cc_prompt.SYSTEM_PROMPT + "\n\n" + user
    prompt_hash = cc_prompt.compute_hash(rendered)
    parsed, meta = llm_client.call(
        model_id=model_id,
        system=cc_prompt.SYSTEM_PROMPT,
        user=user,
        response_model=CapitalCallV1,
        temperature=0.0,
        prompt_version=cc_prompt.version,
        prompt_hash=prompt_hash,
        **send_seams,
    )
    payload = cast(CapitalCallV1, parsed)
    state["extraction_payload"] = payload.model_dump(mode="json")
    state["model_id"] = meta.model_id
    state["prompt_hash"] = meta.prompt_hash
    state["prompt_version"] = meta.prompt_version
    state["schema_version"] = cc_schema_version
    state["temperature"] = meta.temperature
    state["cost_usd"] = str(meta.cost_usd)
    state["stage"] = "extract"
    return state


def run_distro(state: DocState, *, model_id: str, **send_seams: Any) -> DocState:
    text = state["parsed_doc"]["text"]
    user = _render_user(distro_prompt, text, [])
    rendered = distro_prompt.SYSTEM_PROMPT + "\n\n" + user
    prompt_hash = distro_prompt.compute_hash(rendered)
    parsed, meta = llm_client.call(
        model_id=model_id,
        system=distro_prompt.SYSTEM_PROMPT,
        user=user,
        response_model=DistributionV1,
        temperature=0.0,
        prompt_version=distro_prompt.version,
        prompt_hash=prompt_hash,
        **send_seams,
    )
    payload = cast(DistributionV1, parsed)
    state["extraction_payload"] = payload.model_dump(mode="json")
    state["model_id"] = meta.model_id
    state["prompt_hash"] = meta.prompt_hash
    state["prompt_version"] = meta.prompt_version
    state["schema_version"] = distro_schema_version
    state["temperature"] = meta.temperature
    state["cost_usd"] = str(meta.cost_usd)
    state["stage"] = "extract"
    return state
