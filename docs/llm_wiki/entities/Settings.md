# Settings

**Location:** `src/config.py:77`
**Bases:** `BaseSettings`
**Module:** [config](../modules/config.md)

## Description

Application settings loaded from environment variables.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `service_name` | `str` | `Field(...)` | — |
| `host` | `str` | `Field(...)` | — |
| `port` | `int` | `Field(...)` | — |
| `environment` | `str` | `Field(...)` | — |
| `log_level` | `str` | `Field(...)` | — |
| `api_v1_prefix` | `str` | `Field(...)` | — |
| `autoresearch_api_token` | `SecretStr | None` | `Field(...)` | — |
| `autoresearch_prometheus_token` | `SecretStr | None` | `Field(...)` | — |
| `identity_service_url` | `str` | `Field(...)` | — |
| `identity_introspection_timeout_s` | `float` | `Field(...)` | — |
| `anthropic_base_url` | `str` | `Field(...)` | — |
| `anthropic_auth_token` | `SecretStr` | `Field(...)` | — |
| `anthropic_model` | `str` | `Field(...)` | — |
| `anthropic_default_haiku_model` | `str` | `Field(...)` | — |
| `anthropic_default_sonnet_model` | `str` | `Field(...)` | — |
| `anthropic_default_opus_model` | `str` | `Field(...)` | — |
| `workspace_root` | `str` | `Field(...)` | — |
| `host_configs_path` | `str` | `Field(...)` | — |
| `max_iterations` | `int` | `Field(...)` | — |
| `max_budget_usd` | `float` | `Field(...)` | — |
| `experiment_timeout_s` | `int` | `Field(...)` | — |
| `default_quick_mode` | `bool` | `Field(...)` | — |
| `max_concurrent_sessions` | `int` | `Field(...)` | — |
| `anthropic_api_timeout_s` | `int` | `Field(...)` | — |
| `max_api_retries` | `int` | `Field(...)` | — |
| `context_compaction_threshold` | `int` | `Field(...)` | — |
| `iteration_context_enabled` | `bool` | `Field(...)` | — |
| `iteration_context_max_chars` | `int` | `Field(...)` | — |
| `iteration_context_recent_attempts` | `int` | `Field(...)` | — |
| `autoresearch_cross_session_duplicate_check` | `bool` | `Field(...)` | — |
| `ws_max_clients` | `int` | `Field(...)` | — |
| `mlflow_tracking_uri` | `str` | `Field(...)` | — |
| `mlflow_service_url` | `str` | `Field(...)` | — |
| `mlflow_external_url` | `str` | `Field(...)` | — |
| `data_ingest_url` | `str` | `Field(...)` | — |
| `ensemble_trainer_url` | `str` | `Field(...)` | — |
| `rl_trainer_url` | `str` | `Field(...)` | — |
| `feature_service_url` | `str` | `Field(...)` | — |
| `inference_service_url` | `str` | `Field(...)` | — |
| `nats_url` | `Optional[str]` | `Field(...)` | — |
| `inference_replay_sample_path` | `Optional[str]` | `Field(...)` | — |
| `rl_trainer_service_token` | `SecretStr | None` | `Field(...)` | — |
| `vdmc_indicator_url` | `str` | `Field(...)` | — |
| `admin_service_url` | `str` | `Field(...)` | — |
| `promotion_service_url` | `str` | `Field(...)` | — |
| `mlflow_service_auth_token` | `SecretStr | None` | `Field(...)` | — |
| `s3_endpoint_url` | `Optional[str]` | `Field(...)` | — |
| `mlflow_s3_endpoint_url` | `Optional[str]` | `Field(...)` | — |
| `preflight_enabled` | `bool` | `Field(...)` | — |
| `allow_unready_services` | `bool` | `Field(...)` | — |
| `preflight_timeout_s` | `float` | `Field(...)` | — |
| `artifact_logging_required` | `bool` | `Field(...)` | — |
| `cors_origins_raw` | `str` | `Field(...)` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `settings_customise_sources` | `(settings_cls: type[BaseSettings], init_settings: Any, env_settings: Any, dotenv_settings: Any, file_secret_settings: Any) -> tuple[Any, Ellipsis]` | `@classmethod` | Use Vault as defaults below explicit init args, env vars, and .env. |
| `cors_origins` | `() -> List[str]` | `@property` | — |
| `db_path` | `() -> str` | `@property` | — |
| `skills_dir` | `() -> str` | `@property` | — |
| `autotuner_scripts_dir` | `() -> str` | `@property` | — |
| `configs_dir` | `() -> str` | `@property` | — |
| `runs_dir` | `() -> str` | `@property` | — |
| `venv_python` | `() -> str` | `@property` | — |
| `artifact_store_endpoint_url` | `() -> Optional[str]` | `@property` | — |

## Relationships

- **imported_by**: [test_api_auth](../modules/test_api_auth.md)
