"""
Configuration utilities for the TRAID Platform config library.

This module provides utility functions for:
- Secret masking and sanitization
- Environment variable handling
- Configuration validation helpers
- Common configuration transformations
"""

from collections.abc import Callable
import logging
import os
from pathlib import Path
import re
from typing import Any

logger = logging.getLogger(__name__)


# Patterns for identifying sensitive data
SENSITIVE_PATTERNS = [
    r".*password.*",
    r".*secret.*",
    r".*token.*",
    r".*key.*",
    r".*credential.*",
    r".*auth.*",
    r".*private.*",
    r".*cert.*",
    r".*pem.*",
]

# Compiled regex patterns for performance
SENSITIVE_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS]


def is_sensitive_key(key: str) -> bool:
    """
    Check if a configuration key contains sensitive data.
    
    Args:
        key: Configuration key name
        
    Returns:
        True if the key appears to contain sensitive data
    """
    key_lower = key.lower()
    
    # Check against common sensitive patterns
    for pattern in SENSITIVE_REGEX:
        if pattern.match(key_lower):
            return True
    
    return False


def mask_sensitive_value(value: Any, mask_char: str = "*", show_chars: int = 4) -> str:
    """
    Mask a sensitive value for logging/display.
    
    Args:
        value: Value to mask
        mask_char: Character to use for masking
        show_chars: Number of characters to show at the end
        
    Returns:
        Masked string representation
    """
    if value is None:
        return "None"
    
    str_value = str(value)
    
    if len(str_value) <= show_chars:
        # If value is too short, mask completely
        return mask_char * len(str_value)
    
    # Show last few characters
    masked_part = mask_char * (len(str_value) - show_chars)
    visible_part = str_value[-show_chars:]
    
    return f"{masked_part}{visible_part}"


def sanitize_config_dict(
    config: dict[str, Any], 
    mask_secrets: bool = True,
    exclude_keys: list[str] | None = None
) -> dict[str, Any]:
    """
    Sanitize a configuration dictionary for safe logging/display.
    
    Args:
        config: Configuration dictionary to sanitize
        mask_secrets: Whether to mask sensitive values
        exclude_keys: Keys to exclude from output
        
    Returns:
        Sanitized configuration dictionary
    """
    exclude_keys = exclude_keys or []
    sanitized = {}
    
    for key, value in config.items():
        # Skip excluded keys
        if key in exclude_keys:
            continue
        
        # Handle nested dictionaries
        if isinstance(value, dict):
            sanitized[key] = sanitize_config_dict(value, mask_secrets, exclude_keys)
        elif mask_secrets and is_sensitive_key(key):
            # Mask sensitive values
            sanitized[key] = mask_sensitive_value(value)
        else:
            sanitized[key] = value
    
    return sanitized


def get_environment_prefix(service_name: str) -> str:
    """
    Get environment variable prefix for a service.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Environment variable prefix
    """
    # Convert service name to uppercase and replace hyphens with underscores
    return service_name.upper().replace("-", "_") + "_"


