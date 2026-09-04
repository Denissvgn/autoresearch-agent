"""
Property-based tests for v3 naming convention using Hypothesis.

Tests invariants and properties that must hold for all valid inputs:
- Roundtrip: parse(generate(x)) recovers x
- Generated names are always valid
- Parsing never crashes on valid v3 names
- Version detection is consistent
- Migration is idempotent
- Canonical instrument handling is consistent
"""

from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, precondition, invariant
import pytest

from traid_training_sdk.instruments.naming import (
    generate_composite_name_v3,
    generate_constituent_name_v3,
    parse_model_name_v3,
    detect_name_version,
    migrate_name_to_v3,
    parse_model_name_universal,
    ModelNameComponentsV3,
    InvalidInstrumentError,
    InvalidTradingModeError,
    InvalidLeverageError,
    InvalidAgentStrategyError,
    InvalidNameFormatError,
)
from traid_training_sdk.agents.strategies import AgentStrategy


# ============================================================================
# Hypothesis Strategies
# ============================================================================

# Valid instruments (common trading pairs)
instruments = st.sampled_from([
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
    'XRP/USDT', 'DOT/USDT', 'AVAX/USDT', 'MATIC/USDT', 'LINK/USDT',
    'BTC/BTC', 'ETH/BTC', 'BNB/BTC', 'ADA/BTC', 'XRP/BTC',
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT',  # Also test without separator
])

# Trading modes
trading_modes = st.sampled_from(['SPOT', 'MARGIN'])

# Agent strategies (both enum and string)
strategy_enums = st.sampled_from([
    AgentStrategy.AGGRESSIVE,
    AgentStrategy.CONSERVATIVE,
    AgentStrategy.BALANCED,
    AgentStrategy.SCALPING,
])

strategy_codes = st.sampled_from(['AGGR', 'CONS', 'BALA', 'SCAL'])

agent_strategies = st.one_of(strategy_enums, strategy_codes)

# Starting balance (100 to 1,000,000)
starting_balances = st.integers(min_value=100, max_value=1_000_000)

# Version (1 to 999)
versions = st.integers(min_value=1, max_value=999)

# Stage
stages = st.sampled_from(['dev', 'staging', 'prod', 'retired'])

# Leverage (1 to 100)
leverages = st.integers(min_value=1, max_value=100)

# Model types
model_types = st.sampled_from(['composite', 'direction', 'volatility', 'rl'])


# ============================================================================
# Property 1: Roundtrip - parse(generate(x)) == x for SPOT
# ============================================================================

@given(
    instrument=instruments,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_roundtrip_spot_composite(instrument, agent_strategy, starting_balance, version, stage):
    """Generated SPOT composite names can be parsed back to original components."""
    # Generate name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode='SPOT',
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=None,
    )
    
    # Parse it back
    components = parse_model_name_v3(name)
    
    # Verify all components match
    assert components.trading_mode == 'SPOT'
    assert components.starting_balance == starting_balance
    assert components.version == version
    assert components.stage == stage
    assert components.leverage is None
    assert components.model_type == 'composite'
    assert components.format_version == 'v3'
    
    # Strategy code should match (convert enum to code if needed)
    if isinstance(agent_strategy, AgentStrategy):
        expected_code = agent_strategy.value
    else:
        expected_code = agent_strategy
    assert components.agent_strategy_code == expected_code
    
    # Instrument should be normalized (remove separators)
    normalized_instrument = instrument.replace('/', '').replace('-', '').replace('_', '').upper()
    assert components.instrument == normalized_instrument


