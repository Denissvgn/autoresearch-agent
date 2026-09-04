"""Feature engineering library for train/serve consistency."""

from .version import LIBRARY_VERSION, FEATURE_SPEC_VERSION
from .core.config import (
    ADAPTIVE_LEVEL_FEATURE_VERSION,
    CROSS_ASSET_FEATURE_VERSION,
    DERIVATIVES_FEATURE_VERSION,
    DIRECTIONAL_CHANGE_FEATURE_VERSION,
    VDMC_FEATURE_VERSION,
    FeatureConfig,
)
from .core.indicators import FeatureEngineer
from .external_series import merge_external_series
from .directional_change import (
    dc_confirmed_state,
    dc_forward_direction,
    dc_pivots,
)
from .contracts import (
    ADAPTIVE_LEVEL_FEATURE_CONTRACTS,
    CROSS_ASSET_FEATURE_CONTRACTS,
    DERIVATIVES_FEATURE_CONTRACTS,
    DIRECTIONAL_CHANGE_FEATURE_CONTRACTS,
    SPECTRAL_FEATURE_CONTRACTS,
    FUNDING_FEATURE_CONTRACTS,
    OPEN_INTEREST_FEATURE_CONTRACTS,
    FEATURE_CONTRACTS,
    VDMC_FEATURE_CONTRACTS,
    FeatureContract,
    FeatureContractViolation,
    ValidationResult,
    build_feature_schema_flags,
    build_feature_schema_hash_payload,
    validate_feature_frame,
    compute_drift_report,
    compute_psi,
    get_feature_contracts,
)

__version__ = LIBRARY_VERSION

__all__ = [
    "LIBRARY_VERSION",
    "FEATURE_SPEC_VERSION",
    "ADAPTIVE_LEVEL_FEATURE_VERSION",
    "CROSS_ASSET_FEATURE_VERSION",
    "DERIVATIVES_FEATURE_VERSION",
    "DIRECTIONAL_CHANGE_FEATURE_VERSION",
    "VDMC_FEATURE_VERSION",
    "FeatureConfig",
    "FeatureEngineer",
    "dc_confirmed_state",
    "dc_forward_direction",
    "dc_pivots",
    "ADAPTIVE_LEVEL_FEATURE_CONTRACTS",
    "CROSS_ASSET_FEATURE_CONTRACTS",
    "DERIVATIVES_FEATURE_CONTRACTS",
    "DIRECTIONAL_CHANGE_FEATURE_CONTRACTS",
    "SPECTRAL_FEATURE_CONTRACTS",
    "FUNDING_FEATURE_CONTRACTS",
    "OPEN_INTEREST_FEATURE_CONTRACTS",
    "FEATURE_CONTRACTS",
    "VDMC_FEATURE_CONTRACTS",
    "FeatureContract",
    "FeatureContractViolation",
    "ValidationResult",
    "build_feature_schema_flags",
    "build_feature_schema_hash_payload",
    "validate_feature_frame",
    "compute_drift_report",
    "compute_psi",
    "get_feature_contracts",
    "merge_external_series",
]
