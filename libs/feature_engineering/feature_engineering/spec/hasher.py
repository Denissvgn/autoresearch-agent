"""Feature specification hashing for reproducibility validation.

Provides deterministic hash computation for feature specs to detect drift.
"""

import hashlib
import json
from typing import Dict, List


def compute_feature_spec_hash(spec: dict) -> str:
    """Compute deterministic hash of feature specification.
    
    The hash is computed from:
    - Ordered feature names
    - Feature dtypes
    - Library version
    - Feature spec version
    
    This allows validation that training and serving use identical features.
    
    Args:
        spec: Feature specification dictionary
        
    Returns:
        SHA256 hash (hex string)
        
    Example:
        >>> spec = {"feature_names": ["close", "sma_10"], "feature_dtypes": {...}}
        >>> hash1 = compute_feature_spec_hash(spec)
        >>> hash2 = compute_feature_spec_hash(spec)
        >>> assert hash1 == hash2  # Deterministic
    """
    # Extract hashable components (order matters)
    feature_names = spec.get("feature_names", [])
    feature_dtypes = spec.get("feature_dtypes", {})
    library_version = spec.get("library_version", "unknown")
    spec_version = spec.get("feature_spec_version", "unknown")
    feature_flags = spec.get("feature_flags") or {}
    
    # Build canonical payload
    payload = {
        "feature_names": feature_names,  # Already ordered
        "feature_dtypes": {name: feature_dtypes.get(name, "unknown") for name in feature_names},
        "library_version": library_version,
        "feature_spec_version": spec_version,
    }
    canonical_flags = {}
    adaptive_levels = feature_flags.get("adaptive_levels", {})
    if adaptive_levels.get("enabled"):
        canonical_flags["adaptive_levels"] = {
            "enabled": True,
            "version": adaptive_levels.get("version", "unknown"),
            "selected_feature_names": list(
                adaptive_levels.get("selected_feature_names", feature_names)
            ),
        }
    spectral_features = feature_flags.get("spectral_features", {})
    if spectral_features.get("enabled"):
        canonical_flags["spectral_features"] = {
            "enabled": True,
            "version": spectral_features.get("version", "unknown"),
            "evidence_report_path": spectral_features.get(
                "evidence_report_path",
                "unknown",
            ),
            "selected_feature_names": list(
                spectral_features.get("selected_feature_names", feature_names)
            ),
        }
    vdmc = feature_flags.get("vdmc", {})
    if vdmc.get("enabled"):
        canonical_flags["vdmc"] = {
            "enabled": True,
            "version": vdmc.get("version", "unknown"),
            "params": vdmc.get("params", {}),
            "selected_feature_names": list(
                vdmc.get("selected_feature_names", feature_names)
            ),
        }
    if canonical_flags:
        payload["feature_flags"] = canonical_flags
    
    # Compute hash
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload_bytes).hexdigest()


def compute_feature_names_hash(feature_names: List[str]) -> str:
    """Compute hash of feature names only (lightweight check).
    
    Args:
        feature_names: Ordered list of feature names
        
    Returns:
        SHA256 hash (hex string, first 16 chars)
    """
    payload = json.dumps(feature_names).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()[:16]


def verify_spec_hash(spec: dict, expected_hash: str) -> bool:
    """Verify feature spec hash matches expected value.
    
    Args:
        spec: Feature specification dictionary
        expected_hash: Expected SHA256 hash
        
    Returns:
        True if hashes match, False otherwise
    """
    actual_hash = compute_feature_spec_hash(spec)
    return actual_hash == expected_hash


def compute_config_hash(config: dict) -> str:
    """Compute hash of feature configuration.
    
    Args:
        config: Feature configuration dictionary
        
    Returns:
        SHA256 hash (hex string, first 8 chars)
    """
    payload = json.dumps(config, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()[:8]
