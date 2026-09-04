"""
Comprehensive unit tests for v3 naming convention.

Tests cover:
- generate_composite_name_v3()
- generate_constituent_name_v3()
- parse_model_name_v3()
- Version detection
- Migration utilities
- Error handling
"""

import pytest
from traid_training_sdk.agents.strategies import AgentStrategy
from traid_training_sdk.instruments.naming import (
    # v3 functions
    generate_composite_name_v3,
    generate_constituent_name_v3,
    parse_model_name_v3,
    ModelNameComponentsV3,
    detect_name_version,
    can_migrate_automatically,
    migrate_name_to_v3,
    parse_model_name_universal,
    # Exceptions
    InvalidInstrumentError,
    InvalidTradingModeError,
    InvalidLeverageError,
    InvalidAgentStrategyError,
    InvalidNameFormatError,
)


# =============================================================================
# Test generate_composite_name_v3() - SPOT Mode
# =============================================================================


class TestGenerateCompositeNameV3Spot:
    """Test v3 composite name generation for SPOT mode."""
    
    def test_basic_spot_aggressive(self):
        """Test basic SPOT mode with AGGRESSIVE strategy."""
        name = generate_composite_name_v3(
            instrument='BTCUSDT',
            trading_mode='SPOT',
            agent_strategy=AgentStrategy.AGGRESSIVE,
            starting_balance=10000,
            version=1,
            stage='dev'
        )
        assert name == 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
    
    def test_spot_conservative(self):
        """Test SPOT mode with CONSERVATIVE strategy."""
        name = generate_composite_name_v3(
            instrument='ETH/USDT',
            trading_mode='SPOT',
            agent_strategy=AgentStrategy.CONSERVATIVE,
            starting_balance=50000,
            version=2,
            stage='prod'
        )
        assert name == 'ETHUSDT.SPOT.CONS.SB50000.v2.prod'
    
    def test_spot_balanced(self):
        """Test SPOT mode with BALANCED strategy."""
        name = generate_composite_name_v3(
            instrument='BNB-BTC',
            trading_mode='spot',  # lowercase
            agent_strategy='BALA',  # string code
            starting_balance=5000,
            version=1,
            stage='staging'
        )
        assert name == 'BNBBTC.SPOT.BALA.SB5000.v1.staging'
    
    def test_spot_scalping(self):
        """Test SPOT mode with SCALPING strategy."""
        name = generate_composite_name_v3(
            instrument='ADA_USDT',
            trading_mode='SPOT',
            agent_strategy=AgentStrategy.SCALPING,
            starting_balance=25000,
            version=3,
            stage='retired'
        )
        assert name == 'ADAUSDT.SPOT.SCAL.SB25000.v3.retired'
    
    def test_spot_with_leverage_raises(self):
        """Test that SPOT mode with leverage raises error."""
        with pytest.raises(InvalidLeverageError, match="leverage must be None for SPOT mode"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='SPOT',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='dev',
                leverage=5  # Not allowed for SPOT
            )


# =============================================================================
# Test generate_composite_name_v3() - MARGIN Mode
# =============================================================================


