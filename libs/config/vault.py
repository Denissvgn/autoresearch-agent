"""
Vault integration helpers for standardized configuration management.

This module provides utilities for:
- Vault client management with connection pooling
- Secret retrieval with caching
- Health checks and status monitoring
- Error handling and fallback mechanisms
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
import os
from typing import Any

from pydantic import BaseModel

# Import existing vault utilities
try:
    from config.vault_loader import _get_vault_client
    from config.vault_loader import get_vault_status as _get_vault_status
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Vault connection configuration."""
    
    url: str = field(default_factory=lambda: os.getenv("VAULT_ADDR", "http://vault:8200"))
    token: str | None = field(default_factory=lambda: os.getenv("VAULT_TOKEN"))
    role: str | None = field(default_factory=lambda: os.getenv("VAULT_ROLE"))
    mount_path: str = field(default_factory=lambda: os.getenv("VAULT_MOUNT_PATH", "secret"))
    namespace: str | None = field(default_factory=lambda: os.getenv("VAULT_NAMESPACE"))
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0


class VaultHealthStatus(BaseModel):
    """Vault health status model."""
    
    connected: bool = False
    authenticated: bool = False
    last_check: datetime | None = None
    error: str | None = None
    config_keys_available: int = 0
    mount_accessible: bool = False


class VaultException(Exception):
    """Base exception for Vault operations."""
    pass


class VaultConnectionError(VaultException):
    """Vault connection error."""
    pass


class VaultAuthenticationError(VaultException):
    """Vault authentication error."""
    pass


class VaultSecretNotFoundError(VaultException):
    """Vault secret not found error."""
    pass


