# Shared Configuration Library

## Overview

The shared configuration library provides standardized configuration management patterns for all TRAID Platform services using pydantic-settings. This library enables consistent environment variable handling, Vault integration, secret masking, and validation across services.

## Key Features

- **BaseServiceSettings**: Core configuration class with common service fields
- **Vault Integration**: Centralized Vault client management and secret handling
- **Environment Management**: Automatic environment variable loading and validation
- **Secret Masking**: Automatic detection and masking of sensitive configuration values
- **Configuration Validation**: Comprehensive validation with clear error messages
- **Backward Compatibility**: Graceful fallback when new modules are not available
- **Legacy Support**: Maintains compatibility with existing vault_loader patterns

## Core Components

### BaseServiceSettings

The foundation class that all services should inherit from:

```python
from libs.config import BaseServiceSettings

class MyServiceSettings(BaseServiceSettings):
    # Service-specific configuration
    my_service_endpoint: str = "http://localhost:8080"
    my_feature_flag: bool = False
    
    class Config:
        env_prefix = "MY_SERVICE_"
```

### Environment Variables

All services automatically support these standard environment variables:

#### Service Identification
- `{SERVICE}_SERVICE_NAME` - Service identifier
- `{SERVICE}_SERVICE_VERSION` - Service version
- `{SERVICE}_ENVIRONMENT` - Environment (development/staging/production)

#### Network Configuration
- `{SERVICE}_HOST` - Bind host (default: 0.0.0.0)
- `{SERVICE}_PORT` - Bind port (default: 8000)
- `{SERVICE}_BASE_URL` - External base URL

#### Logging
- `{SERVICE}_LOG_LEVEL` - Logging level (debug/info/warning/error)
- `{SERVICE}_LOG_FORMAT` - Log format (json/text)

#### Redis
- `{SERVICE}_REDIS_URL` - Redis connection URL
- `{SERVICE}_REDIS_PASSWORD` - Redis password
- `{SERVICE}_REDIS_DB` - Redis database number

#### Database  
- `{SERVICE}_DATABASE_URL` - Database connection URL
- `{SERVICE}_DB_PASSWORD` - Database password

#### Vault
- `{SERVICE}_VAULT_URL` - Vault server URL
- `{SERVICE}_VAULT_TOKEN` - Vault authentication token
- `{SERVICE}_VAULT_MOUNT_POINT` - Vault secrets mount point

#### API & Security
- `{SERVICE}_API_PREFIX` - API route prefix
- `{SERVICE}_JWT_SECRET` - JWT signing secret
- `{SERVICE}_ENCRYPTION_KEY` - Data encryption key

## Usage Examples

### Basic Service Configuration

```python
from libs.config import BaseServiceSettings

class TradingServiceSettings(BaseServiceSettings):
    max_order_size: float = 1000.0
    risk_threshold: float = 0.05
    
    class Config:
        env_prefix = "TRADING_"

# Load configuration
settings = TradingServiceSettings()

# Access standard fields
print(f"Service: {settings.service_name}")
print(f"Port: {settings.port}")
print(f"Environment: {settings.environment}")

# Access custom fields
print(f"Max Order: {settings.max_order_size}")
```

### Vault Integration

```python
from libs.config import BaseServiceSettings, get_vault_manager

class MyServiceSettings(BaseServiceSettings):
    vault_path: str = "secret/myservice"

settings = MyServiceSettings()

# Get Vault manager
vault_manager = get_vault_manager(settings.to_vault_config())

# Retrieve secrets
async def load_secrets():
    secret = await vault_manager.get_secret("database/password")
    return secret
```

### Configuration Validation

```python
from libs.config import BaseServiceSettings, validate_required_config

class APIServiceSettings(BaseServiceSettings):
    api_key: str
    rate_limit: int = 100
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("API key must be at least 10 characters")
        return v

# Validate configuration
settings = APIServiceSettings()
errors = validate_required_config(settings.dict())
if errors:
    print(f"Configuration errors: {errors}")
```

### Secret Masking

```python
from libs.config import sanitize_config_dict

config = {
    "database_url": "postgresql://user:secret@localhost/db",
    "api_key": "sk_live_abcd1234",
    "public_setting": "visible_value"
}

# Sanitize for logging
safe_config = sanitize_config_dict(config)
print(safe_config)
# Output: {
#   "database_url": "postgresql://user:***@localhost/db",
#   "api_key": "sk_live_***",
#   "public_setting": "visible_value"
# }
```

## Legacy Vault Loader Integration

The library maintains full compatibility with existing vault_loader patterns:

