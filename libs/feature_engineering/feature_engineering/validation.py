"""Feature consistency validation between library and legacy implementations."""

import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def validate_feature_consistency(
    library_features: pd.DataFrame,
    legacy_features: pd.DataFrame,
    tolerance: float = 1e-6,
    ignore_columns: Optional[list] = None,
    require_identical_columns: bool = True,
) -> Tuple[bool, dict]:
    """Validate that library and legacy features match.

    Args:
        library_features: Features from shared library
        legacy_features: Features from legacy computation
        tolerance: Numeric tolerance for floating point comparison
        ignore_columns: Columns to ignore in comparison
        require_identical_columns: When True (default) any column-set difference is
            a hard inconsistency. When False, one-sided columns are reported as an
            informational ``column_diffs`` field and validation proceeds on the
            SHARED (intersection) columns — for the case where the library is
            authoritative and legitimately produces opt-in lanes (DC/VDMC/spectral/
            funding) the legacy engine cannot, and the legacy engine has columns
            (e.g. price_change) the library doesn't. Real value drift on shared
            columns is still caught.

    Returns:
        Tuple of (is_consistent, diff_report)

    Example:
        >>> is_consistent, diff = validate_feature_consistency(lib_df, legacy_df)
        >>> if not is_consistent:
        ...     logger.warning(f"Feature mismatch: {diff}")
    """
    ignore = set(ignore_columns or [])

    # Find common columns
    lib_cols = set(library_features.columns) - ignore
    legacy_cols = set(legacy_features.columns) - ignore

    # Check for missing columns
    missing_in_library = legacy_cols - lib_cols
    missing_in_legacy = lib_cols - legacy_cols

    column_diffs = None
    if missing_in_library or missing_in_legacy:
        if require_identical_columns:
            return False, {
                "error": "column_mismatch",
                "missing_in_library": list(missing_in_library),
                "missing_in_legacy": list(missing_in_legacy),
            }
        # Informational only — validate values on the shared columns below.
        column_diffs = {
            "missing_in_library": sorted(missing_in_library),
            "missing_in_legacy": sorted(missing_in_legacy),
        }

    # Compare common columns
    common_cols = sorted(lib_cols & legacy_cols)
    mismatches = []
    nan_placement_mismatches = []

    for col in common_cols:
        lib_vals = np.asarray(library_features[col].values, dtype=np.float64)
        legacy_vals = np.asarray(legacy_features[col].values, dtype=np.float64)

        # Check shapes
        if lib_vals.shape != legacy_vals.shape:
            mismatches.append({
                "column": col,
                "error": "shape_mismatch",
                "library_shape": lib_vals.shape,
                "legacy_shape": legacy_vals.shape,
            })
            continue

        # Numeric comparison with tolerance.
        #
        # NaN handling: positions where exactly ONE side is NaN are reported
        # as `nan_placement_mismatch` (informational — in practice the
        # engines' warm-up-window policies differ for rolling features, e.g.
        # legacy zero-fills where the library leaves NaN). They previously
        # surfaced as `value_mismatch` with max_diff=0.0 (np.allclose flagged
        # them but np.nanmax dropped them from the diff), which read like a
        # contradiction and failed validation on pure warm-up noise.
        # `value_mismatch` now means exactly what it says: numeric drift
        # beyond tolerance where BOTH engines produced a value.
        try:
            lib_nan = np.isnan(lib_vals)
            legacy_nan = np.isnan(legacy_vals)
            placement = lib_nan ^ legacy_nan
            if placement.any():
                nan_placement_mismatches.append({
                    "column": col,
                    "error": "nan_placement_mismatch",
                    "positions": int(placement.sum()),
                    "library_only_nan": int((lib_nan & ~legacy_nan).sum()),
                    "legacy_only_nan": int((legacy_nan & ~lib_nan).sum()),
                })
            co_valued = ~lib_nan & ~legacy_nan
            if co_valued.any() and not np.allclose(
                lib_vals[co_valued], legacy_vals[co_valued],
                rtol=tolerance, atol=tolerance,
            ):
                diffs = np.abs(lib_vals[co_valued] - legacy_vals[co_valued])
                mismatches.append({
                    "column": col,
                    "error": "value_mismatch",
                    "max_diff": float(np.max(diffs)),
                    "mean_diff": float(np.mean(diffs)),
                    "tolerance": tolerance,
                })
        except (TypeError, ValueError):
            # Non-numeric columns - do exact comparison
            lib_vals_orig = library_features[col].values
            legacy_vals_orig = legacy_features[col].values
            comparison = lib_vals_orig == legacy_vals_orig
            # Handle both numpy arrays and pandas ExtensionArrays
            if isinstance(comparison, np.ndarray):
                all_equal = comparison.all()
            else:
                all_equal = bool(np.all(np.asarray(comparison)))
            
            if not all_equal:
                mismatches.append({
                    "column": col,
                    "error": "non_numeric_mismatch",
                })
    
    if mismatches:
        return False, {
            "error": "value_mismatches",
            "total_columns": len(common_cols),
            "mismatch_columns": len(mismatches),
            "mismatches": mismatches,
            "nan_placement_mismatches": nan_placement_mismatches,
            "column_diffs": column_diffs,
        }

    return True, {
        "consistent": True,
        "total_columns": len(common_cols),
        "tolerance": tolerance,
        # Informational: columns whose values agree wherever both engines
        # produce one, but whose NaN warm-up placement differs.
        "nan_placement_mismatches": nan_placement_mismatches,
        # Present (non-None) only when require_identical_columns=False AND the column
        # sets differed — i.e. shared columns agreed but one side had extra columns.
        "column_diffs": column_diffs,
    }


def compare_feature_statistics(
    library_features: pd.DataFrame,
    legacy_features: pd.DataFrame,
) -> dict:
    """Compare statistical properties of features.
    
    Args:
        library_features: Features from shared library
        legacy_features: Features from legacy computation
        
    Returns:
        Dictionary with statistical comparison
    """
    common_cols = sorted(set(library_features.columns) & set(legacy_features.columns))
    
    stats = []
    for col in common_cols:
        lib_vals = library_features[col].dropna()
        legacy_vals = legacy_features[col].dropna()
        
        if len(lib_vals) == 0 or len(legacy_vals) == 0:
            continue
        
        stats.append({
            "column": col,
            "library_mean": float(lib_vals.mean()),
            "legacy_mean": float(legacy_vals.mean()),
            "library_std": float(lib_vals.std()),
            "legacy_std": float(legacy_vals.std()),
            "library_min": float(lib_vals.min()),
            "legacy_min": float(legacy_vals.min()),
            "library_max": float(lib_vals.max()),
            "legacy_max": float(legacy_vals.max()),
        })
    
    return {
        "total_columns": len(common_cols),
        "statistics": stats,
    }
