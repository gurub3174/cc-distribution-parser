"""Unit tests for VLMParser + services.parse fallback wiring + services.vlm_transcribe.

No Bedrock calls — `transcribe_fn` / `real_send` seams inject fakes.
"""

from __future__ import annotations

from typing import Any

import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel

from cc_distribution_parser.parsing.vlm_parser import VLMParser
from cc_distribution_parser.schemas.chunk import ChunkRow
from cc_distribution_parser.schemas.document import ParserMetadata
from cc_distribution_parser.schemas.parsed_doc import ParsedDoc
from cc_distribution_parser.services import parse as parse_service
from cc_distribution_parser.services import vlm_transcribe
from cc_distribution_parser.workflow.types import DocState

BUCKET = "ccdp-dev"
PINNED_SONNET = "us.anthropic.claude-sonnet-4-6"


class _ProducesNothingParser:
    name = "empty-stub"
    version = "empty@0.0.0"

    def parse(self, file_bytes, mime_type, *, doc_id, user_id):
        parsed = ParsedDoc(
            doc_id=doc_id,
            text="",
            parser_version=self.version,
            page_count=1,
            language="en",
            contains_tables=False,
            contains_images=True,
            ocr_used=False,
            parse_duration_ms=1,
        )
        meta = ParserMetadata(
            page_count=1,
            language="en",
            contains_tables=False,
            contains_images=True,
            ocr_used=False,
            parse_duration_ms=1,
        )
        return parsed, [], meta


class _OneChunkParser:
    name = "one-chunk-stub"
    version = "one@0.0.0"

    def parse(self, file_bytes, mime_type, *, doc_id, user_id):
        text = "Hello"
        parsed = ParsedDoc(
            doc_id=doc_id,
            text=text,
            parser_version=self.version,
            page_count=1,
            language="en",
            contains_tables=False,
            contains_images=False,
            ocr_used=False,
            parse_duration_ms=1,
        )
        chunk = ChunkRow(
            id=f"{doc_id}:c1",
            doc_id=doc_id,
            page=1,
            layout_role="body",
            text=text,
            bbox=(0.0, 0.0, 1.0, 1.0),
            read_order=1,
            hierarchy_level=3,
            char_offset_start=0,
            char_offset_end=len(text),
            user_id=user_id,
        )
        meta = ParserMetadata(
            page_count=1,
            language="en",
            contains_tables=False,
            contains_images=False,
            ocr_used=False,
            parse_duration_ms=1,
        )
        return parsed, [chunk], meta


@pytest.fixture
def s3_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("CCDP_S3_ENDPOINT_URL", "")
    from cc_distribution_parser.config import get_settings

    get_settings.cache_clear()
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield
    get_settings.cache_clear()


# ---- VLMParser unit tests ------------------------------------------------


def _fake_transcribe_ok(**kwargs) -> tuple[str, Any]:
    return "Capital Call Notice\nFund: Acme Capital Partners III, L.P.\nAmount: $250,000", None


def test_vlm_parser_emits_single_chunk_with_full_text():
    parser = VLMParser(model_id=PINNED_SONNET, transcribe_fn=_fake_transcribe_ok)
    parsed, chunks, meta = parser.parse(
        b"%PDF-fake",
        "application/pdf",
        doc_id="d-1",
        user_id="u-1",
    )
    assert parsed.parser_version == "vlm-bedrock@0.1.0"
    assert parsed.ocr_used is True
    assert parsed.contains_images is True
    assert len(chunks) == 1
    assert chunks[0].layout_role == "body"
    assert "Acme Capital Partners" in chunks[0].text
    assert chunks[0].char_offset_start == 0
    assert chunks[0].char_offset_end == len(parsed.text)
    assert meta.page_count == 1


def test_vlm_parser_empty_transcription_emits_no_chunks():
    parser = VLMParser(model_id=PINNED_SONNET, transcribe_fn=lambda **_: ("   ", None))
    parsed, chunks, _meta = parser.parse(
        b"%PDF-empty",
        "application/pdf",
        doc_id="d-2",
        user_id="u-1",
    )
    assert parsed.text == ""
    assert chunks == []


# ---- services.parse fallback wiring -------------------------------------


def test_parse_run_no_fallback_when_primary_returns_chunks(s3_env):
    state: DocState = {
        "doc_id": "d-3",
        "user_id": "u-1",
        "mime_type": "application/pdf",
        "pipeline_run_id": "r-1",
    }
    called = {"fallback": 0}

    class _Fallback(_OneChunkParser):
        name = "fallback"
        version = "fallback@0.0.0"

        def parse(self, *args, **kwargs):
            called["fallback"] += 1
            return super().parse(*args, **kwargs)

    out = parse_service.run(
        state,
        parser=_OneChunkParser(),
        file_bytes=b"%PDF-fake",
        fallback_parser=_Fallback(),
    )
    assert out["parser_version"] == "one@0.0.0"
    assert called["fallback"] == 0


