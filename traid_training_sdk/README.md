# Traid Training SDK

Shared SDK for training and inference in the Traid Platform.

## Overview

The Traid Training SDK provides automated machine learning model training with hyperparameter optimization, feature parameter auto-tuning, and integrated model registry management for trading applications.

## Key Features

- **Automated Hyperparameter Tuning**: Random search with configurable trials, timeouts, and objectives
- **Feature Parameter Auto-Tuning**: Joint optimization of feature engineering parameters alongside model hyperparameters
- **Population-Based Training (PBT)**: Advanced optimization that perturbs best-performing models
- **Multi-Model Support**: Sklearn, PyTorch MLP, and RL (PPO) models
- **Unified Pipeline**: Chains feature generation with model training for reproducible inference
- **Model Registry**: Filesystem-based versioned model storage with stage promotion
- **Trading Metrics**: Sharpe, Sortino, Max Drawdown, PnL, Hit Rate

## Quick Start

```python
from traid_training_sdk.core.client import TraidClient

client = TraidClient.from_env()

result = client.autotrain(
    instrument="BTC/USDT",
    timeframe="M15",
    bars=5000,
    objective="sharpe",
    budget={
        "trials": 50,
        "timeout": 3600,
        "enable_pbt": True,
    },
)

print(f"Model URI: {result['model_uri']}")
print(f"Metrics: {result['metrics']}")
```

## Documentation

For comprehensive documentation, see:

- **[Full SDK Guide](../docs/TRAID_TRAINING_SDK_GUIDE.md)** - Complete documentation with examples
- [Configuration Guide](../docs/CONFIGURATION_GUIDE.md)
- [ML Compliance Guide](../docs/ML_COMPLIANCE_VERIFICATION_GUIDE.md)

## Module Structure

```
traid_training_sdk/
├── agents/            # Agent strategy definitions
├── cli/               # Command-line interface
├── core/              # Client, config, context, errors
├── data/              # Data loading, transforms, RL datasets
├── eval/              # Metrics, validation, backtesting
├── indicators/        # VDMC configuration
├── instruments/       # Symbol/instrument handling
├── integrations/      # External service integrations
├── io/                # Artifacts, serialization
├── models/            # Model implementations
├── observability/     # Metrics, events, logging
├── plugins/           # Plugin system
├── registry/          # Model registry
├── security/          # Secrets management
├── tracking/          # Experiment tracking
└── train/             # Training core
```

## Requirements

- Python 3.10+
- scikit-learn
- numpy, pandas
- pydantic
- joblib

### Optional

- PyTorch (for MLP models)
- stable-baselines3 (for RL training)
- Ray (for distributed tuning)
