"""Configuration for the autoresearch-agent service."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, List, Literal, Optional

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:8030,"
    "http://127.0.0.1:8030,"
    "http://localhost:5173,"
    "http://127.0.0.1:5173"
)


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
        # deliberate (pydantic-settings): env files carry unrelated keys
        extra="ignore",
        populate_by_name=True,
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
    agent_output_digest_max_chars: int = Field(
        default=12_000,
        description=(
            "Bash tool outputs longer than this are digested before "
            "entering the agent's context (metrics block / markers / errors "
            "kept, noise collapsed, full log persisted to the workspace). "
            "0 disables digesting (legacy: full raw output every turn)."
        ),
        validation_alias=AliasChoices(
            "AUTORESEARCH_AGENT_OUTPUT_DIGEST_MAX_CHARS",
            "AGENT_OUTPUT_DIGEST_MAX_CHARS",
        ),
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
            "scrape is rejected with HTTP 401."
        ),
    )
    identity_introspection_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AUTORESEARCH_IDENTITY_INTROSPECTION_URL",
            # Legacy aliases from the platform identity-service integration;
            # the value must now be the full introspection endpoint URL.
            "AUTORESEARCH_IDENTITY_SERVICE_URL",
            "IDENTITY_SERVICE_URL",
        ),
        description=(
            "Optional OAuth2 token-introspection endpoint URL (RFC 7666) used "
            "to authenticate admin JWT bearer tokens. Empty (default) disables "
            "JWT introspection; only the static API token is accepted then."
        ),
    )
    identity_introspection_timeout_s: float = Field(
        default=5.0,
        gt=0,
        validation_alias=AliasChoices(
            "AUTORESEARCH_IDENTITY_INTROSPECTION_TIMEOUT_S",
            "IDENTITY_INTROSPECTION_TIMEOUT_S",
        ),
        description="Timeout in seconds for token introspection.",
    )

    # --- Anthropic ---
    anthropic_base_url: str = Field(
        default="",
        description="Anthropic API base URL (e.g. https://api.anthropic.com)",
    )
    anthropic_auth_token: SecretStr | None = Field(
        default=None,
        repr=False,
        description="Anthropic API authentication token",
    )
    # NOTE: SecretStr fields here are NOT inherited by governed experiment
    # subprocesses. See src.core.command_runner._CHILD_ENV_ALLOWLIST /
    # _FORBIDDEN_CHILD_ENV for the agent-path env contract. New server
    # control-plane secrets added below should also be added to
    # _FORBIDDEN_CHILD_ENV there.
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

    # --- OpenAI & Wide Provider / Local LLM Routing ---
    # Supports OpenAI, OpenAI-compatible servers (vLLM, Ollama, LM Studio,
    # llama.cpp, OpenRouter, LiteLLM, custom proxies), and Anthropic.
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        repr=False,
        description="OpenAI API key (optional for keyless local servers)",
    )
    openai_model: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_MODEL", "AUTORESEARCH_OPENAI_MODEL"),
        description=(
            "Default model for OpenAI / OpenAI-compatible providers when not "
            "set in SKILL.yaml"
        ),
    )
    openai_api_timeout_s: int = Field(
        default=600,
        description="OpenAI API timeout in seconds",
    )
    llm_provider: str = Field(
        default="",
        validation_alias=AliasChoices("AUTORESEARCH_LLM_PROVIDER", "LLM_PROVIDER"),
        description=(
            "Global LLM provider override (anthropic, openai, openai-compatible, "
            "ollama, vllm, lmstudio, llamacpp, local, openrouter, mock). When "
            "empty, each skill uses its manifest llm.provider."
        ),
    )
    llm_model: str = Field(
        default="",
        validation_alias=AliasChoices("AUTORESEARCH_LLM_MODEL", "LLM_MODEL"),
        description=(
            "Global primary model override or default across providers "
            "(e.g. qwen2.5-coder:32b, llama3.3:70b, gpt-4o)."
        ),
    )
    llm_insight_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AUTORESEARCH_LLM_INSIGHT_MODEL", "LLM_INSIGHT_MODEL"
        ),
        description="Optional global insight/summarization model override.",
    )
    llm_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("AUTORESEARCH_LLM_BASE_URL", "LLM_BASE_URL"),
        description="Global base URL override for the active LLM provider.",
    )
    llm_api_key: SecretStr | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices("AUTORESEARCH_LLM_API_KEY", "LLM_API_KEY"),
        description="Global API key override for the active LLM provider.",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        validation_alias=AliasChoices(
            "OLLAMA_BASE_URL", "AUTORESEARCH_OLLAMA_BASE_URL"
        ),
        description="Local Ollama OpenAI-compatible base URL",
    )
    vllm_base_url: str = Field(
        default="http://localhost:8000/v1",
        validation_alias=AliasChoices("VLLM_BASE_URL", "AUTORESEARCH_VLLM_BASE_URL"),
        description="Local/self-hosted vLLM OpenAI-compatible base URL",
    )
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1",
        validation_alias=AliasChoices(
            "LMSTUDIO_BASE_URL", "AUTORESEARCH_LMSTUDIO_BASE_URL"
        ),
        description="Local LM Studio OpenAI-compatible base URL",
    )
    llamacpp_base_url: str = Field(
        default="http://localhost:8080/v1",
        validation_alias=AliasChoices(
            "LLAMACPP_BASE_URL", "AUTORESEARCH_LLAMACPP_BASE_URL"
        ),
        description="Local llama.cpp (llama-server) OpenAI-compatible base URL",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices(
            "OPENROUTER_BASE_URL", "AUTORESEARCH_OPENROUTER_BASE_URL"
        ),
        description="OpenRouter OpenAI-compatible base URL",
    )
    openrouter_api_key: SecretStr | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices(
            "OPENROUTER_API_KEY", "AUTORESEARCH_OPENROUTER_API_KEY"
        ),
        description="OpenRouter API key",
    )

    # --- Workspace ---
    demo_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("AUTORESEARCH_DEMO", "DEMO_MODE"),
        description=(
            "Demo mode: route all LLM calls to the zero-credential "
            "MockProvider. Never enable in production (refused by router)."
        ),
    )
    skill_generator_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "AUTORESEARCH_SKILL_GENERATOR_ENABLED", "SKILL_GENERATOR_ENABLED",
        ),
        description=(
            "Skill SDK: expose POST /skills/generate (LLM-drafted skill "
            "packages). Operator opt-in — generation spends real tokens and "
            "writes validated-but-untrusted drafts into skills/_drafts/."
        ),
    )
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
    # Per-call token budgets (cost control at the provider boundary).
    max_output_tokens_per_call: int = Field(
        default=8192,
        ge=128,
        validation_alias=AliasChoices(
            "AUTORESEARCH_MAX_OUTPUT_TOKENS_PER_CALL",
            "MAX_OUTPUT_TOKENS_PER_CALL",
        ),
        description=(
            "Hard cap on max_tokens per LLM call (clamped at the historical "
            "8192 ceiling regardless of how high this is set)."
        ),
    )
    max_input_tokens_per_call: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices(
            "AUTORESEARCH_MAX_INPUT_TOKENS_PER_CALL",
            "MAX_INPUT_TOKENS_PER_CALL",
        ),
        description=(
            "0 = uncapped. When >0, a turn whose previous call consumed more "
            "input tokens than this forces hardest context compaction before "
            "the next call (keeps per-call spend bounded on long sessions)."
        ),
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
    work_lease_seconds: float = Field(
        default=300.0,
        validation_alias=AliasChoices(
            "AUTORESEARCH_WORK_LEASE_SECONDS",
            "WORK_LEASE_SECONDS",
        ),
    )
    authorized_spend_cap_usd: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices(
            "AUTORESEARCH_AUTHORIZED_SPEND_CAP_USD",
            "AUTHORIZED_SPEND_CAP_USD",
        ),
    )

    # --- API Robustness ---
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
    global_stagnation_window: int = Field(
        default=12,
        ge=1,
        validation_alias=AliasChoices(
            "AUTORESEARCH_GLOBAL_STAGNATION_WINDOW",
            "GLOBAL_STAGNATION_WINDOW",
        ),
        description=(
            "Number of consecutive iterations with no metric improvement "
            "that triggers a GLOBAL_STAGNATION nudge demanding TERMINATE_REQUEST."
        ),
    )
    global_stagnation_epsilon: float = Field(
        default=1e-4,
        ge=0.0,
        validation_alias=AliasChoices(
            "AUTORESEARCH_GLOBAL_STAGNATION_EPSILON",
            "GLOBAL_STAGNATION_EPSILON",
        ),
        description=(
            "Minimum metric improvement above the session best required to "
            "reset the stagnation window. Improvements <= epsilon are treated as "
            "stagnant."
        ),
    )
    stagnation_exempt_phases: List[str] = Field(
        default=[
            "baseline_capture",
            "robustness",
            "promotion_proposal",
        ],
        validation_alias=AliasChoices(
            "AUTORESEARCH_STAGNATION_EXEMPT_PHASES",
            "STAGNATION_EXEMPT_PHASES",
        ),
        description=(
            "Phases where metric stagnation is expected (validation/evidence "
            "work, not hyperparameter tuning). The global stagnation guard is "
            "suppressed when the session is in one of these phases."
        ),
    )
    iteration_context_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "AUTORESEARCH_ITERATION_CONTEXT_ENABLED",
            "ITERATION_CONTEXT_ENABLED",
        ),
        description="Inject a compact persisted-iteration digest after recorded attempts.",
    )
    iteration_context_max_chars: int = Field(
        default=6000,
        ge=500,
        validation_alias=AliasChoices(
            "AUTORESEARCH_ITERATION_CONTEXT_MAX_CHARS",
            "ITERATION_CONTEXT_MAX_CHARS",
        ),
        description="Maximum characters in the injected iteration context digest.",
    )
    iteration_context_recent_attempts: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices(
            "AUTORESEARCH_ITERATION_CONTEXT_RECENT_ATTEMPTS",
            "ITERATION_CONTEXT_RECENT_ATTEMPTS",
        ),
        description="Number of recent attempts summarized in iteration context.",
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
            "Default is True so wasted compute on already-explored points is "
            "the opt-out, not the opt-in."
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

    # --- Optional MLflow tracking (generic; empty = disabled) ---
    mlflow_tracking_uri: str = Field(
        default="",
        description=(
            "MLflow tracking server URI (e.g. http://mlflow:5000). "
            "Empty disables MLflow integration."
        ),
    )
    mlflow_external_url: str = Field(
        default="",
        description="Browser-accessible MLflow URL for deep-linking from UI",
    )

    production_approval_verifier: SecretStr | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices(
            "AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER",
            "PRODUCTION_APPROVAL_VERIFIER",
        ),
        description=(
            "HMAC-SHA256 secret used to verify the signature on production-scope "
            "promotion approvals. When unset, all production promotions are "
            "rejected (fail-closed). The approval.signature must be the hex "
            "HMAC-SHA256 of the canonical approval message (hmac-sha256-v2) "
            "keyed by this secret."
        ),
    )
    result_receipt_key: SecretStr | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices(
            "AUTORESEARCH_RESULT_RECEIPT_KEY",
            "RESULT_RECEIPT_KEY",
        ),
        description=(
            "Server-only HMAC-SHA256 key for authenticated result receipts "
            "when evaluator results cross a trust boundary. Never delivered "
            "to candidates or evaluators. When unset, receipts use "
            "deterministic digest ids (tamper-evident and idempotent within "
            "the server's own records)."
        ),
    )
    execution_isolation_mode: Literal["enforced", "trusted_local_code"] = Field(
        default="enforced",
        validation_alias=AliasChoices(
            "AUTORESEARCH_EXECUTION_ISOLATION_MODE",
            "EXECUTION_ISOLATION_MODE",
        ),
        description=(
            "Execution boundary policy for candidate-controlled subprocesses "
            "(skill plugins and governed commands). 'enforced' (default) runs "
            "them in the isolation backend with filesystem/network caps "
            "enforced at the OS boundary and refuses unenforceable capability "
            "requests or unavailable isolation (fail-closed). "
            "'trusted_local_code' is the operator's explicitly retained "
            "local-code policy: subprocesses run unsandboxed, separately "
            "labeled, and are never advertised as sandboxed."
        ),
    )
    execution_max_processes: int = Field(
        default=512,
        ge=1,
        validation_alias=AliasChoices(
            "AUTORESEARCH_EXECUTION_MAX_PROCESSES",
            "EXECUTION_MAX_PROCESSES",
        ),
        description=(
            "Maximum live processes in one candidate-controlled process tree. "
            "Breaches terminate the tree immediately (resource guard)."
        ),
    )
    execution_max_output_bytes: int = Field(
        default=4_194_304,
        ge=1024,
        validation_alias=AliasChoices(
            "AUTORESEARCH_EXECUTION_MAX_OUTPUT_BYTES",
            "EXECUTION_MAX_OUTPUT_BYTES",
        ),
        description=(
            "Maximum total stdout+stderr bytes one candidate-controlled run "
            "may deliver before the tree is terminated; capture itself stays "
            "bounded regardless."
        ),
    )
    execution_max_file_write_bytes: int = Field(
        default=2_147_483_648,
        ge=1024,
        validation_alias=AliasChoices(
            "AUTORESEARCH_EXECUTION_MAX_FILE_WRITE_BYTES",
            "EXECUTION_MAX_FILE_WRITE_BYTES",
        ),
        description=(
            "Kernel per-file write quota (RLIMIT_FSIZE) for candidate-controlled "
            "subprocesses. When set and prlimit is unavailable the capability is "
            "rejected rather than run unbounded."
        ),
    )
    command_max_rss_mb: int = Field(
        default=4096,
        ge=64,
        validation_alias=AliasChoices(
            "AUTORESEARCH_COMMAND_MAX_RSS_MB",
            "COMMAND_MAX_RSS_MB",
        ),
        description=(
            "Process-tree RSS cap in MB for governed evaluator commands "
            "(plugin runs use their manifest caps)."
        ),
    )
    command_max_cpu_s: float = Field(
        default=3600.0,
        gt=0,
        validation_alias=AliasChoices(
            "AUTORESEARCH_COMMAND_MAX_CPU_S",
            "COMMAND_MAX_CPU_S",
        ),
        description=(
            "Cumulative CPU cap in seconds for governed evaluator commands "
            "(plugin runs use their manifest caps)."
        ),
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

    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AUTORESEARCH_DATABASE_URL",
            "DATABASE_URL",
        ),
        description=(
            "Optional Postgres DSN enabling the PostgresStateStore backend. "
            "When unset (or when the DSN is a sqlite URL), the service uses "
            "SQLiteStateStore and the WEB_CONCURRENCY>1 guard stays active. "
            "Set to a postgresql:// (or postgresql+asyncpg://) DSN to enable "
            "horizontal scaling."
        ),
    )

    @property
    def skills_dir(self) -> str:
        return f"{self.workspace_root}/.github/skills"

    @property
    def configs_dir(self) -> str:
        return f"{self.workspace_root}/configs"

    @property
    def runs_dir(self) -> str:
        return f"{self.workspace_root}/runs/autotuner"

    @property
    def venv_python(self) -> str:
        return f"{self.workspace_root}/.venv/bin/python"



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached service settings instance."""

    settings = Settings()  # type: ignore[call-arg]
    logger.info("Settings loaded for %s", settings.service_name)
    return settings


settings = get_settings()
