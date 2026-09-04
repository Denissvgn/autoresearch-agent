"""Unified configuration framework for ML training services.

Enhanced with Task 05.1 security considerations and rotation features.
"""

from datetime import datetime, timedelta
import logging
import os
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Vault integration
try:
    from .vault_loader import get_vault_status, load_config
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False
    logging.getLogger(__name__).warning("Vault loader unavailable; falling back to env/defaults")

logger = logging.getLogger(__name__)


# Security utilities for sensitive data handling
class SecurityMaskingUtils:
    """Utilities for masking sensitive data in logs and audit trails."""
    
    # Patterns for identifying sensitive keys
    SENSITIVE_PATTERNS = [
        re.compile(r".*password.*", re.IGNORECASE),
        re.compile(r".*secret.*", re.IGNORECASE),
        re.compile(r".*key.*", re.IGNORECASE),
        re.compile(r".*token.*", re.IGNORECASE),
        re.compile(r".*credential.*", re.IGNORECASE),
        re.compile(r".*auth.*", re.IGNORECASE),
        re.compile(r".*access.*", re.IGNORECASE),
        re.compile(r".*private.*", re.IGNORECASE),
    ]
    
    @staticmethod
    def is_sensitive_key(key: str) -> bool:
        """Check if a configuration key contains sensitive data.
        
        Args:
            key: Configuration key name
            
        Returns:
            True if key appears to contain sensitive data
        """
        return any(pattern.match(key) for pattern in SecurityMaskingUtils.SENSITIVE_PATTERNS)
    
    @staticmethod
    def mask_value(value: Any) -> str:
        """Mask a sensitive value for logging.
        
        Args:
            value: Value to mask
            
        Returns:
            Masked representation of the value
        """
        if value is None:
            return "<None>"
        
        value_str = str(value)
        if len(value_str) <= 4:
            return "*" * len(value_str)
        else:
            return value_str[:2] + "*" * (len(value_str) - 4) + value_str[-2:]
    
    @staticmethod
    def safe_log_config(config_dict: dict[str, Any], logger_instance: logging.Logger, 
                       message_prefix: str = "Configuration loaded") -> None:
        """Safely log configuration with sensitive data masked.
        
        Args:
            config_dict: Configuration dictionary
            logger_instance: Logger instance to use
            message_prefix: Prefix for log message
        """
        safe_config = {}
        sensitive_count = 0
        
        for key, value in config_dict.items():
            if SecurityMaskingUtils.is_sensitive_key(key):
                safe_config[key] = SecurityMaskingUtils.mask_value(value)
                sensitive_count += 1
            else:
                safe_config[key] = value
        
        logger_instance.info(
            f"{message_prefix}: {len(config_dict)} keys loaded "
            f"({sensitive_count} sensitive keys masked)"
        )
        logger_instance.debug(f"Configuration keys: {list(config_dict.keys())}")


class AuditLogger:
    """Audit logging for configuration access and security events."""
    
    def __init__(self, service_name: str):
        """Initialize audit logger for a service.
        
        Args:
            service_name: Name of the service
        """
        self.service_name = service_name
        self.audit_logger = logging.getLogger(f"audit.{service_name}")
        
        # Configure audit logger if not already configured
        if not self.audit_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - AUDIT - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(logging.INFO)
            # Prevent audit messages from propagating to the root logger
            # (would cause double-emission: plain text here + JSON via root handler)
            self.audit_logger.propagate = False
    
    def log_config_access(self, source: str, key_count: int, sensitive_count: int) -> None:
        """Log configuration access event.
        
        Args:
            source: Configuration source (env/vault/default)
            key_count: Total number of keys accessed
            sensitive_count: Number of sensitive keys accessed
        """
        self.audit_logger.info(
            f"Config access - Service: {self.service_name}, "
            f"Source: {source}, Keys: {key_count}, Sensitive: {sensitive_count}"
        )
    
    def log_vault_rotation(self, success: bool, next_rotation: datetime | None = None) -> None:
        """Log Vault rotation event.
        
        Args:
            success: Whether rotation was successful
            next_rotation: Next scheduled rotation time
        """
        status = "SUCCESS" if success else "FAILED"
        message = f"Vault rotation - Service: {self.service_name}, Status: {status}"
        if next_rotation:
            message += f", Next: {next_rotation.isoformat()}"
        
        if success:
            self.audit_logger.info(message)
        else:
            self.audit_logger.error(message)
    
    def log_security_event(self, event_type: str, details: str) -> None:
        """Log security-related event.
        
        Args:
            event_type: Type of security event
            details: Event details (no sensitive data)
        """
        self.audit_logger.warning(
            f"Security event - Service: {self.service_name}, "
            f"Type: {event_type}, Details: {details}"
        )


