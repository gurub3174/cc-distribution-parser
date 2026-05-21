"""Tests for cc_distribution_parser.config."""

from __future__ import annotations

from cc_distribution_parser.config import Settings, get_settings


def test_defaults_load_without_env():
    s = Settings()
    assert s.aws_region == "us-east-1"
    assert s.auto_approve_threshold == 0.0
    assert s.s3_bucket == "ccdp-dev"


def test_threshold_clamped_to_unit_interval():
    Settings(auto_approve_threshold=0.5)  # ok
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(auto_approve_threshold=1.5)


def test_get_settings_cached():
    assert get_settings() is get_settings()


def test_env_prefix_applied(monkeypatch):
    monkeypatch.setenv("CCDP_S3_BUCKET", "override-bucket")
    s = Settings()
    assert s.s3_bucket == "override-bucket"
