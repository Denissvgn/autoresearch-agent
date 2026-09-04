from __future__ import annotations

import re
from typing import Literal, Optional, Tuple, Union, TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from .symbols import normalize_timeframe, parse_instrument

# Import AgentStrategy for v3 naming
if TYPE_CHECKING:
    from traid_training_sdk.agents.strategies import AgentStrategy
else:
    try:
        from traid_training_sdk.agents.strategies import AgentStrategy
    except ImportError:
        # For backward compatibility if strategies module not available
        AgentStrategy = None  # type: ignore


_SAFE_RE = re.compile(r"[^A-Za-z0-9_:\-]")


def sanitize_name(value: str) -> str:
    return _SAFE_RE.sub("_", value)


def model_name(kind: str, instrument_spec: str, timeframe: str, initial_balance: int) -> str:
    inst = parse_instrument(instrument_spec)
    tf = normalize_timeframe(timeframe)
    canon = f"{inst.base}_{inst.quote}"
    name = f"{kind}__{canon}__{tf}__bal{int(initial_balance)}"
    return sanitize_name(name)


def composite_alias(
    instrument_spec: str,
    timeframe: Optional[str] = None,
    initial_balance: int = 10000,
    trading_mode: Literal['stock', 'margin', 'SPOT', 'MARGIN'] = 'stock',
    use_v2_format: bool = True,
    # V3 parameters
    agent_strategy: Optional[Union[str, 'AgentStrategy']] = None,
    version: Optional[int] = None,
    stage: Optional[Literal['dev', 'staging', 'prod', 'retired']] = None,
    leverage: Optional[int] = None,
    use_v3_format: bool = False,
) -> str:
    """
    Generate composite model alias (backward-compatible wrapper with v3 support).
    
    This function maintains backward compatibility while supporting both v2 and v3 formats.
    For new code, prefer using generate_composite_name_v3() or generate_model_name() directly.
    
    Args:
        instrument_spec: Instrument specification
        timeframe: Timeframe string (required for v2, ignored for v3)
        initial_balance: Initial balance (default 10000)
        trading_mode: Trading mode ('stock'/'margin' for v2, 'SPOT'/'MARGIN' for v3)
        use_v2_format: Use v2 format with trading_mode (only used if not use_v3_format)
        agent_strategy: Strategy code (required for v3, e.g., 'AGGR')
        version: Model version (required for v3)
        stage: Lifecycle stage (required for v3)
        leverage: Leverage level (required for MARGIN mode in v3)
        use_v3_format: If True, use v3 format; if False, use v2 format
    
    Returns:
        Composite model name
    
    Examples:
        # V2 format (default, deprecated)
        >>> composite_alias('BTC/USDT', '1m', 10000)
        'composite__BTC_USDT__1m__bal10000__stock'
        
        >>> composite_alias('BTC/USDT', '1m', 10000, 'margin')
        'composite__BTC_USDT__1m__bal10000__margin'
        
        # V3 format (recommended)
        >>> composite_alias(
        ...     'BTCUSDT',
        ...     initial_balance=10000,
        ...     trading_mode='SPOT',
        ...     agent_strategy='AGGR',
        ...     version=1,
        ...     stage='dev',
        ...     use_v3_format=True
        ... )
        'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
    """
    if use_v3_format:
        # V3 format
        if agent_strategy is None or version is None or stage is None:
            raise ValueError(
                "agent_strategy, version, and stage are required for v3 format"
            )
        
        # Map v2 trading_mode to v3 if needed
        if trading_mode.lower() == 'stock':
            trading_mode_v3 = 'SPOT'
        elif trading_mode.lower() == 'margin':
            trading_mode_v3 = 'MARGIN'
        else:
            trading_mode_v3 = trading_mode.upper()
        
        return generate_composite_name_v3(
            instrument=instrument_spec,
            trading_mode=trading_mode_v3,  # type: ignore
            agent_strategy=agent_strategy,
            starting_balance=initial_balance,
            version=version,
            stage=stage,
            leverage=leverage
        )
    else:
        # V2 format (deprecated)
        _deprecation_warning_v2('composite_alias with v2 format')
        
        if timeframe is None:
            raise ValueError(
                "timeframe is required for v2 format. "
                "Use use_v3_format=True for v3 naming without timeframe."
            )
        
        # Delegate to v2 function for consistency
        return generate_composite_name_v2(
            instrument=instrument_spec,
            timeframe=timeframe,
            initial_balance=initial_balance,
            trading_mode=trading_mode,  # type: ignore
            use_v2_format=use_v2_format
        )


def autotrain_model_name(instrument_spec: str, timeframe: str, initial_balance: Optional[float] = None) -> str:
    if initial_balance is None:
        inst = parse_instrument(instrument_spec)
        tf = normalize_timeframe(timeframe)
        canon = f"{inst.base}_{inst.quote}"
        return sanitize_name(f"autotrain__{canon}__{tf}")
    return model_name("autotrain", instrument_spec, timeframe, int(initial_balance))


# =============================================================================
# ML-2.0 / ML-2.1 Enhanced Naming Convention (v2)
# =============================================================================


class ModelNameComponents(BaseModel):
    """
    Parsed components of a model name.
    
    Supports both v1 and v2 formats:
    - v1: composite__BTC_USDT__1m__bal10000
    - v2: composite__BTC_USDT__1m__bal10000__stock
    """
    
    model_type: str = Field(description="Type of model (composite, direction, volatility, rl)")
    instrument: str = Field(description="Trading instrument (e.g., BTC_USDT)")
    timeframe: str = Field(description="Timeframe (e.g., 1m, 5m, 1h)")
    initial_balance: int = Field(gt=0, description="Initial balance for training")
    trading_mode: Optional[Literal['stock', 'margin']] = Field(
        None,
        description="Trading mode (v2 only, None for v1)"
    )
    version: Literal['v1', 'v2'] = Field(description="Name format version")
    
    @property
    def is_v2(self) -> bool:
        """Check if this is v2 format."""
        return self.version == 'v2'
    
    @property
    def canonical_instrument(self) -> str:
        """Get canonical instrument name with slash separator."""
        return self.instrument.replace('_', '/')