def test_parse_run_invokes_fallback_when_primary_returns_zero_chunks(s3_env):
    state: DocState = {
        "doc_id": "d-4",
        "user_id": "u-1",
        "mime_type": "application/pdf",
        "pipeline_run_id": "r-1",
    }
    out = parse_service.run(
        state,
        parser=_ProducesNothingParser(),
        file_bytes=b"%PDF-fake",
        fallback_parser=VLMParser(model_id=PINNED_SONNET, transcribe_fn=_fake_transcribe_ok),
    )
    assert out["parser_version"] == "vlm-bedrock@0.1.0"
    assert len(out["chunks"]) == 1
    assert "Acme Capital Partners" in out["chunks"][0]["text"]


def test_parse_run_no_fallback_kwarg_leaves_zero_chunks_intact(s3_env):
    """Backwards-compat: existing callers without fallback_parser still work."""
    state: DocState = {
        "doc_id": "d-5",
        "user_id": "u-1",
        "mime_type": "application/pdf",
        "pipeline_run_id": "r-1",
    }
    out = parse_service.run(state, parser=_ProducesNothingParser(), file_bytes=b"%PDF-fake")
    assert out["chunks"] == []
    assert out["parser_version"] == "empty@0.0.0"


# ---- services.vlm_transcribe unit tests ---------------------------------


def _fake_real_send_ok(**kwargs) -> tuple[BaseModel, dict[str, Any]]:
    parsed = vlm_transcribe.TranscribedText(
        reasoning="single-page capital call notice",
        text="Capital Call Notice\nAmount: $1,000,000",
    )
    return parsed, {
        "input_tokens": 1500,
        "output_tokens": 80,
        "cached_tokens": 0,
        "cost_usd": "0.012",
    }


def test_transcribe_returns_text_and_metadata(monkeypatch, tmp_path):
    # Point cassette dir at a tmp dir so we don't pollute committed cassettes.
    monkeypatch.setattr(
        "cc_distribution_parser.services.llm_cassette.DEFAULT_CASSETTE_DIR",
        tmp_path / "cassettes",
    )
    monkeypatch.setenv("CCDP_LLM_MODE", "auto")
    text, meta = vlm_transcribe.transcribe(
        file_bytes=b"%PDF-fake-bytes",
        mime_type="application/pdf",
        model_id=PINNED_SONNET,
        real_send=_fake_real_send_ok,
    )
    assert "Capital Call Notice" in text
    assert meta.input_tokens == 1500
    assert meta.prompt_version == "vlm_transcribe@0.1.0"


def test_transcribe_rejects_loose_model_id():
    with pytest.raises(ValueError, match="loose model id"):
        vlm_transcribe.transcribe(
            file_bytes=b"%PDF",
            mime_type="application/pdf",
            model_id="sonnet",
            real_send=_fake_real_send_ok,
        )


def test_transcribe_rejects_unsupported_mime():
    with pytest.raises(ValueError, match="unsupported mime_type"):
        vlm_transcribe.transcribe(
            file_bytes=b"<html/>",
            mime_type="text/html",
            model_id=PINNED_SONNET,
            real_send=_fake_real_send_ok,
        )


def test_transcribe_cassette_replay_is_deterministic(monkeypatch, tmp_path):
    """First call records; second call (replay) hits the cassette, never calls real_send."""
    monkeypatch.setattr(
        "cc_distribution_parser.services.llm_cassette.DEFAULT_CASSETTE_DIR",
        tmp_path / "cassettes",
    )
    monkeypatch.setenv("CCDP_LLM_MODE", "auto")
    real_send_call_count = {"n": 0}

    def _counting_send(**kwargs):
        real_send_call_count["n"] += 1
        return _fake_real_send_ok(**kwargs)

    text1, _ = vlm_transcribe.transcribe(
        file_bytes=b"%PDF-fixed",
        mime_type="application/pdf",
        model_id=PINNED_SONNET,
        real_send=_counting_send,
    )
    # Switch to replay; should hit cassette, NOT call real_send again.
    monkeypatch.setenv("CCDP_LLM_MODE", "replay")
    text2, _ = vlm_transcribe.transcribe(
        file_bytes=b"%PDF-fixed",
        mime_type="application/pdf",
        model_id=PINNED_SONNET,
        real_send=_counting_send,
    )
    assert text1 == text2
    assert real_send_call_count["n"] == 1  # second was served from cassette
