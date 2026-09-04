"""
Unit tests for model naming conventions (ML-2.1).

Tests both v1 and v2 formats:
- v1: composite__BTC_USDT__1m__bal10000
- v2: composite__BTC_USDT__1m__bal10000__stock
"""

import pytest
from pydantic import ValidationError

# Import directly to avoid circular dependency issues
import sys
from pathlib import Path

# Add parent directory to path
sdk_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(sdk_path))

from instruments.naming import (
    ModelNameComponents,
    generate_composite_name_v2,
    generate_constituent_name_v2,
    parse_model_name,
    validate_model_name,
    migrate_v1_to_v2,
    get_default_trading_mode,
)


# =============================================================================
# Test: ModelNameComponents Pydantic Model
# =============================================================================


class TestModelNameComponents:
    """Test ModelNameComponents Pydantic model."""
    
    def test_v1_components(self):
        """Test v1 format components."""
        components = ModelNameComponents(
            model_type='composite',
            instrument='BTC_USDT',
            timeframe='1m',
            initial_balance=10000,
            trading_mode=None,
            version='v1'
        )
        
        assert components.model_type == 'composite'
        assert components.instrument == 'BTC_USDT'
        assert components.timeframe == '1m'
        assert components.initial_balance == 10000
        assert components.trading_mode is None
        assert components.version == 'v1'
        assert not components.is_v2
    
    def test_v2_components(self):
        """Test v2 format components."""
        components = ModelNameComponents(
            model_type='composite',
            instrument='BTC_USDT',
            timeframe='1m',
            initial_balance=10000,
            trading_mode='stock',
            version='v2'
        )
        
        assert components.trading_mode == 'stock'
        assert components.version == 'v2'
        assert components.is_v2
    
    def test_canonical_instrument_property(self):
        """Test canonical_instrument property converts underscore to slash."""
        components = ModelNameComponents(
            model_type='composite',
            instrument='BTC_USDT',
            timeframe='1m',
            initial_balance=10000,
            trading_mode='stock',
            version='v2'
        )
        
        assert components.canonical_instrument == 'BTC/USDT'
    
    def test_invalid_balance(self):
        """Test that non-positive balance is rejected."""
        with pytest.raises(ValidationError):
            ModelNameComponents(
                model_type='composite',
                instrument='BTC_USDT',
                timeframe='1m',
                initial_balance=0,  # Invalid: must be > 0
                trading_mode='stock',
                version='v2'
            )
    
    def test_invalid_trading_mode(self):
        """Test that invalid trading_mode is rejected."""
        with pytest.raises(ValidationError):
            ModelNameComponents(
                model_type='composite',
                instrument='BTC_USDT',
                timeframe='1m',
                initial_balance=10000,
                trading_mode='futures',  # Invalid
                version='v2'
            )


# =============================================================================
# Test: generate_composite_name_v2
# =============================================================================


class TestGenerateCompositeName:
    """Test composite model name generation."""
    
    def test_generate_v2_format_stock(self):
        """Test v2 format generation with stock mode."""
        name = generate_composite_name_v2('BTC/USDT', '1m', 10000, 'stock')
        assert name == 'composite__BTC_USDT__1m__bal10000__stock'
    
    def test_generate_v2_format_margin(self):
        """Test v2 format generation with margin mode."""
        name = generate_composite_name_v2('BTC/USDT', '1m', 10000, 'margin')
        assert name == 'composite__BTC_USDT__1m__bal10000__margin'
    
    def test_generate_v1_format_fallback(self):
        """Test v1 format generation (backward compatibility)."""
        name = generate_composite_name_v2(
            'BTC/USDT', '1m', 10000, 'stock', use_v2_format=False
        )
        assert name == 'composite__BTC_USDT__1m__bal10000'
    
    def test_instrument_normalization_slash(self):
        """Test instrument name normalization with slash separator."""
        name = generate_composite_name_v2('BTC/USDT', '5m', 5000, 'stock')
        assert 'BTC_USDT' in name
    
    def test_instrument_normalization_dash(self):
        """Test that dash separator alone is rejected as ambiguous."""
        # Dash separator without additional context is still ambiguous even though
        # provider-style symbols (BTCUSDT) are now accepted.
        with pytest.raises(ValueError, match="(Ambiguous|Unable to parse)"):
            generate_composite_name_v2('BTC-USDT', '5m', 5000, 'stock')
    
    def test_instrument_normalization_underscore(self):
        """Test instrument name normalization with underscore separator."""
        name = generate_composite_name_v2('BTC_USDT', '5m', 5000, 'stock')
        assert 'BTC_USDT' in name

    def test_instrument_provider_symbol_without_exchange(self):
        """Provider-style symbols without exchange should resolve heuristically."""
        name = generate_composite_name_v2('BTCUSDT', '1m', 10000, 'stock')
        assert 'BTC_USDT' in name
    
    def test_timeframe_normalization(self):
        """Test timeframe normalization."""
        name = generate_composite_name_v2('BTC/USDT', '1min', 10000, 'stock')
        assert '__1m__' in name  # normalized to '1m'
    
    def test_different_instruments(self):
        """Test various instrument pairs."""
        instruments = ['ETH/USDT', 'BNB/USDT', 'SOL/USDT']
        for inst in instruments:
            name = generate_composite_name_v2(inst, '1m', 10000, 'stock')
            assert inst.replace('/', '_') in name
    
    def test_different_timeframes(self):
        """Test various timeframes."""
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        for tf in timeframes:
            name = generate_composite_name_v2('BTC/USDT', tf, 10000, 'stock')
            assert f'__{tf}__' in name
    
    def test_different_balances(self):
        """Test various initial balances."""
        balances = [1000, 5000, 10000, 50000, 100000]
        for bal in balances:
            name = generate_composite_name_v2('BTC/USDT', '1m', bal, 'stock')
            assert f'__bal{bal}__' in name