class MLTrainingVaultManager:
    """Manages Vault configuration for ML training services.
    
    Enhanced with Task 05.1 security considerations:
    - Never logs secret values, only key presence
    - Audit logging for config sources (env/vault/default)
    - Support for Vault rotation tracking
    """
    
    def __init__(self, service_name: str, environment: str = "development"):
        """Initialize Vault manager for a service.
        
        Args:
            service_name: Name of the service
            environment: Environment name (development, staging, production)
        """
        self.service_name = service_name
        self.environment = environment
        self._vault_available = VAULT_AVAILABLE
        self._vault_loaded = False
        self._vault_data: dict[str, Any] = {}
        self._config_sources: dict[str, str] = {}  # Track source of each config key
        
        # Initialize security components
        self._audit_logger = AuditLogger(service_name)
        
        # Track rotation settings
        self._rotation_enabled = os.getenv("VAULT_ROTATION_ENABLED", "true").lower() == "true"
        self._rotation_interval_hours = int(os.getenv("VAULT_ROTATION_INTERVAL_HOURS", "6"))
        self._last_rotation_check = None
        
        # Load Vault configuration if available
        self._load_vault_config()
    
    def _load_vault_config(self) -> None:
        """Load configuration from Vault with security-aware logging."""
        if not self._vault_available:
            logger.debug(f"Vault unavailable for service {self.service_name}")
            self._audit_logger.log_config_access("unavailable", 0, 0)
            return
        
        try:
            # Use the correct function signature from vault_loader
            vault_config = load_config(self.service_name)
            
            if vault_config:
                self._vault_data = vault_config
                self._vault_loaded = True
                
                # Track config sources
                for key in vault_config.keys():
                    self._config_sources[key] = "vault"
                
                # Count sensitive keys for audit logging
                sensitive_count = sum(
                    1 for key in vault_config.keys() 
                    if SecurityMaskingUtils.is_sensitive_key(key)
                )
                
                # Safe logging with masking
                SecurityMaskingUtils.safe_log_config(
                    vault_config, logger, 
                    f"Vault configuration loaded for {self.service_name}"
                )
                
                # Audit log
                self._audit_logger.log_config_access("vault", len(vault_config), sensitive_count)
            else:
                logger.debug(f"No Vault configuration found for {self.service_name}")
                self._audit_logger.log_config_access("vault_empty", 0, 0)
            
        except Exception as e:
            logger.warning(
                "Failed to load Vault configuration for %s: %s. Using environment fallback.", 
                self.service_name, e
            )
            self._vault_loaded = False
            self._vault_data = {}
            self._audit_logger.log_security_event(
                "vault_load_failure", 
                f"Vault config load failed, using env fallback: {type(e).__name__}"
            )
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with precedence: env > vault > default.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        # 1. Check environment variables first (highest precedence)
        env_value = os.getenv(key)
        if env_value is not None:
            self._config_sources[key] = "env"
            # Log access without value for security
            if SecurityMaskingUtils.is_sensitive_key(key):
                logger.debug(f"Retrieved sensitive config key '{key}' from environment")
            return env_value
        
        # 2. Check Vault data (second precedence)
        if self._vault_loaded and key in self._vault_data:
            # Source already tracked during load
            if SecurityMaskingUtils.is_sensitive_key(key):
                logger.debug(f"Retrieved sensitive config key '{key}' from Vault")
            return self._vault_data[key]
        
        # 3. Return default (lowest precedence)
        if default is not None:
            self._config_sources[key] = "default"
        return default
    
    def get_vault_status(self) -> dict[str, Any]:
        """Get Vault integration status information.
        
        Returns:
            Dictionary with vault status details (no sensitive data)
        """
        status = {
            "service": self.service_name,
            "environment": self.environment,
            "vault_loader_available": self._vault_available,
            "vault_loaded": self._vault_loaded,
            "total_keys": len(self._vault_data),
            "keys": list(self._vault_data.keys()) if self._vault_loaded else [],
            "rotation_enabled": self._rotation_enabled,
            "rotation_interval_hours": self._rotation_interval_hours
        }
        
        # Add rotation status if enabled
        if self._rotation_enabled:
            status.update(self._get_rotation_status())
        
        return status
    
    def get_config_sources_audit(self) -> dict[str, Any]:
        """Get audit information about configuration sources.
        
        Returns:
            Dictionary with config source information (no values)
        """
        source_counts = {"env": 0, "vault": 0, "default": 0}
        sensitive_by_source = {"env": 0, "vault": 0, "default": 0}
        
        for key, source in self._config_sources.items():
            source_counts[source] = source_counts.get(source, 0) + 1
            if SecurityMaskingUtils.is_sensitive_key(key):
                sensitive_by_source[source] = sensitive_by_source.get(source, 0) + 1
        
        return {
            "service": self.service_name,
            "total_keys": len(self._config_sources),
            "source_counts": source_counts,
            "sensitive_by_source": sensitive_by_source,
            "config_keys": list(self._config_sources.keys())
        }
    
    def _get_rotation_status(self) -> dict[str, Any]:
        """Get Vault rotation status information.
        
        Returns:
            Dictionary with rotation status
        """
        now = datetime.now()
        
        # Calculate next rotation time
        next_rotation = None
        if self._last_rotation_check:
            next_rotation = self._last_rotation_check + timedelta(hours=self._rotation_interval_hours)
        else:
            # If no last check, schedule for next interval
            next_rotation = now + timedelta(hours=self._rotation_interval_hours)
        
        rotation_due = next_rotation and now >= next_rotation
        
        return {
            "last_rotation_check": self._last_rotation_check.isoformat() if self._last_rotation_check else None,
            "next_rotation": next_rotation.isoformat() if next_rotation else None,
            "rotation_due": rotation_due,
            "rotation_interval_hours": self._rotation_interval_hours
        }
    
    def check_rotation_due(self) -> bool:
        """Check if Vault rotation is due.
        
        Returns:
            True if rotation should be performed
        """
        if not self._rotation_enabled:
            return False
        
        rotation_status = self._get_rotation_status()
        return rotation_status.get("rotation_due", False)
    
    def mark_rotation_completed(self) -> None:
        """Mark that Vault rotation has been completed."""
        self._last_rotation_check = datetime.now()
        self._audit_logger.log_vault_rotation(True, 
            self._last_rotation_check + timedelta(hours=self._rotation_interval_hours))
    
    def mark_rotation_failed(self, error_details: str) -> None:
        """Mark that Vault rotation has failed.
        
        Args:
            error_details: Details about the failure (no sensitive data)
        """
        self._audit_logger.log_vault_rotation(False)
        self._audit_logger.log_security_event("rotation_failure", error_details)