def generate_composite_name_v2(
    instrument: str,
    timeframe: str,
    initial_balance: int,
    trading_mode: Literal['stock', 'margin'] = 'stock',
    use_v2_format: bool = True
) -> str:
    """
    Generate composite model name with ML-2.1 trading_mode support.
    
    .. deprecated:: 3.0
        This function is deprecated and will be removed in Q3 2026.
        Use :func:`generate_composite_name_v3` or :func:`generate_model_name` with
        ``use_v3_format=True`` for new models.
        See docs/sdk/naming_migration_guide.md for migration instructions.
    
    Args:
        instrument: Trading instrument (e.g., 'BTC/USDT', 'BTC-USDT', 'BTC_USDT')
        timeframe: Timeframe (e.g., '1m', '5m', '1h')
        initial_balance: Initial balance for trading
        trading_mode: Trading mode ('stock' or 'margin')
        use_v2_format: If True, use v2 format with trading_mode
    
    Returns:
        Model name string
    
    Examples:
        >>> generate_composite_name_v2('BTC/USDT', '1m', 10000, 'stock')
        'composite__BTC_USDT__1m__bal10000__stock'
        
        >>> generate_composite_name_v2('BTC-USDT', '5m', 5000, 'margin')
        'composite__BTC_USDT__5m__bal5000__margin'
        
        >>> generate_composite_name_v2('ETH/USDT', '1h', 10000, use_v2_format=False)
        'composite__ETH_USDT__1h__bal10000'
    """
    warnings.warn(
        "generate_composite_name_v2() is deprecated and will be removed in Q3 2026. "
        "Use generate_composite_name_v3() or generate_model_name() with use_v3_format=True. "
        "See docs/sdk/naming_migration_guide.md for migration guide.",
        DeprecationWarning,
        stacklevel=2
    )
    
    inst = parse_instrument(instrument)
    tf = normalize_timeframe(timeframe)
    canon = f"{inst.base}_{inst.quote}"
    
    base = f"composite__{canon}__{tf}__bal{int(initial_balance)}"
    
    if use_v2_format:
        name = f"{base}__{trading_mode}"
    else:
        name = base
    
    return sanitize_name(name)


def generate_constituent_name_v2(
    model_type: Literal['direction', 'volatility', 'rl'],
    instrument: str,
    timeframe: str,
    initial_balance: int,
    trading_mode: Literal['stock', 'margin'] = 'stock',
    use_v2_format: bool = True
) -> str:
    """
    Generate constituent model name.
    
    .. deprecated:: 3.0
        This function is deprecated and will be removed in Q3 2026.
        Use :func:`generate_constituent_name_v3` for new models.
        See docs/sdk/naming_migration_guide.md for migration instructions.
    
    Only RL models include trading_mode in the name (affects environment).
    Direction and volatility models are training_mode-agnostic.
    
    Args:
        model_type: Type of constituent model
        instrument: Trading instrument
        timeframe: Timeframe
        initial_balance: Initial balance (for RL models)
        trading_mode: Trading mode (for RL models only)
        use_v2_format: If True, use v2 format for RL models
    
    Returns:
        Model name string
    
    Examples:
        >>> generate_constituent_name_v2('direction', 'BTC/USDT', '1m', 10000)
        'direction__BTC_USDT__1m__bal10000'
        
        >>> generate_constituent_name_v2('rl', 'BTC/USDT', '1m', 10000, 'margin')
        'rl__BTC_USDT__1m__bal10000__margin'
        
        >>> generate_constituent_name_v2('volatility', 'BTC/USDT', '5m', 5000)
        'volatility__BTC_USDT__5m__bal5000'
    """
    warnings.warn(
        "generate_constituent_name_v2() is deprecated and will be removed in Q3 2026. "
        "Use generate_constituent_name_v3() for new models. "
        "See docs/sdk/naming_migration_guide.md for migration guide.",
        DeprecationWarning,
        stacklevel=2
    )
    
    inst = parse_instrument(instrument)
    tf = normalize_timeframe(timeframe)
    canon = f"{inst.base}_{inst.quote}"
    
    base = f"{model_type}__{canon}__{tf}__bal{int(initial_balance)}"
    
    # Only RL models need trading_mode (affects environment/leverage)
    if use_v2_format and model_type == 'rl':
        name = f"{base}__{trading_mode}"
    else:
        name = base
    
    return sanitize_name(name)


