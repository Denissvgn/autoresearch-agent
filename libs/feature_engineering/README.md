# Feature Engineering Library

**Version:** 1.0.0  
**Purpose:** Shared feature engineering library for ML training and serving to eliminate train/serve skew.

## Overview

This library provides a single source of truth for feature computation, ensuring identical features are generated during training (ensemble-trainer) and serving (Feature Service → inference-service).

## Key Components

- **Indicators (`core/indicators.py`):** Modular technical indicator calculations (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, volume, price changes, volatility)
- **Spec Generation (`spec/generator.py`):** Generate `feature_spec.json` with metadata (names, dtypes, lookbacks, version)
- **Spec Hashing (`spec/hasher.py`):** Deterministic `feature_spec_hash` for reproducibility validation
- **Version Management (`version.py`):** Library version tracking for lineage
- **Builders (`builders/`):** High-level builders for direction/volatility features

## Installation

### Development (editable install)
```bash
cd libs/feature_engineering
pip install -e .
```

### Production (Docker)
```dockerfile
# In Dockerfile
COPY libs/feature_engineering /app/libs/feature_engineering
RUN pip install /app/libs/feature_engineering
```

## Usage

### Basic Feature Computation
```python
from feature_engineering import FeatureEngineer, FeatureConfig
import pandas as pd

# Configure features
config = FeatureConfig(
    sma_periods=[5, 10, 20, 50],
    ema_periods=[5, 10, 20, 50],
    rsi_periods=[14, 21],
)

# Compute features
engineer = FeatureEngineer(config)
df_with_features = engineer.calculate_all_features(ohlcv_df)
```

### Generate Feature Spec
```python
from feature_engineering.spec import generate_feature_spec, compute_feature_spec_hash

# Generate spec
spec = generate_feature_spec(
    feature_names=list(df_with_features.columns),
    config=config,
    library_version="1.0.0"
)

# Compute hash for validation
spec_hash = compute_feature_spec_hash(spec)
print(f"Feature Spec ID: {spec['feature_spec_id']}")
print(f"Feature Spec Hash: {spec_hash}")
```

### Validate Feature Consistency
```python
from feature_engineering.validation import validate_feature_consistency

# Compare library output to legacy output
is_consistent, diff = validate_feature_consistency(
    library_features=df_library,
    legacy_features=df_legacy,
    tolerance=1e-6
)

if not is_consistent:
    print(f"Feature mismatch: {diff}")
```

## Feature Spec Schema

```json
{
  "feature_spec_id": "f_v1.0.0_20241104_abc123",
  "feature_spec_version": "1.0",
  "library_version": "1.0.0",
  "feature_names": ["close", "sma_10", "rsi_14", ...],
  "feature_count": 87,
  "feature_dtypes": {"close": "float64", "sma_10": "float64", ...},
  "indicator_lookbacks": {"sma_10": 10, "rsi_14": 14, ...},
  "max_lookback": 50,
  "config_hash": "sha256:...",
  "created_at": "2024-11-04T12:00:00Z"
}
```

## Versioning Strategy

- **Library Version (`1.0.0`):** Semantic versioning for code changes
- **Feature Spec Version (`1.0`):** Schema version for spec JSON
- **Feature Spec ID:** Unique identifier combining version, timestamp, config hash
- **Feature Spec Hash:** SHA256 of ordered feature names + dtypes + version

## Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=feature_engineering tests/

# Benchmark performance
pytest tests/test_performance.py -v
```

## Integration

### Trainer (ensemble-trainer)
```python
# In training config
config = {
    "use_shared_feature_library": True,
    "feature_library_version": "1.0.0",
    "feature_spec_id_override": None,  # Auto-generate
    "log_feature_provenance": True,
}
```

### Feature Service
```python
# In Feature Service
from feature_engineering import FeatureEngineer, LIBRARY_VERSION

engineer = FeatureEngineer(config)
features = engineer.calculate_all_features(ohlcv_df)

# Include in API response
response = {
    "features": features.to_dict(),
    "feature_spec_id": spec["feature_spec_id"],
    "feature_spec_hash": compute_feature_spec_hash(spec),
    "feature_service_version": LIBRARY_VERSION,
}
```

## Rollout Plan

See `docs/sprint2_rollout.md` for detailed rollout phases.

**Phase 1:** Library development and testing (Week 1)  
**Phase 2:** Trainer integration with flag=False (Week 2)  
**Phase 3:** Side-by-side validation (Week 3)  
**Phase 4:** Canary rollout (Week 4)  
**Phase 5:** Full rollout and legacy deprecation (Week 5+)

## Backward Compatibility

- Legacy feature computation remains available via flag `use_shared_feature_library=False`
- Consistency validation detects differences during transition
- No breaking changes to existing APIs

## Contributing

See `CONTRIBUTING.md` for development guidelines.

## License

Internal use only - Traid Platform ML Engineering