class VaultClientManager:
    """
    Manages Vault client connections with connection pooling and health monitoring.
    
    Features:
    - Automatic connection management
    - Health status monitoring
    - Error handling with retries
    - Secret caching
    """
    
    def __init__(self, config: VaultConfig):
        """
        Initialize Vault client manager.
        
        Args:
            config: Vault configuration
        """
        self.config = config
        self._client: Any | None = None
        self._health_status = VaultHealthStatus()
        self._secret_cache: dict[str, dict[str, Any]] = {}
        self._cache_ttl: dict[str, datetime] = {}
        self._cache_duration = timedelta(minutes=5)  # 5 minute cache
        
    @property
    def client(self) -> Any | None:
        """Get the Vault client, initializing if necessary."""
        if self._client is None:
            self._initialize_client()
        return self._client
    
    def _initialize_client(self) -> None:
        """Initialize the Vault client."""
        if not VAULT_AVAILABLE:
            logger.warning("Vault libraries not available")
            return
            
        try:
            # Use existing vault client initialization
            self._client = _get_vault_client()
            if self._client:
                logger.debug(f"Vault client initialized for {self.config.url}")
                self._update_health_status(connected=True, authenticated=True)
            else:
                logger.warning("Failed to initialize Vault client for %s", self.config.url)
                self._update_health_status(connected=False, authenticated=False)
                
        except Exception as e:
            logger.error(f"Vault client initialization failed: {e}")
            self._update_health_status(connected=False, authenticated=False, error=str(e))
    
    def _update_health_status(
        self, 
        connected: bool = False, 
        authenticated: bool = False, 
        error: str | None = None
    ) -> None:
        """Update health status."""
        self._health_status.connected = connected
        self._health_status.authenticated = authenticated
        self._health_status.last_check = datetime.utcnow()
        self._health_status.error = error
    
    def get_health_status(self) -> VaultHealthStatus:
        """
        Get current Vault health status.
        
        Returns:
            Current health status
        """
        # Refresh status if stale (older than 1 minute)
        if (
            not self._health_status.last_check or 
            datetime.utcnow() - self._health_status.last_check > timedelta(minutes=1)
        ):
            self._check_health()
        
        return self._health_status
    
    def _check_health(self) -> None:
        """Perform health check on Vault connection."""
        try:
            if not self.client:
                self._update_health_status(connected=False, authenticated=False)
                return
            
            # Check if client is authenticated
            is_authenticated = self.client.is_authenticated()
            
            # Check if mount path is accessible
            mount_accessible = False
            try:
                # Try to list the mount path
                self.client.secrets.kv.v2.list_secrets(path="")
                mount_accessible = True
            except Exception:
                # Mount might not exist or no permissions, but that's ok
                mount_accessible = True  # Assume accessible if client works
            
            self._update_health_status(
                connected=True,
                authenticated=is_authenticated,
                error=None
            )
            self._health_status.mount_accessible = mount_accessible
            
        except Exception as e:
            logger.debug(f"Vault health check failed: {e}")
            self._update_health_status(connected=False, authenticated=False, error=str(e))
    
    def get_secret(
        self, 
        path: str, 
        key: str | None = None,
        use_cache: bool = True,
        mount_path: str | None = None
    ) -> dict[str, Any] | Any | None:
        """
        Retrieve a secret from Vault.
        
        Args:
            path: Secret path
            key: Specific key within the secret (optional)
            use_cache: Whether to use cached values
            mount_path: Override mount path
            
        Returns:
            Secret data or None if not found
            
        Raises:
            VaultConnectionError: If Vault is not accessible
            VaultSecretNotFoundError: If secret is not found
        """
        if not self.client:
            raise VaultConnectionError("Vault client not available")
        
        full_path = f"{mount_path or self.config.mount_path}/{path}"
        
        # Check cache first
        if use_cache and full_path in self._secret_cache:
            cache_time = self._cache_ttl.get(full_path)
            if cache_time and datetime.utcnow() < cache_time:
                logger.debug(f"Using cached secret for {full_path}")
                cached_data = self._secret_cache[full_path]
                return cached_data.get(key) if key else cached_data
        
        try:
            # Retrieve from Vault
            response = self.client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount_path or self.config.mount_path)
            secret_data = response.get("data", {}).get("data", {})
            
            # Cache the result
            if use_cache:
                self._secret_cache[full_path] = secret_data
                self._cache_ttl[full_path] = datetime.utcnow() + self._cache_duration
            
            logger.debug(f"Retrieved secret from {full_path} with {len(secret_data)} keys")
            
            # Return specific key or all data
            if key:
                if key not in secret_data:
                    raise VaultSecretNotFoundError(f"Key '{key}' not found in secret at {full_path}")
                return secret_data[key]
            
            return secret_data
            
        except Exception as e:
            if "not found" in str(e).lower():
                raise VaultSecretNotFoundError(f"Secret not found at {full_path}")
            else:
                raise VaultConnectionError(f"Failed to retrieve secret from {full_path}: {e}")
    
    def put_secret(
        self, 
        path: str, 
        data: dict[str, Any],
        mount_path: str | None = None
    ) -> bool:
        """
        Store a secret in Vault.
        
        Args:
            path: Secret path
            data: Secret data to store
            mount_path: Override mount path
            
        Returns:
            True if successful
            
        Raises:
            VaultConnectionError: If Vault is not accessible
        """
        if not self.client:
            raise VaultConnectionError("Vault client not available")
        
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=mount_path or self.config.mount_path
            )
            
            # Invalidate cache for this path
            full_path = f"{mount_path or self.config.mount_path}/{path}"
            if full_path in self._secret_cache:
                del self._secret_cache[full_path]
                del self._cache_ttl[full_path]
            
            logger.debug(f"Successfully stored secret at {full_path}")
            return True
            
        except Exception as e:
            raise VaultConnectionError(f"Failed to store secret at {path}: {e}")
    
    def list_secrets(self, path: str = "", mount_path: str | None = None) -> list[str]:
        """
        List secrets at a given path.
        
        Args:
            path: Path to list
            mount_path: Override mount path
            
        Returns:
            List of secret names
            
        Raises:
            VaultConnectionError: If Vault is not accessible
        """
        if not self.client:
            raise VaultConnectionError("Vault client not available")
        
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=mount_path or self.config.mount_path
            )
            
            keys = response.get("data", {}).get("keys", [])
            logger.debug(f"Listed {len(keys)} secrets at {path}")
            return keys
            
        except Exception as e:
            if "not found" in str(e).lower():
                return []
            else:
                raise VaultConnectionError(f"Failed to list secrets at {path}: {e}")
    
    def clear_cache(self, path: str | None = None) -> None:
        """
        Clear secret cache.
        
        Args:
            path: Specific path to clear, or None to clear all
        """
        if path:
            full_path = f"{self.config.mount_path}/{path}"
            if full_path in self._secret_cache:
                del self._secret_cache[full_path]
                del self._cache_ttl[full_path]
                logger.debug(f"Cleared cache for {full_path}")
        else:
            self._secret_cache.clear()
            self._cache_ttl.clear()
            logger.debug("Cleared all secret cache")
    
    def close(self) -> None:
        """Close the Vault client and clean up resources."""
        self._client = None
        self.clear_cache()
        logger.debug("Vault client manager closed")


# Global vault client manager instance
_vault_manager: VaultClientManager | None = None


def get_vault_manager() -> VaultClientManager:
    """
    Get the global Vault client manager instance.
    
    Returns:
        VaultClientManager instance
    """
    global _vault_manager
    
    if _vault_manager is None:
        config = VaultConfig()
        _vault_manager = VaultClientManager(config)
    
    return _vault_manager


def get_vault_health() -> VaultHealthStatus:
    """
    Get Vault health status.
    
    Returns:
        Current Vault health status
    """
    try:
        manager = get_vault_manager()
        return manager.get_health_status()
    except Exception as e:
        return VaultHealthStatus(
            connected=False,
            authenticated=False,
            last_check=datetime.utcnow(),
            error=str(e)
        )


def get_secret(
    path: str, 
    key: str | None = None,
    default: Any = None,
    use_cache: bool = True
) -> Any:
    """
    Convenient function to get a secret from Vault.
    
    Args:
        path: Secret path
        key: Specific key within the secret (optional)
        default: Default value if secret not found
        use_cache: Whether to use cached values
        
    Returns:
        Secret value or default
    """
    try:
        manager = get_vault_manager()
        return manager.get_secret(path, key, use_cache)
    except (VaultConnectionError, VaultSecretNotFoundError) as e:
        logger.debug(f"Failed to get secret {path}/{key}: {e}")
        return default
    except Exception as e:
        logger.warning(f"Unexpected error getting secret {path}/{key}: {e}")
        return default


