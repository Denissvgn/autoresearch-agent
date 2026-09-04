"""Advanced optional feature lanes."""

from .vdmc import (
    VDMC_FEATURE_COLUMNS,
    VDMC_PARAMS_HASH_VARIANT,
    calculate_vdmc_indicators,
    compute_vdmc_params_hash,
    canonical_vdmc_params,
)

__all__ = [
    "VDMC_FEATURE_COLUMNS",
    "VDMC_PARAMS_HASH_VARIANT",
    "calculate_vdmc_indicators",
    "compute_vdmc_params_hash",
    "canonical_vdmc_params",
]
