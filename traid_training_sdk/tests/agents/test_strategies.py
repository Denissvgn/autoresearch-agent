"""Tests for agent strategy enumeration."""

import pytest
from traid_training_sdk.agents.strategies import (
    AgentStrategy,
    validate_strategy_code,
    get_strategy_comparison_matrix,
)


class TestAgentStrategyEnum:
    """Test AgentStrategy enum basic functionality."""
    
    def test_all_strategies_defined(self):
        """Test all 4 strategies are defined."""
        strategies = list(AgentStrategy)
        assert len(strategies) == 4
        
        codes = {s.value for s in strategies}
        expected = {"AGGR", "CONS", "BALA", "SCAL"}
        assert codes == expected
    
    def test_strategy_values(self):
        """Test strategy enum values are correct."""
        assert AgentStrategy.AGGRESSIVE.value == "AGGR"
        assert AgentStrategy.CONSERVATIVE.value == "CONS"
        assert AgentStrategy.BALANCED.value == "BALA"
        assert AgentStrategy.SCALPING.value == "SCAL"
    
    def test_strategy_is_string_enum(self):
        """Test strategies can be used as strings."""
        strategy = AgentStrategy.AGGRESSIVE
        assert isinstance(strategy, str)
        assert strategy == "AGGR"


class TestAgentStrategyProperties:
    """Test AgentStrategy property accessors."""
    
    def test_display_names(self):
        """Test all strategies have display names."""
        assert AgentStrategy.AGGRESSIVE.display_name == "Aggressive"
        assert AgentStrategy.CONSERVATIVE.display_name == "Conservative"
        assert AgentStrategy.BALANCED.display_name == "Balanced"
        assert AgentStrategy.SCALPING.display_name == "Scalping"
    
    def test_descriptions_not_empty(self):
        """Test all strategies have descriptions."""
        for strategy in AgentStrategy:
            assert len(strategy.description) > 20
            assert isinstance(strategy.description, str)
    
    def test_max_drawdown_limits(self):
        """Test max drawdown limits are correct."""
        assert AgentStrategy.AGGRESSIVE.max_drawdown_limit == 0.25
        assert AgentStrategy.CONSERVATIVE.max_drawdown_limit == 0.10
        assert AgentStrategy.BALANCED.max_drawdown_limit == 0.15
        assert AgentStrategy.SCALPING.max_drawdown_limit == 0.05
    
    def test_max_drawdown_limits_are_valid(self):
        """Test all drawdown limits are in valid range."""
        for strategy in AgentStrategy:
            limit = strategy.max_drawdown_limit
            assert 0.0 < limit <= 1.0
    
    def test_typical_holding_periods(self):
        """Test holding periods are defined."""
        for strategy in AgentStrategy:
            period = strategy.typical_holding_period
            assert isinstance(period, str)
            assert len(period) > 0
    
    def test_trading_frequencies(self):
        """Test trading frequencies are valid."""
        valid_frequencies = {"low", "moderate", "high", "very high"}
        for strategy in AgentStrategy:
            assert strategy.trading_frequency in valid_frequencies
    
    def test_risk_levels(self):
        """Test risk levels are valid."""
        valid_risk_levels = {"low", "moderate", "high"}
        for strategy in AgentStrategy:
            assert strategy.risk_level in valid_risk_levels
    
    def test_aggressive_characteristics(self):
        """Test aggressive strategy has high-risk characteristics."""
        strategy = AgentStrategy.AGGRESSIVE
        assert strategy.risk_level == "high"
        assert strategy.trading_frequency == "high"
        assert strategy.max_drawdown_limit > 0.20
    
    def test_conservative_characteristics(self):
        """Test conservative strategy has low-risk characteristics."""
        strategy = AgentStrategy.CONSERVATIVE
        assert strategy.risk_level == "low"
        assert strategy.trading_frequency == "low"
        assert strategy.max_drawdown_limit < 0.15
    
    def test_scalping_characteristics(self):
        """Test scalping strategy has very high frequency."""
        strategy = AgentStrategy.SCALPING
        assert strategy.trading_frequency == "very high"
        assert "Seconds" in strategy.typical_holding_period or "minutes" in strategy.typical_holding_period


