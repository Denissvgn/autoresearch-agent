"""ML-1: Parity metadata collection for training artifacts.

Captures the runtime environment and model configuration at training time
so that the inference service can validate compatibility before activation.

Metadata includes:
- Dependency versions (xgboost, lightgbm, sklearn, etc.)
- Ordered base learner roster
- Feature schema hash (order-sensitive)
- Threshold strategy and calibration diagnostics
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import sys
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)

PARITY_METADATA_VERSION = "1.0"


def _get_package_version(package_name: str) -> Optional[str]:
    """Return installed version of *package_name*, or ``None``."""
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None


def collect_dependency_versions() -> Dict[str, Optional[str]]:
    """Snapshot versions of all ML-critical dependencies."""
    packages = [
        "xgboost",
        "lightgbm",
        "scikit-learn",
        "catboost",
        "numpy",
        "pandas",
        "mlflow",
        "joblib",
        "torch",
    ]
    versions: Dict[str, Optional[str]] = {
        "python": platform.python_version(),
    }
    for pkg in packages:
        versions[pkg] = _get_package_version(pkg)
    return versions


def compute_feature_schema_hash(
    feature_names: List[str],
    feature_dtypes: Optional[Dict[str, str]] = None,
    feature_schema_flags: Optional[Dict[str, Any]] = None,
) -> str:
    """Compute a deterministic SHA-256 hash of the feature schema.

    The hash is sensitive to feature **order** because base learners
    depend on positional alignment of columns.

    Args:
        feature_names: Ordered list of feature column names.
        feature_dtypes: Optional mapping of name→dtype string.
        feature_schema_flags: Optional feature flag/version metadata.

    Returns:
        64-character hex SHA-256 digest.
    """
    payload: Dict[str, Any] = {"feature_names": list(feature_names)}
    if feature_dtypes:
        payload["feature_dtypes"] = {
            name: feature_dtypes.get(name, "unknown") for name in feature_names
        }
    adaptive_levels = (feature_schema_flags or {}).get("adaptive_levels", {})
    if adaptive_levels.get("enabled"):
        payload["feature_schema_flags"] = {
            "adaptive_levels": {
                "enabled": True,
                "version": adaptive_levels.get("version", "unknown"),
                "selected_feature_names": list(
                    adaptive_levels.get("selected_feature_names", feature_names)
                ),
            }
        }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compute_selected_feature_names_hash(feature_names: List[str]) -> str:
    """Compute an order-sensitive hash of the selected model input columns."""
    payload = {"selected_feature_names": list(feature_names)}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_parity_metadata(
    *,
    base_learner_roster: List[str],
    meta_learner: str,
    feature_names: List[str],
    feature_dtypes: Optional[Dict[str, str]] = None,
    threshold_strategy: Optional[str] = None,
    optimal_threshold: Optional[float] = None,
    calibration_method: Optional[str] = None,
    calibration_is_fitted: bool = False,
    calibration_diagnostics: Optional[Dict[str, Any]] = None,
    stacking_config_dict: Optional[Dict[str, Any]] = None,
    feature_schema_flags: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the canonical parity metadata dict.

    This dict is embedded in the training artifact (``ensemble.pkl``) and
    also logged as a standalone MLflow artifact (``parity_metadata.json``).
    The inference service reads it at load-time to validate environment
    compatibility before activating the model.

    Returns:
        Parity metadata dictionary.
    """
    metadata: Dict[str, Any] = {
        "parity_version": PARITY_METADATA_VERSION,
        "dependency_versions": collect_dependency_versions(),
        "base_learner_roster": list(base_learner_roster),
        "meta_learner": meta_learner,
        "feature_schema_hash": compute_feature_schema_hash(
            feature_names, feature_dtypes, feature_schema_flags
        ),
        "feature_count": len(feature_names),
        "feature_names": list(feature_names),
        "selected_feature_names_hash": compute_selected_feature_names_hash(
            feature_names
        ),
    }
    if feature_schema_flags:
        metadata["feature_schema_flags"] = feature_schema_flags

    # Threshold info
    if threshold_strategy is not None:
        metadata["threshold_strategy"] = threshold_strategy
    if optimal_threshold is not None:
        metadata["optimal_threshold"] = float(optimal_threshold)

    # Calibration info
    metadata["calibration"] = {
        "method": calibration_method,
        "is_fitted": calibration_is_fitted,
        "diagnostics": calibration_diagnostics or {},
    }

    # Training config snapshot (non-sensitive subset)
    if stacking_config_dict:
        metadata["training_config"] = stacking_config_dict

    return metadata