def parse_model_name(name: str) -> ModelNameComponents:
    """
    Parse model name into components.
    
    Supports both v1 and v2 formats:
    - v1: composite__BTC_USDT__1m__bal10000
    - v2: composite__BTC_USDT__1m__bal10000__stock
    
    Args:
        name: Model name string
    
    Returns:
        ModelNameComponents with parsed fields
    
    Raises:
        ValueError: If name format is invalid
    
    Examples:
        >>> components = parse_model_name('composite__BTC_USDT__1m__bal10000__stock')
        >>> components.model_type
        'composite'
        >>> components.trading_mode
        'stock'
        >>> components.version
        'v2'
        >>> components.is_v2
        True
    """
    parts = name.split('__')
    
    if len(parts) < 4:
        raise ValueError(
            f"Invalid model name format: {name}. "
            f"Expected at least 4 parts separated by '__'"
        )
    
    model_type = parts[0]
    instrument = parts[1]
    timeframe = parts[2]
    
    # Parse balance (format: bal10000)
    balance_str = parts[3]
    if not balance_str.startswith('bal'):
        raise ValueError(
            f"Invalid balance format in name: {balance_str}. "
            f"Expected format: bal10000"
        )
    
    try:
        initial_balance = int(balance_str[3:])  # Remove 'bal' prefix
    except ValueError:
        raise ValueError(
            f"Invalid balance value in name: {balance_str}. "
            f"Expected numeric value after 'bal'"
        )
    
    # Determine version and parse trading_mode
    if len(parts) == 4:
        # v1 format (no trading_mode)
        return ModelNameComponents(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            initial_balance=initial_balance,
            trading_mode=None,
            version='v1'
        )
    elif len(parts) == 5:
        # v2 format (with trading_mode)
        trading_mode_str = parts[4]
        
        if trading_mode_str not in ['stock', 'margin']:
            raise ValueError(
                f"Invalid trading_mode in name: {trading_mode_str}. "
                f"Expected 'stock' or 'margin'"
            )
        
        return ModelNameComponents(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            initial_balance=initial_balance,
            trading_mode=trading_mode_str,  # type: ignore
            version='v2'
        )
    else:
        raise ValueError(
            f"Invalid model name format: {name}. "
            f"Expected 4 or 5 parts, got {len(parts)}"
        )


def validate_model_name(name: str) -> bool:
    """
    Validate model name format.
    
    Args:
        name: Model name to validate
    
    Returns:
        True if valid, False otherwise
    
    Examples:
        >>> validate_model_name('composite__BTC_USDT__1m__bal10000__stock')
        True
        >>> validate_model_name('composite__BTC_USDT__1m__bal10000')
        True
        >>> validate_model_name('invalid_name')
        False
    """
    try:
        parse_model_name(name)
        return True
    except ValueError:
        return False


def migrate_v1_to_v2(
    v1_name: str,
    trading_mode: Literal['stock', 'margin'] = 'stock'
) -> str:
    """
    Migrate v1 model name to v2 format.
    
    Args:
        v1_name: Original v1 format name
        trading_mode: Trading mode to add (default: 'stock')
    
    Returns:
        v2 format name with trading_mode
    
    Raises:
        ValueError: If v1_name is not valid v1 format
    
    Examples:
        >>> migrate_v1_to_v2('composite__BTC_USDT__1m__bal10000')
        'composite__BTC_USDT__1m__bal10000__stock'
        
        >>> migrate_v1_to_v2('composite__BTC_USDT__1m__bal10000', 'margin')
        'composite__BTC_USDT__1m__bal10000__margin'
    """
    components = parse_model_name(v1_name)
    
    if components.is_v2:
        # Already v2 format, return as is
        return v1_name
    
    # Append trading_mode to create v2 format
    return f"{v1_name}__{trading_mode}"


def get_default_trading_mode(model_name: str) -> Literal['stock', 'margin']:
    """
    Get trading mode from model name, defaulting to 'stock' for v1 names.
    
    Args:
        model_name: Model name (v1 or v2 format)
    
    Returns:
        Trading mode ('stock' or 'margin')
    
    Examples:
        >>> get_default_trading_mode('composite__BTC_USDT__1m__bal10000')
        'stock'
        
        >>> get_default_trading_mode('composite__BTC_USDT__1m__bal10000__margin')
        'margin'
    """
    components = parse_model_name(model_name)
    return components.trading_mode if components.trading_mode else 'stock'


# =============================================================================
# Backward Compatibility Layer (Task 3.6)
# =============================================================================
# Added: October 22, 2025
# Purpose: Smooth transition from v2 to v3 naming convention
# Deprecation Timeline:
# - Q1 2026: v1/v2 write operations deprecated (warnings added)
# - Q3 2026: v1/v2 write operations removed
# - Indefinite: v1/v2 read operations supported for backward compatibility
# =============================================================================

import warnings


def _deprecation_warning_v2(function_name: str) -> None:
    """Issue deprecation warning for v2 naming functions."""
    warnings.warn(
        f"{function_name} is deprecated and will be removed in Q3 2026. "
        f"Use the v3 naming convention with generate_composite_name_v3() or "
        f"generate_model_name() with use_v3_format=True. "
        f"See docs/sdk/naming_migration_guide.md for migration guide.",
        DeprecationWarning,
        stacklevel=3
    )


