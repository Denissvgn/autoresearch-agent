from __future__ import annotations

import json
import os
from typing import Any, Mapping, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, ConfigDict

from .errors import ConfigurationError
from libs.config.parsing import parse_bool


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    json_mode: bool = Field(default=False, alias="json")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("level")
    @classmethod
    def _normalize_level(cls, v: str) -> str:
        upper = (v or "INFO").upper()
        if upper == "WARN":
            upper = "WARNING"
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if upper not in allowed:
            raise ConfigurationError(f"Invalid log level: {v}")
        return upper

    @property
    def json(self) -> bool:  # backward compatibility accessor
        return self.json_mode


class IORegistryConfig(BaseModel):
    backend: str = Field(default="filesystem")  # filesystem | s3 | mlflow
    root: Optional[str] = Field(default=None)
    bucket: Optional[str] = Field(default=None)
    prefix: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    endpoint_url: Optional[str] = Field(default=None)


class ObservabilityConfig(BaseModel):
    metrics_enabled: bool = Field(default=False)
    events_enabled: bool = Field(default=False)
    service_name: str = Field(default="traid-training-sdk")


class FeatureFlagsConfig(BaseModel):
    enabled: bool = Field(default=False)
    namespace: Optional[str] = Field(default=None)


class SecretsConfig(BaseModel):
    provider: str = Field(default="env")  # env | vault
    env_prefix: Optional[str] = Field(default=None)
    vault_addr: Optional[str] = Field(default=None)
    vault_mount: str = Field(default="secret")
    vault_namespace: Optional[str] = Field(default=None)
    vault_token_env: str = Field(default="VAULT_TOKEN")


class SdkConfig(BaseModel):
    profile: str = Field(default="default")
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    seed: Optional[int] = Field(default=None)
    io_registry: IORegistryConfig = Field(default_factory=IORegistryConfig)
    io_runs_root: str = Field(default="runs")
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    feature_flags: FeatureFlagsConfig = Field(default_factory=FeatureFlagsConfig)
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)
    
    # Sprint 4: CLI-related configuration fields
    direction_backend: Optional[str] = Field(default=None)
    rl_auto_data: Optional[bool] = Field(default=None)
    include: Optional[str] = Field(default=None)
    enable_quantization: Optional[bool] = Field(default=None)


def load_default_config(*, profile: Optional[str] = None) -> SdkConfig:
    base = SdkConfig()
    if profile:
        base = base.model_copy(update={"profile": profile})
    return base


def from_file(path: str) -> SdkConfig:
    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.endswith(".json"):
                raw: dict[str, Any] = json.load(f)
            elif path.endswith(".yaml") or path.endswith(".yml"):
                try:
                    import yaml  # type: ignore
                except Exception as exc:  # pragma: no cover - import guard
                    raise ConfigurationError(
                        "YAML config provided but PyYAML is not installed"
                    ) from exc
                raw = yaml.safe_load(f) or {}
            else:
                # Try JSON as a safe default
                raw = json.load(f)
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in config file: {path}") from exc

    try:
        return SdkConfig.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - exercised in tests
        raise ConfigurationError(str(exc)) from exc


def _parse_bool(val: Optional[str]) -> Optional[bool]:
    if val is None:
        return None
    normalized = val.strip().lower()
    if normalized in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        return parse_bool(normalized)
    return None


