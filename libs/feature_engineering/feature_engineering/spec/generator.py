"""Feature specification generation.

Generates authoritative feature spec JSON with metadata for reproducibility.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from ..core.config import FeatureConfig
from ..core.indicators import compute_indicator_lookbacks
from ..contracts import build_feature_schema_flags
from ..version import LIBRARY_VERSION, FEATURE_SPEC_VERSION


def generate_feature_spec(
    feature_names: List[str],
    feature_dtypes: Optional[Dict[str, str]] = None,
    config: Optional[FeatureConfig] = None,
    library_version: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> dict:
    """Generate feature specification with complete metadata.
    
    Args:
        feature_names: Ordered list of feature column names
        feature_dtypes: Optional mapping of feature names to dtypes
        config: Feature configuration used to generate features
        library_version: Library version (defaults to current)
        created_at: Timestamp of spec creation (defaults to now UTC)
        
    Returns:
        Feature spec dictionary with all metadata
    """
    cfg = config or FeatureConfig()
    lib_version = library_version or LIBRARY_VERSION
    created = created_at or datetime.now(timezone.utc)
    
    # Compute indicator lookbacks
    lookbacks = compute_indicator_lookbacks(cfg)
    max_lookback = max(lookbacks.values()) if lookbacks else 0
    
    # Config hash for versioning
    config_payload = json.dumps(cfg.model_dump(), sort_keys=True).encode('utf-8')
    config_hash = hashlib.sha256(config_payload).hexdigest()[:8]
    
    # Generate unique feature spec ID
    timestamp_str = created.strftime('%Y%m%d')
    feature_spec_id = f"f_v{lib_version}_{timestamp_str}_{config_hash}"
    
    spec = {
        "feature_spec_id": feature_spec_id,
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "library_version": lib_version,
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "feature_dtypes": feature_dtypes or {},
        "indicator_lookbacks": lookbacks,
        "max_lookback": max_lookback,
        "config_hash": f"sha256:{config_hash}",
        "config": cfg.model_dump(),
        "created_at": created.isoformat(),
    }

    feature_flags = build_feature_schema_flags(
        cfg,
        selected_feature_names=feature_names,
    )
    if feature_flags:
        spec["feature_flags"] = feature_flags
    
    return spec


def extract_feature_dtypes(df: pd.DataFrame) -> Dict[str, str]:
    """Extract feature dtypes from DataFrame.
    
    Args:
        df: DataFrame with features
        
    Returns:
        Dictionary mapping feature names to dtype strings
    """
    return {col: str(df[col].dtype) for col in df.columns}


def summarize_lookbacks(lookbacks: Dict[str, int]) -> dict:
    """Summarize lookback periods with aggregate statistics.
    
    Args:
        lookbacks: Dictionary of indicator lookbacks
        
    Returns:
        Summary with max_lookback, counts, and per-indicator details
    """
    if not lookbacks:
        return {
            "max_lookback": 0,
            "total_indicators": 0,
            "indicators": []
        }
    
    max_lookback = max(lookbacks.values())
    indicators = [
        {"indicator": name, "lookback": period}
        for name, period in sorted(lookbacks.items(), key=lambda x: x[1], reverse=True)
    ]
    
    return {
        "max_lookback": max_lookback,
        "total_indicators": len(lookbacks),
        "indicators": indicators
    }
