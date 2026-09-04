"""
Shared configuration management library for TRAID Platform services.

This module provides BaseServiceSettings that standardizes configuration management
across all services using pydantic-settings with Vault integration.

Key Features:
- Common service configuration fields
- Vault integration with fallback to environment variables
- Secret masking for security
- Configuration validation
- Environment variable precedence

Resolution order (first wins in pydantic-settings v2):
    init_settings  >  env_settings  >  vault_settings  >  dotenv_settings  >  field defaults
"""

from enum import Enum
from importlib import import_module
import logging
import os
from types import ModuleType
from typing import Any, Callable

from pydantic import Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_vault_import_errors: list[str] = []
_vault_loader_module: ModuleType | None = None


def _import_vault_loader() -> ModuleType | None:
    """Lazily import the vault loader to avoid circular imports during module init."""
    global _vault_loader_module
    if _vault_loader_module is not None:
        return _vault_loader_module

    for _module_path in (
        "libs.config.config.vault_loader",
        "config.config.vault_loader",
        "config.vault_loader",
    ):
        try:
            _vault_loader_module = import_module(_module_path)
            break
        except ImportError as exc:  # pragma: no cover - defensive path resolution
            _vault_import_errors.append(f"{_module_path}: {exc}")
            continue

    return _vault_loader_module


def _get_loader_attr(name: str) -> Callable[..., Any] | None:
    module = _import_vault_loader()
    if module is None:
        return None
    return getattr(module, name, None)  # type: ignore[no-any-return]


def load_vault_only(prefix: str, env: str | None = None) -> dict[str, Any]:
    """Load vault-only config (no env vars) for pydantic-settings source."""
    loader = _get_loader_attr("load_vault_only")
    if callable(loader):
        return loader(prefix, env)
    return {}


def load_config(prefix: str, env: str | None = None) -> dict[str, Any]:  # type: ignore[override]
    loader = _get_loader_attr("load_config")
    if callable(loader):
        return loader(prefix, env)
    return {}


def get_vault_status() -> dict[str, Any]:  # type: ignore[override]
    status_fn = _get_loader_attr("get_vault_status")
    if callable(status_fn):
        return status_fn()
    return {
        "vault_enabled": False,
        "vault_connected": False,
        "error": "Vault configuration library unavailable",
    }


VAULT_AVAILABLE = _import_vault_loader() is not None

_check_vault_status: Callable[[], Any] | None = None
if VAULT_AVAILABLE:
    for _module_path in (
        "config.vault",
        "libs.config.vault",
    ):
        try:
            _check_vault_status = getattr(import_module(_module_path), "check_vault_status")  # type: ignore[misc]
            break
        except ImportError as exc:  # pragma: no cover - defensive path resolution
            _vault_import_errors.append(f"{_module_path}: {exc}")

if _check_vault_status is not None:
    check_vault_status = _check_vault_status  # type: ignore[assignment]
else:

    async def check_vault_status() -> dict[str, Any]:  # type: ignore[override]
        return {
            "vault_available": False,
            "vault_enabled": False,
            "vault_connected": False,
            "error": "Vault status check unavailable",
        }

    if VAULT_AVAILABLE:
        # Loader available but status helper missing; treat as degraded support
        VAULT_AVAILABLE = False

if not VAULT_AVAILABLE:
    _log_kwargs: dict[str, Any] = {}
    if _vault_import_errors:
        _log_kwargs["extra"] = {"vault_import_errors": _vault_import_errors}
    logger.warning(
        "Vault configuration unavailable, falling back to environment variables only",
        **_log_kwargs,
    )



