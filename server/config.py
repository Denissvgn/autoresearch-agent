"""Configuration for the autoresearch-agent service."""

from __future__ import annotations

import logging
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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

    # --- Workspace ---
    workspace_root: str = Field(default="/app/workspace")
    host_configs_path: str = Field(default="/host/configs")

    # --- Experiment Limits ---
    max_iterations: int = Field(default=30)
    max_budget_usd: float = Field(default=10.0)
    experiment_timeout_s: int = Field(default=14400)
    default_quick_mode: bool = Field(
        default=False,
        description="Standard (full) research mode by default",
    )
    max_concurrent_sessions: int = Field(default=2)

    # --- ML Service URLs (Docker DNS) ---
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")
    mlflow_service_url: str = Field(default="http://mlflow-service:8000")
    data_ingest_url: str = Field(default="http://data-ingest:8000")
    ensemble_trainer_url: str = Field(default="http://ensemble-trainer:8000")
    rl_trainer_url: str = Field(default="http://rl-trainer:8000")
    feature_service_url: str = Field(default="http://feature-service:8000")

    # --- CORS ---
    cors_origins_raw: str = Field(default="*")

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