class TestGenerateCompositeNameV3Margin:
    """Test v3 composite name generation for MARGIN mode."""
    
    def test_margin_with_leverage_3x(self):
        """Test MARGIN mode with 3x leverage."""
        name = generate_composite_name_v3(
            instrument='BTCUSDT',
            trading_mode='MARGIN',
            agent_strategy=AgentStrategy.CONSERVATIVE,
            starting_balance=10000,
            version=1,
            stage='dev',
            leverage=3
        )
        assert name == 'BTCUSDT.MARGIN.LEVx3.CONS.SB10000.v1.dev'
    
    def test_margin_with_leverage_5x(self):
        """Test MARGIN mode with 5x leverage."""
        name = generate_composite_name_v3(
            instrument='ETH/USDT',
            trading_mode='MARGIN',
            agent_strategy='BALA',
            starting_balance=50000,
            version=2,
            stage='prod',
            leverage=5
        )
        assert name == 'ETHUSDT.MARGIN.LEVx5.BALA.SB50000.v2.prod'
    
    def test_margin_with_leverage_10x(self):
        """Test MARGIN mode with 10x leverage."""
        name = generate_composite_name_v3(
            instrument='BNB/USDT',
            trading_mode='margin',  # lowercase
            agent_strategy=AgentStrategy.AGGRESSIVE,
            starting_balance=25000,
            version=1,
            stage='staging',
            leverage=10
        )
        assert name == 'BNBUSDT.MARGIN.LEVx10.AGGR.SB25000.v1.staging'
    
    def test_margin_with_leverage_20x(self):
        """Test MARGIN mode with 20x leverage."""
        name = generate_composite_name_v3(
            instrument='SOLUSDT',
            trading_mode='MARGIN',
            agent_strategy=AgentStrategy.SCALPING,
            starting_balance=100000,
            version=5,
            stage='prod',
            leverage=20
        )
        assert name == 'SOLUSDT.MARGIN.LEVx20.SCAL.SB100000.v5.prod'
    
    def test_margin_without_leverage_raises(self):
        """Test that MARGIN mode without leverage raises error."""
        with pytest.raises(InvalidLeverageError, match="leverage is required when trading_mode is MARGIN"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='MARGIN',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='dev'
                # leverage missing
            )
    
    def test_margin_with_invalid_leverage_too_low(self):
        """Test MARGIN mode with leverage < 1."""
        with pytest.raises(InvalidLeverageError, match="leverage must be >= 1"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='MARGIN',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='dev',
                leverage=0
            )
    
    def test_margin_with_invalid_leverage_too_high(self):
        """Test MARGIN mode with leverage > 100."""
        with pytest.raises(InvalidLeverageError, match="leverage must be <= 100"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='MARGIN',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='dev',
                leverage=150
            )


# =============================================================================
# Test generate_composite_name_v3() - Parameter Validation
# =============================================================================


class TestGenerateCompositeNameV3Validation:
    """Test parameter validation in v3 name generation."""
    
    def test_invalid_instrument_empty(self):
        """Test empty instrument raises error."""
        with pytest.raises(InvalidInstrumentError):
            generate_composite_name_v3(
                instrument='',
                trading_mode='SPOT',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='dev'
            )
    
    def test_invalid_trading_mode(self):
        """Test invalid trading_mode raises error."""
        with pytest.raises(InvalidTradingModeError, match="Invalid trading_mode"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='FUTURES',  # Not supported
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='dev'
            )
    
    def test_invalid_agent_strategy_code(self):
        """Test invalid agent strategy code raises error."""
        with pytest.raises(InvalidAgentStrategyError):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='SPOT',
                agent_strategy='INVALID',  # Not a valid strategy
                starting_balance=10000,
                version=1,
                stage='dev'
            )
    
    def test_starting_balance_too_low(self):
        """Test starting_balance < 100 raises error."""
        with pytest.raises(ValueError, match="starting_balance must be >= 100"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='SPOT',
                agent_strategy='AGGR',
                starting_balance=50,
                version=1,
                stage='dev'
            )
    
    def test_starting_balance_too_high(self):
        """Test starting_balance > 1000000 raises error."""
        with pytest.raises(ValueError, match="starting_balance must be <= 1000000"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='SPOT',
                agent_strategy='AGGR',
                starting_balance=2000000,
                version=1,
                stage='dev'
            )
    
    def test_version_too_low(self):
        """Test version < 1 raises error."""
        with pytest.raises(ValueError, match="version must be >= 1"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='SPOT',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=0,
                stage='dev'
            )
    
    def test_invalid_stage(self):
        """Test invalid stage raises error."""
        with pytest.raises(ValueError, match="Invalid stage"):
            generate_composite_name_v3(
                instrument='BTCUSDT',
                trading_mode='SPOT',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='testing'  # Not a valid stage
            )


# =============================================================================
# Test generate_constituent_name_v3()
# =============================================================================


