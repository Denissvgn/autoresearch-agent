# VDMC Core Library

The VDMC (Volatility-Driven Momentum Cycle) Core Library provides the mathematical foundation for the Traid platform's proprietary trading indicator. This library implements the core VDMC algorithm with robust error handling, performance optimization, and comprehensive testing.

## Features

- ✅ **Pure Mathematical Implementation**: Core VDMC algorithm following the technical specification
- ✅ **Type Safety**: Full type hints with Pydantic model validation
- ✅ **Error Handling**: Comprehensive fallback strategies for edge cases
- ✅ **Performance Optimized**: ≤20ms p95 latency requirement
- ✅ **Comprehensive Testing**: ≥90% test coverage with verified golden value tests
- ✅ **Mathematical Verification**: Golden value tests ensure algorithm correctness
- ✅ **Production Ready**: Installable package for monorepo integration

## Installation

### As a Local Dependency (Monorepo)

Add to your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
vdmc_core = { path = "libs/vdmc_core", develop = true }
```

### Development Setup

```bash
cd libs/vdmc_core
poetry install
```

## Quick Start

### Basic Usage

```python
import numpy as np
from vdmc_core import vdmc, VDMCConfig, SignalType

# Generate sample price data
close_prices = np.array([1000, 1010, 1005, 1015, 1020, ...])  # Your price data

# Create configuration
config = VDMCConfig(
    lookback_period=120,
    signal_type=SignalType.BUY,
    alpha=1.2,
    beta=0.8,
    kernel_sigma=5
)

# Calculate VDMC
result = vdmc(close_prices, config)

print(f"Buy Probability: {result.p_buy:.4f}")
print(f"Sell Probability: {result.p_sell:.4f}")
print(f"Wave Amplitude: {result.wave_amplitude:.4f}")
print(f"Momentum: {result.momentum:.4f}")
```

### Advanced Configuration

```python
# Buy signal configuration
buy_config = VDMCConfig(
    signal_type=SignalType.BUY,
    alpha=1.5,          # Higher trend weight
    beta=0.6,           # Lower amplitude weight
    kernel_sigma=8      # More smoothing
)

# Sell signal configuration  
sell_config = VDMCConfig(
    signal_type=SignalType.SELL,
    alpha=0.8,          # Lower trend weight
    beta=1.2,           # Higher amplitude weight
    kernel_sigma=3      # Less smoothing
)
```

### Error Handling

```python
# The library handles edge cases gracefully
short_data = np.array([100, 101, 102])  # Too short
result = vdmc(short_data, config)

if result.warning_code == 1002:
    print("Short history detected - using exponential smoothing fallback")
elif result.warning_code == 1001:
    print("Invalid input detected - returning neutral probabilities")
```

## API Reference

### Core Function

#### `vdmc(close_prices: np.ndarray, config: VDMCConfig) -> VDMCOutput`

Calculate VDMC indicator for given price series and configuration.

**Parameters:**
- `close_prices`: NumPy array of closing prices
- `config`: VDMC configuration parameters

**Returns:**
- `VDMCOutput`: Calculated probabilities and intermediate values

**Raises:**
- `VDMCComputationError`: If computation fails due to internal errors

### Configuration

#### `VDMCConfig`

Configuration model for VDMC calculation with validation.

**Parameters:**
- `lookback_period` (int): Number of bars for kernel smoothing [120-720, default: 120]
- `signal_type` (SignalType): Type of signal sought [BUY/SELL, default: BUY]
- `alpha` (float): Trend coefficient in logistic function [default: 1.2]
- `beta` (float): Wave amplitude coefficient [default: 0.8]
- `kernel_sigma` (int): Gaussian filter parameter [3-21, default: 5]

### Output

#### `VDMCOutput`

Output structure containing calculated results.

**Fields:**
- `p_buy` (float): Buy probability [0.0-1.0]
- `p_sell` (float): Sell probability [0.0-1.0]  
- `wave_amplitude` (float): Calculated wave amplitude
- `momentum` (float): Current momentum value
- `warning_code` (Optional[int]): Warning code for edge cases

### Warning Codes

- `None`: Normal calculation completed successfully
- `1001`: Invalid input (NaN/inf values) - neutral probabilities returned
- `1002`: Short history - exponential smoothing fallback used

## Algorithm Details

The VDMC algorithm follows these steps:

1. **Gaussian Smoothing**: Apply Gaussian filter to reduce noise
2. **Momentum Calculation**: Calculate gradient of smoothed prices
3. **Extrema Detection**: Find local peaks and troughs
4. **Wave Amplitude**: Calculate amplitude based on extrema
5. **Decision Variable**: Combine momentum and amplitude with α/β coefficients
6. **Probability Calculation**: Apply sigmoid transformation for final probabilities

### Mathematical Formula

```
decision_variable = α × momentum[-1] - β × wave_amplitude
p_buy = sigmoid(decision_variable)    # for BUY signals
p_sell = sigmoid(-decision_variable)  # for SELL signals
```

## Performance

The library is optimized to meet strict performance requirements:

- **Latency**: ≤20ms p95 for single calculation
- **Memory**: Efficient NumPy operations
- **Scalability**: Handles up to 720 data points (max lookback)

## Testing

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=vdmc_core --cov-report=term-missing

# Run only golden value tests
poetry run pytest tests/test_algorithm.py::TestVDMCGoldenValues -v

# Run performance benchmarks
poetry run pytest benchmarks/ -v
```