def generate_model_name(
    *,
    instrument: str,
    trading_mode: Union[str, Literal['SPOT', 'MARGIN', 'spot', 'margin', 'stock', 'margin']],
    starting_balance: int,
    agent_strategy: Optional[Union[str, 'AgentStrategy']] = None,
    version: Optional[int] = None,
    stage: Optional[Literal['dev', 'staging', 'prod', 'retired']] = None,
    leverage: Optional[int] = None,
    timeframe: Optional[str] = None,
    use_v3_format: bool = True,
) -> str:
    """
    Universal model name generator with automatic format selection.
    
    This function provides a unified interface for generating model names
    in either v2 or v3 format. It's recommended to use v3 format for all
    new models.
    
    Args:
        instrument: Instrument symbol (e.g., 'BTCUSDT', 'BTC/USDT')
        trading_mode: Trading mode ('SPOT'/'MARGIN' for v3, 'stock'/'margin' for v2)
        starting_balance: Starting balance in quote asset
        agent_strategy: Strategy code (required for v3, e.g., 'AGGR', 'CONS')
        version: Model version (required for v3, positive integer)
        stage: Lifecycle stage (required for v3: 'dev', 'staging', 'prod', 'retired')
        leverage: Leverage level (required for MARGIN mode in v3)
        timeframe: Timeframe (required for v2, e.g., '1m', '5m')
        use_v3_format: If True, use v3 format; if False, use v2 format
    
    Returns:
        Model name in the specified format
    
    Raises:
        ValueError: If required parameters are missing for the selected format
        InvalidLeverageError: If leverage validation fails
        InvalidAgentStrategyError: If agent_strategy is invalid
    
    Examples:
        # V3 format (recommended)
        >>> generate_model_name(
        ...     instrument='BTCUSDT',
        ...     trading_mode='SPOT',
        ...     starting_balance=10000,
        ...     agent_strategy='AGGR',
        ...     version=1,
        ...     stage='dev',
        ...     use_v3_format=True
        ... )
        'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        
        # V2 format (deprecated)
        >>> generate_model_name(
        ...     instrument='BTC/USDT',
        ...     trading_mode='stock',
        ...     starting_balance=10000,
        ...     timeframe='1m',
        ...     use_v3_format=False
        ... )
        'composite__BTC_USDT__1m__bal10000__stock'
    """
    if use_v3_format:
        # V3 format - requires agent_strategy, version, stage
        if agent_strategy is None:
            raise ValueError(
                "agent_strategy is required for v3 format. "
                "Provide one of: 'AGGR', 'CONS', 'BALA', 'SCAL'"
            )
        if version is None:
            raise ValueError(
                "version is required for v3 format. "
                "Provide a positive integer (e.g., 1, 2, 3)"
            )
        if stage is None:
            raise ValueError(
                "stage is required for v3 format. "
                "Provide one of: 'dev', 'staging', 'prod', 'retired'"
            )
        
        # Map v2 trading_mode to v3 if needed
        if trading_mode.lower() == 'stock':
            trading_mode_v3 = 'SPOT'
        elif trading_mode.lower() == 'margin':
            trading_mode_v3 = 'MARGIN'
        else:
            trading_mode_v3 = trading_mode
        
        return generate_composite_name_v3(
            instrument=instrument,
            trading_mode=trading_mode_v3,  # type: ignore
            agent_strategy=agent_strategy,
            starting_balance=starting_balance,
            version=version,
            stage=stage,
            leverage=leverage
        )
    else:
        # V2 format (deprecated) - requires timeframe
        _deprecation_warning_v2('generate_model_name with use_v3_format=False')
        
        if timeframe is None:
            raise ValueError(
                "timeframe is required for v2 format. "
                "Provide a timeframe string (e.g., '1m', '5m', '1h')"
            )
        
        # Map v3 trading_mode to v2 if needed
        if trading_mode.upper() == 'SPOT':
            trading_mode_v2 = 'stock'
        elif trading_mode.upper() == 'MARGIN':
            trading_mode_v2 = 'margin'
        else:
            trading_mode_v2 = trading_mode  # type: ignore
        
        return generate_composite_name_v2(
            instrument=instrument,
            timeframe=timeframe,
            initial_balance=starting_balance,
            trading_mode=trading_mode_v2,  # type: ignore
            use_v2_format=True
        )


# =============================================================================
# ML-5.0 Enhanced Naming Convention (v3)
# =============================================================================


class NamingError(Exception):
    """Base exception for naming errors."""
    pass


class InvalidInstrumentError(NamingError):
    """Invalid instrument format or value."""
    pass


class InvalidTradingModeError(NamingError):
    """Invalid trading mode value."""
    pass


class InvalidLeverageError(NamingError):
    """Invalid leverage value or usage."""
    pass


class InvalidAgentStrategyError(NamingError):
    """Invalid agent strategy value."""
    pass


class InvalidNameFormatError(NamingError):
    """Invalid model name format."""
    pass


def _normalize_instrument_v3(instrument: str) -> str:
    """
    Normalize instrument to v3 format (BASEQOUTE, no separator).
    
    Args:
        instrument: Instrument string (e.g., 'BTC/USDT', 'BTC-USDT', 'BTC_USDT', 'BTCUSDT')
    
    Returns:
        Normalized instrument (e.g., 'BTCUSDT')
    
    Raises:
        InvalidInstrumentError: If instrument format is invalid
    """
    if not instrument:
        raise InvalidInstrumentError("Empty instrument string")
    
    # If already in BASEQOUTE format (no separators), just uppercase it
    if '/' not in instrument and '-' not in instrument and '_' not in instrument:
        # Already normalized, just ensure uppercase
        normalized = instrument.upper()
        # Basic validation: should be alphanumeric and reasonable length
        if not normalized.isalnum() or len(normalized) < 4:
            raise InvalidInstrumentError(
                f"Invalid instrument format: {instrument}. "
                f"Expected format like 'BTCUSDT' or 'BTC/USDT'"
            )
        return normalized
    
    # Has separator - normalize to '/' before parsing
    # Replace dash with slash first
    normalized_input = instrument.replace('-', '/').replace('_', '/')
    
    # Use parse_instrument to validate and normalize
    try:
        inst = parse_instrument(normalized_input)
        return f"{inst.base}{inst.quote}".upper()
    except Exception as e:
        raise InvalidInstrumentError(
            f"Invalid instrument format: {instrument}. "
            f"Expected format like 'BTC/USDT' or 'BTCUSDT'"
        ) from e


def _validate_leverage_v3(
    trading_mode: str,
    leverage: Optional[int]
) -> None:
    """
    Validate leverage parameter for v3 naming.
    
    Args:
        trading_mode: Trading mode ('SPOT' or 'MARGIN')
        leverage: Leverage value or None
    
    Raises:
        InvalidLeverageError: If leverage validation fails
    """
    if trading_mode == 'MARGIN':
        if leverage is None:
            raise InvalidLeverageError(
                "leverage is required when trading_mode is MARGIN "
                "(per REQ-001-ML ML-2.0, ML-2.1)"
            )
        if leverage < 1:
            raise InvalidLeverageError(
                f"leverage must be >= 1 for MARGIN mode, got {leverage}"
            )
        if leverage > 100:
            raise InvalidLeverageError(
                f"leverage must be <= 100 (platform maximum), got {leverage}"
            )
    elif trading_mode == 'SPOT':
        if leverage is not None:
            raise InvalidLeverageError(
                "leverage must be None for SPOT mode "
                "(per REQ-001-ML ML-2.1)"
            )


