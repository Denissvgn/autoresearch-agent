from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml_artifacts.ensemble.best_base_pyfunc import BestBasePyfunc


class TwoClassModel:
    def predict_proba(self, features):
        p = np.clip(np.asarray(features, dtype=float).mean(axis=1), 0.0, 1.0)
        return np.column_stack([1.0 - p, p])


class AdditiveCalibrator:
    def transform(self, probabilities):
        return np.clip(np.asarray(probabilities, dtype=float) + 0.1, 0.0, 1.0)


def _loaded_pyfunc() -> BestBasePyfunc:
    model = BestBasePyfunc()
    model._model_type = "sklearn"
    model._sklearn_model = TwoClassModel()
    model._feature_columns = ["a", "b"]
    model._calibrator = AdditiveCalibrator()
    return model


def test_best_base_pyfunc_preserves_feature_columns_and_calibration():
    model = _loaded_pyfunc()

    out = model.predict(None, pd.DataFrame({"a": [0.2], "b": [0.4]}))

    np.testing.assert_allclose(out, np.array([0.4]))


def test_best_base_pyfunc_rejects_mismatched_feature_columns():
    model = _loaded_pyfunc()

    with pytest.raises(ValueError, match="Feature columns do not match"):
        model.predict(None, pd.DataFrame({"b": [0.4], "a": [0.2]}))
