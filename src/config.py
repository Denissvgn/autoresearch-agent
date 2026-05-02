"""Configuration for the autoresearch-agent service."""

from __future__ import annotations

import logging
from typing import List, Optional

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
    service_name: str = Field(
        default="autoresearch-agent",
        validation_alias=AliasChoices("AUTORESEARCH_SERVICE_NAME", "SERVICE_NAME"),
    )
    host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("AUTORESEARCH_HOST", "HOST"),
    )
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("AUTORESEARCH_PORT", "PORT"),
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("AUTORESEARCH_ENVIRONMENT", "ENVIRONMENT"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("AUTORESEARCH_LOG_LEVEL", "LOG_LEVEL"),
    )
    autoresearch_api_token: str | None = Field(
        default=None,
        description="Bearer token required for autoresearch API and WebSocket access.",
    )
    autoresearch_prometheus_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AUTORESEARCH_PROMETHEUS_TOKEN",
            "PROMETHEUS_TOKEN",
        ),
        description=(
            "Optional bearer token required to scrape /metrics. When set, "
            "callers must present 'Authorization: Bearer <token>' or the "
            "scrape is rejected with HTTP 401. Phase 5.2 hardening."
        ),
    )
    identity_service_url: str = Field(
        default="http://identity-service:8000",
        validation_alias=AliasChoices(
            "AUTORESEARCH_IDENTITY_SERVICE_URL",
            "IDENTITY_SERVICE_URL",
        ),
        description="Identity-service base URL used for JWT bearer-token introspection.",
    )
    identity_introspection_timeout_s: float = Field(
        default=5.0,
        gt=0,
        validation_alias=AliasChoices(
            "AUTORESEARCH_IDENTITY_INTROSPECTION_TIMEOUT_S",
            "IDENTITY_INTROSPECTION_TIMEOUT_S",
        ),
        description="Timeout in seconds for identity-service token introspection.",
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
    workspace_root: str = Field(
        default="/app/workspace",
        validation_alias=AliasChoices("AUTORESEARCH_WORKSPACE_ROOT", "WORKSPACE_ROOT"),
    )
    host_configs_path: str = Field(
        default="/host/configs",
        validation_alias=AliasChoices("AUTORESEARCH_HOST_CONFIGS_PATH", "HOST_CONFIGS_PATH"),
    )

    # --- Experiment Limits ---
    max_iterations: int = Field(
        default=30,
        validation_alias=AliasChoices("AUTORESEARCH_MAX_ITERATIONS", "MAX_ITERATIONS"),
    )
    max_budget_usd: float = Field(
        default=10.0,
        validation_alias=AliasChoices("AUTORESEARCH_MAX_BUDGET_USD", "MAX_BUDGET_USD"),
    )
    experiment_timeout_s: int = Field(
        default=14400,
        validation_alias=AliasChoices(
            "AUTORESEARCH_TIMEOUT_S",
            "AUTORESEARCH_EXPERIMENT_TIMEOUT_S",
            "EXPERIMENT_TIMEOUT_S",
        ),
    )
    default_quick_mode: bool = Field(
        default=True,
        validation_alias=AliasChoices("AUTORESEARCH_DEFAULT_QUICK_MODE", "DEFAULT_QUICK_MODE"),
        description="Quick mode by default (2 folds, 50k steps). Override per-session with quick_mode=false.",
    )
    max_concurrent_sessions: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "AUTORESEARCH_MAX_CONCURRENT",
            "AUTORESEARCH_MAX_CONCURRENT_SESSIONS",
            "MAX_CONCURRENT_SESSIONS",
        ),
    )

    # --- API Robustness (ML-68) ---
    anthropic_api_timeout_s: int = Field(
        default=600,
        validation_alias=AliasChoices(
            "AUTORESEARCH_ANTHROPIC_API_TIMEOUT_S",
            "ANTHROPIC_API_TIMEOUT_S",
        ),
        description="Per-request timeout for Anthropic API calls (seconds).",
    )
    max_api_retries: int = Field(
        default=3,
        validation_alias=AliasChoices("AUTORESEARCH_MAX_API_RETRIES", "MAX_API_RETRIES"),
        description="Max retries on transient API errors (timeout, 500, 429).",
    )
    context_compaction_threshold: int = Field(
        default=80,
        validation_alias=AliasChoices(
            "AUTORESEARCH_CONTEXT_COMPACTION_THRESHOLD",
            "CONTEXT_COMPACTION_THRESHOLD",
        ),
        description="Number of messages before old tool results are compacted.",
    )
    autoresearch_cross_session_duplicate_check: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "AUTORESEARCH_CROSS_SESSION_DUPLICATE_CHECK",
            "AUTORESEARCH_ENABLE_CROSS_SESSION_DUPLICATE_CHECK",
        ),
        description=(
            "Reject duplicate config/seed/mode/split attempts across prior "
            "sessions for the same instrument, timeframe, and model type. "
            "Phase 3.4: default flipped to True so wasted compute on "
            "already-explored points is the opt-out, not the opt-in."
        ),
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
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("S3_ENDPOINT_URL", "MINIO_ENDPOINT_URL"),
        description="S3-compatible artifact endpoint used by MLflow artifacts.",
    )
    mlflow_s3_endpoint_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MLFLOW_S3_ENDPOINT_URL"),
        description="MLflow S3 artifact endpoint override.",
    )

    # --- Dependency Preflight ---
    preflight_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "AUTORESEARCH_PREFLIGHT_ENABLED",
            "PREFLIGHT_ENABLED",
        ),
        description="Run service dependency checks before starting research sessions.",
    )
    allow_unready_services: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "AUTORESEARCH_ALLOW_UNREADY_SERVICES",
            "ALLOW_UNREADY_SERVICES",
        ),
        description="Dedicated override allowing sessions to start when preflight fails.",
    )
    preflight_timeout_s: float = Field(
        default=3.0,
        gt=0,
        validation_alias=AliasChoices(
            "AUTORESEARCH_PREFLIGHT_TIMEOUT_S",
            "PREFLIGHT_TIMEOUT_S",
        ),
        description="Per-service preflight timeout in seconds.",
    )
    artifact_logging_required: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "AUTORESEARCH_ARTIFACT_LOGGING_REQUIRED",
            "ARTIFACT_LOGGING_REQUIRED",
        ),
        description="Require the S3/MinIO endpoint during session preflight.",
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

    @property
    def artifact_store_endpoint_url(self) -> Optional[str]:
        return self.mlflow_s3_endpoint_url or self.s3_endpoint_url


settings = Settings()  # type: ignore[call-arg]