def _get_strategy_code(agent_strategy: Union[str, AgentStrategy]) -> str:
    """
    Get 4-character strategy code from strategy value.
    
    Args:
        agent_strategy: AgentStrategy enum or strategy code string
    
    Returns:
        4-character strategy code (e.g., 'AGGR')
    
    Raises:
        InvalidAgentStrategyError: If strategy is invalid
    """
    if AgentStrategy is None:
        # Fallback if AgentStrategy not available
        if isinstance(agent_strategy, str):
            code = agent_strategy.upper()
            if len(code) == 4 and code.isalpha():
                return code
            raise InvalidAgentStrategyError(
                f"Invalid strategy code: {agent_strategy}. Expected 4-letter code."
            )
        raise InvalidAgentStrategyError(
            f"AgentStrategy enum not available and strategy is not a string: {agent_strategy}"
        )
    
    if isinstance(agent_strategy, str):
        # Try to convert string to enum
        try:
            strategy_enum = AgentStrategy(agent_strategy.upper())
            return strategy_enum.value
        except (ValueError, KeyError):
            # Try to match by name
            try:
                strategy_enum = AgentStrategy[agent_strategy.upper()]
                return strategy_enum.value
            except KeyError:
                raise InvalidAgentStrategyError(
                    f"Invalid agent strategy: {agent_strategy}. "
                    f"Valid values: {[s.value for s in AgentStrategy]}"
                )
    elif hasattr(agent_strategy, 'value'):
        # Already an enum
        return agent_strategy.value
    else:
        raise InvalidAgentStrategyError(
            f"Invalid agent_strategy type: {type(agent_strategy)}. "
            f"Expected AgentStrategy enum or string."
        )


def generate_composite_name_v3(
    *,
    instrument: str,
    trading_mode: Union[str, Literal['SPOT', 'MARGIN', 'spot', 'margin']],
    agent_strategy: Union[str, AgentStrategy],
    starting_balance: int,
    version: int,
    stage: Literal['dev', 'staging', 'prod', 'retired'],
    leverage: Optional[int] = None,
) -> str:
    """
    Generate v3 composite model name.
    
    Format: INSTR.MODE[.LEVx{n}].STRAT.SB{amount}.v{version}.{stage}
    
    Per REQ-001-ML ML-5.0, this format encodes all fixed training parameters
    in the model name for easy discovery and filtering.
    
    Args:
        instrument: Instrument symbol (e.g., 'BTCUSDT', 'BTC/USDT', 'ETH-USDT')
        trading_mode: 'SPOT' or 'MARGIN' (case-insensitive)
        agent_strategy: Strategy code (e.g., 'AGGR', 'CONS') or AgentStrategy enum
        starting_balance: Starting balance in quote asset (100-1000000)
        version: Model version (positive integer)
        stage: Lifecycle stage ('dev', 'staging', 'prod', 'retired')
        leverage: Leverage level (required for MARGIN, forbidden for SPOT)
    
    Returns:
        v3 format composite model name
    
    Raises:
        InvalidInstrumentError: If instrument format is invalid
        InvalidTradingModeError: If trading_mode is invalid
        InvalidAgentStrategyError: If agent_strategy is invalid
        InvalidLeverageError: If leverage validation fails
        ValueError: If other parameters are invalid
    
    Examples:
        >>> generate_composite_name_v3(
        ...     instrument='BTCUSDT',
        ...     trading_mode='SPOT',
        ...     agent_strategy='AGGR',
        ...     starting_balance=10000,
        ...     version=1,
        ...     stage='dev'
        ... )
        'BTCUSDT.SPOT.AGGR.SB10000.v1.dev'
        
        >>> generate_composite_name_v3(
        ...     instrument='ETH/USDT',
        ...     trading_mode='MARGIN',
        ...     agent_strategy='CONS',
        ...     starting_balance=50000,
        ...     version=2,
        ...     stage='prod',
        ...     leverage=5
        ... )
        'ETHUSDT.MARGIN.LEVx5.CONS.SB50000.v2.prod'
    """
    # Validate and normalize instrument
    instr_part = _normalize_instrument_v3(instrument)
    
    # Validate and normalize trading_mode
    mode_str = str(trading_mode).upper()
    if mode_str not in ['SPOT', 'MARGIN']:
        raise InvalidTradingModeError(
            f"Invalid trading_mode: {trading_mode}. Expected 'SPOT' or 'MARGIN'"
        )
    
    # Validate leverage vs trading_mode
    _validate_leverage_v3(mode_str, leverage)
    
    # Get strategy code
    strat_code = _get_strategy_code(agent_strategy)
    
    # Validate starting_balance
    if starting_balance < 100:
        raise ValueError(
            f"starting_balance must be >= 100, got {starting_balance}"
        )
    if starting_balance > 1_000_000:
        raise ValueError(
            f"starting_balance must be <= 1000000, got {starting_balance}"
        )
    
    # Validate version
    if version < 1:
        raise ValueError(
            f"version must be >= 1, got {version}"
        )
    
    # Validate stage
    valid_stages = ['dev', 'staging', 'prod', 'retired']
    if stage not in valid_stages:
        raise ValueError(
            f"Invalid stage: {stage}. Expected one of {valid_stages}"
        )
    
    # Build name parts
    parts = [instr_part, mode_str]
    
    # Add leverage for MARGIN mode
    if mode_str == 'MARGIN':
        parts.append(f"LEVx{leverage}")
    
    # Add strategy, balance, version, stage
    parts.extend([
        strat_code,
        f"SB{starting_balance}",
        f"v{version}",
        stage
    ])
    
    return '.'.join(parts)