```python
# Existing pattern still works
from config import load_config, get_vault_status

config = load_config("autotrade-service")
status = get_vault_status()

# New pattern with enhanced features  
from libs.config import BaseServiceSettings

class AutotradeSettings(BaseServiceSettings):
    class Config:
        env_prefix = "AUTOTRADE_"

settings = AutotradeSettings()
```

## Migration Guide

### From Custom Configuration

If your service currently uses custom configuration:

**Before:**
```python
import os
from dataclasses import dataclass

@dataclass
class Config:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
```

**After:**
```python
from libs.config import BaseServiceSettings

class MyServiceSettings(BaseServiceSettings):
    # BaseServiceSettings provides host, port, log_level automatically
    pass

settings = MyServiceSettings()
```

### From Direct Environment Variables

**Before:**
```python
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")
DATABASE_URL = os.getenv("DATABASE_URL")
```

**After:**
```python
from libs.config import BaseServiceSettings

class MyServiceSettings(BaseServiceSettings):
    class Config:
        env_prefix = "MY_SERVICE_"

settings = MyServiceSettings()
# Access via settings.redis_url, settings.database_url
```

## Error Handling

The library provides specific exceptions for different error types:

```python
from libs.config import (
    ConfigurationError,
    VaultConfigurationError, 
    ValidationError,
    EnvironmentError
)

try:
    settings = MyServiceSettings()
except ValidationError as e:
    print(f"Invalid configuration: {e}")
except EnvironmentError as e:
    print(f"Environment error: {e}")
except ConfigurationError as e:
    print(f"General config error: {e}")
```

## Best Practices

1. **Always inherit from BaseServiceSettings** for consistency
2. **Use service-specific env_prefix** to avoid conflicts
3. **Validate sensitive configuration** early in application startup
4. **Use Vault for secrets** rather than environment variables in production
5. **Sanitize configuration** before logging or error reporting
6. **Test configuration loading** in different environments

## Testing Configuration

```python
import pytest
from libs.config import BaseServiceSettings

class TestServiceSettings(BaseServiceSettings):
    test_value: str = "default"
    
    class Config:
        env_prefix = "TEST_"

def test_configuration():
    # Test with environment variables
    import os
    os.environ["TEST_TEST_VALUE"] = "test_override"
    
    settings = TestServiceSettings()
    assert settings.test_value == "test_override"
    
    # Test validation
    settings.service_name = ""  # Should trigger validation error
    with pytest.raises(ValidationError):
        settings.validate_all()
```

## Integration with Existing Services

This library is designed to integrate seamlessly with existing services:

1. **Gradual Migration**: Services can adopt the library incrementally
2. **Backward Compatibility**: Existing configuration patterns continue to work
3. **No Breaking Changes**: Current environment variables remain supported
4. **Enhanced Features**: Services gain Vault integration and secret masking automatically

## Next Steps

With the shared configuration library in place, services can now:

1. Migrate to use `BaseServiceSettings` for consistent configuration
2. Leverage Vault integration for secure secret management  
3. Benefit from automatic environment variable handling
4. Use standardized validation and error handling
5. Prepare for automated configuration management and deployment
print(f"Vault enabled: {status['vault_enabled']}")
print(f"Vault connected: {status['vault_connected']}")
print(f"Vault authenticated: {status['vault_authenticated']}")
```

## Configuration Resolution Order

The library follows a specific precedence order when merging configuration:

1. **Environment Variables**: Base layer from `os.environ` and `.env` files
2. **Vault Global**: Configuration from `secret/config/global`
3. **Vault Service**: Configuration from `secret/config/{service-name}/{environment}`

Later sources override earlier ones, so service-specific Vault configuration takes precedence over global Vault configuration, which takes precedence over environment variables.

## Environment Variables

### Core Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_VAULT` | `true` | Enable/disable Vault integration |
| `VAULT_ADDR` | - | Vault server URL (required for Vault) |
| `VAULT_TOKEN` | - | Vault authentication token (required for Vault) |
| `APP_ENV` | `development` | Default environment name |

### Example Configuration

```bash
# Production with Vault
USE_VAULT=true
VAULT_ADDR=https://vault.company.com:8200
VAULT_TOKEN=s.abc123def456...
APP_ENV=production

# Development without Vault
USE_VAULT=false
DATABASE_URL=postgres://localhost:5432/devdb
REDIS_URL=redis://localhost:6379
DEBUG=true
```

## Vault Path Structure

The library uses a hierarchical path structure in Vault:

```
secret/
├── config/
│   ├── global                          # Global configuration
│   └── {service-name}/
│       ├── development                 # Development environment
│       ├── staging                     # Staging environment
│       └── production                  # Production environment
```

### Example Vault Configuration