class TestGenerateConstituentNameV3:
    """Test v3 constituent model name generation."""
    
    def test_rl_constituent_spot(self):
        """Test RL constituent in SPOT mode."""
        name = generate_constituent_name_v3(
            model_type='rl',
            instrument='BTCUSDT',
            trading_mode='SPOT',
            agent_strategy='BALA',
            starting_balance=10000,
            version=1,
            stage='dev'
        )
        assert name == 'rl.BTCUSDT.SPOT.BALA.SB10000.v1.dev'
    
    def test_direction_constituent_margin(self):
        """Test direction constituent in MARGIN mode."""
        name = generate_constituent_name_v3(
            model_type='direction',
            instrument='ETH/USDT',
            trading_mode='MARGIN',
            agent_strategy=AgentStrategy.SCALPING,
            starting_balance=25000,
            version=3,
            stage='prod',
            leverage=10
        )
        assert name == 'direction.ETHUSDT.MARGIN.LEVx10.SCAL.SB25000.v3.prod'
    
    def test_volatility_constituent_spot(self):
        """Test volatility constituent in SPOT mode."""
        name = generate_constituent_name_v3(
            model_type='volatility',
            instrument='BNB/USDT',
            trading_mode='SPOT',
            agent_strategy='CONS',
            starting_balance=50000,
            version=2,
            stage='staging'
        )
        assert name == 'volatility.BNBUSDT.SPOT.CONS.SB50000.v2.staging'


# =============================================================================
# Test parse_model_name_v3()
# =============================================================================


class TestParseModelNameV3:
    """Test v3 model name parsing."""
    
    def test_parse_spot_composite(self):
        """Test parsing SPOT composite name."""
        name = 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        components = parse_model_name_v3(name)
        
        assert components.model_type == 'composite'
        assert components.instrument == 'BTCUSDT'
        assert components.trading_mode == 'SPOT'
        assert components.agent_strategy_code == 'AGGR'
        assert components.starting_balance == 10000
        assert components.version == 1
        assert components.stage == 'dev'
        assert components.leverage is None
        assert components.is_v3
    
    def test_parse_margin_composite(self):
        """Test parsing MARGIN composite name with leverage."""
        name = 'ETHUSDT.MARGIN.LEVx5.CONS.SB50000.v2.prod'
        components = parse_model_name_v3(name)
        
        assert components.model_type == 'composite'
        assert components.instrument == 'ETHUSDT'
        assert components.trading_mode == 'MARGIN'
        assert components.leverage == 5
        assert components.agent_strategy_code == 'CONS'
        assert components.starting_balance == 50000
        assert components.version == 2
        assert components.stage == 'prod'
    
    def test_parse_rl_constituent(self):
        """Test parsing RL constituent name."""
        name = 'rl.BTCUSDT.SPOT.BALA.SB25000.v3.staging'
        components = parse_model_name_v3(name)
        
        assert components.model_type == 'rl'
        assert components.instrument == 'BTCUSDT'
        assert components.agent_strategy_code == 'BALA'
        assert components.starting_balance == 25000
        assert components.version == 3
        assert components.stage == 'staging'
    
    def test_parse_direction_constituent_margin(self):
        """Test parsing direction constituent with leverage."""
        name = 'direction.SOLUSDT.MARGIN.LEVx10.SCAL.SB100000.v5.retired'
        components = parse_model_name_v3(name)
        
        assert components.model_type == 'direction'
        assert components.trading_mode == 'MARGIN'
        assert components.leverage == 10
        assert components.agent_strategy_code == 'SCAL'
    
    def test_parse_invalid_format_too_few_parts(self):
        """Test parsing name with too few parts."""
        with pytest.raises(InvalidNameFormatError, match="at least 6 components"):
            parse_model_name_v3('BTCUSDT.SPOT.AGGR')
    
    def test_parse_invalid_trading_mode(self):
        """Test parsing name with invalid trading mode."""
        with pytest.raises(InvalidNameFormatError, match="Invalid trading_mode"):
            parse_model_name_v3('BTCUSDT.FUTURES.AGGR.SB10000.v1.dev')
    
    def test_parse_margin_without_leverage(self):
        """Test parsing MARGIN name without leverage."""
        with pytest.raises(InvalidNameFormatError, match="Expected leverage"):
            parse_model_name_v3('BTCUSDT.MARGIN.AGGR.SB10000.v1.dev')
    
    def test_parse_spot_with_leverage(self):
        """Test parsing SPOT name with leverage (should fail)."""
        with pytest.raises(InvalidNameFormatError, match="Leverage not allowed for SPOT"):
            parse_model_name_v3('BTCUSDT.SPOT.LEVx5.AGGR.SB10000.v1.dev')
    
    def test_canonical_instrument_property(self):
        """Test canonical_instrument property."""
        name = 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        components = parse_model_name_v3(name)
        assert components.canonical_instrument == 'BTC/USDT'
        
        name2 = 'ETHUSDT.SPOT.CONS.SB50000.v2.prod'
        components2 = parse_model_name_v3(name2)
        assert components2.canonical_instrument == 'ETH/USDT'


