from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .base import ModelProtocol, joblib_load, joblib_save
from ..core.errors import ConfigurationError, NotImplementedSDK


_ALLOWED_REGISTRY: Dict[str, Callable[..., Any]] = {}


def _register_defaults() -> None:
    try:
        from sklearn.linear_model import LinearRegression, LogisticRegression
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

        _ALLOWED_REGISTRY.update(
            {
                "LinearRegression": LinearRegression,
                "RandomForestRegressor": RandomForestRegressor,
                "LogisticRegression": LogisticRegression,
                "RandomForestClassifier": RandomForestClassifier,
            }
        )
    except Exception as exc:  # pragma: no cover - only when sklearn missing
        raise ConfigurationError("scikit-learn is required for SklearnModel") from exc


if not _ALLOWED_REGISTRY:
    _register_defaults()


@dataclass
class SklearnModel(ModelProtocol):
    class_name: str
    params: dict[str, Any]
    _estimator: Any | None = None

    def _ensure_estimator(self) -> Any:
        if self._estimator is None:
            if self.class_name not in _ALLOWED_REGISTRY:
                raise ConfigurationError(f"Unsupported estimator: {self.class_name}")
            ctor = _ALLOWED_REGISTRY[self.class_name]
            self._estimator = ctor(**self.params)
        return self._estimator

    def fit(self, X, y, **kwargs) -> "SklearnModel":
        est = self._ensure_estimator()
        est.fit(X, y, **kwargs)
        return self

    def predict(self, X):
        est = self._ensure_estimator()
        return est.predict(X)

    def predict_proba(self, X):
        est = self._ensure_estimator()
        if hasattr(est, "predict_proba"):
            return est.predict_proba(X)
        raise NotImplementedSDK("predict_proba is not supported by this estimator")

    def save(self, path: str) -> None:
        est = self._ensure_estimator()
        joblib_save({"class_name": self.class_name, "params": self.params, "estimator": est}, path)

    @classmethod
    def load(cls, path: str) -> "SklearnModel":
        payload = joblib_load(path)
        obj = cls(class_name=payload["class_name"], params=payload["params"])
        obj._estimator = payload["estimator"]
        return obj

