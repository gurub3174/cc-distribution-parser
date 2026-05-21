"""Runtime settings loaded from env via pydantic-settings.

Single source of truth for AWS, Snowflake, S3, and feature toggles. The
defaults are dev-only (MinIO, localhost Phoenix); production overrides come
from env vars per pydantic-settings precedence.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="CCDP_",
    )

    # AWS / Bedrock
    aws_region: str = "us-east-1"
    bedrock_classifier_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_extractor_model_id: str = "us.anthropic.claude-sonnet-4-6-20250929-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    # S3 (MinIO defaults for local dev)
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_bucket: str = "ccdp-dev"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"

    # Snowflake
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_warehouse: str = "CCDP_WH"
    snowflake_database: str = "CCDP"
    snowflake_schema: str = "PUBLIC"

    # SQLite ops-state
    sqlite_path: str = ".ccdp-ops.sqlite"

    # OTel / Phoenix
    otlp_endpoint: str = "http://localhost:6006/v1/traces"
    service_name: str = "cc-distribution-parser"

    # Feature flags
    auto_approve_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
