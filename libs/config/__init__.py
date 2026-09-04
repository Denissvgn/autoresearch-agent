"""
TRAID Platform - Shared Configuration Library

This package provides standardized configuration classes and utilities for all TRAID services.

Key Components:
- BaseServiceSettings: Standard configuration base class
- Vault integration for secure secret management
- Environment and logging configuration
- Utility functions for config validation and masking
"""

from .base import BaseServiceSettings, Environment, LogLevel, VaultSettingsSource
from .exceptions import ConfigurationError, VaultConfigurationError
from .ml_training_config import BaseMLTrainingConfig, MLTrainingVaultManager, SecurityMaskingUtils
from .utils import sanitize_config_dict
from .vault import (
    VaultClientManager,
    VaultConfig,
    check_vault_status,
    get_vault_health,
    get_vault_manager,
)

__all__ = [
    "BaseServiceSettings",
    "BaseMLTrainingConfig",
    "Environment", 
    "LogLevel",
    "VaultClientManager",
    "VaultConfig",
    "VaultSettingsSource",
    "get_vault_manager",
    "get_vault_health",
    "check_vault_status",
    "sanitize_config_dict",
    "ConfigurationError",
    "VaultConfigurationError",
    "MLTrainingVaultManager",
    "SecurityMaskingUtils",
]