class BaseMLTrainingConfig(BaseModel):
    """Base configuration class for ML training services."""
    
    model_config = {"arbitrary_types_allowed": True}
    
    # Private attributes to store service info and vault manager
    _svc: str = ""
    _vault: MLTrainingVaultManager | None = None
    
    def __init__(self, service_name: str, **data: Any):
        # Set private attributes before calling super().__init__
        super().__init__(**data)
        object.__setattr__(self, "_svc", service_name)
        object.__setattr__(self, "_vault", MLTrainingVaultManager(service_name))
    
    def get_training_params(self) -> dict[str, Any]:
        """Get training-specific parameters. Override in subclasses."""
        return {}
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value using vault manager."""
        return self._vault.get_config_value(key, default) if self._vault else default
    
    def get_vault_status(self) -> dict[str, Any]:
        """Get Vault status information."""
        if self._vault:
            return self._vault.get_vault_status()
        return {"vault_loader_available": False, "vault_loaded": False}


class MLflowConfig(BaseModel):
    """MLflow configuration for training services."""
    
    tracking_uri: str = Field(default="http://mlflow-service:8000")
    experiment_name: str = Field(default="ML_Training")
    model_registry_name: str | None = None
    enable_logging: bool = True
    auto_register_model: bool = False
    log_interval: int = 1000
    tags: dict[str, str] = Field(default_factory=dict)
    
    @field_validator("tracking_uri")
    @classmethod
    def validate_tracking_uri(cls, v: str) -> str:
        if not v or not v.startswith(("http://", "https://", "file://")):
            raise ValueError("tracking_uri must be a valid URI")
        return v


class ResourceConfig(BaseModel):
    """Resource management configuration."""
    
    memory_limit_gb: int = 8
    cpu_cores: int = 4
    gpu_enabled: bool = False
    max_training_time_hours: int = 24
    
    @field_validator("memory_limit_gb", "cpu_cores", mode="before")
    @classmethod
    def _gt_zero(cls, v: Any) -> Any:
        """Validate that numeric values are greater than zero."""
        iv = int(v)
        if iv <= 0:
            raise ValueError("must be > 0")
        return iv
    
    @field_validator("max_training_time_hours", mode="before")
    @classmethod
    def _validate_training_time(cls, v: Any) -> Any:
        """Validate training time is reasonable (1 hour to 1 week)."""
        iv = int(v)
        if iv < 1 or iv > 168:  # 1 week max
            raise ValueError("must be between 1 and 168 hours")
        return iv
