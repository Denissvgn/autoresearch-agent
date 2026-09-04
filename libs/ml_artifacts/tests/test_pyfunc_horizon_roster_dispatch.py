"""DM-5 — multi-horizon pyfunc dispatch in ``build_stacking_base_matrix``.

Pins three pieces:

1. Single-horizon artifacts (``horizon_roster`` absent / None) take the
   legacy code path bit-identically — back-compat for pre-DM-5 models
   loading under the new library version.

2. Multi-horizon artifacts (``horizon_roster`` non-empty) dispatch to
   ``_build_multi_horizon_base_matrix`` and produce a meta-feature
   matrix of shape ``(n, H*B)`` with columns laid out in
   ``[h0_b0, h0_b1, …, hK_bN]`` row-major order.

3. The ``feature_contract_version`` and ``LIBRARY_VERSION`` constants
   are reachable from the library namespace so trainer code can pin
   them into the serialised ensemble dict.
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from ml_artifacts import FEATURE_CONTRACT_VERSION, LIBRARY_VERSION, __version__
from ml_artifacts.ensemble.stacking_pyfunc import (
    OPTION_B_BASE_SOURCE,
    _build_multi_horizon_base_matrix,
    build_stacking_base_matrix,
)


# --------------------------------------------------------------------------- #
# Library-version constants — locked so trainer code can rely on them.
# --------------------------------------------------------------------------- #
def test_library_version_bumped_to_020() -> None:
    """DM-5 multi-horizon ensemble changes the meta-feature matrix shape.
    The library version must be bumped so consumers can detect the new
    artifact contract."""
    assert __version__ == "0.2.0"
    assert LIBRARY_VERSION == "0.2.0"


def test_feature_contract_version_constant_is_020() -> None:
    """The trainer writes ``feature_contract_version`` into the
    ensemble dict; the pyfunc reads it back. Both must agree on
    "0.2.0" for new multi-horizon artifacts."""
    assert FEATURE_CONTRACT_VERSION == "0.2.0"


# --------------------------------------------------------------------------- #
# Shared fakes — base fold models that emit deterministic probas.
# --------------------------------------------------------------------------- #
class _ConstProbaModel:
    """Fake base model whose ``predict_proba`` always emits the same
    P(class=1) for every row. Lets the test assert that
    ``build_stacking_base_matrix`` puts the value in the column it
    expects (i.e. the column-layout claim of the dispatch path)."""

    def __init__(self, p_pos: float):
        self._p = float(p_pos)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n = len(X)
        out = np.zeros((n, 2), dtype=float)
        out[:, 0] = 1.0 - self._p
        out[:, 1] = self._p
        return out


def _feature_frame(n: int = 16) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {"x1": rng.normal(size=n), "x2": rng.normal(size=n)},
        index=pd.RangeIndex(start=0, stop=n),
    )


# --------------------------------------------------------------------------- #
# Back-compat: legacy single-horizon artifact must take the original path.
# --------------------------------------------------------------------------- #
def test_legacy_artifact_without_horizon_roster_uses_single_horizon_path() -> None:
    """No ``horizon_roster`` in the ensemble dict → legacy
    ``(n, B)`` matrix produced from un-prefixed ``base_fold_models``."""
    base_keys = ["lgb", "xgb"]
    base_fold_models = {
        "lgb": [_ConstProbaModel(0.30)],
        "xgb": [_ConstProbaModel(0.70)],
    }
    ensemble = {
        "base_model_keys": base_keys,
        "base_fold_models": base_fold_models,
        "option_b_base_source": OPTION_B_BASE_SOURCE,
        # NOTE: no ``horizon_roster`` key — pre-DM-5 artifact shape.
    }
    matrix = build_stacking_base_matrix(ensemble, _feature_frame())
    assert matrix.shape == (16, 2)
    np.testing.assert_allclose(matrix[:, 0], 0.30)
    np.testing.assert_allclose(matrix[:, 1], 0.70)


def test_legacy_artifact_with_none_horizon_roster_uses_single_horizon_path() -> None:
    """``horizon_roster=None`` is the explicit single-horizon marker
    (the trainer writes None for legacy configs). Same path as
    horizon_roster missing entirely."""
    ensemble = {
        "base_model_keys": ["lgb"],
        "base_fold_models": {"lgb": [_ConstProbaModel(0.42)]},
        "option_b_base_source": OPTION_B_BASE_SOURCE,
        "horizon_roster": None,
    }
    matrix = build_stacking_base_matrix(ensemble, _feature_frame())
    assert matrix.shape == (16, 1)
    np.testing.assert_allclose(matrix[:, 0], 0.42)


# --------------------------------------------------------------------------- #
# DM-5 dispatch: multi-horizon artifact produces (n, H*B) matrix in the
# expected column layout.
# --------------------------------------------------------------------------- #
def test_multi_horizon_artifact_produces_expanded_matrix() -> None:
    """Three horizons × two bases → (n, 6) matrix. Each column carries
    the constant proba of its fake fold model so the layout is
    inspectable: column index = horizon_idx * n_bases + base_idx."""
    horizon_roster = [6, 12, 18]
    base_keys = ["lgb", "xgb"]
    # Per-(horizon, base) probas pin a unique value per cell so the
    # column-layout claim can be asserted directly.
    probas = {
        ("h6", "lgb"): 0.10, ("h6", "xgb"): 0.20,
        ("h12", "lgb"): 0.30, ("h12", "xgb"): 0.40,
        ("h18", "lgb"): 0.50, ("h18", "xgb"): 0.60,
    }
    base_fold_models = {
        f"{h_key}_{b}": [_ConstProbaModel(probas[(h_key, b)])]
        for (h_key, b) in probas
    }
    ensemble = {
        "base_model_keys": base_keys,
        "base_fold_models": base_fold_models,
        "horizon_roster": horizon_roster,
        "option_b_base_source": OPTION_B_BASE_SOURCE,
    }
    matrix = build_stacking_base_matrix(ensemble, _feature_frame())
    assert matrix.shape == (16, 6)
    # Column layout: [h6_lgb, h6_xgb, h12_lgb, h12_xgb, h18_lgb, h18_xgb].
    expected_per_col = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
    for col_idx, exp in enumerate(expected_per_col):
        np.testing.assert_allclose(matrix[:, col_idx], exp), col_idx


def test_multi_horizon_missing_fold_models_raises_when_required() -> None:
    """A multi-horizon artifact that declares ``horizon_roster`` but
    forgets to ship fold models for a (horizon, base) cell must raise
    when ``option_b_base_source`` requires fold models — silent
    zero-fill of a missing cell would hide a serialisation bug."""
    ensemble = {
        "base_model_keys": ["lgb", "xgb"],
        "base_fold_models": {
            "h6_lgb": [_ConstProbaModel(0.5)],
            # MISSING: "h6_xgb", "h12_lgb", "h12_xgb"
        },
        "horizon_roster": [6, 12],
        "option_b_base_source": OPTION_B_BASE_SOURCE,
    }
    with pytest.raises(ValueError, match="missing fold models"):
        build_stacking_base_matrix(ensemble, _feature_frame())


def test_multi_horizon_helper_callable_directly() -> None:
    """``_build_multi_horizon_base_matrix`` is a private helper but
    callable for unit testing. Pin its signature so refactors of the
    dispatch don't silently change the public contract."""
    ensemble = {
        "base_model_keys": ["lgb"],
        "base_fold_models": {"h6_lgb": [_ConstProbaModel(0.33)]},
        "option_b_base_source": OPTION_B_BASE_SOURCE,
    }
    matrix = _build_multi_horizon_base_matrix(
        ensemble, _feature_frame(),
        horizon_roster=[6],
        require_fold_models=True,
    )
    assert matrix.shape == (16, 1)
    np.testing.assert_allclose(matrix[:, 0], 0.33)


