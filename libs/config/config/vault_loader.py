"""
Vault-backed configuration loader with safe fallbacks.

This module provides a centralized way to load configuration from HashiCorp Vault
with graceful fallback to environment variables and .env files.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Global state for Vault client
_vault_client: Any | None = None
_vault_initialized = False

# Process-lifetime cache for load_config results — prevents duplicate vault reads
# when multiple modules call load_config with the same (prefix, env) on startup.
_load_config_cache: dict[tuple[str, str], dict[str, Any]] = {}


def _get_vault_client() -> Any | None:
    """
    Get or create a Vault client instance.

    Retries the connection a few times to tolerate Vault starting concurrently
    in multi-container environments (e.g. Docker Compose).  Controlled via:
      VAULT_CONNECT_RETRIES  (default 3)
      VAULT_CONNECT_RETRY_DELAY  (default 2, seconds between retries)
    
    Returns:
        Vault client instance or None if unavailable/disabled
    """
    global _vault_client, _vault_initialized
    
    if _vault_initialized:
        return _vault_client
    
    # Check if Vault is disabled
    if os.getenv("USE_VAULT", "true").lower() == "false":
        logger.debug("Vault disabled via USE_VAULT=false")
        _vault_initialized = True
        return None
    
    # Check for required Vault environment variables
    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")
    
    if not vault_addr or not vault_token:
        logger.debug("Vault credentials not available (VAULT_ADDR or VAULT_TOKEN missing)")
        _vault_initialized = True
        return None

    max_retries = int(os.getenv("VAULT_CONNECT_RETRIES", "3"))
    retry_delay = float(os.getenv("VAULT_CONNECT_RETRY_DELAY", "2"))

    try:
        import hvac
    except ImportError:
        logger.warning("hvac library not available, falling back to environment variables")
        _vault_initialized = True
        return None

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            client = hvac.Client(
                url=vault_addr,
                token=vault_token,
                timeout=10,
            )
            if client.is_authenticated():
                _vault_client = client
                logger.debug("Vault client initialized successfully for %s", vault_addr)
                break
            else:
                logger.warning("Vault authentication failed (attempt %d/%d)", attempt, max_retries)
                last_error = None
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.debug(
                    "Vault unreachable (attempt %d/%d), retrying in %gs: %s",
                    attempt, max_retries, retry_delay, e,
                )
                time.sleep(retry_delay)
            # else: fall through to final handling

    if _vault_client is None:
        if last_error is not None:
            logger.warning(
                "Vault at %s unreachable after %d attempts, using env vars: %s",
                vault_addr, max_retries, last_error,
            )
        # Do NOT set _vault_initialized when the connection failed but was
        # expected (VAULT_ADDR and VAULT_TOKEN present).  This allows a
        # subsequent call to retry once Vault becomes healthy — matching
        # the compose philosophy of "rely on app-level retries" instead
        # of cross-file depends_on.
        return None

    _vault_initialized = True
    return _vault_client


def _load_from_vault(path: str) -> dict[str, Any]:
    """
    Load configuration from a Vault path.
    
    Args:
        path: Vault path to read from (e.g., 'secret/config/global')
        
    Returns:
        Configuration dictionary or empty dict if path doesn't exist or error occurs
    """
    client = _get_vault_client()
    if not client:
        return {}
    
    try:
        response = client.secrets.kv.v2.read_secret_version(path=path)
        data = response.get("data", {}).get("data", {})
        logger.debug(f"Loaded {len(data)} keys from Vault path: {path}")
        return data
    except Exception as e:
        logger.debug(f"Failed to read from Vault path '{path}': {e}")
        return {}


def _load_from_env() -> dict[str, Any]:
    """
    Load configuration from environment variables and .env files.
    
    Returns:
        Configuration dictionary from environment
    """
    config = {}
    
    # Load from .env file if it exists
    try:
        from dotenv import dotenv_values

        # Look for .env file in current directory or parent directories
        current_path = Path.cwd()
        for path in [current_path] + list(current_path.parents):
            env_file = path / ".env"
            if env_file.exists():
                env_config = dotenv_values(env_file)
                config.update(env_config)
                logger.debug(f"Loaded configuration from {env_file}")
                break
    except ImportError:
        logger.debug("python-dotenv not available, skipping .env file loading")
    except Exception as e:
        logger.debug(f"Error loading .env file: {e}")
    
    # Override with actual environment variables
    config.update(dict(os.environ))
    
    return config


def _normalize_keys(config: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize configuration keys to uppercase.
    
    Args:
        config: Raw configuration dictionary
        
    Returns:
        Configuration dictionary with uppercase keys
    """
    return {key.upper(): value for key, value in config.items()}


def _merge_configs(*configs: dict[str, Any]) -> dict[str, Any]:
    """
    Merge multiple configuration dictionaries.
    
    Later dictionaries override earlier ones.
    
    Args:
        *configs: Configuration dictionaries to merge
        
    Returns:
        Merged configuration dictionary
    """
    result = {}
    for config in configs:
        result.update(config)
    return result