**Global Configuration** (`secret/config/global`):
```json
{
  "database_host": "db.company.com",
  "redis_host": "redis.company.com",
  "log_level": "INFO"
}
```

**Service Configuration** (`secret/config/autotrade-service/production`):
```json
{
  "database_url": "postgres://user:pass@db.company.com:5432/autotrade",
  "redis_url": "redis://redis.company.com:6379/1",
  "max_positions": "100",
  "api_timeout": "30"
}
```

## Development Workflow

### Local Development (No Vault)

```bash
# Create .env file
echo "USE_VAULT=false" >> .env
echo "DATABASE_URL=postgres://localhost:5432/traid_dev" >> .env
echo "REDIS_URL=redis://localhost:6379" >> .env
echo "DEBUG=true" >> .env

# Use in your service
from config import load_config
config = load_config("my-service")
```

### Production Deployment (With Vault)

```bash
# Set environment variables
export USE_VAULT=true
export VAULT_ADDR=https://vault.company.com:8200
export VAULT_TOKEN=${VAULT_TOKEN}
export APP_ENV=production

# Configuration loaded from Vault automatically
from config import load_config
config = load_config("my-service")  # Uses production environment
```

## Integration with Services

### FastAPI Service Integration

```python
# services/my-service/src/main.py
from fastapi import FastAPI
from config import load_config

# Load configuration at startup
config = load_config("my-service")

app = FastAPI(
    title="My Service",
    debug=config.get("DEBUG", "false").lower() == "true"
)

# Use configuration throughout the service
DATABASE_URL = config["DATABASE_URL"]
REDIS_URL = config["REDIS_URL"]
```

### Database Connection Example

```python
from config import load_config
import asyncpg

# Load service configuration
config = load_config("user-service")

# Create database connection
async def create_db_pool():
    return await asyncpg.create_pool(
        config["DATABASE_URL"],
        min_size=int(config.get("DB_POOL_MIN_SIZE", "1")),
        max_size=int(config.get("DB_POOL_MAX_SIZE", "10"))
    )
```

## Error Handling

The library is designed to be resilient and never crash your service:

### Vault Connection Failures

```python
# If Vault is unavailable, falls back to environment variables
config = load_config("my-service")  # Always returns a dict, never raises
```

### Missing Configuration

```python
# Use dict.get() for optional configuration
timeout = int(config.get("API_TIMEOUT", "30"))  # Default to 30 seconds

# Use dict access for required configuration with try/catch
try:
    database_url = config["DATABASE_URL"]
except KeyError:
    logger.error("DATABASE_URL not configured")
    raise
```

## Testing

The library includes comprehensive test coverage for all scenarios:

```bash
cd libs/config
python -m pytest tests/ -v
```

### Test Scenarios Covered

- Vault disabled via environment variable
- Vault missing credentials
- Successful Vault connection and configuration loading
- Partial Vault failure with fallback
- Environment-only configuration
- .env file loading with environment override
- Key normalization to uppercase
- Configuration merging precedence
- Default environment detection
- Vault authentication failure
- Import error handling

## Logging

The library uses Python's standard logging module:

```python
import logging

# Enable debug logging for configuration
logging.getLogger("config.vault_loader").setLevel(logging.DEBUG)
```

Log levels used:
- **DEBUG**: Detailed operation information
- **INFO**: Configuration loading summary
- **WARNING**: Non-critical issues (Vault unavailable, etc.)
- **ERROR**: Critical configuration errors

## Security Considerations

1. **Sensitive Values**: The library never logs sensitive configuration values
2. **Vault Tokens**: Ensure `VAULT_TOKEN` is properly secured and rotated
3. **Environment Variables**: Be cautious with sensitive data in environment variables
4. **Access Control**: Use Vault policies to restrict configuration access by service

## Best Practices

1. **Service Naming**: Use consistent service names across your infrastructure
2. **Environment Separation**: Maintain separate Vault paths for each environment
3. **Default Values**: Always provide sensible defaults for optional configuration
4. **Validation**: Validate critical configuration values in your service startup
5. **Documentation**: Document your service's configuration requirements

## Troubleshooting

### Common Issues

1. **Configuration not loaded**: Check `USE_VAULT`, `VAULT_ADDR`, and `VAULT_TOKEN`
2. **Values not updated**: Vault caches may need time to propagate changes
3. **Missing keys**: Verify Vault paths and service name spelling
4. **Authentication errors**: Check Vault token permissions and expiry

### Debug Commands

```python
from config import get_vault_status, load_config
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Check Vault status
print(get_vault_status())

# Load with verbose logging
config = load_config("my-service")
```

For more details, see the comprehensive test suite in `tests/test_vault_loader.py`.