def test_multi_horizon_missing_base_model_keys_raises() -> None:
    """The pyfunc needs ``base_model_keys`` to know how many bases per
    horizon to expect — missing it is a serialisation error."""
    ensemble = {
        "base_fold_models": {"h6_lgb": [_ConstProbaModel(0.1)]},
        "horizon_roster": [6],
        # NOTE: no ``base_model_keys``.
    }
    with pytest.raises(ValueError, match="base_model_keys"):
        _build_multi_horizon_base_matrix(
            ensemble, _feature_frame(),
            horizon_roster=[6],
            require_fold_models=True,
        )


def test_multi_horizon_means_across_multiple_folds_per_cell() -> None:
    """Per (horizon, base) cell the matrix entry must be the MEAN of
    the cell's fold-model predictions. Single-horizon path already
    does this; verify the multi-horizon path inherits the contract."""
    ensemble = {
        "base_model_keys": ["lgb"],
        "base_fold_models": {
            "h6_lgb": [_ConstProbaModel(0.2), _ConstProbaModel(0.8)],  # mean = 0.5
        },
        "horizon_roster": [6],
        "option_b_base_source": OPTION_B_BASE_SOURCE,
    }
    matrix = build_stacking_base_matrix(ensemble, _feature_frame())
    np.testing.assert_allclose(matrix[:, 0], 0.5)