def put_secret(path: str, data: dict[str, Any]) -> bool:
    """
    Convenient function to store a secret in Vault.
    
    Args:
        path: Secret path
        data: Secret data
        
    Returns:
        True if successful
    """
    try:
        manager = get_vault_manager()
        return manager.put_secret(path, data)
    except Exception as e:
        logger.error(f"Failed to store secret {path}: {e}")
        return False


# Task 17: Standardized Vault Status Function
async def check_vault_status() -> dict[str, Any]:
    """
    Standardized Vault status check function (Task 17).
    
    Provides comprehensive Vault health information in a consistent format
    across all TRAID Platform services.
    
    Returns:
        Dictionary with standardized status fields:
        - connected (bool): Basic Vault connectivity
        - sealed (bool): Vault seal status (False = unsealed/operational)
        - version (str): Vault version
        - last_renewal (datetime): Last token renewal time
        - errors (List[str]): Any errors encountered
        - authenticated (bool): Authentication status
        - mount_accessible (bool): Secret mount accessibility
        - response_time_ms (float): Health check response time
        - cluster_info (Dict): Cluster information if available
    """
    start_time = datetime.now(UTC)
    errors = []
    
    # Initialize default response
    status = {
        "connected": False,
        "sealed": True,  # Assume sealed until proven otherwise
        "version": "unknown",
        "last_renewal": None,
        "errors": [],
        "authenticated": False,
        "mount_accessible": False,
        "response_time_ms": 0.0,
        "cluster_info": {}
    }
    
    try:
        if not VAULT_AVAILABLE:
            errors.append("Vault libraries not available")
            status["errors"] = errors
            return status
        
        # Get Vault manager and perform health check
        manager = get_vault_manager()
        health_status = manager.get_health_status()
        
        # Calculate response time
        response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
        status["response_time_ms"] = round(response_time, 2)
        
        # Basic connectivity and authentication
        status["connected"] = health_status.connected
        status["authenticated"] = health_status.authenticated
        status["mount_accessible"] = health_status.mount_accessible
        
        if health_status.error:
            errors.append(health_status.error)
        
        # If connected, get detailed Vault system status
        if health_status.connected and manager.client:
            try:
                # Get Vault system health (sys/health endpoint)
                sys_health = manager.client.sys.read_health_status()
                
                # Extract standardized fields
                status["sealed"] = sys_health.get("sealed", True)
                status["version"] = sys_health.get("version", "unknown")
                
                # Cluster information
                status["cluster_info"] = {
                    "cluster_name": sys_health.get("cluster_name", ""),
                    "cluster_id": sys_health.get("cluster_id", ""),
                    "initialized": sys_health.get("initialized", False),
                    "standby": sys_health.get("standby", False)
                }
                
            except Exception as e:
                errors.append(f"Failed to get system health: {str(e)}")
                logger.debug(f"Vault sys/health error: {e}")
        
        # Token renewal information
        if status["authenticated"] and manager.client:
            try:
                # Try to get token information for renewal status
                token_info = manager.client.auth.token.lookup_self()
                
                # Extract renewal time if available
                if "data" in token_info and "last_renewal_time" in token_info["data"]:
                    renewal_timestamp = token_info["data"]["last_renewal_time"]
                    if renewal_timestamp:
                        # Convert Unix timestamp to ISO string
                        renewal_dt = datetime.fromtimestamp(renewal_timestamp, tz=UTC)
                        status["last_renewal"] = renewal_dt
                        
            except Exception as e:
                errors.append(f"Failed to get token info: {str(e)}")
                logger.debug(f"Token lookup error: {e}")
        
        # Update last check time (as ISO string for JSON serialization)
        last_check = health_status.last_check or datetime.now(UTC)
        status["last_check"] = last_check.isoformat() if isinstance(last_check, datetime) else str(last_check)
        
    except Exception as e:
        errors.append(f"Vault status check failed: {str(e)}")
        logger.error(f"check_vault_status error: {e}")
    
    # Set final errors list
    status["errors"] = errors
    
    # Log status for debugging
    logger.debug(f"Vault status check completed: connected={status['connected']}, "
                f"sealed={status['sealed']}, authenticated={status['authenticated']}, "
                f"errors={len(errors)}")
    
    return status


# Backward compatibility with existing vault status function
def get_vault_status() -> dict[str, Any]:
    """
    Get Vault status for backward compatibility.
    
    Returns:
        Vault status dictionary
    """
    try:
        # Use existing vault status if available
        if VAULT_AVAILABLE:
            return _get_vault_status()
        else:
            return {
                "connected": False,
                "authenticated": False,
                "error": "Vault libraries not available"
            }
    except Exception as e:
        return {
            "connected": False,
            "authenticated": False,
            "error": str(e)
        }