def generate_constituent_name_v3(
    *,
    model_type: Literal['direction', 'volatility', 'rl'],
    instrument: str,
    trading_mode: Union[str, Literal['SPOT', 'MARGIN', 'spot', 'margin']],
    agent_strategy: Union[str, AgentStrategy],
    starting_balance: int,
    version: int,
    stage: Literal['dev', 'staging', 'prod', 'retired'],
    leverage: Optional[int] = None,
) -> str:
    """
    Generate v3 constituent model name.
    
    Format same as composite but with model_type prefix:
    {type}.INSTR.MODE[.LEVx{n}].STRAT.SB{amount}.v{version}.{stage}
    
    Args:
        model_type: Type of constituent ('direction', 'volatility', 'rl')
        instrument: Instrument symbol
        trading_mode: 'SPOT' or 'MARGIN'
        agent_strategy: Strategy code or AgentStrategy enum
        starting_balance: Starting balance
        version: Model version
        stage: Lifecycle stage
        leverage: Leverage level (required for MARGIN)
    
    Returns:
        v3 format constituent model name
    
    Raises:
        Same exceptions as generate_composite_name_v3
    
    Examples:
        >>> generate_constituent_name_v3(
        ...     model_type='rl',
        ...     instrument='BTCUSDT',
        ...     trading_mode='SPOT',
        ...     agent_strategy='BALA',
        ...     starting_balance=10000,
        ...     version=1,
        ...     stage='dev'
        ... )
        'rl.BTCUSDT.SPOT.BALA.SB10000.v1.dev'
        
        >>> generate_constituent_name_v3(
        ...     model_type='direction',
        ...     instrument='ETH/USDT',
        ...     trading_mode='MARGIN',
        ...     agent_strategy='SCAL',
        ...     starting_balance=25000,
        ...     version=3,
        ...     stage='prod',
        ...     leverage=10
        ... )
        'direction.ETHUSDT.MARGIN.LEVx10.SCAL.SB25000.v3.prod'
    """
    # Generate composite-style name
    composite_name = generate_composite_name_v3(
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage
    )
    
    # Prepend model type
    return f"{model_type}.{composite_name}"


def parse_model_name_v3(name: str) -> "ModelNameComponentsV3":
    """
    Parse v3 model name into components.
    
    Format: INSTR.MODE[.LEVx{n}].STRAT.SB{amount}.v{version}.{stage}
    Or with type: {type}.INSTR.MODE[.LEVx{n}].STRAT.SB{amount}.v{version}.{stage}
    
    Args:
        name: v3 format model name
    
    Returns:
        ModelNameComponentsV3 with all parsed fields
    
    Raises:
        InvalidNameFormatError: If name format is invalid
    
    Examples:
        >>> components = parse_model_name_v3('BTCUSDT.SPOT.AGGR.SB10000.v1.dev')
        >>> components.instrument
        'BTCUSDT'
        >>> components.trading_mode
        'SPOT'
        >>> components.agent_strategy_code
        'AGGR'
        >>> components.leverage
        None
        
        >>> components = parse_model_name_v3('ETHUSDT.MARGIN.LEVx5.CONS.SB50000.v2.prod')
        >>> components.leverage
        5
    """
    parts = name.split('.')
    
    # Determine if there's a model_type prefix
    model_type: Optional[str] = None
    start_idx = 0
    
    # Check if first part is a known model type
    if len(parts) > 0 and parts[0].lower() in ['composite', 'direction', 'volatility', 'rl']:
        model_type = parts[0].lower()
        start_idx = 1
    
    # Expected format without type: INSTR.MODE[.LEVx{n}].STRAT.SB{amount}.v{version}.{stage}
    # Minimum parts: 6 (SPOT) or 7 (MARGIN with leverage)
    remaining_parts = parts[start_idx:]
    
    if len(remaining_parts) < 6:
        raise InvalidNameFormatError(
            f"Invalid v3 name format: {name}. Expected at least 6 components."
        )
    
    try:
        # Parse instrument (part 0)
        instrument = remaining_parts[0]
        
        # Parse trading_mode (part 1)
        trading_mode = remaining_parts[1]
        if trading_mode not in ['SPOT', 'MARGIN']:
            raise InvalidNameFormatError(
                f"Invalid trading_mode in name: {trading_mode}. Expected 'SPOT' or 'MARGIN'"
            )
        
        # Check for leverage (only in MARGIN mode)
        leverage: Optional[int] = None
        strategy_idx = 2
        
        if trading_mode == 'MARGIN':
            # Next part should be LEVx{n}
            if not remaining_parts[2].startswith('LEVx'):
                raise InvalidNameFormatError(
                    f"Expected leverage (LEVx{{n}}) for MARGIN mode in: {name}"
                )
            try:
                leverage = int(remaining_parts[2][4:])  # Remove 'LEVx' prefix
            except ValueError:
                raise InvalidNameFormatError(
                    f"Invalid leverage format in name: {remaining_parts[2]}"
                )
            strategy_idx = 3
        elif remaining_parts[2].startswith('LEVx'):
            raise InvalidNameFormatError(
                f"Leverage not allowed for SPOT mode in: {name}"
            )
        
        # Parse strategy code
        agent_strategy_code = remaining_parts[strategy_idx]
        if len(agent_strategy_code) != 4 or not agent_strategy_code.isupper():
            raise InvalidNameFormatError(
                f"Invalid strategy code in name: {agent_strategy_code}. "
                f"Expected 4 uppercase letters."
            )
        
        # Parse starting balance (SB{amount})
        sb_part = remaining_parts[strategy_idx + 1]
        if not sb_part.startswith('SB'):
            raise InvalidNameFormatError(
                f"Invalid balance format in name: {sb_part}. Expected 'SB{{amount}}'"
            )
        try:
            starting_balance = int(sb_part[2:])  # Remove 'SB' prefix
        except ValueError:
            raise InvalidNameFormatError(
                f"Invalid balance value in name: {sb_part}"
            )
        
        # Parse version (v{n})
        version_part = remaining_parts[strategy_idx + 2]
        if not version_part.startswith('v'):
            raise InvalidNameFormatError(
                f"Invalid version format in name: {version_part}. Expected 'v{{n}}'"
            )
        try:
            version = int(version_part[1:])  # Remove 'v' prefix
        except ValueError:
            raise InvalidNameFormatError(
                f"Invalid version value in name: {version_part}"
            )
        
        # Parse stage
        stage = remaining_parts[strategy_idx + 3]
        valid_stages = ['dev', 'staging', 'prod', 'retired']
        if stage not in valid_stages:
            raise InvalidNameFormatError(
                f"Invalid stage in name: {stage}. Expected one of {valid_stages}"
            )
        
        return ModelNameComponentsV3(
            model_type=model_type or 'composite',
            instrument=instrument,
            trading_mode=trading_mode,  # type: ignore
            agent_strategy_code=agent_strategy_code,
            starting_balance=starting_balance,
            version=version,
            stage=stage,  # type: ignore
            leverage=leverage,
            format_version='v3'
        )
        
    except (IndexError, ValueError) as e:
        raise InvalidNameFormatError(
            f"Failed to parse v3 name: {name}. Error: {str(e)}"
        ) from e


