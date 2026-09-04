"""
Secret masking utility for structured logging and configuration display.
Provides secure logging by masking sensitive information.
"""

from copy import deepcopy
import json
import re
from typing import Any

# Sensitive keys that should be masked in logs
SENSITIVE_KEYS = {
    "password", "secret", "token", "key", "api_key", "access_key", 
    "secret_key", "private_key", "auth_token", "jwt", "bearer",
    "credential", "vault_token", "database_url", "connection_string",
    "aws_secret_access_key", "azure_client_secret", "gcp_key"
}

# Patterns for sensitive values (case insensitive)
SENSITIVE_PATTERNS = [
    r".*password.*",
    r".*secret.*", 
    r".*token.*",
    r".*key.*",
    r".*credential.*",
    r".*auth.*",
    r".*bearer.*",
    r".*jwt.*"
]

# Compiled regex patterns for better performance
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS]


def mask_value(value: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """
    Mask a sensitive value, showing only the last few characters.
    
    Args:
        value: The value to mask
        mask_char: Character to use for masking (default: *)
        visible_chars: Number of characters to show at the end (default: 4)
    
    Returns:
        Masked string with format: ****abcd
    """
    if not value or not isinstance(value, str):
        return str(value)
    
    if len(value) <= visible_chars:
        return mask_char * len(value)
    
    visible_part = value[-visible_chars:]
    mask_length = max(4, len(value) - visible_chars)  # At least 4 mask characters
    masked_part = mask_char * mask_length
    return f"{masked_part}{visible_part}"


def is_sensitive_key(key: str) -> bool:
    """
    Check if a key name indicates sensitive information.
    
    Args:
        key: The key name to check
        
    Returns:
        True if the key should be considered sensitive
    """
    key_lower = key.lower()
    
    # Check exact matches first
    if key_lower in SENSITIVE_KEYS:
        return True
    
    # Check pattern matches
    for pattern in COMPILED_PATTERNS:
        if pattern.match(key_lower):
            return True
    
    return False


def mask_sensitive_dict(data: dict[str, Any], deep_copy: bool = True) -> dict[str, Any]:
    """
    Recursively mask sensitive values in a dictionary.
    
    Args:
        data: Dictionary to process
        deep_copy: Whether to create a deep copy (default: True)
        
    Returns:
        Dictionary with sensitive values masked
    """
    if deep_copy:
        data = deepcopy(data)
    
    for key, value in data.items():
        if is_sensitive_key(key):
            if isinstance(value, str):
                data[key] = mask_value(value)
            else:
                data[key] = "***MASKED***"
        elif isinstance(value, dict):
            data[key] = mask_sensitive_dict(value, deep_copy=False)
        elif isinstance(value, list):
            data[key] = [
                mask_sensitive_dict(item, deep_copy=False) if isinstance(item, dict) 
                else mask_value(str(item)) if is_sensitive_key(str(item)) 
                else item
                for item in value
            ]
    
    return data


def mask_sensitive_json(json_str: str) -> str:
    """
    Mask sensitive values in a JSON string.
    
    Args:
        json_str: JSON string to process
        
    Returns:
        JSON string with sensitive values masked
    """
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            masked_data = mask_sensitive_dict(data)
            return json.dumps(masked_data, indent=2)
        return json_str
    except (json.JSONDecodeError, TypeError):
        return json_str


def get_config_summary(config: Any, include_sensitive: bool = False) -> dict[str, Any]:
    """
    Generate a configuration summary suitable for logging.
    
    Args:
        config: Configuration object or dictionary
        include_sensitive: Whether to include sensitive values (masked)
        
    Returns:
        Dictionary with configuration summary
    """
    if hasattr(config, "model_dump"):
        # Pydantic v2 model – excludes PrivateAttr fields like _vault
        config_dict = config.model_dump()
    elif hasattr(config, "dict") and callable(config.dict):
        # Pydantic v1 model
        config_dict = config.dict()
    elif isinstance(config, dict):
        config_dict = config
    elif hasattr(config, "__dict__"):
        # Generic object – filter out private/dunder attributes
        config_dict = {
            k: v for k, v in config.__dict__.items()
            if not k.startswith("_")
        }
    else:
        return {"error": "Unsupported configuration type"}
    
    if include_sensitive:
        return mask_sensitive_dict(config_dict)
    else:
        # Filter out sensitive keys entirely
        filtered_config = {}
        for key, value in config_dict.items():
            if not is_sensitive_key(key):
                if isinstance(value, dict):
                    filtered_config[key] = get_config_summary(value, include_sensitive=False)
                else:
                    filtered_config[key] = value
        return filtered_config


def format_config_for_logging(config: Any, service_name: str) -> str:
    """
    Format configuration for structured logging.
    
    Args:
        config: Configuration object
        service_name: Name of the service
        
    Returns:
        Formatted configuration string suitable for logging
    """
    summary = get_config_summary(config, include_sensitive=False)
    
    return f"{service_name} configuration loaded: " + json.dumps(summary, indent=2)
