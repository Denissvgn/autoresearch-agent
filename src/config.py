"""Configuration for the autoresearch-agent service."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, List, Optional

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

try:
    from libs.config.config.vault_loader import get_vault_status as _get_vault_client_status
    from libs.config.config.vault_loader import load_vault_only as _load_vault_only

    _VAULT_AVAILABLE = True
except ImportError:
    try:
        from config.vault_loader import get_vault_status as _get_vault_client_status
        from config.vault_loader import load_vault_only as _load_vault_only

        _VAULT_AVAILABLE = True
    except ImportError:
        _VAULT_AVAILABLE = False
        _get_vault_client_status = None
        _load_vault_only = None

DEFAULT_CORS_ORIGINS = (
    "http://localhost:8030,"
    "http://127.0.0.1:8030,"
    "http://localhost:5173,"
    "http://127.0.0.1:5173"
)

_SERVICE_NAME = "autoresearch-agent"


def _settings_env() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("AUTORESEARCH_ENVIRONMENT")
        or os.getenv("ENVIRONMENT")
        or "development"
    )


@lru_cache(maxsize=1)
def _vault_settings_source() -> dict[str, Any]:
    """Load service defaults from Vault only, leaving env/.env precedence intact."""

    if not _VAULT_AVAILABLE or _load_vault_only is None:
        return {}
    env = _settings_env()
    try:
        return _load_vault_only(_SERVICE_NAME, env)
    except Exception as exc:
        logger.warning(
            "Failed to load Vault config for %s (%s): %s",
            _SERVICE_NAME,
            env,
            type(exc).__name__,
        )
        return {}


def secret_value(value: SecretStr | str | None) -> str | None:
    """Return a plain string for secret values at API/client boundaries."""

    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        """Use Vault as defaults below explicit init args, env vars, and .env."""

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _vault_settings_source,
            file_secret_settings,
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
    api_v1_prefix: str = Field(
        default="/api/v1",
        validation_alias=AliasChoices("AUTORESEARCH_API_V1_PREFIX", "API_V1_PREFIX"),
        description="Preferred versioned API prefix for autoresearch routes.",
    )
    autoresearch_api_token: SecretStr | None = Field(
        default=None,
        repr=False,
        description="Bearer token required for autoresearch API and WebSocket access.",
    )
    autoresearch_prometheus_token: SecretStr | None = Field(
        default=None,
        repr=False,
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
    anthropic_auth_token: SecretStr = Field(
        ...,
        repr=False,
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
        validation_alias=AliasChoices(
            "AUTORESEARCH_DEFAULT_QUICK_MODE",
            "DEFAULT_QUICK_MODE",
        ),
        description=(
            "Quick mode by default (2 folds, 50k steps). "
            "Override per-session with quick_mode=false."
        ),
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
    ws_max_clients: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices(
            "AUTORESEARCH_WS_MAX_CLIENTS",
            "WS_MAX_CLIENTS",
        ),
        description="Maximum concurrently connected WebSocket event clients.",
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
    vdmc_indicator_url: str = Field(
        default="http://vdmc-indicator:8000",
        validation_alias=AliasChoices(
            "AUTORESEARCH_VDMC_INDICATOR_URL",
            "VDMC_SERVICE_URL",
        ),
        description="VDMC indicator service URL used by RL/pipeline preflight checks.",
    )
    admin_service_url: str = Field(default="http://admin-service:8000")
    promotion_service_url: str = Field(
        default="http://mlflow-service:8000",
        description=(
            "Service owning promotion/composite APIs. Defaults to mlflow-service "
            "because autoresearch development promotion updates composites there."
        ),
    )
    mlflow_service_auth_token: SecretStr | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices(
            "AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN",
            "MLFLOW_SERVICE_AUTH_TOKEN",
            "SERVICE_AUTH_TOKEN",
            "ML_ADMIN_TOKEN",
        ),
        description=(
            "Bearer token used when autoresearch writes mlflow-service composite "
            "versions or promotes production composites."
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached service settings instance."""

    settings = Settings()  # type: ignore[call-arg]
    logger.info("Settings loaded for %s", settings.service_name)
    return settings


def get_vault_status() -> dict[str, Any]:
    """Return Vault configuration status for health/debug endpoints."""

    vault_config = _vault_settings_source()
    status: dict[str, Any] = {
        "vault_library_available": _VAULT_AVAILABLE,
        "vault_config_loaded": bool(vault_config),
        "vault_config_keys": len(vault_config),
        "service_name": _SERVICE_NAME,
        "app_env": _settings_env(),
    }
    if _VAULT_AVAILABLE and _get_vault_client_status is not None:
        try:
            status.update(_get_vault_client_status())
        except Exception as exc:
            status["vault_client_error"] = type(exc).__name__
    return status


settings = get_settings()