class TestRewardWeights:
    """Test default reward weight configurations."""
    
    def test_all_strategies_have_reward_weights(self):
        """Test all strategies return reward weights."""
        for strategy in AgentStrategy:
            weights = strategy.get_default_reward_weights()
            assert isinstance(weights, dict)
            assert len(weights) > 0
    
    def test_reward_weights_have_required_components(self):
        """Test reward weights include required components."""
        required_components = {"pnl", "risk", "leverage", "flip", "hold"}
        for strategy in AgentStrategy:
            weights = strategy.get_default_reward_weights()
            assert set(weights.keys()) == required_components
    
    def test_reward_weights_are_numeric(self):
        """Test all weight values are numeric."""
        for strategy in AgentStrategy:
            weights = strategy.get_default_reward_weights()
            for component, weight in weights.items():
                assert isinstance(weight, (int, float))
                assert weight >= 0.0
    
    def test_aggressive_weights_emphasize_pnl(self):
        """Test aggressive strategy emphasizes PnL over risk."""
        weights = AgentStrategy.AGGRESSIVE.get_default_reward_weights()
        assert weights["pnl"] > weights["risk"]
        assert weights["pnl"] > 1.0
    
    def test_conservative_weights_emphasize_risk(self):
        """Test conservative strategy emphasizes risk management."""
        weights = AgentStrategy.CONSERVATIVE.get_default_reward_weights()
        assert weights["risk"] > weights["leverage"]
        assert weights["risk"] >= 0.3  # Higher risk penalty
    
    def test_scalping_weights_minimize_hold_penalty(self):
        """Test scalping strategy has minimal hold penalty."""
        weights = AgentStrategy.SCALPING.get_default_reward_weights()
        assert weights["hold"] <= 0.01  # Very low or zero


class TestLeverageRecommendations:
    """Test leverage recommendation methods."""
    
    def test_spot_mode_returns_none(self):
        """Test all strategies return None for SPOT mode."""
        for strategy in AgentStrategy:
            result = strategy.get_recommended_leverage_range("SPOT")
            assert result is None
    
    def test_margin_mode_returns_tuple(self):
        """Test all strategies return tuple for MARGIN mode."""
        for strategy in AgentStrategy:
            result = strategy.get_recommended_leverage_range("MARGIN")
            assert isinstance(result, tuple)
            assert len(result) == 2
    
    def test_leverage_ranges_are_valid(self):
        """Test leverage ranges are in valid order."""
        for strategy in AgentStrategy:
            min_lev, max_lev = strategy.get_recommended_leverage_range("MARGIN")
            assert min_lev >= 1
            assert max_lev <= 100
            assert min_lev <= max_lev
    
    def test_aggressive_has_high_leverage(self):
        """Test aggressive strategy recommends high leverage."""
        min_lev, max_lev = AgentStrategy.AGGRESSIVE.get_recommended_leverage_range("MARGIN")
        assert max_lev >= 10
    
    def test_conservative_has_low_leverage(self):
        """Test conservative strategy recommends low leverage."""
        min_lev, max_lev = AgentStrategy.CONSERVATIVE.get_recommended_leverage_range("MARGIN")
        assert max_lev <= 5


class TestFromCode:
    """Test from_code class method."""
    
    def test_from_code_uppercase(self):
        """Test creating strategy from uppercase code."""
        strategy = AgentStrategy.from_code("AGGR")
        assert strategy == AgentStrategy.AGGRESSIVE
        
        strategy = AgentStrategy.from_code("CONS")
        assert strategy == AgentStrategy.CONSERVATIVE
    
    def test_from_code_lowercase(self):
        """Test creating strategy from lowercase code (case-insensitive)."""
        strategy = AgentStrategy.from_code("aggr")
        assert strategy == AgentStrategy.AGGRESSIVE
        
        strategy = AgentStrategy.from_code("bala")
        assert strategy == AgentStrategy.BALANCED
    
    def test_from_code_mixed_case(self):
        """Test creating strategy from mixed case code."""
        strategy = AgentStrategy.from_code("Scal")
        assert strategy == AgentStrategy.SCALPING
    
    def test_from_code_invalid_raises_error(self):
        """Test invalid code raises ValueError."""
        with pytest.raises(ValueError, match="Invalid agent strategy code"):
            AgentStrategy.from_code("INVALID")
    
    def test_from_code_error_message_includes_valid_codes(self):
        """Test error message lists valid codes."""
        try:
            AgentStrategy.from_code("WRONG")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            error_msg = str(e)
            assert "AGGR" in error_msg
            assert "CONS" in error_msg
            assert "BALA" in error_msg
            assert "SCAL" in error_msg


