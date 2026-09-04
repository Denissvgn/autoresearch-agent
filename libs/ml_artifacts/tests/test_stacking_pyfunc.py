from __future__ import annotations

import numpy as np
import pytest

from ml_artifacts.ensemble.stacking_pyfunc import (
    OPTION_B_BASE_SOURCE,
    build_stacking_base_matrix,
    predict_stacking_ensemble_proba,
)


class ConstantProbabilityModel:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def predict_proba(self, features):
        n = len(features)
        return np.column_stack(
            [
                np.full(n, 1.0 - self.probability),
                np.full(n, self.probability),
            ]
        )


class MeanMetaModel:
    def predict_proba(self, base_matrix):
        p = np.asarray(base_matrix, dtype=float).mean(axis=1)
        return np.column_stack([1.0 - p, p])


def test_option_b_uses_fold_models_instead_of_full_refit_models():
    ensemble = {
        "base_models": {
            "lgb": ConstantProbabilityModel(0.99),
            "xgb": ConstantProbabilityModel(0.01),
        },
        "base_fold_models": {
            "lgb": [ConstantProbabilityModel(0.2), ConstantProbabilityModel(0.4)],
            "xgb": [ConstantProbabilityModel(0.8), ConstantProbabilityModel(0.6)],
        },
        "base_model_keys": ["lgb", "xgb"],
        "meta_model": MeanMetaModel(),
        "option_b_base_source": OPTION_B_BASE_SOURCE,
    }

    features = np.zeros((3, 2))

    matrix = build_stacking_base_matrix(ensemble, features)
    np.testing.assert_allclose(matrix, np.array([[0.3, 0.7]] * 3))
    np.testing.assert_allclose(predict_stacking_ensemble_proba(ensemble, features), 0.5)


def test_option_b_requires_fold_models_when_marker_is_present():
    ensemble = {
        "base_models": {"lgb": ConstantProbabilityModel(0.9)},
        "base_model_keys": ["lgb"],
        "meta_model": MeanMetaModel(),
        "option_b_base_source": OPTION_B_BASE_SOURCE,
    }

    with pytest.raises(ValueError, match="base_fold_models"):
        build_stacking_base_matrix(ensemble, np.zeros((1, 2)))


def test_legacy_artifact_falls_back_to_base_models():
    ensemble = {
        "base_models": {"lgb": ConstantProbabilityModel(0.75)},
        "base_model_keys": ["lgb"],
        "meta_model": MeanMetaModel(),
    }

    matrix = build_stacking_base_matrix(ensemble, np.zeros((2, 2)))
    np.testing.assert_allclose(matrix, np.array([[0.75], [0.75]]))
