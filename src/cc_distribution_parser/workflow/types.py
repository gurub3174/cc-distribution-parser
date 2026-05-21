"""DocState — framework-free pipeline state passed between service functions.

Per .claude/rules/framework-swap.md containment invariant #2: this is a plain
TypedDict importable anywhere. It carries ZERO LangGraph dependencies. The
graph module reads/writes the same TypedDict shape that pure service
functions read/write, so a future framework swap is one-directory.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

DocClass = Literal["capital_call", "distribution", "other_or_reject"]
PipelineStage = Literal[
    "ingest",
    "parse",
    "classify",
    "extract",
    "validate",
    "gate",
    "hitl",
    "commit",
]


class DocState(TypedDict, total=False):
    """Mutable state threaded through the pipeline.

    All keys are optional (`total=False`) because each stage only sets the
    keys it knows about. Reading code MUST tolerate missing keys.
    """

    # Identity
    doc_id: str
    pipeline_run_id: str
    user_id: str

    # Ingress
    original_filename: str
    mime_type: str
    file_hash: str
    original_s3_uri: str
    byte_size: int

    # Parse stage
    parsed_doc: dict[str, Any]  # serialized ParsedDoc
    docling_json_s3_uri: str
    chunks: list[dict[str, Any]]  # serialized ChunkRow list
    parser_version: str
    parser_metadata: dict[str, Any]

    # Classify / extract stages
    doc_class: DocClass
    classification_confidence: float
    extraction_payload: dict[str, Any]
    extraction_id: str

    # Versioning
    model_id: str
    prompt_hash: str
    prompt_version: str
    schema_version: str
    temperature: float

    # Validate / gate
    validation_report: dict[str, Any]
    gate_decision: Literal["auto_commit", "hitl", "reclassify", "skip_extract"]

    # Provenance
    few_shot_ids: list[str]
    provenance: dict[str, Any]
    cost_usd: str  # Decimal-as-string for serialization

    # Stage marker (for tracing)
    stage: PipelineStage

    # Error path
    error_class: str
    error_message: str
    retry_count: int
