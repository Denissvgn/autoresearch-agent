"""
Pipeline implementation for combining feature engineering and model training.

Standardizes the interaction between raw data processing and model fitting/inference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

import numpy as np
import pandas as pd

from .base import ModelProtocol


class FeatureGenerator(Protocol):
    def __call__(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame: ...


@dataclass
class Pipeline(ModelProtocol):
    """
    A pipeline that chains feature generation and model training.
    
    Attributes:
        model: The underlying predictive model (e.g., TorchMLPModel).
        feature_gen: A callable that transforms raw DataFrame into feature DataFrame.
        feature_params: Parameters to pass to the feature generator.
    """
    model: ModelProtocol
    feature_gen: Callable[[pd.DataFrame], pd.DataFrame]
    feature_params: dict[str, Any] = field(default_factory=dict)
    
    # Internal state
    _feature_cols: Optional[list[str]] = field(default=None, init=False)

    def fit(self, X: Any, y: Any, **kwargs: Any) -> "Pipeline":
        """
        Fit the pipeline.
        
        Args:
            X: Raw input data (pandas DataFrame).
            y: Target values.
        """
        # 1. Generate features
        X_features = self._transform(X)
        self._feature_cols = list(X_features.columns)
        
        # 2. Fit model
        self.model.fit(X_features.values, y, **kwargs)
        return self

    def predict(self, X: Any) -> np.ndarray:
        """
        Make predictions using the pipeline.
        
        Args:
            X: Raw input data (pandas DataFrame).
        """
        X_features = self._transform(X)
        
        # Ensure columns match training
        if self._feature_cols:
            # Align columns, filling missing with 0 or handling as needed
            # For now, we assume strict schema match or subset
            X_features = X_features[self._feature_cols]
            
        return self.model.predict(X_features.values)

    def predict_proba(self, X: Any) -> np.ndarray:
        """
        Predict probabilities (if supported by underlying model).
        """
        if not hasattr(self.model, "predict_proba"):
            raise NotImplementedError("Underlying model does not support predict_proba")
            
        X_features = self._transform(X)
        if self._feature_cols:
            X_features = X_features[self._feature_cols]
            
        return self.model.predict_proba(X_features.values)

    def _transform(self, X: Any) -> pd.DataFrame:
        """Apply feature generation."""
        if not isinstance(X, pd.DataFrame):
            raise ValueError("Pipeline input X must be a pandas DataFrame")
            
        # Apply feature generator with stored params
        return self.feature_gen(X, **self.feature_params)

    def save(self, path: str) -> None:
        """Save pipeline model (feature gen logic is assumed code-based/stateless)."""
        # We delegate save to the model. 
        # Note: This doesn't persist the feature_gen function itself, 
        # so loading requires reconstructing the Pipeline with the same function.
        self.model.save(path)

    @classmethod
    def load(cls, path: str) -> "Pipeline":
        raise NotImplementedError("Pipeline.load not implemented. Load inner model and reconstruct Pipeline.")