class ModelNameComponentsV3(BaseModel):
    """
    Parsed components of a v3 model name.
    
    Format: INSTR.MODE[.LEVx{n}].STRAT.SB{amount}.v{version}.{stage}
    """
    
    model_type: str = Field(description="Type of model (composite, direction, volatility, rl)")
    instrument: str = Field(description="Trading instrument (e.g., BTCUSDT)")
    trading_mode: Literal['SPOT', 'MARGIN'] = Field(description="Trading mode")
    agent_strategy_code: str = Field(description="4-character strategy code (e.g., AGGR)")
    starting_balance: int = Field(gt=0, description="Starting balance for training")
    version: int = Field(ge=1, description="Model version")
    stage: Literal['dev', 'staging', 'prod', 'retired'] = Field(description="Lifecycle stage")
    leverage: Optional[int] = Field(None, description="Leverage (only for MARGIN mode)")
    format_version: Literal['v3'] = Field('v3', description="Name format version")
    
    @field_validator('agent_strategy_code')
    @classmethod
    def validate_strategy_code(cls, v: str) -> str:
        """Validate strategy code format."""
        if len(v) != 4 or not v.isupper():
            raise ValueError(
                f"Invalid strategy code: {v}. Expected 4 uppercase letters."
            )
        return v
    
    @field_validator('leverage')
    @classmethod
    def validate_leverage(cls, v: Optional[int], info) -> Optional[int]:
        """Validate leverage based on trading_mode."""
        # Get trading_mode from values dict
        trading_mode = info.data.get('trading_mode')
        
        if trading_mode == 'MARGIN':
            if v is None:
                raise ValueError("leverage required for MARGIN mode")
            if v < 1 or v > 100:
                raise ValueError(f"leverage must be 1-100, got {v}")
        elif trading_mode == 'SPOT':
            if v is not None:
                raise ValueError("leverage must be None for SPOT mode")
        
        return v
    
    @property
    def is_v3(self) -> bool:
        """Check if this is v3 format."""
        return True
    
    @property
    def canonical_instrument(self) -> str:
        """
        Get canonical instrument name with slash separator.
        
        Attempts to split into base/quote for common patterns.
        """
        # Common quote assets
        quote_assets = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB', 'USD']
        
        for quote in quote_assets:
            if self.instrument.endswith(quote) and len(self.instrument) > len(quote):
                base = self.instrument[:-len(quote)]
                return f"{base}/{quote}"
        
        # Fallback: return as is
        return self.instrument
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'model_type': self.model_type,
            'instrument': self.instrument,
            'trading_mode': self.trading_mode,
            'agent_strategy_code': self.agent_strategy_code,
            'starting_balance': self.starting_balance,
            'version': self.version,
            'stage': self.stage,
            'leverage': self.leverage,
            'format_version': self.format_version
        }


# =============================================================================
# Version Detection and Migration Utilities
# =============================================================================


def detect_name_version(name: str) -> Literal['v1', 'v2', 'v3']:
    """
    Auto-detect model name format version.
    
    Detection logic:
    - v3: Contains dots as separators (e.g., 'BTCUSDT.SPOT.AGGR.SB10000.v1.dev')
    - v2: Contains '__' separators and 5 parts (with trading_mode)
    - v1: Contains '__' separators and 4 parts (no trading_mode)
    
    Args:
        name: Model name string
    
    Returns:
        Detected version ('v1', 'v2', or 'v3')
    
    Raises:
        InvalidNameFormatError: If name format cannot be determined
    
    Examples:
        >>> detect_name_version('BTCUSDT.SPOT.AGGR.SB10000.v1.dev')
        'v3'
        >>> detect_name_version('composite__BTC_USDT__1m__bal10000__stock')
        'v2'
        >>> detect_name_version('composite__BTC_USDT__1m__bal10000')
        'v1'
    """
    if not name:
        raise InvalidNameFormatError("Empty model name")
    
    # v3 uses dots
    if '.' in name and '__' not in name:
        # Verify it's actually v3 format
        try:
            parse_model_name_v3(name)
            return 'v3'
        except InvalidNameFormatError:
            raise InvalidNameFormatError(
                f"Name contains dots but is not valid v3 format: {name}"
            )
    
    # v1/v2 use double underscores
    if '__' in name:
        parts = name.split('__')
        if len(parts) == 5:
            return 'v2'
        elif len(parts) == 4:
            return 'v1'
        else:
            raise InvalidNameFormatError(
                f"Invalid v1/v2 name format: {name}. "
                f"Expected 4 or 5 parts, got {len(parts)}"
            )
    
    raise InvalidNameFormatError(
        f"Cannot determine version for name: {name}. "
        f"Expected dots (v3) or double underscores (v1/v2)"
    )