# =============================================================================
# Test: generate_constituent_name_v2
# =============================================================================


class TestGenerateConstituentName:
    """Test constituent model name generation."""
    
    def test_generate_rl_v2_stock(self):
        """Test RL model name generation with stock mode."""
        name = generate_constituent_name_v2(
            'rl', 'BTC/USDT', '1m', 10000, 'stock'
        )
        assert name == 'rl__BTC_USDT__1m__bal10000__stock'
    
    def test_generate_rl_v2_margin(self):
        """Test RL model name generation with margin mode."""
        name = generate_constituent_name_v2(
            'rl', 'BTC/USDT', '1m', 10000, 'margin'
        )
        assert name == 'rl__BTC_USDT__1m__bal10000__margin'
    
    def test_generate_direction_no_trading_mode(self):
        """Test direction model name (no trading_mode)."""
        name = generate_constituent_name_v2(
            'direction', 'BTC/USDT', '1m', 10000, 'stock'
        )
        # Direction models don't include trading_mode
        assert name == 'direction__BTC_USDT__1m__bal10000'
        assert '__stock' not in name
    
    def test_generate_volatility_no_trading_mode(self):
        """Test volatility model name (no trading_mode)."""
        name = generate_constituent_name_v2(
            'volatility', 'BTC/USDT', '1m', 10000, 'margin'
        )
        # Volatility models don't include trading_mode
        assert name == 'volatility__BTC_USDT__1m__bal10000'
        assert '__margin' not in name
    
    def test_rl_v1_format(self):
        """Test RL model v1 format fallback."""
        name = generate_constituent_name_v2(
            'rl', 'BTC/USDT', '1m', 10000, 'stock', use_v2_format=False
        )
        assert name == 'rl__BTC_USDT__1m__bal10000'
        assert '__stock' not in name


# =============================================================================
# Test: parse_model_name
# =============================================================================