# =============================================================================
# Test Version Detection
# =============================================================================


class TestDetectNameVersion:
    """Test version detection utility."""
    
    def test_detect_v3(self):
        """Test detection of v3 format."""
        name = 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        assert detect_name_version(name) == 'v3'
    
    def test_detect_v2(self):
        """Test detection of v2 format."""
        name = 'composite__BTC_USDT__1m__bal10000__stock'
        assert detect_name_version(name) == 'v2'
    
    def test_detect_v1(self):
        """Test detection of v1 format."""
        name = 'composite__BTC_USDT__1m__bal10000'
        assert detect_name_version(name) == 'v1'
    
    def test_detect_empty_raises(self):
        """Test empty name raises error."""
        with pytest.raises(InvalidNameFormatError, match="Empty model name"):
            detect_name_version('')
    
    def test_detect_invalid_format_raises(self):
        """Test invalid format raises error."""
        with pytest.raises(InvalidNameFormatError):
            detect_name_version('invalid_name_format')


# =============================================================================
# Test Migration Utilities
# =============================================================================


class TestCanMigrateAutomatically:
    """Test migration feasibility check."""
    
    def test_can_migrate_v1_to_v2(self):
        """Test v1 to v2 migration is automatic."""
        name = 'composite__BTC_USDT__1m__bal10000'
        can_migrate, reason = can_migrate_automatically(name, 'v2')
        assert can_migrate is True
        assert reason is None
    
    def test_cannot_migrate_v1_to_v3(self):
        """Test v1 to v3 migration requires parameters."""
        name = 'composite__BTC_USDT__1m__bal10000'
        can_migrate, reason = can_migrate_automatically(name, 'v3')
        assert can_migrate is False
        assert 'requires agent_strategy' in reason
    
    def test_cannot_migrate_v3_to_v2(self):
        """Test v3 to v2 migration is lossy."""
        name = 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        can_migrate, reason = can_migrate_automatically(name, 'v2')
        assert can_migrate is False
        assert 'lossy' in reason
    
    def test_cannot_migrate_same_version(self):
        """Test same version migration is rejected."""
        name = 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        can_migrate, reason = can_migrate_automatically(name, 'v3')
        assert can_migrate is False
        assert 'already v3' in reason


class TestMigrateNameToV3:
    """Test v1/v2 to v3 migration."""
    
    def test_migrate_v2_spot_to_v3(self):
        """Test migrating v2 SPOT name to v3."""
        old_name = 'composite__BTC_USDT__1m__bal10000__stock'
        new_name = migrate_name_to_v3(
            old_name,
            agent_strategy='BALA',
            version=1,
            stage='dev'
        )
        assert new_name == 'BTCUSDT.SPOT.BALA.SB10000.v1.dev'
    
    def test_migrate_v2_margin_to_v3(self):
        """Test migrating v2 MARGIN name to v3."""
        old_name = 'composite__ETH_USDT__5m__bal50000__margin'
        new_name = migrate_name_to_v3(
            old_name,
            agent_strategy=AgentStrategy.AGGRESSIVE,
            leverage=5,
            version=2,
            stage='prod'
        )
        assert new_name == 'ETHUSDT.MARGIN.LEVx5.AGGR.SB50000.v2.prod'
    
    def test_migrate_v1_to_v3(self):
        """Test migrating v1 name to v3."""
        old_name = 'composite__BTC_USDT__1m__bal25000'
        new_name = migrate_name_to_v3(
            old_name,
            agent_strategy='CONS',
            version=3,
            stage='staging'
        )
        assert new_name == 'BTCUSDT.SPOT.CONS.SB25000.v3.staging'
    
    def test_migrate_v3_returns_same(self):
        """Test migrating v3 name returns it unchanged."""
        old_name = 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        new_name = migrate_name_to_v3(
            old_name,
            agent_strategy='BALA',
            version=2,
            stage='prod'
        )
        # Returns unchanged (could update in future if needed)
        assert new_name == old_name