def can_migrate_automatically(
    old_name: str,
    target_version: Literal['v2', 'v3'] = 'v3'
) -> Tuple[bool, Optional[str]]:
    """
    Check if a model name can be migrated automatically to target version.
    
    Args:
        old_name: Original model name
        target_version: Target version ('v2' or 'v3')
    
    Returns:
        Tuple of (can_migrate: bool, reason: Optional[str])
        If can_migrate is False, reason explains why
    
    Examples:
        >>> can_migrate_automatically('composite__BTC_USDT__1m__bal10000', 'v3')
        (False, 'Migration to v3 requires agent_strategy and other parameters')
        >>> can_migrate_automatically('composite__BTC_USDT__1m__bal10000', 'v2')
        (True, None)
    """
    try:
        current_version = detect_name_version(old_name)
    except InvalidNameFormatError as e:
        return (False, f"Invalid name format: {str(e)}")
    
    if current_version == target_version:
        return (False, f"Name is already {target_version} format")
    
    if target_version == 'v2':
        if current_version == 'v1':
            # v1 -> v2: Just add trading_mode (can default to 'stock')
            return (True, None)
        elif current_version == 'v3':
            # v3 -> v2: Lossy (loses agent_strategy, leverage, version, stage)
            return (False, "Downgrade from v3 to v2 is lossy (not recommended)")
    
    elif target_version == 'v3':
        if current_version in ['v1', 'v2']:
            # v1/v2 -> v3: Requires additional parameters
            return (False, "Migration to v3 requires agent_strategy and other parameters")
    
    return (False, "Unknown migration path")


def migrate_name_to_v3(
    old_name: str,
    agent_strategy: Union[str, AgentStrategy],
    leverage: Optional[int] = None,
    version: int = 1,
    stage: Literal['dev', 'staging', 'prod', 'retired'] = 'dev'
) -> str:
    """
    Migrate v1/v2 model name to v3 format.
    
    This function extracts what it can from the old name and requires
    the caller to provide the new v3-required parameters.
    
    Args:
        old_name: Original v1 or v2 format name
        agent_strategy: Agent strategy for the model
        leverage: Leverage (required if MARGIN mode)
        version: Model version (default: 1)
        stage: Lifecycle stage (default: 'dev')
    
    Returns:
        v3 format model name
    
    Raises:
        InvalidNameFormatError: If old_name is invalid
        InvalidLeverageError: If leverage validation fails
    
    Examples:
        >>> migrate_name_to_v3(
        ...     'composite__BTC_USDT__1m__bal10000__stock',
        ...     agent_strategy='BALA',
        ...     version=1,
        ...     stage='dev'
        ... )
        'BTCUSDT.SPOT.BALA.SB10000.v1.dev'
        
        >>> migrate_name_to_v3(
        ...     'composite__ETH_USDT__5m__bal50000__margin',
        ...     agent_strategy='AGGR',
        ...     leverage=5,
        ...     version=2,
        ...     stage='prod'
        ... )
        'ETHUSDT.MARGIN.LEVx5.AGGR.SB50000.v2.prod'
    """
    # Detect and validate old name version
    old_version = detect_name_version(old_name)
    
    if old_version == 'v3':
        # Already v3, just return it
        # (Could optionally update parameters, but for now just return)
        return old_name
    
    # Parse old name
    old_components = parse_model_name(old_name)
    
    # Extract instrument (normalize to v3 format)
    instrument = _normalize_instrument_v3(old_components.canonical_instrument)
    
    # Map trading_mode
    if old_components.trading_mode == 'stock' or old_components.trading_mode is None:
        trading_mode = 'SPOT'
    elif old_components.trading_mode == 'margin':
        trading_mode = 'MARGIN'
    else:
        trading_mode = 'SPOT'  # Default fallback
    
    # Extract starting_balance
    starting_balance = old_components.initial_balance
    
    # Generate v3 name with new parameters
    return generate_composite_name_v3(
        instrument=instrument,
        trading_mode=trading_mode,
        agent_strategy=agent_strategy,
        starting_balance=starting_balance,
        version=version,
        stage=stage,
        leverage=leverage
    )


def parse_model_name_universal(name: str) -> Union[ModelNameComponents, ModelNameComponentsV3]:
    """
    Parse model name of any version (v1, v2, or v3).
    
    Automatically detects version and returns appropriate components object.
    
    Args:
        name: Model name string (any version)
    
    Returns:
        ModelNameComponents (for v1/v2) or ModelNameComponentsV3 (for v3)
    
    Raises:
        InvalidNameFormatError: If name format is invalid
    
    Examples:
        >>> components = parse_model_name_universal('BTCUSDT.SPOT.AGGR.SB10000.v1.dev')
        >>> isinstance(components, ModelNameComponentsV3)
        True
        >>> components = parse_model_name_universal('composite__BTC_USDT__1m__bal10000__stock')
        >>> isinstance(components, ModelNameComponents)
        True
    """
    version = detect_name_version(name)
    
    if version == 'v3':
        return parse_model_name_v3(name)
    else:
        return parse_model_name(name)
