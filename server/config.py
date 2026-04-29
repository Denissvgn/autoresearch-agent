"""Configuration for the autoresearch-agent service."""

from __future__ import annotations

import logging
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:8030,"
    "http://127.0.0.1:8030,"
    "http://localhost:5173,"
    "http://127.0.0.1:5173"
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Service ---
    service_name: str = Field(default="autoresearch-agent")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    autoresearch_api_token: str | None = Field(
        default=None,
        description="Bearer token required for autoresearch API and WebSocket access.",
    )

    # --- Anthropic ---
    anthropic_base_url: str = Field(
        ...,
        description="Anthropic API base URL (e.g. https://api.anthropic.com)",
    )
    anthropic_auth_token: str = Field(
        ...,
        description="Anthropic API authentication token",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model to use for agent sessions",
    )
    anthropic_default_haiku_model: str = Field(
        default="claude-haiku-4-20250514",
        description="Haiku-tier model alias (cheap/fast tasks like insight extraction)",
    )
    anthropic_default_sonnet_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Sonnet-tier model alias",
    )
    anthropic_default_opus_model: str = Field(
        default="claude-opus-4-20250514",
        description="Opus-tier model alias",
    )

    # --- Workspace ---
    workspace_root: str = Field(default="/app/workspace")
    host_configs_path: str = Field(default="/host/configs")

    # --- Experiment Limits ---
    max_iterations: int = Field(default=30)
    max_budget_usd: float = Field(default=10.0)
    experiment_timeout_s: int = Field(default=14400)
    default_quick_mode: bool = Field(
        default=True,
        description="Quick mode by default (2 folds, 50k steps). Override per-session with quick_mode=false.",
    )
    max_concurrent_sessions: int = Field(default=2)

    # --- API Robustness (ML-68) ---
    anthropic_api_timeout_s: int = Field(
        default=600,
        description="Per-request timeout for Anthropic API calls (seconds).",
    )
    max_api_retries: int = Field(
        default=3,
        description="Max retries on transient API errors (timeout, 500, 429).",
    )
    context_compaction_threshold: int = Field(
        default=80,
        description="Number of messages before old tool results are compacted.",
    )

    # --- ML Service URLs (Docker DNS) ---
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")
    mlflow_service_url: str = Field(default="http://mlflow-service:8000")
    mlflow_external_url: str = Field(
        default="http://localhost:5000",
        description="Browser-accessible MLflow URL for deep-linking from UI",
    )
    data_ingest_url: str = Field(default="http://data-ingest:8000")
    ensemble_trainer_url: str = Field(default="http://ensemble-trainer:8000")
    rl_trainer_url: str = Field(default="http://rl-trainer:8000")
    feature_service_url: str = Field(default="http://feature-service:8000")
    admin_service_url: str = Field(default="http://admin-service:8000")
    promotion_service_url: str = Field(
        default="http://mlflow-service:8000",
        description=(
            "Service owning promotion/composite APIs. Defaults to mlflow-service "
            "because autoresearch development promotion updates composites there."
        ),
    )

    # --- CORS ---
    cors_origins_raw: str = Field(
        default=DEFAULT_CORS_ORIGINS,
        validation_alias=AliasChoices(
            "AUTORESEARCH_CORS_ORIGINS",
            "CORS_ORIGINS_RAW",
            "CORS_ORIGINS",
        ),
    )

    @property
    def cors_origins(self) -> List[str]:
        if self.cors_origins_raw == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def db_path(self) -> str:
        return f"{self.workspace_root}/db/experiments.db"

    @property
    def skills_dir(self) -> str:
        return f"{self.workspace_root}/.github/skills"

    @property
    def autotuner_scripts_dir(self) -> str:
        return f"{self.workspace_root}/scripts/autotuner"

    @property
    def configs_dir(self) -> str:
        return f"{self.workspace_root}/configs"

    @property
    def runs_dir(self) -> str:
        return f"{self.workspace_root}/runs/autotuner"

    @property
    def venv_python(self) -> str:
        return f"{self.workspace_root}/.venv/bin/python"


settings = Settings()
