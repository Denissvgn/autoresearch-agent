# Golden Value Generation Scripts

This directory contains utility scripts for the VDMC core library.

## Scripts

### `generate_golden_values.py`

**Purpose**: Generates mathematically verified golden values for VDMC algorithm testing.

**What it does**:
1. Creates a deterministic 150-point price series (base + trend + sine wave)
2. Manually calculates each step of the VDMC algorithm with full documentation
3. Outputs verified expected values for use in golden value tests
4. Provides step-by-step calculation verification for transparency

**Usage**:
```bash
# Generate golden values with detailed output
python scripts/generate_golden_values.py

# Example output:
🌟 VDMC Golden Value Generator
========================================

🔍 Manual VDMC Calculation for Golden Values
==================================================
📊 Input Data:
   Close prices: [100.0, 100.084, 100.334, ...]
   Length: 150
   Config: {'lookback_period': 120, 'kernel_sigma': 5, ...}

🔧 Step 1: Gaussian Smoothing
   Smoothed prices: [100.002, 100.085, 100.333, ...]

📈 Step 2: Momentum Calculation  
   Momentum array: [0.083, 0.248, 0.411, ...]
   Current momentum: 0.04533067368890897

🏔️ Step 3: Find Peaks and Troughs
   Peak indices: [37, 112, 149]
   Trough indices: [74]
   ...

✅ Golden Values Generated:
   p_buy: 0.5057130185499209
   p_sell: 0.49428698145007904
   wave_amplitude: 0.03942967458758536
   momentum: 0.04533067368890897
```

**When to run**:
- After modifying the core VDMC algorithm
- When updating test parameters
- For verification of mathematical correctness
- To regenerate test fixtures

**Integration**:
After running this script, copy the generated values to `tests/conftest.py` and verify all tests pass.

### `run_tests.sh`

**Purpose**: Convenient test runner script with coverage and quality checks.

**Usage**:
```bash
# Run all tests with coverage
./scripts/run_tests.sh

# Or manually:
poetry run pytest --cov=vdmc_core --cov-report=term-missing
```

## Development Workflow

1. **Modify Algorithm**: Make changes to `vdmc_core/algorithm.py`
2. **Regenerate Golden Values**: Run `python scripts/generate_golden_values.py`
3. **Update Test Fixture**: Copy new values to `tests/conftest.py`
4. **Verify Tests**: Run `poetry run pytest tests/test_algorithm.py::TestVDMCGoldenValues -v`
5. **Update Documentation**: Update expected values in README and docs

## Quality Assurance

The golden value generation process ensures:
- **Mathematical Accuracy**: Step-by-step manual calculation verification
- **Reproducibility**: Deterministic test data and expected outputs
- **Transparency**: Full documentation of calculation process
- **Regression Protection**: Immediate detection of algorithm changes

This approach provides confidence that the VDMC implementation correctly follows the technical specification and maintains mathematical accuracy across code changes.
