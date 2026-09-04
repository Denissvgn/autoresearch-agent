# Example: Modernized Admin Service Configuration with Vault Integration
# File: services/admin-service/src/config_vault_example.py

"""
Example of how to integrate the shared Vault configuration loader
with existing service configuration patterns.

This shows backward-compatible migration from environment variables
to Vault-backed configuration.
"""

import os

from pydantic_settings import BaseSettings

# Import the shared Vault loader (adjust import path based on context)
try:
    from libs.config.config.vault_loader import load_config
except ImportError:
    from config.vault_loader import load_config


class VaultBackedConfig(BaseSettings):
    """
    Admin Service configuration with Vault integration.
    
    This configuration class demonstrates how to use the shared
    vault_loader while maintaining backward compatibility.
    """
    
    def __init__(self, **kwargs):
        # Load configuration from Vault with fallbacks
        vault_config = load_config("admin-service")
        
        # Merge Vault config with any explicit overrides
        merged_config = {**vault_config, **kwargs}
        
        super().__init__(**merged_config)
    
    # Service Identity
    APP_NAME: str = "Admin Service"
    API_V1_STR: str = "/api/v1"
    SERVICE_NAME: str = "admin-service"
    
    # Environment
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_ENV: str = "development"
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./test.db"
    ADMIN_DB_POOL_SIZE: int = 10
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 300
    
    # Admin-specific Settings (from Vault)
    ADMIN_API_RATE_LIMIT: str = "100/minute"
    ENABLE_ADMIN_AUDIT_LOG: bool = True
    ADMIN_SESSION_TIMEOUT: int = 1800
    MAX_EXPORT_RECORDS: int = 10000
    
    # S3 Configuration
    S3_BUCKET: str = "traid-platform-data"
    S3_PREFIX: str = "market-data"
    AWS_REGION: str = "us-east-1"
    
    # Service URLs
    DATA_INGEST_SERVICE_URL: str = "http://data-ingest:8000"
    EXCHANGE_SERVICE_URL: str = "http://exchange-service:8000"
    AUTOTRADE_SERVICE_URL: str = "http://autotrade-service:8000"
    
    # Security Settings (from Vault global config)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    REQUEST_TIMEOUT_SECONDS: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Simple function-based approach (alternative)
def get_admin_config() -> dict:
    """
    Simple function to get admin service configuration.
    
    Returns:
        Configuration dictionary ready for use
    """
    return load_config("admin-service")


# Usage examples:
if __name__ == "__main__":
    
    # Method 1: Pydantic Settings Class
    config = VaultBackedConfig()
    
    # Method 2: Simple Function
    simple_config = get_admin_config()
    
    # Method 3: Direct Usage
    direct_config = load_config("admin-service", "development")
    vault_keys = [k for k in direct_config.keys() if k not in os.environ]
    env_keys = [k for k in direct_config.keys() if k in os.environ]