class LogLevel(str, Enum):
    """Log level enumeration."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(str, Enum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


# ---------------------------------------------------------------------------
# Vault-backed settings source for pydantic-settings v2
# ---------------------------------------------------------------------------

class VaultSettingsSource:
    """
    A pydantic-settings source that loads values from Vault.

    It merges all ``secret/config/global/*`` sub-paths and the service-specific
    path ``secret/config/<service_name>/<environment>`` into a single dict.
    The dict is returned with **lowercase** keys so that pydantic can match
    them to model field names.

    If Vault is unreachable or disabled, this source silently returns an
    empty dict so that env-var / dotenv / field-default fallbacks still work.
    """

    def __init__(self, settings_cls: type["BaseServiceSettings"]) -> None:
        self._settings_cls = settings_cls

    def __call__(self) -> dict[str, Any]:
        """Return a dict of configuration values loaded from Vault."""
        if not VAULT_AVAILABLE:
            return {}

        # Determine service name and environment from env vars (before
        # pydantic has finished construction) so we can query the right
        # vault path.
        service_name = os.getenv(
            "SERVICE_NAME",
            getattr(self._settings_cls, "__vault_service_name__", "unknown-service"),
        )
        # Also check the model's field default.
        for field_name in ("service_name",):
            field_obj = self._settings_cls.model_fields.get(field_name)
            if field_obj and field_obj.default and field_obj.default != "unknown-service":
                service_name = field_obj.default
                break

        env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development"))

        try:
            config = load_vault_only(service_name, env)
        except Exception as exc:
            logger.debug("VaultSettingsSource: load_vault_only failed: %s", exc)
            return {}

        # Already lowercase from load_vault_only
        return config

    def __repr__(self) -> str:
        return "VaultSettingsSource()"


class BaseServiceSettings(BaseSettings):
    """
    Base settings class with common configuration fields for all TRAID Platform services.
    
    This class provides:
    - Common service configuration fields
    - Vault integration with environment variable fallbacks
    - Secret masking for sensitive data
    - Configuration validation
    - Standardized configuration patterns
    
    Usage:
        class MyServiceSettings(BaseServiceSettings):
            service_name: str = "my-service"
            my_specific_setting: str = "default_value"
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
        # Allow field aliases for backward compatibility
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
        """
        Insert VaultSettingsSource between env vars and dotenv so that:

            init_settings  >  env_settings  >  **vault**  >  dotenv  >  defaults

        Env vars always win; Vault overrides dotenv & field defaults.
        """
        return (
            init_settings,
            env_settings,
            VaultSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
    
    # Core service identification
    service_name: str = Field(
        default="unknown-service",
        description="Name of the service for identification and logging"
    )
    
    version: str = Field(
        default="1.0.0",
        description="Service version for deployment tracking"
    )
    
    # Environment and deployment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment (development, staging, production, test)"
    )
    
    # Network configuration
    host: str = Field(
        default="0.0.0.0",
        description="Host interface to bind the service"
    )
    
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port number for the service"
    )
    
    # Logging configuration
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level for the service"
    )
    
    log_path: str = Field(
        default="/app/logs",
        description="Directory path for log files"
    )
    
    # Redis configuration (common across many services)
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for caching and session storage"
    )
    
    redis_password: SecretStr | None = Field(
        default=None,
        description="Redis password for authenticated connections"
    )
    
    # Database configuration (common pattern)
    database_url: str | None = Field(
        default=None,
        description="Database connection URL"
    )
    
    # Vault configuration
    vault_enabled: bool = Field(
        default=True,
        description="Enable Vault configuration loading"
    )
    
    vault_url: str | None = Field(
        default=None,
        description="Vault server URL"
    )
    
    vault_token: SecretStr | None = Field(
        default=None,
        description="Vault authentication token"
    )
    
    vault_mount_path: str = Field(
        default="secret",
        description="Vault mount path for secrets"
    )
    
    vault_role: str | None = Field(
        default=None,
        description="Vault role for AppRole authentication"
    )
    
    # API configuration
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="API version 1 prefix path"
    )
    
    enable_docs: bool = Field(
        default=True,
        description="Enable FastAPI documentation endpoints"
    )
    
    # CORS configuration
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated list of allowed CORS origins"
    )
    
    cors_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests"
    )
    
    # Monitoring and observability
    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection"
    )
    
    metrics_path: str = Field(
        default="/metrics",
        description="Path for Prometheus metrics endpoint"
    )
    
    health_check_path: str = Field(
        default="/health",
        description="Path for health check endpoint"
    )
    
    # Security settings
    request_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="HTTP request timeout in seconds"
    )
    
    max_request_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum request size in megabytes"
    )
    
    # Feature flags
    enable_feature_flags: bool = Field(
        default=False,
        description="Enable feature flag support"
    )
    
    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service name format."""
        if not v or not v.strip():
            raise ValueError("Service name cannot be empty")
        
        # Ensure service name follows naming conventions
        normalized = v.lower().strip()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Service name must contain only alphanumeric characters, hyphens, and underscores")
        
        return normalized
    
    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Validate CORS origins format."""
        if not v:
            return v
            
        # Basic validation - check that each origin looks like a URL
        origins = [origin.strip() for origin in v.split(",")]
        for origin in origins:
            if origin and not (origin.startswith("http://") or origin.startswith("https://") or origin == "*"):
                raise ValueError(f"Invalid CORS origin format: {origin}")
        
        return v
    
    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT
    
    def get_vault_status(self) -> dict[str, Any]:
        """
        Get Vault configuration status for debugging and health checks.
        
        Returns:
            Dictionary with Vault status information
        """
        if not VAULT_AVAILABLE:
            return {
                "vault_available": False,
                "vault_enabled": False,
                "vault_connected": False,
                "error": "Vault library not available"
            }
        
        try:
            # Use existing vault status function if available
            status = get_vault_status()
            return {
                "vault_available": True,
                "vault_enabled": self.vault_enabled,
                "vault_connected": status.get("connected", False),
                "vault_url": self.vault_url,
                "vault_mount_path": self.vault_mount_path,
                "config_keys_loaded": status.get("config_keys", 0)
            }
        except Exception as e:
            return {
                "vault_available": True,
                "vault_enabled": self.vault_enabled,
                "vault_connected": False,
                "error": str(e)
            }
    
    async def get_vault_status_async(self) -> dict[str, Any]:
        """
        Get standardized Vault status using Task 17 implementation.
        
        Returns:
            Dictionary with comprehensive Vault status information using
            the standardized check_vault_status() function.
        """
        if not VAULT_AVAILABLE:
            return {
                "vault_available": False,
                "vault_enabled": False,
                "vault_connected": False,
                "error": "Vault library not available"
            }
        
        try:
            # Use new standardized vault status function
            standardized_status = await check_vault_status()
            
            # Enhance with service-specific configuration details
            return {
                "vault_available": True,
                "vault_enabled": self.vault_enabled,
                "vault_url": self.vault_url,
                "vault_mount_path": self.vault_mount_path,
                "service_name": self.service_name,
                "environment": self.environment.value,
                **standardized_status  # Include all standardized fields
            }
            
        except Exception as e:
            return {
                "vault_available": True,
                "vault_enabled": self.vault_enabled,
                "vault_connected": False,
                "error": str(e)
            }
    
    def get_config_summary(self, mask_secrets: bool = True) -> dict[str, Any]:
        """
        Get a summary of configuration without sensitive data.
        
        Args:
            mask_secrets: Whether to mask sensitive configuration values
            
        Returns:
            Dictionary with configuration summary
        """
        config = {
            "service_name": self.service_name,
            "version": self.version,
            "environment": self.environment.value,
            "log_level": self.log_level.value,
            "vault_enabled": self.vault_enabled,
            "features": {
                "docs_enabled": self.enable_docs,
                "metrics_enabled": self.enable_metrics,
                "feature_flags_enabled": self.enable_feature_flags,
            }
        }
        
        if mask_secrets:
            # Add non-sensitive network info
            config.update({
                "host": self.host,
                "port": self.port,
                "api_prefix": self.api_v1_prefix,
            })
            
            # Mask sensitive fields
            if self.database_url:
                config["database_configured"] = True
            if self.redis_password:
                config["redis_auth_configured"] = True
            if self.vault_token:
                config["vault_token_configured"] = True
        else:
            # Include all non-secret configuration
            config.update(self.model_dump(exclude={"vault_token", "redis_password"}))
        
        return config
    
    def load_from_vault(self, service_path: str | None = None) -> dict[str, Any]:
        """
        Load additional configuration from Vault.
        
        Args:
            service_path: Custom service path for Vault lookup
            
        Returns:
            Configuration dictionary from Vault
        """
        if not VAULT_AVAILABLE or not self.vault_enabled:
            logger.debug("Vault not available or disabled, skipping Vault configuration load")
            return {}
        
        # Use service name for vault path if not specified
        vault_path = service_path or self.service_name
        
        try:
            config = load_config(vault_path, self.environment.value)
            logger.info(f"Loaded {len(config)} configuration keys from Vault path: {vault_path}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load configuration from Vault: {e}")
            return {}