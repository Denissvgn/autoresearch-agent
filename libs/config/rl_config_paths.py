"""ML-67: Shared RL config path resolution for strategy + market type separation.

Single source of truth for building and resolving RL production config
filenames. All consumers (setup.py, promote.py, instrument_rl_config.py,
config_promoter.py, retraining_scheduler.py, etc.) import from here to
guarantee consistent naming conventions.

Naming convention:
    {INSTRUMENT}_{TIMEFRAME}_{STRATEGY}_{MARKET}_production.yaml
    e.g. DOGE_USDT_15m_BALA_stock_production.yaml

Resolution cascade (first match wins):
    Tier 2: configs/rl/{INST}_{TF}_{STRAT}_{MKT}_production.yaml  (promoted)
    Tier 1L: configs/rl/{INST}_{TF}_production.yaml                (legacy)
    Tier 1: configs/rl/presets/{STRATEGY}.yaml                     (strategy preset)
    Tier 0: configs/rl/default_production.yaml                     (global default)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Valid strategies (must match AgentStrategy enum values)
VALID_STRATEGIES = {"AGGR", "CONS", "BALA", "SCAL"}
# Valid market types
VALID_MARKET_TYPES = {"stock", "margin"}

DEFAULT_STRATEGY = "BALA"
DEFAULT_MARKET_TYPE = "stock"


def production_config_filename(
    instrument: str,
    timeframe: str,
    strategy: str = DEFAULT_STRATEGY,
    market_type: str = DEFAULT_MARKET_TYPE,
) -> str:
    """Build the production config filename for a given combination.

    Returns:
        e.g. ``"DOGE_USDT_15m_BALA_stock_production.yaml"``
    """
    strategy = strategy.upper()
    market_type = market_type.lower()
    return f"{instrument}_{timeframe}_{strategy}_{market_type}_production.yaml"


def legacy_config_filename(instrument: str, timeframe: str) -> str:
    """Build the legacy (pre-ML-67) production config filename.

    Returns:
        e.g. ``"DOGE_USDT_15m_production.yaml"``
    """
    return f"{instrument}_{timeframe}_production.yaml"


def preset_filename(strategy: str) -> str:
    """Build the strategy preset filename.

    Returns:
        e.g. ``"presets/BALA.yaml"``
    """
    return f"presets/{strategy.upper()}.yaml"


def resolve_production_config(
    instrument: str,
    timeframe: str,
    strategy: Optional[str] = None,
    market_type: Optional[str] = None,
    configs_dir: Optional[Path] = None,
) -> Tuple[Optional[Path], int]:
    """Resolve the best-match RL production config via the 4-tier cascade.

    Cascade:
        Tier 2: exact match  {INST}_{TF}_{STRAT}_{MKT}_production.yaml
        Tier 1L: legacy      {INST}_{TF}_production.yaml
        Tier 1: preset       presets/{STRATEGY}.yaml
        Tier 0: default      default_production.yaml

    Returns:
        ``(path, tier)`` where ``path`` is the resolved Path and ``tier``
        is the tier number (0–2, or -1 if nothing found).
    """
    if configs_dir is None:
        configs_dir = Path("configs/rl")

    strat = (strategy or DEFAULT_STRATEGY).upper()
    mkt = (market_type or DEFAULT_MARKET_TYPE).lower()

    # Tier 2: exact match (new naming)
    exact = configs_dir / production_config_filename(instrument, timeframe, strat, mkt)
    if exact.exists():
        logger.info(
            "rl_config_resolved tier=2 path=%s instrument=%s strategy=%s market=%s",
            exact, instrument, strat, mkt,
        )
        return exact, 2

    # Tier 1L: legacy naming (pre-ML-67 backward compat)
    legacy = configs_dir / legacy_config_filename(instrument, timeframe)
    if legacy.exists():
        logger.info(
            "rl_config_resolved tier=1L path=%s instrument=%s (legacy fallback)",
            legacy, instrument,
        )
        return legacy, 1

    # Tier 1: strategy preset
    preset = configs_dir / preset_filename(strat)
    if preset.exists():
        logger.info(
            "rl_config_resolved tier=1 path=%s strategy=%s (preset)",
            preset, strat,
        )
        return preset, 1

    # Tier 0: global default
    default = configs_dir / "default_production.yaml"
    if default.exists():
        logger.info(
            "rl_config_resolved tier=0 path=%s (global default)", default,
        )
        return default, 0

    logger.warning(
        "rl_config_not_found instrument=%s timeframe=%s strategy=%s market=%s",
        instrument, timeframe, strat, mkt,
    )
    return None, -1


def resolve_and_merge_config(
    instrument: str,
    timeframe: str,
    strategy: Optional[str] = None,
    market_type: Optional[str] = None,
    configs_dir: Optional[Path] = None,
) -> Tuple[Dict[str, Any], int]:
    """Resolve and deep-merge the full config stack.

    Merge order: default → preset → promoted (each layer overrides the previous).

    Returns:
        ``(merged_config, highest_tier)`` where ``highest_tier`` is the highest
        tier that was found and merged (0=default only, 1=preset, 2=promoted).
    """
    import yaml

    if configs_dir is None:
        configs_dir = Path("configs/rl")

    strat = (strategy or DEFAULT_STRATEGY).upper()
    mkt = (market_type or DEFAULT_MARKET_TYPE).lower()
    merged: Dict[str, Any] = {}
    highest_tier = -1

    # Layer 0: global default
    default_path = configs_dir / "default_production.yaml"
    if default_path.exists():
        with open(default_path) as f:
            default_cfg = yaml.safe_load(f) or {}
        merged = deep_merge(merged, default_cfg)
        highest_tier = 0

    # Layer 1: strategy preset
    preset_path = configs_dir / preset_filename(strat)
    if preset_path.exists():
        with open(preset_path) as f:
            preset_cfg = yaml.safe_load(f) or {}
        merged = deep_merge(merged, preset_cfg)
        highest_tier = max(highest_tier, 1)

    # Layer 2: promoted instrument config (try exact first, then legacy)
    promoted_path = configs_dir / production_config_filename(instrument, timeframe, strat, mkt)
    if not promoted_path.exists():
        promoted_path = configs_dir / legacy_config_filename(instrument, timeframe)
    if promoted_path.exists():
        with open(promoted_path) as f:
            promoted_cfg = yaml.safe_load(f) or {}
        merged = deep_merge(merged, promoted_cfg)
        highest_tier = max(highest_tier, 2)

    return merged, highest_tier


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively deep-merge *override* into *base*.

    - Dict values are merged recursively.
    - All other types: override replaces base.
    - Neither input is mutated; returns a new dict.
    """
    result = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def parse_production_filename(filename: str) -> Dict[str, Optional[str]]:
    """Parse a production config filename into its components.

    Handles both new and legacy naming conventions:
        New:    DOGE_USDT_15m_BALA_stock_production.yaml
        Legacy: DOGE_USDT_15m_production.yaml

    Returns:
        Dict with keys: instrument, timeframe, strategy, market_type.
        strategy and market_type are None for legacy filenames.
    """
    stem = filename.replace("_production.yaml", "").replace("_production", "")

    # Try new format: {BASE}_{QUOTE}_{TF}_{STRAT}_{MKT}
    parts = stem.split("_")

    # Minimum 3 parts: BASE_QUOTE_TF
    if len(parts) >= 5:
        # Check if second-to-last is a strategy and last is a market type
        candidate_strategy = parts[-2].upper()
        candidate_market = parts[-1].lower()
        if candidate_strategy in VALID_STRATEGIES and candidate_market in VALID_MARKET_TYPES:
            instrument = "_".join(parts[:-3])
            timeframe = parts[-3]
            return {
                "instrument": instrument,
                "timeframe": timeframe,
                "strategy": candidate_strategy,
                "market_type": candidate_market,
            }

    # Legacy format: {BASE}_{QUOTE}_{TF}
    if len(parts) >= 3:
        timeframe = parts[-1]
        instrument = "_".join(parts[:-1])
        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "strategy": None,
            "market_type": None,
        }

    return {"instrument": stem, "timeframe": None, "strategy": None, "market_type": None}