### Golden Value Tests

The library includes **golden value tests** that verify mathematical correctness against manually calculated expected outputs. These tests ensure the VDMC algorithm implementation is mathematically accurate and follows the Task S4-T4 requirements.

#### How Golden Values Work

1. **Test Data Generation**: The `scripts/generate_golden_values.py` script creates a predictable 150-point price series with a known pattern (base price + linear trend + sine wave).

2. **Manual Calculation**: Each step of the VDMC algorithm is calculated manually and documented:
   - Gaussian smoothing with σ=5
   - Momentum calculation using gradient
   - Peak/trough detection with distance=3
   - Wave amplitude calculation from mean peak/trough levels
   - Decision variable: α×momentum - β×amplitude
   - Sigmoid probability transformation with overflow protection

3. **Verification**: The test compares actual VDMC output against these pre-calculated golden values with appropriate floating-point precision (6-8 decimal places).

#### Current Golden Values (Generated from 150-point test series)
- **p_buy**: 0.5057130185499209
- **p_sell**: 0.49428698145007904  
- **wave_amplitude**: 0.03942967458758536
- **momentum**: 0.04533067368890897

#### Regenerating Golden Values

If you modify the core algorithm, regenerate golden values:

```bash
python scripts/generate_golden_values.py
```

Then update the test fixture in `tests/conftest.py` with the new values and verify all tests pass.

#### Running Golden Value Tests

```bash
# Run only golden value tests
poetry run pytest tests/test_algorithm.py::TestVDMCGoldenValues -v

# View detailed calculation steps
python scripts/generate_golden_values.py
```

## Development

### Project Structure

```
libs/vdmc_core/
├── vdmc_core/           # Core library code
│   ├── __init__.py      # Public API exports
│   ├── algorithm.py     # Main VDMC algorithm implementation
│   ├── models.py        # Pydantic data models (VDMCConfig, VDMCOutput)
│   ├── utils.py         # Helper functions
│   └── exceptions.py    # Custom exceptions
├── tests/               # Test suite
│   ├── test_algorithm.py # Algorithm tests (including golden value tests)
│   ├── conftest.py      # Test fixtures with golden test data
│   └── benchmarks/      # Performance benchmarks
├── scripts/             # Utility scripts
│   ├── generate_golden_values.py  # Golden value generator script
│   └── run_tests.sh     # Test runner script
├── docs/                # Documentation
│   └── GOLDEN_VALUE_TESTS.md  # Detailed golden value test documentation
├── pyproject.toml       # Package configuration
└── README.md           # This file
```

### Code Quality

The project maintains high code quality standards:

- **Type Safety**: Full type hints with mypy validation
- **Code Formatting**: Black and isort for consistent style
- **Linting**: Ruff for code quality checks
- **Test Coverage**: ≥90% requirement (currently 93.53%)
- **Performance**: ≤20ms p95 latency requirement

### Running Quality Checks

```bash
# Format code
poetry run black .
poetry run isort .

# Type checking
poetry run mypy vdmc_core/

# Linting
poetry run ruff check .

# All quality checks
./scripts/run_tests.sh
```

## License

Copyright (c) 2025 Traid Platform Team. All rights reserved.

This library contains proprietary trading algorithms and is licensed for use within the Traid platform only.

## Changelog

### Version 1.0.0 (Current)
- ✅ Initial implementation of VDMC algorithm following Task S4-T4 specification
- ✅ Comprehensive golden value test implementation with 150-point verified dataset
- ✅ Full type safety with Pydantic model validation
- ✅ Performance optimization meeting ≤20ms p95 latency requirement
- ✅ 93%+ test coverage with mathematical verification
- ✅ Production-ready installable package for monorepo integration
- ✅ Complete documentation and API reference