def load_env_file(env_file: str | Path, required: bool = False) -> dict[str, str]:
    """
    Load environment variables from a .env file.
    
    Args:
        env_file: Path to .env file
        required: Whether the file is required to exist
        
    Returns:
        Dictionary of environment variables
        
    Raises:
        FileNotFoundError: If required file doesn't exist
    """
    env_file = Path(env_file)
    env_vars = {}
    
    if not env_file.exists():
        if required:
            raise FileNotFoundError(f"Required environment file not found: {env_file}")
        else:
            logger.debug(f"Environment file not found: {env_file}")
            return env_vars
    
    try:
        with open(env_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                
                # Parse KEY=VALUE format
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    env_vars[key] = value
                else:
                    logger.warning(f"Invalid line format in {env_file}:{line_num}: {line}")
        
        logger.debug(f"Loaded {len(env_vars)} environment variables from {env_file}")
        
    except Exception as e:
        logger.error(f"Failed to load environment file {env_file}: {e}")
        if required:
            raise
    
    return env_vars


def apply_env_overrides(
    config: dict[str, Any], 
    service_name: str | None = None,
    prefix: str | None = None
) -> dict[str, Any]:
    """
    Apply environment variable overrides to configuration.
    
    Args:
        config: Base configuration dictionary
        service_name: Service name for auto-prefix generation
        prefix: Custom environment variable prefix
        
    Returns:
        Configuration with environment overrides applied
    """
    if not prefix and service_name:
        prefix = get_environment_prefix(service_name)
    
    updated_config = config.copy()
    
    for key, value in config.items():
        # Generate environment variable name
        if prefix:
            env_key = f"{prefix}{key.upper()}"
        else:
            env_key = key.upper()
        
        # Check for environment override
        env_value = os.getenv(env_key)
        if env_value is not None:
            # Convert environment string to appropriate type
            converted_value = convert_env_value(env_value, type(value))
            updated_config[key] = converted_value
            logger.debug(f"Applied environment override: {env_key} -> {mask_sensitive_value(converted_value) if is_sensitive_key(key) else converted_value}")
    
    return updated_config


def convert_env_value(env_value: str, target_type: type) -> Any:
    """
    Convert environment variable string to target type.
    
    Args:
        env_value: Environment variable value as string
        target_type: Target type for conversion
        
    Returns:
        Converted value
    """
    if target_type == bool:
        return env_value.lower() in ("true", "1", "yes", "on")
    elif target_type == int:
        try:
            return int(env_value)
        except ValueError:
            logger.warning(f"Failed to convert '{env_value}' to int, using 0")
            return 0
    elif target_type == float:
        try:
            return float(env_value)
        except ValueError:
            logger.warning(f"Failed to convert '{env_value}' to float, using 0.0")
            return 0.0
    elif target_type == list:
        # Handle comma-separated lists
        return [item.strip() for item in env_value.split(",") if item.strip()]
    else:
        return env_value


def validate_required_config(
    config: dict[str, Any], 
    required_keys: list[str],
    config_name: str = "configuration"
) -> None:
    """
    Validate that required configuration keys are present and not empty.
    
    Args:
        config: Configuration dictionary to validate
        required_keys: List of required keys
        config_name: Name of configuration for error messages
        
    Raises:
        ValueError: If required keys are missing or empty
    """
    missing_keys = []
    empty_keys = []
    
    for key in required_keys:
        if key not in config:
            missing_keys.append(key)
        elif not config[key] or (isinstance(config[key], str) and not config[key].strip()):
            empty_keys.append(key)
    
    errors = []
    if missing_keys:
        errors.append(f"Missing required keys: {', '.join(missing_keys)}")
    if empty_keys:
        errors.append(f"Empty required keys: {', '.join(empty_keys)}")
    
    if errors:
        raise ValueError(f"{config_name} validation failed: {'; '.join(errors)}")


def normalize_service_name(name: str) -> str:
    """
    Normalize service name to standard format.
    
    Args:
        name: Service name to normalize
        
    Returns:
        Normalized service name (lowercase, hyphens for word separation)
    """
    # Convert to lowercase and replace underscores with hyphens
    normalized = name.lower().replace("_", "-")
    
    # Remove invalid characters
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)
    
    # Remove multiple consecutive hyphens
    normalized = re.sub(r"-+", "-", normalized)
    
    # Remove leading/trailing hyphens
    normalized = normalized.strip("-")
    
    return normalized


def get_config_file_paths(
    service_name: str, 
    environment: str = "development",
    config_dir: Path | None = None
) -> list[Path]:
    """
    Get potential configuration file paths for a service.
    
    Args:
        service_name: Name of the service
        environment: Environment name
        config_dir: Base configuration directory
        
    Returns:
        List of potential configuration file paths (in order of precedence)
    """
    if config_dir is None:
        config_dir = Path.cwd() / "config"
    
    config_dir = Path(config_dir)
    
    paths = [
        # Environment-specific service config
        config_dir / f"{service_name}.{environment}.env",
        # Service-specific config
        config_dir / f"{service_name}.env",
        # Environment-specific global config
        config_dir / f"{environment}.env",
        # Global config
        config_dir / ".env",
        # Root .env file
        Path.cwd() / ".env",
    ]
    
    return paths


def merge_configs(*configs: dict[str, Any]) -> dict[str, Any]:
    """
    Merge multiple configuration dictionaries.
    
    Args:
        *configs: Configuration dictionaries to merge (later configs override earlier ones)
        
    Returns:
        Merged configuration dictionary
    """
    merged = {}
    
    for config in configs:
        if config:
            merged.update(config)
    
    return merged


def create_config_validator(validators: dict[str, Callable[[Any], bool]]) -> Callable[[dict[str, Any]], list[str]]:
    """
    Create a configuration validator function.
    
    Args:
        validators: Dictionary mapping config keys to validation functions
        
    Returns:
        Validator function that returns list of validation errors
    """
    def validate(config: dict[str, Any]) -> list[str]:
        errors = []
        
        for key, validator_func in validators.items():
            if key in config:
                try:
                    if not validator_func(config[key]):
                        errors.append(f"Validation failed for {key}")
                except Exception as e:
                    errors.append(f"Validation error for {key}: {e}")
        
        return errors
    
    return validate