from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="POLYGRAPHML_",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    agent_mode: Literal["fixture", "live"] = "fixture"
    storage_backend: Literal["local", "aws"] = "local"
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "POLYGRAPHML_OPENAI_API_KEY"),
    )
    openai_model: str = Field(
        default="gpt-5.6-sol",
        validation_alias=AliasChoices("OPENAI_MODEL", "POLYGRAPHML_OPENAI_MODEL"),
    )
    database_path: Path = Path(".polygraphml-data/polygraphml.db")
    artifact_root: Path = Path(".polygraphml-data/artifacts")
    session_ttl_seconds: int = 86_400
    max_artifact_bytes: int = 50 * 1024 * 1024
    max_github_tree_entries: int = 5_000
    max_github_import_bytes: int = 150 * 1024 * 1024
    compute_wall_timeout_seconds: float = 120
    compute_cpu_limit_seconds: int = 90
    compute_memory_limit_bytes: int = 2 * 1024 * 1024 * 1024
    compute_file_descriptor_limit: int = 64
    release_version: str = "0.2.0"
    build_sha: str = Field(
        default="unknown",
        validation_alias=AliasChoices(
            "POLYGRAPHML_BUILD_SHA",
            "GIT_SHA",
            "CODEBUILD_RESOLVED_SOURCE_VERSION",
        ),
    )
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    worker_poll_seconds: float = 0.25
    worker_lease_seconds: int = 300
    enqueue_recovery_seconds: int = 30
    aws_region: str = "us-east-1"
    s3_bucket: str | None = None
    dynamodb_table: str | None = None
    sqs_queue_url: str | None = None
    sqs_dlq_url: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(origin.strip() for origin in value.split(",") if origin.strip())
        return value

    @property
    def live_agent_ready(self) -> bool:
        return bool(
            self.agent_mode == "live"
            and self.openai_api_key is not None
            and self.openai_api_key.get_secret_value().strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
