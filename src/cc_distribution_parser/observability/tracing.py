"""OTel tracing → Phoenix sidecar.

Every LLM call + DB write + stage transition emits a span with the
versioning attributes (model_id, prompt_hash, prompt_version, parser_version,
schema_version, temperature). Phoenix at localhost:6006 ingests via OTLP.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

VERSIONING_ATTRS = (
    "model_id",
    "prompt_hash",
    "prompt_version",
    "parser_version",
    "schema_version",
    "temperature",
)

_configured = False


def configure_tracing(*, service_name: str, otlp_endpoint: str) -> None:
    """Idempotent setup. Safe to call multiple times in tests."""
    global _configured
    if _configured:
        return
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def attach_versioning_attrs(span: trace.Span, **attrs: Any) -> None:
    """Attach the canonical versioning attribute set to a span.

    Unknown keys are dropped silently; the canonical set is fixed
    (VERSIONING_ATTRS). Pass values; None entries are skipped.
    """
    for key in VERSIONING_ATTRS:
        if key in attrs and attrs[key] is not None:
            span.set_attribute(key, attrs[key])
