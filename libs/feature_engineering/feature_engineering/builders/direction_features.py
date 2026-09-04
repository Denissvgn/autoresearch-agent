"""Direction model feature builder."""

import logging
from typing import Optional

import pandas as pd

from ..core.config import FeatureConfig
from ..core.indicators import FeatureEngineer
from ..spec.generator import generate_feature_spec, extract_feature_dtypes
from ..spec.hasher import compute_feature_spec_hash

logger = logging.getLogger(__name__)


class DirectionFeatureBuilder:
    """Build features specifically for direction (classification) models.
    
    Handles feature computation, specification generation, and provenance
    tracking for direction prediction models.
    """
    
    def __init__(
        self,
        config: Optional[FeatureConfig] = None,
        feature_spec_id: Optional[str] = None,
    ):
        """Initialize direction feature builder.
        
        Args:
            config: Feature configuration
            feature_spec_id: Optional override for spec ID (for pinning)
        """
        self.config = config or FeatureConfig()
        self.engineer = FeatureEngineer(self.config)
        self.feature_spec_id_override = feature_spec_id
        self._spec = None
        self._spec_hash = None
        
    def build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build all features for direction model.
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            DataFrame with all features added
        """
        logger.info("Building direction model features")
        features_df = self.engineer.calculate_all_features(df)
        
        # Generate spec after features are computed
        self._generate_spec(features_df)
        
        return features_df
    
    def _generate_spec(self, df: pd.DataFrame) -> None:
        """Generate feature specification."""
        feature_names = list(df.columns)
        feature_dtypes = extract_feature_dtypes(df)
        
        self._spec = generate_feature_spec(
            feature_names=feature_names,
            feature_dtypes=feature_dtypes,
            config=self.config,
        )
        
        # Override spec ID if provided
        if self.feature_spec_id_override:
            self._spec["feature_spec_id"] = self.feature_spec_id_override
        
        self._spec_hash = compute_feature_spec_hash(self._spec)
        
        logger.info(f"Generated feature spec: {self._spec['feature_spec_id']}")
        logger.info(f"Feature spec hash: {self._spec_hash}")
    
    def get_spec(self) -> dict:
        """Get feature specification.
        
        Returns:
            Feature spec dictionary
            
        Raises:
            RuntimeError: If features not yet built
        """
        if self._spec is None:
            raise RuntimeError("Features not yet built. Call build_features() first.")
        return self._spec
    
    def get_spec_hash(self) -> str:
        """Get feature specification hash.
        
        Returns:
            Feature spec hash (SHA256)
            
        Raises:
            RuntimeError: If features not yet built
        """
        if self._spec_hash is None:
            raise RuntimeError("Features not yet built. Call build_features() first.")
        return self._spec_hash
    
    def get_max_lookback(self) -> int:
        """Get maximum lookback period across all indicators.
        
        Returns:
            Maximum lookback period
            
        Raises:
            RuntimeError: If features not yet built
        """
        if self._spec is None:
            raise RuntimeError("Features not yet built. Call build_features() first.")
        return self._spec.get("max_lookback", 0)
