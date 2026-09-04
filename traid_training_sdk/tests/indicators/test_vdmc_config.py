"""Tests for VDMC configuration."""

import pytest
import warnings
from traid_training_sdk.indicators.vdmc_config import VDMCConfig, SignalType


class TestSignalType:
    """Test SignalType enum."""
    
    def test_signal_types_defined(self):
        """Test both signal types are defined."""
        assert SignalType.BUY.value == "buy"
        assert SignalType.SELL.value == "sell"
    
    def test_from_string_case_insensitive(self):
        """Test case-insensitive signal type creation."""
        assert SignalType.from_string("BUY") == SignalType.BUY
        assert SignalType.from_string("buy") == SignalType.BUY
        assert SignalType.from_string("Sell") == SignalType.SELL
    
    def test_from_string_invalid(self):
        """Test invalid signal type raises error."""
        with pytest.raises(ValueError, match="Invalid signal type"):
            SignalType.from_string("invalid")


class TestVDMCConfigDefaults:
    """Test VDMCConfig default values."""
    
    def test_default_construction(self):
        """Test creating config with defaults."""
        config = VDMCConfig()
        
        assert config.lookback_period == 120
        assert config.signal_type == SignalType.BUY
        assert config.alpha == 1.2
        assert config.beta == 0.8
        assert config.kernel_sigma == 5
        assert config.amplitude_scaling == 1.0
        assert config.smoothing_factor == 0.3
    
    def test_config_is_frozen(self):
        """Test config is immutable."""
        config = VDMCConfig()
        with pytest.raises(Exception):  # Pydantic ValidationError
            config.alpha = 2.0