class TestParseModelNameUniversal:
    """Test universal parser that handles all versions."""
    
    def test_parse_universal_v3(self):
        """Test universal parser with v3 name."""
        name = 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        components = parse_model_name_universal(name)
        assert isinstance(components, ModelNameComponentsV3)
        assert components.format_version == 'v3'
    
    def test_parse_universal_v2(self):
        """Test universal parser with v2 name."""
        from traid_training_sdk.instruments.naming import ModelNameComponents
        
        name = 'composite__BTC_USDT__1m__bal10000__stock'
        components = parse_model_name_universal(name)
        assert isinstance(components, ModelNameComponents)
        assert components.version == 'v2'
    
    def test_parse_universal_v1(self):
        """Test universal parser with v1 name."""
        from traid_training_sdk.instruments.naming import ModelNameComponents
        
        name = 'composite__BTC_USDT__1m__bal10000'
        components = parse_model_name_universal(name)
        assert isinstance(components, ModelNameComponents)
        assert components.version == 'v1'


# =============================================================================
# Test Roundtrip Property (generate -> parse -> generate)
# =============================================================================


class TestRoundtrip:
    """Test that parsing generated names recovers original parameters."""
    
    def test_roundtrip_spot_aggressive(self):
        """Test roundtrip for SPOT AGGRESSIVE."""
        name = generate_composite_name_v3(
            instrument='BTCUSDT',
            trading_mode='SPOT',
            agent_strategy='AGGR',
            starting_balance=10000,
            version=1,
            stage='dev'
        )
        
        components = parse_model_name_v3(name)
        
        # Regenerate
        name2 = generate_composite_name_v3(
            instrument=components.instrument,
            trading_mode=components.trading_mode,
            agent_strategy=components.agent_strategy_code,
            starting_balance=components.starting_balance,
            version=components.version,
            stage=components.stage,
            leverage=components.leverage
        )
        
        assert name == name2
    
    def test_roundtrip_margin_balanced(self):
        """Test roundtrip for MARGIN BALANCED with leverage."""
        name = generate_composite_name_v3(
            instrument='ETH/USDT',
            trading_mode='MARGIN',
            agent_strategy='BALA',
            starting_balance=50000,
            version=5,
            stage='prod',
            leverage=5
        )
        
        components = parse_model_name_v3(name)
        
        name2 = generate_composite_name_v3(
            instrument=components.instrument,
            trading_mode=components.trading_mode,
            agent_strategy=components.agent_strategy_code,
            starting_balance=components.starting_balance,
            version=components.version,
            stage=components.stage,
            leverage=components.leverage
        )
        
        assert name == name2


# =============================================================================
# Edge Cases and Corner Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def test_minimum_balance(self):
        """Test with minimum allowed balance (100)."""
        name = generate_composite_name_v3(
            instrument='BTCUSDT',
            trading_mode='SPOT',
            agent_strategy='AGGR',
            starting_balance=100,
            version=1,
            stage='dev'
        )
        assert 'SB100' in name
    
    def test_maximum_balance(self):
        """Test with maximum allowed balance (1000000)."""
        name = generate_composite_name_v3(
            instrument='BTCUSDT',
            trading_mode='SPOT',
            agent_strategy='AGGR',
            starting_balance=1000000,
            version=1,
            stage='dev'
        )
        assert 'SB1000000' in name
    
    def test_high_version_number(self):
        """Test with high version number."""
        name = generate_composite_name_v3(
            instrument='BTCUSDT',
            trading_mode='SPOT',
            agent_strategy='AGGR',
            starting_balance=10000,
            version=999,
            stage='dev'
        )
        assert 'v999' in name
    
    def test_instrument_various_formats(self):
        """Test that various instrument formats normalize correctly."""
        formats = ['BTC/USDT', 'BTC-USDT', 'BTC_USDT', 'BTCUSDT']
        
        for fmt in formats:
            name = generate_composite_name_v3(
                instrument=fmt,
                trading_mode='SPOT',
                agent_strategy='AGGR',
                starting_balance=10000,
                version=1,
                stage='dev'
            )
            assert name.startswith('BTCUSDT.SPOT.')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