def from_env(prefix: str = "TRAID_SDK_", env: Optional[Mapping[str, str]] = None) -> SdkConfig:
    e = dict(env or os.environ)

    def g(key: str) -> Optional[str]:
        return e.get(prefix + key)

    logging_level = g("LOG_LEVEL")
    logging_json = _parse_bool(g("LOG_JSON"))
    profile = g("PROFILE")
    seed_raw = g("SEED") or e.get("TRAID_SDK_SEED")
    seed = int(seed_raw) if seed_raw and seed_raw.isdigit() else None
    reg_backend = g("REGISTRY_BACKEND")
    reg_root = g("REGISTRY_ROOT")
    reg_bucket = g("REGISTRY_BUCKET")
    reg_prefix = g("REGISTRY_PREFIX")
    reg_region = g("REGISTRY_REGION")
    reg_endpoint = g("REGISTRY_ENDPOINT")
    runs_root = g("RUNS_ROOT")
    metrics_enabled = _parse_bool(g("OBSERVABILITY_METRICS_ENABLED"))
    events_enabled = _parse_bool(g("OBSERVABILITY_EVENTS_ENABLED"))
    service_name = g("OBSERVABILITY_SERVICE_NAME")
    ff_enabled = _parse_bool(g("FEATURE_FLAGS_ENABLED"))
    ff_namespace = g("FEATURE_FLAGS_NAMESPACE")
    secrets_provider = g("SECRETS_PROVIDER")
    secrets_env_prefix = g("SECRETS_ENV_PREFIX")
    vault_addr = g("VAULT_ADDR")
    vault_mount = g("VAULT_MOUNT")
    vault_namespace = g("VAULT_NAMESPACE")
    vault_token_env = g("VAULT_TOKEN_ENV")
    
    # Sprint 4: Add support for new environment variables
    direction_backend = g("DIRECTION_BACKEND")
    rl_auto_data = _parse_bool(g("RL_AUTO_DATA"))
    include = g("INCLUDE")
    enable_quantization = _parse_bool(g("ENABLE_QUANTIZATION"))

    data: dict[str, Any] = {}
    if profile:
        data["profile"] = profile
    if seed is not None:
        data["seed"] = seed
    if logging_level or logging_json is not None:
        data["logging"] = {}
        if logging_level:
            data["logging"]["level"] = logging_level
        if logging_json is not None:
            data["logging"]["json"] = logging_json
    if reg_backend or reg_root or reg_bucket or reg_prefix or reg_region or reg_endpoint:
        data["io_registry"] = {}
        if reg_backend:
            data["io_registry"]["backend"] = reg_backend
        if reg_root:
            data["io_registry"]["root"] = reg_root
        if reg_bucket:
            data["io_registry"]["bucket"] = reg_bucket
        if reg_prefix:
            data["io_registry"]["prefix"] = reg_prefix
        if reg_region:
            data["io_registry"]["region"] = reg_region
        if reg_endpoint:
            data["io_registry"]["endpoint_url"] = reg_endpoint
    if runs_root:
        data["io_runs_root"] = runs_root
    if metrics_enabled is not None or events_enabled is not None or service_name:
        data["observability"] = {}
        if metrics_enabled is not None:
            data["observability"]["metrics_enabled"] = metrics_enabled
        if events_enabled is not None:
            data["observability"]["events_enabled"] = events_enabled
        if service_name:
            data["observability"]["service_name"] = service_name
    if ff_enabled is not None or ff_namespace:
        data["feature_flags"] = {}
        if ff_enabled is not None:
            data["feature_flags"]["enabled"] = ff_enabled
        if ff_namespace:
            data["feature_flags"]["namespace"] = ff_namespace
    if secrets_provider or secrets_env_prefix or vault_addr or vault_mount or vault_namespace or vault_token_env:
        data["secrets"] = {"provider": secrets_provider or "env"}
        if secrets_env_prefix:
            data["secrets"]["env_prefix"] = secrets_env_prefix
        if vault_addr:
            data["secrets"]["vault_addr"] = vault_addr
        if vault_mount:
            data["secrets"]["vault_mount"] = vault_mount
        if vault_namespace:
            data["secrets"]["vault_namespace"] = vault_namespace
        if vault_token_env:
            data["secrets"]["vault_token_env"] = vault_token_env
    
    # Sprint 4: Add support for CLI-related environment variables
    if direction_backend:
        data["direction_backend"] = direction_backend
    if rl_auto_data is not None:
        data["rl_auto_data"] = rl_auto_data
    if include:
        data["include"] = include
    if enable_quantization is not None:
        data["enable_quantization"] = enable_quantization

    try:
        return SdkConfig.model_validate(data)
    except ValidationError as exc:  # pragma: no cover
        raise ConfigurationError(str(exc)) from exc


def merge(base: SdkConfig, override: SdkConfig) -> SdkConfig:
    """Deep-merge two configs where override wins for non-null/non-empty fields."""
    base_d = base.model_dump()
    over_d = override.model_dump(exclude_unset=True)

    def deep_update(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                a[k] = deep_update(a[k], v)
            elif v is not None:
                a[k] = v
        return a

    merged = deep_update(base_d, over_d)
    return SdkConfig.model_validate(merged)