class TestParseModelName:
    """Test model name parsing."""
    
    def test_parse_v1_composite(self):
        """Test parsing v1 composite name."""
        name = 'composite__BTC_USDT__1m__bal10000'
        components = parse_model_name(name)
        
        assert components.model_type == 'composite'
        assert components.instrument == 'BTC_USDT'
        assert components.timeframe == '1m'
        assert components.initial_balance == 10000
        assert components.trading_mode is None
        assert components.version == 'v1'
        assert not components.is_v2
    
    def test_parse_v2_composite_stock(self):
        """Test parsing v2 composite name with stock mode."""
        name = 'composite__BTC_USDT__1m__bal10000__stock'
        components = parse_model_name(name)
        
        assert components.model_type == 'composite'
        assert components.instrument == 'BTC_USDT'
        assert components.timeframe == '1m'
        assert components.initial_balance == 10000
        assert components.trading_mode == 'stock'
        assert components.version == 'v2'
        assert components.is_v2
    
    def test_parse_v2_composite_margin(self):
        """Test parsing v2 composite name with margin mode."""
        name = 'composite__BTC_USDT__1m__bal10000__margin'
        components = parse_model_name(name)
        
        assert components.trading_mode == 'margin'
        assert components.version == 'v2'
    
    def test_parse_v1_rl(self):
        """Test parsing v1 RL model name."""
        name = 'rl__ETH_USDT__5m__bal5000'
        components = parse_model_name(name)
        
        assert components.model_type == 'rl'
        assert components.instrument == 'ETH_USDT'
        assert components.timeframe == '5m'
        assert components.initial_balance == 5000
        assert components.version == 'v1'
    
    def test_parse_v2_rl(self):
        """Test parsing v2 RL model name."""
        name = 'rl__ETH_USDT__5m__bal5000__margin'
        components = parse_model_name(name)
        
        assert components.model_type == 'rl'
        assert components.trading_mode == 'margin'
        assert components.version == 'v2'
    
    def test_parse_direction_model(self):
        """Test parsing direction model name."""
        name = 'direction__BTC_USDT__1h__bal10000'
        components = parse_model_name(name)
        
        assert components.model_type == 'direction'
        assert components.timeframe == '1h'
    
    def test_parse_volatility_model(self):
        """Test parsing volatility model name."""
        name = 'volatility__SOL_USDT__15m__bal20000'
        components = parse_model_name(name)
        
        assert components.model_type == 'volatility'
        assert components.instrument == 'SOL_USDT'
        assert components.initial_balance == 20000
    
    def test_parse_invalid_too_few_parts(self):
        """Test parsing fails with too few parts."""
        with pytest.raises(ValueError, match="at least 4 parts"):
            parse_model_name('composite__BTC_USDT')
    
    def test_parse_invalid_balance_format(self):
        """Test parsing fails with invalid balance format."""
        with pytest.raises(ValueError, match="Invalid balance format"):
            parse_model_name('composite__BTC_USDT__1m__10000')  # Missing 'bal' prefix
    
    def test_parse_invalid_balance_value(self):
        """Test parsing fails with non-numeric balance."""
        with pytest.raises(ValueError, match="Invalid balance value"):
            parse_model_name('composite__BTC_USDT__1m__balXYZ')
    
    def test_parse_invalid_trading_mode(self):
        """Test parsing fails with invalid trading_mode."""
        with pytest.raises(ValueError, match="Invalid trading_mode"):
            parse_model_name('composite__BTC_USDT__1m__bal10000__futures')
    
    def test_parse_invalid_too_many_parts(self):
        """Test parsing fails with too many parts."""
        with pytest.raises(ValueError, match="Expected 4 or 5 parts"):
            parse_model_name('composite__BTC_USDT__1m__bal10000__stock__extra')
    
    def test_canonical_instrument_roundtrip(self):
        """Test canonical instrument property."""
        name = 'composite__BTC_USDT__1m__bal10000__stock'
        components = parse_model_name(name)
        assert components.canonical_instrument == 'BTC/USDT'


# =============================================================================
# Test: validate_model_name
# =============================================================================


class TestValidateModelName:
    """Test model name validation."""
    
    def test_validate_v1_composite(self):
        """Test v1 composite name is valid."""
        assert validate_model_name('composite__BTC_USDT__1m__bal10000')
    
    def test_validate_v2_composite(self):
        """Test v2 composite name is valid."""
        assert validate_model_name('composite__BTC_USDT__1m__bal10000__stock')
        assert validate_model_name('composite__BTC_USDT__1m__bal10000__margin')
    
    def test_validate_constituent_models(self):
        """Test constituent model names are valid."""
        assert validate_model_name('rl__BTC_USDT__1m__bal10000__stock')
        assert validate_model_name('direction__BTC_USDT__1m__bal10000')
        assert validate_model_name('volatility__BTC_USDT__1m__bal10000')
    
    def test_validate_invalid_names(self):
        """Test invalid names are rejected."""
        assert not validate_model_name('invalid_name')
        assert not validate_model_name('composite__BTC_USDT')  # Too few parts
        assert not validate_model_name('composite__BTC_USDT__1m__10000')  # No 'bal'
        assert not validate_model_name('composite__BTC_USDT__1m__bal10000__futures')  # Invalid mode


# =============================================================================
# Test: migrate_v1_to_v2
# =============================================================================


class TestMigrateV1ToV2:
    """Test v1 to v2 migration."""
    
    def test_migrate_composite_default_stock(self):
        """Test migrating composite name defaults to stock mode."""
        v1_name = 'composite__BTC_USDT__1m__bal10000'
        v2_name = migrate_v1_to_v2(v1_name)
        
        assert v2_name == 'composite__BTC_USDT__1m__bal10000__stock'
    
    def test_migrate_composite_explicit_margin(self):
        """Test migrating composite name with explicit margin mode."""
        v1_name = 'composite__BTC_USDT__1m__bal10000'
        v2_name = migrate_v1_to_v2(v1_name, trading_mode='margin')
        
        assert v2_name == 'composite__BTC_USDT__1m__bal10000__margin'
    
    def test_migrate_rl_model(self):
        """Test migrating RL model name."""
        v1_name = 'rl__ETH_USDT__5m__bal5000'
        v2_name = migrate_v1_to_v2(v1_name, trading_mode='stock')
        
        assert v2_name == 'rl__ETH_USDT__5m__bal5000__stock'
    
    def test_migrate_already_v2(self):
        """Test migrating already v2 name returns unchanged."""
        v2_name = 'composite__BTC_USDT__1m__bal10000__stock'
        result = migrate_v1_to_v2(v2_name)
        
        assert result == v2_name  # Should return as is
    
    def test_migrate_preserves_components(self):
        """Test migration preserves all components."""
        v1_name = 'composite__SOL_USDT__15m__bal20000'
        v2_name = migrate_v1_to_v2(v1_name, trading_mode='margin')
        
        components = parse_model_name(v2_name)
        assert components.model_type == 'composite'
        assert components.instrument == 'SOL_USDT'
        assert components.timeframe == '15m'
        assert components.initial_balance == 20000
        assert components.trading_mode == 'margin'
    
    def test_migrate_invalid_v1_name(self):
        """Test migration fails with invalid v1 name."""
        with pytest.raises(ValueError):
            migrate_v1_to_v2('invalid_name')