_GLOBAL_SUBPATHS: tuple[str, ...] = (
    "config/global/network",
    "config/global/logging",
    "config/global/cors",
    "config/global/jwt",
    "config/global/redis",
    "config/global/database",
    "config/global/vault",
    "config/global/storage",
    "config/global/nats",
    "config/global/identity_client",
    "config/global/service_urls",
    "config/global/resilience",
    "config/global/monitoring",
    "config/global/trading",
)


def _load_vault_global_config() -> dict[str, Any]:
    """
    Load all global configuration sections from Vault.

    Reads each ``config/global/<section>`` path individually and merges them.
    Also falls back to the legacy single-path ``config/global`` for backward
    compatibility with existing seed data.

    Returns:
        Merged global configuration dictionary.
    """
    merged: dict[str, Any] = {}

    # Legacy single-path (backward compat with old seed scripts)
    merged.update(_load_from_vault("config/global"))

    # New granular sub-paths seeded by seed_platform_defaults.sh
    for subpath in _GLOBAL_SUBPATHS:
        section_data = _load_from_vault(subpath)
        if section_data:
            merged.update(section_data)

    return merged


def load_config(prefix: str, env: str | None = None) -> dict[str, Any]:
    """
    Load configuration by prefix and environment with safe fallbacks.
    
    Resolution order (later wins):
    1) Environment variables / ``.env`` file
    2) Vault global sections (``secret/config/global/*``)
    3) Vault service-specific (``secret/config/<prefix>/<env>``)

    Environment variables set on the container **always** win because
    pydantic-settings reads them after this dict is returned.
    
    Args:
        prefix: Service prefix (e.g., 'admin-service', 'autotrade-service')
        env: Environment name (defaults to APP_ENV or 'development')
        
    Returns:
        Merged configuration dictionary with uppercase keys
        
    Examples:
        >>> config = load_config('admin-service', 'production')
        >>> database_url = config.get('DATABASE_URL')
        
        >>> config = load_config('autotrade-service')  # Uses APP_ENV
        >>> redis_url = config.get('REDIS_URL')
    """
    # Determine environment
    if env is None:
        env = os.getenv("APP_ENV", "development")

    # Return cached result to prevent duplicate vault reads during startup
    cache_key = (prefix, env)
    if cache_key in _load_config_cache:
        logger.debug(f"Returning cached config for '{prefix}' ({env})")
        return _load_config_cache[cache_key]

    logger.debug(f"Loading configuration for service '{prefix}' in environment '{env}'")
    
    # Start with environment variables as base
    env_config = _load_from_env()
    
    # Load all global sections from Vault
    vault_global_config = _load_vault_global_config()

    # Load service-specific overrides from Vault
    vault_service_config = _load_from_vault(f"config/{prefix}/{env}")
    
    # Merge configurations with precedence: env < vault_global < vault_service
    merged_config = _merge_configs(
        env_config,
        vault_global_config,
        vault_service_config
    )
    
    # Normalize keys to uppercase
    normalized_config = _normalize_keys(merged_config)
    
    # Log configuration summary (without sensitive values)
    config_sources: list[str] = []
    if env_config:
        config_sources.append("environment")
    if vault_global_config:
        config_sources.append("vault-global")
    if vault_service_config:
        config_sources.append(f"vault-{prefix}")
    
    logger.info(
        f"Configuration loaded for '{prefix}' ({env}): "
        f"{len(normalized_config)} keys from {', '.join(config_sources) or 'none'}"
    )

    _load_config_cache[cache_key] = normalized_config
    return normalized_config


def load_vault_only(prefix: str, env: str | None = None) -> dict[str, Any]:
    """
    Load configuration from Vault **only** — no environment variables.

    This is designed for use as a pydantic-settings custom source so that
    vault values don't duplicate the env-var source that pydantic already
    provides.

    Resolution order (later wins):
        vault global sections  <  vault service-specific

    Args:
        prefix: Service prefix (e.g., ``admin-service``)
        env: Environment name (defaults to ``APP_ENV`` or ``development``)

    Returns:
        Merged vault configuration dictionary with **lowercase** keys,
        suitable for direct consumption by pydantic model fields.
    """
    if env is None:
        env = os.getenv("APP_ENV", "development")

    vault_global_config = _load_vault_global_config()
    vault_service_config = _load_from_vault(f"config/{prefix}/{env}")

    merged = _merge_configs(vault_global_config, vault_service_config)

    # Lowercase keys for pydantic field matching
    return {k.lower(): v for k, v in merged.items()}


def reload_vault_client() -> None:
    """
    Force reload of the Vault client.
    
    Useful for testing or when Vault credentials change at runtime.
    """
    global _vault_client, _vault_initialized
    _vault_client = None
    _vault_initialized = False
    logger.debug("Vault client state reset")


def get_vault_status() -> dict[str, Any]:
    """
    Get current Vault connection status.
    
    Returns:
        Status dictionary with connection information
    """
    client = _get_vault_client()
    
    return {
        "vault_enabled": os.getenv("USE_VAULT", "true").lower() == "true",
        "vault_addr": os.getenv("VAULT_ADDR"),
        "vault_connected": client is not None,
        "vault_authenticated": client.is_authenticated() if client else False,
    }
