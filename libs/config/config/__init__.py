"""
Configuration library for TRAID Platform.

This package provides shared utilities for loading configuration from HashiCorp Vault
with graceful fallback to environment variables and .env files.

The library includes:
- BaseServiceSettings: Standardized service configuration with Vault integration
- Vault helpers: Client management, secret retrieval, health monitoring
- Configuration utilities: Secret masking, validation, environment handling
"""

from importlib import import_module
from pathlib import Path
from typing import Any

# Import new Task 5 modules from parent directory
import sys

from .ml_training_config import (
    BaseMLTrainingConfig,
    MLflowConfig,
    MLTrainingVaultManager,
    ResourceConfig,
)
from .vault_loader import get_vault_status, load_config, reload_vault_client

# Add parent directory to path to import new modules
config_lib_root = Path(__file__).parent.parent
if str(config_lib_root) not in sys.path:
    sys.path.insert(0, str(config_lib_root))

_TASK5_EXPORTS = {
    "BaseServiceSettings": ("libs.config.base", "BaseServiceSettings"),
    "Environment": ("libs.config.base", "Environment"),
    "LogLevel": ("libs.config.base", "LogLevel"),
    "ConfigurationError": ("libs.config.exceptions", "ConfigurationError"),
    "EnvironmentError": ("libs.config.exceptions", "EnvironmentError"),
    "SecretMaskingError": ("libs.config.exceptions", "SecretMaskingError"),
    "ValidationError": ("libs.config.exceptions", "ValidationError"),
    "VaultConfigurationError": ("libs.config.exceptions", "VaultConfigurationError"),
    "VaultAuthenticationError": ("libs.config.vault", "VaultAuthenticationError"),
    "VaultClientManager": ("libs.config.vault", "VaultClientManager"),
    "VaultConfig": ("libs.config.vault", "VaultConfig"),
    "VaultConnectionError": ("libs.config.vault", "VaultConnectionError"),
    "VaultException": ("libs.config.vault", "VaultException"),
    "VaultHealthStatus": ("libs.config.vault", "VaultHealthStatus"),
    "VaultSecretNotFoundError": ("libs.config.vault", "VaultSecretNotFoundError"),
    "check_vault_status": ("libs.config.vault", "check_vault_status"),
    "get_secret": ("libs.config.vault", "get_secret"),
    "get_vault_health": ("libs.config.vault", "get_vault_health"),
    "get_vault_manager": ("libs.config.vault", "get_vault_manager"),
    "put_secret": ("libs.config.vault", "put_secret"),
    "apply_env_overrides": ("libs.config.utils", "apply_env_overrides"),
    "convert_env_value": ("libs.config.utils", "convert_env_value"),
    "create_config_validator": ("libs.config.utils", "create_config_validator"),
    "get_config_file_paths": ("libs.config.utils", "get_config_file_paths"),
    "get_environment_prefix": ("libs.config.utils", "get_environment_prefix"),
    "is_sensitive_key": ("libs.config.utils", "is_sensitive_key"),
    "load_env_file": ("libs.config.utils", "load_env_file"),
    "mask_sensitive_value": ("libs.config.utils", "mask_sensitive_value"),
    "merge_configs": ("libs.config.utils", "merge_configs"),
    "normalize_service_name": ("libs.config.utils", "normalize_service_name"),
    "sanitize_config_dict": ("libs.config.utils", "sanitize_config_dict"),
    "validate_required_config": ("libs.config.utils", "validate_required_config"),
}

_task5_loaded = False


def _load_task5_exports() -> None:
    """Lazily import Task 5 exports to avoid circular imports."""
    global _task5_loaded
    if _task5_loaded:
        return

    for name, (module_path, attr) in _TASK5_EXPORTS.items():
        try:
            module = import_module(module_path)
            globals()[name] = getattr(module, attr)
        except Exception:
            # If any import fails, leave the symbol undefined to mirror previous best-effort behavior.
            continue

    _task5_loaded = True

__version__ = "0.2.0"  # Bumped for Task 5 additions

__all__ = [
    # Base exports (always available)
    "load_config",
    "reload_vault_client", 
    "get_vault_status",
    "BaseMLTrainingConfig",
    "MLflowConfig",
    "ResourceConfig",
    "MLTrainingVaultManager",
]

__all__.extend(_TASK5_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _TASK5_EXPORTS:
        _load_task5_exports()
        if name in globals():
            return globals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")