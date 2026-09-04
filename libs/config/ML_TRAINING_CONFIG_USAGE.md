# ML Training Configuration Framework Usage Guide

## Overview

The unified ML training configuration framework provides a standardized way for ML services to load configuration from HashiCorp Vault with graceful fallback to environment variables and defaults.

## Key Components

### 1. MLTrainingVaultManager
Manages Vault configuration loading for ML training services.

**Features:**
- Automatic Vault connection and configuration loading
- Environment variable precedence: `env > vault > default`
- Graceful fallback when Vault is unavailable
- Configuration caching for performance
- Status reporting for debugging

### 2. BaseMLTrainingConfig
Base Pydantic configuration class that all ML services should extend.

**Features:**
- Vault integration through MLTrainingVaultManager
- Type validation with Pydantic
- Standardized configuration methods
- Service identification and status reporting

### 3. Pre-built Configuration Models
- **MLflowConfig**: MLflow integration settings
- **ResourceConfig**: Resource management (CPU, memory, GPU, training time)

## Usage Pattern

### 1. Create Service-Specific Configuration

```python
from config.ml_training_config import BaseMLTrainingConfig, MLflowConfig, ResourceConfig
from pydantic import Field, field_validator
from typing import Dict, Any

class YourServiceConfig(BaseMLTrainingConfig):
    """Configuration for your ML training service."""
    
    # Service-specific parameters
    your_param: str = Field(default="default_value")
    learning_rate: float = Field(default=0.01)
    
    @field_validator("learning_rate")
    @classmethod
    def validate_learning_rate(cls, v: float) -> float:
        if v <= 0 or v > 1:
            raise ValueError("learning_rate must be between 0 and 1")
        return v
    
    def get_training_params(self) -> Dict[str, Any]:
        """Override to return service-specific training parameters."""
        return {
            "learning_rate": self.learning_rate,
            "your_param": self.your_param,
        }

def get_config() -> YourServiceConfig:
    """Get configuration with Vault integration."""
    config = YourServiceConfig("your-service-name")
    
    # Override with Vault values if available
    config.learning_rate = config.get_config_value("LEARNING_RATE", config.learning_rate)
    config.your_param = config.get_config_value("YOUR_PARAM", config.your_param)
    
    return config
```

### 2. Use Configuration in Service

```python
from .config import get_config

def main():
    # Load configuration
    config = get_config()
    
    # Check Vault status
    vault_status = config.get_vault_status()
    print(f"Vault status: {vault_status}")
    
    # Get training parameters
    training_params = config.get_training_params()
    print(f"Training params: {training_params}")
    
    # Access specific configuration values
    learning_rate = config.learning_rate
    print(f"Learning rate: {learning_rate}")
```

## Vault Configuration Structure

The framework expects Vault configuration to be stored at:
```
services/{service-name}/{environment}/
```

For example:
- `services/ensemble-trainer/development/`
- `services/rl-trainer/production/`
- `services/vdmc-indicator/staging/`

## Environment Variable Precedence

Configuration values are resolved in this order:
1. **Environment Variables** (highest precedence)
2. **Vault Configuration** 
3. **Default Values** (lowest precedence)

This allows for:
- Local development with `.env` files
- Production deployment with Vault
- Testing with environment variable overrides

## Error Handling

The framework provides graceful degradation:
- If Vault is unavailable, falls back to environment variables and defaults
- If specific keys are missing in Vault, falls back to environment variables and defaults
- All failures are logged with appropriate warning messages
- Services continue to work even when Vault is down

## Configuration Validation

All configuration classes use Pydantic for validation:
- Type checking at runtime
- Custom validators for ML-specific parameters
- Clear error messages for invalid configurations
- Automatic conversion where appropriate

## Status and Debugging

Each configuration instance provides debugging information:

```python
config = get_config()
status = config.get_vault_status()
# Returns:
# {
#     "service": "your-service",
#     "vault_loader_available": True,
#     "vault_loaded": True,
#     "keys": ["KEY1", "KEY2", ...],  # First 10 keys
#     "total_keys": 25
# }
```

## Best Practices

1. **Service Naming**: Use consistent service names that match your Vault paths
2. **Parameter Validation**: Add appropriate validators for ML-specific parameters
3. **Environment Overrides**: Always allow environment variable overrides for flexibility
4. **Default Values**: Provide sensible defaults for all parameters
5. **Documentation**: Document your service-specific configuration parameters
6. **Testing**: Test configuration loading with and without Vault

## Example Services

See `example_service_config.py` for a complete example of how to implement service-specific configuration using this framework.