class TestListAll:
    """Test list_all class method."""
    
    def test_list_all_returns_list(self):
        """Test list_all returns a list."""
        result = AgentStrategy.list_all()
        assert isinstance(result, list)
        assert len(result) == 4
    
    def test_list_all_includes_required_fields(self):
        """Test each strategy dict has required fields."""
        required_fields = {
            "code", "name", "description", "risk_level",
            "trading_frequency", "max_drawdown", "holding_period"
        }
        
        strategies = AgentStrategy.list_all()
        for strategy_dict in strategies:
            assert set(strategy_dict.keys()) == required_fields
    
    def test_list_all_codes_match_enum_values(self):
        """Test codes in list match enum values."""
        strategies = AgentStrategy.list_all()
        codes = {s["code"] for s in strategies}
        expected = {s.value for s in AgentStrategy}
        assert codes == expected


class TestValidateStrategyCode:
    """Test validate_strategy_code function."""
    
    def test_validate_valid_codes(self):
        """Test validation of valid codes."""
        assert validate_strategy_code("AGGR") is True
        assert validate_strategy_code("CONS") is True
        assert validate_strategy_code("BALA") is True
        assert validate_strategy_code("SCAL") is True
    
    def test_validate_case_insensitive(self):
        """Test validation is case-insensitive."""
        assert validate_strategy_code("aggr") is True
        assert validate_strategy_code("Cons") is True
    
    def test_validate_invalid_codes(self):
        """Test validation of invalid codes."""
        assert validate_strategy_code("INVALID") is False
        assert validate_strategy_code("") is False
        assert validate_strategy_code("ABC") is False


class TestGetStrategyComparisonMatrix:
    """Test get_strategy_comparison_matrix function."""
    
    def test_returns_dict_with_all_strategies(self):
        """Test matrix includes all strategies."""
        matrix = get_strategy_comparison_matrix()
        assert isinstance(matrix, dict)
        assert len(matrix) == 4
        
        expected_codes = {"AGGR", "CONS", "BALA", "SCAL"}
        assert set(matrix.keys()) == expected_codes
    
    def test_matrix_entries_have_required_fields(self):
        """Test each matrix entry has required fields."""
        required_fields = {
            "name", "risk_level", "trading_frequency",
            "max_drawdown", "holding_period", "default_weights",
            "leverage_range_margin"
        }
        
        matrix = get_strategy_comparison_matrix()
        for code, characteristics in matrix.items():
            assert set(characteristics.keys()) == required_fields
    
    def test_matrix_leverage_ranges_valid(self):
        """Test leverage ranges in matrix are valid."""
        matrix = get_strategy_comparison_matrix()
        for code, characteristics in matrix.items():
            lev_range = characteristics["leverage_range_margin"]
            assert isinstance(lev_range, tuple)
            assert len(lev_range) == 2
            assert lev_range[0] <= lev_range[1]


class TestStrategyIntegration:
    """Integration tests for strategy usage."""
    
    def test_strategy_in_config_dict(self):
        """Test strategy can be serialized in config dict."""
        strategy = AgentStrategy.BALANCED
        config = {"agent_strategy": strategy.value}
        assert config["agent_strategy"] == "BALA"
    
    def test_strategy_roundtrip(self):
        """Test strategy code -> enum -> code roundtrip."""
        original_code = "AGGR"
        strategy = AgentStrategy.from_code(original_code)
        retrieved_code = strategy.value
        assert retrieved_code == original_code
    
    def test_all_strategies_can_generate_config(self):
        """Test all strategies can generate complete configuration."""
        for strategy in AgentStrategy:
            # This should not raise any exceptions
            _ = strategy.display_name
            _ = strategy.description
            _ = strategy.get_default_reward_weights()
            _ = strategy.get_recommended_leverage_range("MARGIN")
            _ = strategy.max_drawdown_limit
            _ = strategy.trading_frequency
            _ = strategy.risk_level