class TestVDMCConfigValidation:
    """Test VDMCConfig validation."""
    
    def test_lookback_period_range(self):
        """Test lookback_period validates range."""
        # Valid
        config = VDMCConfig(lookback_period=120)
        assert config.lookback_period == 120
        
        config = VDMCConfig(lookback_period=720)
        assert config.lookback_period == 720
        
        # Too low
        with pytest.raises(ValueError):
            VDMCConfig(lookback_period=100)
        
        # Too high
        with pytest.raises(ValueError):
            VDMCConfig(lookback_period=1000)
    
    def test_alpha_range(self):
        """Test alpha validates range."""
        config = VDMCConfig(alpha=1.0)
        assert config.alpha == 1.0
        
        with pytest.raises(ValueError):
            VDMCConfig(alpha=0.0)  # Must be > 0
        
        with pytest.raises(ValueError):
            VDMCConfig(alpha=6.0)  # Must be <= 5.0
    
    def test_beta_range(self):
        """Test beta validates range."""
        config = VDMCConfig(beta=2.5)
        assert config.beta == 2.5
        
        with pytest.raises(ValueError):
            VDMCConfig(beta=-0.1)
    
    def test_kernel_sigma_range(self):
        """Test kernel_sigma validates range."""
        config = VDMCConfig(kernel_sigma=7)
        assert config.kernel_sigma == 7
        
        with pytest.raises(ValueError):
            VDMCConfig(kernel_sigma=1)  # Too low
        
        with pytest.raises(ValueError):
            VDMCConfig(kernel_sigma=25)  # Too high
    
    def test_kernel_sigma_even_warning(self):
        """Test warning for even kernel_sigma."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = VDMCConfig(kernel_sigma=4)
            assert len(w) == 1
            assert "even" in str(w[0].message).lower()
            assert config.kernel_sigma == 4
    
    def test_signal_type_from_string(self):
        """Test signal_type accepts string."""
        config = VDMCConfig(signal_type="sell")
        assert config.signal_type == SignalType.SELL


class TestVDMCConfigSerialization:
    """Test VDMCConfig serialization methods."""
    
    def test_to_mlflow_params(self):
        """Test conversion to MLflow parameters."""
        config = VDMCConfig(lookback_period=240, alpha=1.5)
        params = config.to_mlflow_params()
        
        assert params["vdmc_lookback_period"] == 240
        assert params["vdmc_alpha"] == 1.5
        assert params["vdmc_signal_type"] == "buy"
        assert "vdmc_" in list(params.keys())[0]  # All keys prefixed
    
    def test_to_mlflow_tags(self):
        """Test conversion to MLflow tags."""
        config = VDMCConfig(signal_type="sell", lookback_period=360)
        tags = config.to_mlflow_tags()
        
        assert tags["vdmc_signal_type"] == "sell"
        assert tags["vdmc_lookback_period"] == "360"  # Converted to string
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = VDMCConfig(alpha=2.0, beta=1.5)
        d = config.to_dict()
        
        assert d["alpha"] == 2.0
        assert d["beta"] == 1.5
        assert d["signal_type"] == "buy"
        assert "vdmc_" not in list(d.keys())[0]  # No prefix
    
    def test_to_api_request(self):
        """Test conversion to API request format."""
        config = VDMCConfig()
        request = config.to_api_request()
        
        # Should include core params
        assert "lookback_period" in request
        assert "signal_type" in request
        assert "alpha" in request
        assert "beta" in request
        assert "kernel_sigma" in request
    
    def test_from_mlflow_params_prefixed(self):
        """Test creating from prefixed MLflow params."""
        params = {
            "vdmc_lookback_period": 360,
            "vdmc_signal_type": "sell",
            "vdmc_alpha": 1.8,
        }
        config = VDMCConfig.from_mlflow_params(params)
        
        assert config.lookback_period == 360
        assert config.signal_type == SignalType.SELL
        assert config.alpha == 1.8
    
    def test_from_mlflow_params_unprefixed(self):
        """Test creating from unprefixed params."""
        params = {
            "lookback_period": 240,
            "signal_type": "buy",
        }
        config = VDMCConfig.from_mlflow_params(params)
        
        assert config.lookback_period == 240
        assert config.signal_type == SignalType.BUY


class TestVDMCConfigStrategyRecommendations:
    """Test strategy-specific recommendations."""
    
    def test_get_recommended_for_aggr(self):
        """Test aggressive strategy recommendations."""
        config = VDMCConfig.get_recommended_for_strategy("AGGR")
        
        assert config.lookback_period == 120  # Shorter for aggressive
        assert config.alpha >= 1.2  # Higher sensitivity
    
    def test_get_recommended_for_cons(self):
        """Test conservative strategy recommendations."""
        config = VDMCConfig.get_recommended_for_strategy("CONS")
        
        assert config.lookback_period >= 240  # Longer for conservative
        assert config.alpha <= 1.0  # Lower sensitivity
    
    def test_get_recommended_case_insensitive(self):
        """Test recommendations are case-insensitive."""
        config1 = VDMCConfig.get_recommended_for_strategy("BALA")
        config2 = VDMCConfig.get_recommended_for_strategy("bala")
        
        assert config1.lookback_period == config2.lookback_period
    
    def test_get_recommended_unknown_strategy(self):
        """Test unknown strategy returns defaults."""
        config = VDMCConfig.get_recommended_for_strategy("UNKNOWN")
        
        # Should return balanced defaults
        assert config.lookback_period == 120  # Default


class TestVDMCConfigUtilities:
    """Test utility methods."""
    
    def test_str_representation(self):
        """Test string representation."""
        config = VDMCConfig()
        s = str(config)
        
        assert "120" in s
        assert "buy" in s
    
    def test_repr_representation(self):
        """Test detailed representation."""
        config = VDMCConfig(alpha=2.0)
        r = repr(config)
        
        assert "VDMCConfig" in r
        assert "2.0" in r


class TestVDMCConfigIntegration:
    """Integration tests."""
    
    def test_config_roundtrip_mlflow(self):
        """Test config -> MLflow params -> config roundtrip."""
        original = VDMCConfig(
            lookback_period=360,
            signal_type="sell",
            alpha=1.8,
            beta=1.2,
        )
        
        params = original.to_mlflow_params()
        reconstructed = VDMCConfig.from_mlflow_params(params)
        
        assert reconstructed.lookback_period == original.lookback_period
        assert reconstructed.signal_type == original.signal_type
        assert reconstructed.alpha == original.alpha
        assert reconstructed.beta == original.beta
    
    def test_all_strategies_have_recommendations(self):
        """Test all strategies have valid recommendations."""
        for strategy in ["AGGR", "CONS", "BALA", "SCAL"]:
            config = VDMCConfig.get_recommended_for_strategy(strategy)
            assert isinstance(config, VDMCConfig)
            # Should not raise validation errors
            _ = config.to_dict()