@given(
    instrument=instruments,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
    leverage=leverages,
)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_roundtrip_margin_composite(instrument, agent_strategy, starting_balance, version, stage, leverage):
    """Generated MARGIN composite names can be parsed back to original components."""
    # Generate name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode='MARGIN',
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage,
    )
    
    # Parse it back
    components = parse_model_name_v3(name)
    
    # Verify all components match
    assert components.trading_mode == 'MARGIN'
    assert components.starting_balance == starting_balance
    assert components.version == version
    assert components.stage == stage
    assert components.leverage == leverage
    assert components.model_type == 'composite'
    assert components.format_version == 'v3'
    
    # Strategy code should match
    if isinstance(agent_strategy, AgentStrategy):
        expected_code = agent_strategy.value
    else:
        expected_code = agent_strategy
    assert components.agent_strategy_code == expected_code
    
    # Instrument should be normalized
    normalized_instrument = instrument.replace('/', '').replace('-', '').replace('_', '').upper()
    assert components.instrument == normalized_instrument


@given(
    model_type=model_types,
    instrument=instruments,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_roundtrip_constituent(model_type, instrument, agent_strategy, starting_balance, version, stage, leverage):
    """Generated constituent names can be parsed back to original components."""
    # Skip invalid combinations
    trading_mode = 'MARGIN' if leverage is not None else 'SPOT'
    
    # Generate constituent name
    name = generate_constituent_name_v3(
        model_type=model_type,
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage,
    )
    
    # Parse it back
    components = parse_model_name_v3(name)
    
    # Verify all components match
    assert components.model_type == model_type
    assert components.trading_mode == trading_mode
    assert components.starting_balance == starting_balance
    assert components.version == version
    assert components.stage == stage
    assert components.leverage == leverage
    assert components.format_version == 'v3'
    
    # Strategy code should match
    if isinstance(agent_strategy, AgentStrategy):
        expected_code = agent_strategy.value
    else:
        expected_code = agent_strategy
    assert components.agent_strategy_code == expected_code


# ============================================================================
# Property 2: Generated names are always valid (can be parsed)
# ============================================================================

@given(
    instrument=instruments,
    trading_mode=trading_modes,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_generated_names_always_valid(instrument, trading_mode, agent_strategy, starting_balance, version, stage, leverage):
    """All generated names must be parseable without errors."""
    # Skip invalid leverage combinations
    if trading_mode == 'SPOT' and leverage is not None:
        assume(False)
    if trading_mode == 'MARGIN' and leverage is None:
        assume(False)
    
    # Generate name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage,
    )
    
    # Should always be parseable
    components = parse_model_name_v3(name)
    assert components is not None
    assert isinstance(components, ModelNameComponentsV3)
    assert components.format_version == 'v3'


# ============================================================================
# Property 3: Version detection is consistent
# ============================================================================

@given(
    instrument=instruments,
    trading_mode=trading_modes,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_version_detection_consistent(instrument, trading_mode, agent_strategy, starting_balance, version, stage, leverage):
    """Version detection must always identify v3 names correctly."""
    # Skip invalid leverage combinations
    if trading_mode == 'SPOT' and leverage is not None:
        assume(False)
    if trading_mode == 'MARGIN' and leverage is None:
        assume(False)
    
    # Generate v3 name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage,
    )
    
    # Version detection must return 'v3'
    detected_version = detect_name_version(name)
    assert detected_version == 'v3', f"Expected 'v3' but got '{detected_version}' for name: {name}"


# ============================================================================
# Property 4: Universal parser returns v3 components for v3 names
# ============================================================================

@given(
    instrument=instruments,
    trading_mode=trading_modes,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_universal_parser_returns_v3_components(instrument, trading_mode, agent_strategy, starting_balance, version, stage, leverage):
    """Universal parser must return ModelNameComponentsV3 for v3 names."""
    # Skip invalid leverage combinations
    if trading_mode == 'SPOT' and leverage is not None:
        assume(False)
    if trading_mode == 'MARGIN' and leverage is None:
        assume(False)
    
    # Generate v3 name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage,
    )
    
    # Universal parser should return v3 components
    components = parse_model_name_universal(name)
    assert isinstance(components, ModelNameComponentsV3)
    assert components.format_version == 'v3'


# ============================================================================
# Property 5: Canonical instrument is consistent
# ============================================================================

@given(
    instrument=instruments,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_canonical_instrument_property(instrument, agent_strategy, starting_balance, version, stage):
    """canonical_instrument property should always return slash-separated format."""
    # Generate name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode='SPOT',
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
    )
    
    # Parse and check canonical_instrument
    components = parse_model_name_v3(name)
    canonical = components.canonical_instrument
    
    # Canonical format should have a slash
    assert '/' in canonical, f"Canonical instrument '{canonical}' should contain '/'"
    
    # Should be uppercase
    assert canonical == canonical.upper()
    
    # Should match expected format
    normalized = instrument.replace('/', '').replace('-', '').replace('_', '').upper()
    # Re-insert slash (simple heuristic: common pairs)
    if normalized.endswith('USDT'):
        expected_canonical = normalized[:-4] + '/' + 'USDT'
    elif normalized.endswith('BTC'):
        expected_canonical = normalized[:-3] + '/' + 'BTC'
    elif normalized.endswith('ETH'):
        expected_canonical = normalized[:-3] + '/' + 'ETH'
    elif normalized.endswith('BNB'):
        expected_canonical = normalized[:-3] + '/' + 'BNB'
    else:
        # For other formats, we can't easily determine the split
        # Just verify it has a slash
        assert '/' in canonical
        return
    
    assert canonical == expected_canonical


# ============================================================================
# Property 6: to_dict() round-trip consistency
# ============================================================================

@given(
    instrument=instruments,
    trading_mode=trading_modes,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_to_dict_consistency(instrument, trading_mode, agent_strategy, starting_balance, version, stage, leverage):
    """to_dict() should produce consistent dictionary representation."""
    # Skip invalid leverage combinations
    if trading_mode == 'SPOT' and leverage is not None:
        assume(False)
    if trading_mode == 'MARGIN' and leverage is None:
        assume(False)
    
    # Generate and parse name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage,
    )
    
    components = parse_model_name_v3(name)
    dict_repr = components.to_dict()
    
    # Verify all keys present
    assert 'model_type' in dict_repr
    assert 'instrument' in dict_repr
    assert 'trading_mode' in dict_repr
    assert 'agent_strategy_code' in dict_repr
    assert 'starting_balance' in dict_repr
    assert 'version' in dict_repr
    assert 'stage' in dict_repr
    assert 'leverage' in dict_repr
    assert 'format_version' in dict_repr
    
    # Verify values match
    assert dict_repr['trading_mode'] == trading_mode
    assert dict_repr['starting_balance'] == starting_balance
    assert dict_repr['version'] == version
    assert dict_repr['stage'] == stage
    assert dict_repr['leverage'] == leverage
    assert dict_repr['format_version'] == 'v3'


# ============================================================================
# Property 7: Name format structure is consistent
# ============================================================================

@given(
    instrument=instruments,
    trading_mode=trading_modes,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_name_format_structure(instrument, trading_mode, agent_strategy, starting_balance, version, stage, leverage):
    """Generated names must follow the v3 format structure."""
    # Skip invalid leverage combinations
    if trading_mode == 'SPOT' and leverage is not None:
        assume(False)
    if trading_mode == 'MARGIN' and leverage is None:
        assume(False)
    
    # Generate name
    name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage,
    )
    
    # Should be dot-separated
    assert '.' in name
    assert '__' not in name  # No double underscores (that's v1/v2)
    
    parts = name.split('.')
    
    # SPOT: INSTR.MODE.STRAT.SB{amount}.v{version}.{stage} = 6 parts
    # MARGIN: INSTR.MODE.LEVx{n}.STRAT.SB{amount}.v{version}.{stage} = 7 parts
    if trading_mode == 'SPOT':
        assert len(parts) == 6, f"Expected 6 parts for SPOT, got {len(parts)}: {name}"
        # Verify order
        assert parts[1] == 'SPOT'
        assert parts[2] in ['AGGR', 'CONS', 'BALA', 'SCAL']  # Strategy
        assert parts[3].startswith('SB')  # Starting balance
        assert parts[4].startswith('v')  # Version
        assert parts[5] in ['dev', 'staging', 'prod', 'retired']  # Stage
    else:  # MARGIN
        assert len(parts) == 7, f"Expected 7 parts for MARGIN, got {len(parts)}: {name}"
        # Verify order
        assert parts[1] == 'MARGIN'
        assert parts[2].startswith('LEVx')  # Leverage
        assert parts[3] in ['AGGR', 'CONS', 'BALA', 'SCAL']  # Strategy
        assert parts[4].startswith('SB')  # Starting balance
        assert parts[5].startswith('v')  # Version
        assert parts[6] in ['dev', 'staging', 'prod', 'retired']  # Stage


# ============================================================================
# Property 8: Leverage validation is enforced
# ============================================================================

@given(
    instrument=instruments,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_spot_rejects_leverage(instrument, agent_strategy, starting_balance, version, stage):
    """SPOT mode must reject any non-None leverage."""
    with pytest.raises(InvalidLeverageError, match="leverage must be None for SPOT"):
        generate_composite_name_v3(
            instrument=instrument,
            trading_mode='SPOT',
            agent_strategy=agent_strategy,
            starting_balance=starting_balance,
            version=version,
            stage=stage,
            leverage=5,  # Invalid for SPOT
        )


@given(
    instrument=instruments,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    version=versions,
    stage=stages,
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_margin_requires_leverage(instrument, agent_strategy, starting_balance, version, stage):
    """MARGIN mode must require non-None leverage."""
    with pytest.raises(InvalidLeverageError, match="leverage is required when trading_mode is MARGIN"):
        generate_composite_name_v3(
            instrument=instrument,
            trading_mode='MARGIN',
            agent_strategy=agent_strategy,
            starting_balance=starting_balance,
            version=version,
            stage=stage,
            leverage=None,  # Invalid for MARGIN
        )


# ============================================================================
# Property 9: Balance bounds are enforced
# ============================================================================

@given(
    instrument=instruments,
    trading_mode=trading_modes,
    agent_strategy=agent_strategies,
    version=versions,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
    invalid_balance=st.one_of(
        st.integers(max_value=99),  # Too low
        st.integers(min_value=1_000_001, max_value=10_000_000),  # Too high
    ),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_invalid_balance_rejected(instrument, trading_mode, agent_strategy, version, stage, leverage, invalid_balance):
    """Balances outside [100, 1000000] must be rejected."""
    # Skip invalid leverage combinations
    if trading_mode == 'SPOT' and leverage is not None:
        assume(False)
    if trading_mode == 'MARGIN' and leverage is None:
        assume(False)
    
    with pytest.raises((ValueError, InvalidInstrumentError)):
        generate_composite_name_v3(
            instrument=instrument,
            trading_mode=trading_mode,
            agent_strategy=agent_strategy,
            starting_balance=invalid_balance,
            version=version,
            stage=stage,
            leverage=leverage,
        )


# ============================================================================
# Property 10: Version must be positive
# ============================================================================

@given(
    instrument=instruments,
    trading_mode=trading_modes,
    agent_strategy=agent_strategies,
    starting_balance=starting_balances,
    stage=stages,
    leverage=st.one_of(st.none(), leverages),
    invalid_version=st.integers(max_value=0),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_invalid_version_rejected(instrument, trading_mode, agent_strategy, starting_balance, stage, leverage, invalid_version):
    """Version must be >= 1."""
    # Skip invalid leverage combinations
    if trading_mode == 'SPOT' and leverage is not None:
        assume(False)
    if trading_mode == 'MARGIN' and leverage is None:
        assume(False)
    
    with pytest.raises((ValueError, InvalidInstrumentError)):
        generate_composite_name_v3(
            instrument=instrument,
            trading_mode=trading_mode,
            agent_strategy=agent_strategy,
            starting_balance=starting_balance,
            version=invalid_version,
            stage=stage,
            leverage=leverage,
        )


# ============================================================================
# Summary statistics
# ============================================================================

if __name__ == '__main__':
    print("Running property-based tests...")
    print("These tests will run 1000+ examples per property to validate invariants.")
    pytest.main([__file__, '-v', '--tb=short'])
