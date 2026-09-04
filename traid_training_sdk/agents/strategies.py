"""Agent strategy enumeration and utilities.

This module defines the agent strategy taxonomy for RL trading agents,
implementing the specifications from docs/design/agent_strategy_taxonomy.md.

Strategies are fixed at training time and encoded in the model name per REQ-001-ML ML-2.1.
"""

from enum import Enum
from typing import Any, Dict, Optional


class AgentStrategy(str, Enum):
    """Agent strategy enumeration for RL trading.
    
    Each strategy represents a distinct trading approach with specific
    characteristics for risk tolerance, trading frequency, and position management.
    
    Strategies are 4-character uppercase codes per v3 naming convention.
    
    Attributes:
        AGGRESSIVE: High-risk, high-reward strategy
        CONSERVATIVE: Capital preservation focused
        BALANCED: Moderate risk/reward tradeoff
        SCALPING: Ultra-high frequency, small profits
    
    Examples:
        >>> strategy = AgentStrategy.AGGRESSIVE
        >>> strategy.value
        'AGGR'
        >>> strategy.display_name
        'Aggressive'
        >>> strategy.description
        'High-risk, high-reward strategy targeting maximum returns'
    """
    
    AGGRESSIVE = "AGGR"
    CONSERVATIVE = "CONS"
    BALANCED = "BALA"
    SCALPING = "SCAL"
    
    @property
    def display_name(self) -> str:
        """Get human-readable strategy name.
        
        Returns:
            Human-readable display name
        """
        display_names = {
            "AGGR": "Aggressive",
            "CONS": "Conservative",
            "BALA": "Balanced",
            "SCAL": "Scalping",
        }
        return display_names[self.value]
    
    @property
    def description(self) -> str:
        """Get detailed strategy description.
        
        Returns:
            Detailed description of strategy characteristics
        """
        descriptions = {
            "AGGR": "High-risk, high-reward strategy targeting maximum returns with aggressive position sizing and frequent trades",
            "CONS": "Capital preservation focused strategy with strict risk limits, lower leverage, and defensive position management",
            "BALA": "Moderate risk/reward tradeoff suitable for most users, balancing growth with risk management",
            "SCAL": "Ultra-high frequency trading strategy focused on small, quick profits with very short holding periods",
        }
        return descriptions[self.value]
    
    @property
    def max_drawdown_limit(self) -> float:
        """Get maximum drawdown limit for this strategy.
        
        Returns:
            Maximum drawdown as fraction (e.g., 0.25 = 25%)
        """
        limits = {
            "AGGR": 0.25,  # 25% max drawdown
            "CONS": 0.10,  # 10% max drawdown
            "BALA": 0.15,  # 15% max drawdown
            "SCAL": 0.05,  # 5% max drawdown
        }
        return limits[self.value]
    
    @property
    def typical_holding_period(self) -> str:
        """Get typical holding period for this strategy.
        
        Returns:
            Human-readable holding period description
        """
        periods = {
            "AGGR": "Hours to days",
            "CONS": "Days to weeks",
            "BALA": "Hours to days",
            "SCAL": "Seconds to minutes",
        }
        return periods[self.value]
    
    @property
    def trading_frequency(self) -> str:
        """Get typical trading frequency.
        
        Returns:
            Trading frequency descriptor (low, moderate, high, very high)
        """
        frequencies = {
            "AGGR": "high",
            "CONS": "low",
            "BALA": "moderate",
            "SCAL": "very high",
        }
        return frequencies[self.value]
    
    @property
    def risk_level(self) -> str:
        """Get risk level descriptor.
        
        Returns:
            Risk level (low, moderate, high)
        """
        risk_levels = {
            "AGGR": "high",
            "CONS": "low",
            "BALA": "moderate",
            "SCAL": "moderate",
        }
        return risk_levels[self.value]
    
    def get_default_reward_weights(self) -> Dict[str, float]:
        """Get default reward function weights for this strategy.
        
        Returns reward weights optimized for the strategy's objectives.
        
        Returns:
            Dictionary of reward component weights
        
        Examples:
            >>> AgentStrategy.AGGRESSIVE.get_default_reward_weights()
            {'pnl': 1.5, 'risk': 0.1, 'leverage': 0.02, 'flip': 0.005, 'hold': 0.002}
        """
        weights = {
            "AGGR": {
                "pnl": 1.5,      # Maximize PnL
                "risk": 0.1,     # Lower risk penalty
                "leverage": 0.02, # Minimal leverage penalty
                "flip": 0.005,   # Minimal flip penalty
                "hold": 0.002,   # Minimal hold penalty
            },
            "CONS": {
                "pnl": 0.8,      # Moderate PnL weight
                "risk": 0.5,     # High risk penalty
                "leverage": 0.1, # Penalize leverage
                "flip": 0.02,    # Discourage flips
                "hold": 0.01,    # Encourage holding
            },
            "BALA": {
                "pnl": 1.0,      # Balanced PnL weight
                "risk": 0.2,     # Moderate risk penalty
                "leverage": 0.05, # Moderate leverage penalty
                "flip": 0.01,    # Moderate flip penalty
                "hold": 0.005,   # Moderate hold penalty
            },
            "SCAL": {
                "pnl": 1.2,      # High PnL weight
                "risk": 0.15,    # Lower risk penalty
                "leverage": 0.08, # Moderate leverage penalty
                "flip": 0.001,   # Minimal flip penalty (frequent trades)
                "hold": 0.0,     # No hold penalty (quick exits)
            },
        }
        return weights[self.value]
    
    def get_recommended_leverage_range(self, trading_mode: str) -> Optional[tuple[int, int]]:
        """Get recommended leverage range for this strategy.
        
        Args:
            trading_mode: 'SPOT' or 'MARGIN'
        
        Returns:
            Tuple of (min_leverage, max_leverage) or None for SPOT mode
        
        Examples:
            >>> AgentStrategy.AGGRESSIVE.get_recommended_leverage_range('MARGIN')
            (10, 20)
            >>> AgentStrategy.CONSERVATIVE.get_recommended_leverage_range('MARGIN')
            (1, 5)
            >>> AgentStrategy.BALANCED.get_recommended_leverage_range('SPOT')
            None
        """
        if trading_mode == "SPOT":
            return None
        
        # Recommended leverage ranges for MARGIN mode
        ranges = {
            "AGGR": (10, 20),  # High leverage
            "CONS": (1, 5),    # Low leverage
            "BALA": (3, 10),   # Moderate leverage
            "SCAL": (5, 15),   # Moderate to high leverage
        }
        return ranges[self.value]
    
    @classmethod
    def from_code(cls, code: str) -> "AgentStrategy":
        """Create AgentStrategy from 4-character code.
        
        Args:
            code: 4-character strategy code (case-insensitive)
        
        Returns:
            AgentStrategy enum value
        
        Raises:
            ValueError: If code is invalid
        
        Examples:
            >>> AgentStrategy.from_code('AGGR')
            <AgentStrategy.AGGRESSIVE: 'AGGR'>
            >>> AgentStrategy.from_code('aggr')
            <AgentStrategy.AGGRESSIVE: 'AGGR'>
            >>> AgentStrategy.from_code('INVALID')
            ValueError: Invalid agent strategy code: INVALID
        """
        code_upper = code.upper()
        try:
            return cls(code_upper)
        except ValueError:
            valid_codes = [s.value for s in cls]
            raise ValueError(
                f"Invalid agent strategy code: {code}. "
                f"Valid codes: {', '.join(valid_codes)}"
            )
    
    @classmethod
    def list_all(cls) -> list[Dict[str, str]]:
        """List all available strategies with metadata.
        
        Returns:
            List of dictionaries containing strategy information
        
        Examples:
            >>> strategies = AgentStrategy.list_all()
            >>> len(strategies)
            4
            >>> strategies[0]['code']
            'AGGR'
        """
        return [
            {
                "code": strategy.value,
                "name": strategy.display_name,
                "description": strategy.description,
                "risk_level": strategy.risk_level,
                "trading_frequency": strategy.trading_frequency,
                "max_drawdown": f"{strategy.max_drawdown_limit * 100:.0f}%",
                "holding_period": strategy.typical_holding_period,
            }
            for strategy in cls
        ]


def validate_strategy_code(code: str) -> bool:
    """Validate if a strategy code is valid.
    
    Args:
        code: Strategy code to validate
    
    Returns:
        True if valid, False otherwise
    
    Examples:
        >>> validate_strategy_code('AGGR')
        True
        >>> validate_strategy_code('INVALID')
        False
    """
    try:
        AgentStrategy.from_code(code)
        return True
    except ValueError:
        return False


def get_strategy_comparison_matrix() -> Dict[str, Dict[str, Any]]:
    """Get comparison matrix of all strategies.
    
    Returns:
        Dictionary with strategy codes as keys and characteristics as values
    
    Examples:
        >>> matrix = get_strategy_comparison_matrix()
        >>> matrix['AGGR']['risk_level']
        'high'
    """
    return {
        strategy.value: {
            "name": strategy.display_name,
            "risk_level": strategy.risk_level,
            "trading_frequency": strategy.trading_frequency,
            "max_drawdown": strategy.max_drawdown_limit,
            "holding_period": strategy.typical_holding_period,
            "default_weights": strategy.get_default_reward_weights(),
            "leverage_range_margin": strategy.get_recommended_leverage_range("MARGIN"),
        }
        for strategy in AgentStrategy
    }