# =============================================================================
# Test: get_default_trading_mode
# =============================================================================


class TestGetDefaultTradingMode:
    """Test default trading mode extraction."""
    
    def test_v1_defaults_to_stock(self):
        """Test v1 name defaults to stock mode."""
        name = 'composite__BTC_USDT__1m__bal10000'
        mode = get_default_trading_mode(name)
        
        assert mode == 'stock'
    
    def test_v2_stock_returns_stock(self):
        """Test v2 name with stock mode."""
        name = 'composite__BTC_USDT__1m__bal10000__stock'
        mode = get_default_trading_mode(name)
        
        assert mode == 'stock'
    
    def test_v2_margin_returns_margin(self):
        """Test v2 name with margin mode."""
        name = 'composite__BTC_USDT__1m__bal10000__margin'
        mode = get_default_trading_mode(name)
        
        assert mode == 'margin'
    
    def test_rl_v1_defaults_to_stock(self):
        """Test RL v1 name defaults to stock."""
        name = 'rl__BTC_USDT__1m__bal10000'
        mode = get_default_trading_mode(name)
        
        assert mode == 'stock'
    
    def test_rl_v2_margin(self):
        """Test RL v2 name with margin."""
        name = 'rl__BTC_USDT__1m__bal10000__margin'
        mode = get_default_trading_mode(name)
        
        assert mode == 'margin'


# =============================================================================
# Test: Edge Cases and Integration
# =============================================================================


class TestEdgeCases:
    """Test edge cases and integration scenarios."""
    
    def test_roundtrip_v2_generation_and_parsing(self):
        """Test generating and parsing v2 name roundtrip."""
        name = generate_composite_name_v2('BTC/USDT', '1m', 10000, 'margin')
        components = parse_model_name(name)
        
        assert components.model_type == 'composite'
        assert components.instrument == 'BTC_USDT'
        assert components.timeframe == '1m'
        assert components.initial_balance == 10000
        assert components.trading_mode == 'margin'
        assert components.is_v2
    
    def test_roundtrip_v1_generation_and_parsing(self):
        """Test generating and parsing v1 name roundtrip."""
        name = generate_composite_name_v2(
            'BTC/USDT', '1m', 10000, 'stock', use_v2_format=False
        )
        components = parse_model_name(name)
        
        assert not components.is_v2
        assert components.trading_mode is None
    
    def test_multiple_instruments_consistency(self):
        """Test consistency across multiple instruments."""
        instruments = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
        
        for inst in instruments:
            name_v2 = generate_composite_name_v2(inst, '5m', 10000, 'stock')
            components = parse_model_name(name_v2)
            
            assert components.is_v2
            assert components.trading_mode == 'stock'
            assert validate_model_name(name_v2)
    
    def test_migration_and_parsing_consistency(self):
        """Test migration produces valid parseable names."""
        v1_names = [
            'composite__BTC_USDT__1m__bal10000',
            'rl__ETH_USDT__5m__bal5000',
            'composite__SOL_USDT__15m__bal20000'
        ]
        
        for v1_name in v1_names:
            v2_name = migrate_v1_to_v2(v1_name, trading_mode='margin')
            components = parse_model_name(v2_name)
            
            assert components.is_v2
            assert components.trading_mode == 'margin'
            assert validate_model_name(v2_name)
    
    def test_special_characters_sanitized(self):
        """Test special characters are sanitized in names."""
        # The parse_instrument already handles normalization
        name = generate_composite_name_v2('BTC/USDT', '1m', 10000, 'stock')
        
        # Should only contain alphanumeric, underscore, colon, dash
        import re
        assert re.fullmatch(r'[A-Za-z0-9_:\-]+', name)
    
    def test_large_balance_values(self):
        """Test large initial balance values."""
        large_balances = [100000, 500000, 1000000]
        
        for bal in large_balances:
            name = generate_composite_name_v2('BTC/USDT', '1m', bal, 'stock')
            components = parse_model_name(name)
            
            assert components.initial_balance == bal
