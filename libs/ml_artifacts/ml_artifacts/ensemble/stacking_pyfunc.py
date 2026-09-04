"""MLflow pyfunc wrapper for stacking ensemble models (Option B).

This module provides a ``StackingEnsemblePyfunc`` class that conforms to the
``mlflow.pyfunc.PythonModel`` interface so the full stacking ensemble can be
registered as a first-class MLflow model alongside the single-best-base model.

Usage at training time::

    from training.ensemble.stacking_pyfunc import log_stacking_ensemble_model

    log_stacking_ensemble_model(
        ensemble_dict=ensemble_result,
        artifact_path="direction_ensemble_model",
        registered_model_name="direction_classifier_ensemble",
    )

The inference service then loads it via::

    model = mlflow.pyfunc.load_model(f"models:/{name}/{stage}")
    # model.predict(...) returns the meta-learner probability

The raw ensemble dict is accessible via ``model._model_impl.python_model.ensemble_dict``
so the inference service's ``ModelAdapterFactory`` can detect it and wrap it in
``StackingEnsembleAdapter`` for full uncertainty support.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

try:
    import mlflow
    import mlflow.pyfunc
    from mlflow.models import infer_signature
except ImportError:  # pragma: no cover
    mlflow = None
    infer_signature = None

logger = logging.getLogger(__name__)

OPTION_B_BASE_SOURCE = "cross_fitted_fold_ensemble"
FOLD_AGGREGATION = "mean"


def _coerce_stacking_input(
    ensemble_dict: Dict[str, Any],
    model_input: Any,
) -> np.ndarray:
    """Validate feature schema and coerce input to a 2-D array."""
    feature_names = ensemble_dict.get("feature_names")
    if isinstance(model_input, pd.DataFrame):
        if feature_names and list(model_input.columns) != list(feature_names):
            raise ValueError(
                "Feature columns do not match trained schema: "
                f"expected={list(feature_names)}, actual={list(model_input.columns)}"
            )
        features = model_input.values
    else:
        features = np.asarray(model_input)
    if features.ndim == 1:
        features = features.reshape(1, -1)
    if feature_names and features.shape[1] != len(feature_names):
        raise ValueError(
            "Feature matrix width does not match trained schema: "
            f"expected={len(feature_names)}, actual={features.shape[1]}"
        )
    return features


def _restore_feature_names(model: Any, features: np.ndarray) -> Any:
    """Wrap a feature matrix in a DataFrame matching the model's trained names.

    Base learners fitted on named DataFrames otherwise emit sklearn's
    "X does not have valid feature names" warning on every prediction, since
    ``_coerce_stacking_input`` passes a bare ndarray. Falls back to the raw
    array when the model was fitted without feature names.
    """
    names = getattr(model, "feature_names_in_", None)
    arr = np.asarray(features)
    if names is not None and arr.ndim == 2 and arr.shape[1] == len(names):
        return pd.DataFrame(arr, columns=list(names))
    return features


def _predict_base_proba(model: Any, features: np.ndarray) -> np.ndarray:
    """Return class-1 probabilities for a base model."""
    features = _restore_feature_names(model, features)
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(features)
        proba = np.asarray(proba, dtype=float)
        if proba.ndim == 2:
            return proba[:, 1] if proba.shape[1] >= 2 else proba[:, -1]
        return proba.ravel()
    if hasattr(model, "predict"):
        return np.clip(np.asarray(model.predict(features), dtype=float), 0.0, 1.0)
    raise TypeError(f"Model {type(model).__name__} has no predict_proba() or predict()")


def build_stacking_base_matrix(
    ensemble_dict: Dict[str, Any],
    model_input: Any,
    *,
    require_fold_models: bool | None = None,
) -> np.ndarray:
    """Build meta-learner features from cross-fitted fold models.

    New Option B artifacts set ``option_b_base_source`` to
    ``cross_fitted_fold_ensemble`` and must contain ``base_fold_models``.
    Legacy artifacts without that marker fall back to full-refit
    ``base_models`` for backward-compatible loading only.

    DM-5 multi-horizon dispatch: when ``ensemble_dict`` carries a
    non-empty ``horizon_roster`` (a list of horizons), the matrix shape
    becomes ``(n, len(horizon_roster) * len(base_keys))`` — one column
    per (horizon, base) pair. Fold-models are stored as
    ``base_fold_models[f"h{horizon}_{base_key}"]``. Single-horizon
    artifacts (``horizon_roster`` absent or None) take the legacy path
    unchanged.
    """
    horizon_roster = ensemble_dict.get("horizon_roster")
    if horizon_roster:
        return _build_multi_horizon_base_matrix(
            ensemble_dict,
            model_input,
            horizon_roster=horizon_roster,
            require_fold_models=require_fold_models,
        )
    features = _coerce_stacking_input(ensemble_dict, model_input)
    base_models = ensemble_dict.get("base_models", {}) or {}
    base_fold_models = ensemble_dict.get("base_fold_models", {}) or {}
    base_keys = ensemble_dict.get("base_model_keys") or list(
        base_fold_models.keys() or base_models.keys()
    )
    source = ensemble_dict.get("option_b_base_source")
    if require_fold_models is None:
        require_fold_models = source == OPTION_B_BASE_SOURCE

    n_samples = features.shape[0]
    base_matrix = np.full((n_samples, len(base_keys)), 0.5, dtype=np.float64)

    if base_fold_models:
        missing = [key for key in base_keys if not base_fold_models.get(key)]
        if missing and require_fold_models:
            raise ValueError(
                "Missing cross-fitted fold models for Option B base learners: "
                f"{missing}"
            )
        for col_idx, key in enumerate(base_keys):
            fold_models = list(base_fold_models.get(key) or [])
            if not fold_models:
                continue
            fold_preds: list[np.ndarray] = []
            for model in fold_models:
                try:
                    pred = np.asarray(_predict_base_proba(model, features), dtype=float).ravel()
                    if len(pred) == n_samples and np.isfinite(pred).all():
                        fold_preds.append(pred)
                except Exception as exc:
                    logger.warning(
                        "Fold model '%s' failed during stacking predict: %s",
                        key,
                        exc,
                    )
            if not fold_preds:
                if require_fold_models:
                    raise ValueError(
                        "No usable cross-fitted fold predictions for "
                        f"Option B base learner '{key}'"
                    )
                continue
            base_matrix[:, col_idx] = np.mean(np.vstack(fold_preds), axis=0)
        return base_matrix

    if require_fold_models:
        raise ValueError(
            "Option B artifact declares cross-fitted serving but has no "
            "base_fold_models"
        )

    # Legacy fallback: old artifacts only stored full-refit base models.
    for col_idx, key in enumerate(base_keys):
        model = base_models.get(key)
        if model is None:
            continue
        try:
            base_matrix[:, col_idx] = _predict_base_proba(model, features)
        except Exception as exc:
            logger.warning("Base model '%s' failed during pyfunc predict: %s", key, exc)
    return base_matrix


def _build_multi_horizon_base_matrix(
    ensemble_dict: Dict[str, Any],
    model_input: Any,
    *,
    horizon_roster: list,
    require_fold_models: bool | None,
) -> np.ndarray:
    """DM-5: build the expanded ``(n, H*B)`` meta-feature matrix.

    Column layout (row-major):
        [h0_b0, h0_b1, …, h0_bN, h1_b0, …, h1_bN, …, hK_bN]

    Per-horizon fold-models live at
    ``base_fold_models[f"h{horizon}_{base_key}"]``. Each (horizon, base)
    cell is the mean prediction over that horizon's fold models. The
    feature matrix is shared across horizons — only the LABELS differed
    at training time — so we compute base predictions once per horizon
    on the SAME ``features``.
    """
    features = _coerce_stacking_input(ensemble_dict, model_input)
    base_fold_models = ensemble_dict.get("base_fold_models", {}) or {}
    base_keys = ensemble_dict.get("base_model_keys") or []
    if not base_keys:
        raise ValueError(
            "DM-5: multi-horizon artifact missing ``base_model_keys``"
        )
    if require_fold_models is None:
        require_fold_models = (
            ensemble_dict.get("option_b_base_source") == OPTION_B_BASE_SOURCE
        )

    n_samples = features.shape[0]
    n_cols = len(horizon_roster) * len(base_keys)
    base_matrix = np.full((n_samples, n_cols), 0.5, dtype=np.float64)

    col_idx = 0
    for horizon in horizon_roster:
        for key in base_keys:
            cell_key = f"h{int(horizon)}_{key}"
            fold_models = list(base_fold_models.get(cell_key) or [])
            if not fold_models:
                if require_fold_models:
                    raise ValueError(
                        f"DM-5: missing fold models for {cell_key!r}"
                    )
                col_idx += 1
                continue
            fold_preds: list[np.ndarray] = []
            for model in fold_models:
                try:
                    pred = np.asarray(
                        _predict_base_proba(model, features), dtype=float,
                    ).ravel()
                    if len(pred) == n_samples and np.isfinite(pred).all():
                        fold_preds.append(pred)
                except Exception as exc:
                    logger.warning(
                        "DM-5 fold model %r failed during predict: %s",
                        cell_key, exc,
                    )
            if fold_preds:
                base_matrix[:, col_idx] = np.mean(
                    np.vstack(fold_preds), axis=0,
                )
            elif require_fold_models:
                raise ValueError(
                    f"DM-5: no usable fold predictions for {cell_key!r}"
                )
            col_idx += 1
    return base_matrix


def predict_stacking_ensemble_proba(
    ensemble_dict: Dict[str, Any],
    model_input: Any,
    *,
    apply_calibration: bool = True,
    require_fold_models: bool | None = None,
) -> np.ndarray:
    """Run base-fold aggregation, meta prediction, and optional calibration."""
    base_matrix = build_stacking_base_matrix(
        ensemble_dict,
        model_input,
        require_fold_models=require_fold_models,
    )
    return predict_stacking_meta_proba(
        ensemble_dict,
        base_matrix,
        apply_calibration=apply_calibration,
    )


def predict_stacking_meta_proba(
    ensemble_dict: Dict[str, Any],
    base_matrix: Any,
    *,
    apply_calibration: bool = True,
) -> np.ndarray:
    """Run meta prediction and optional calibration from base probabilities."""
    base_matrix = np.asarray(base_matrix, dtype=float)
    if base_matrix.ndim == 1:
        base_matrix = base_matrix.reshape(1, -1)
    meta_model = ensemble_dict["meta_model"]
    if hasattr(meta_model, "predict_proba"):
        meta_proba = np.asarray(meta_model.predict_proba(base_matrix), dtype=float)
        out = (
            meta_proba[:, 1]
            if meta_proba.ndim == 2 and meta_proba.shape[1] >= 2
            else meta_proba.ravel()
        )
    elif hasattr(meta_model, "predict"):
        out = np.clip(np.asarray(meta_model.predict(base_matrix), dtype=float), 0, 1)
    else:
        out = base_matrix.mean(axis=1)

    if apply_calibration:
        calibrator = ensemble_dict.get("calibrator")
        if calibrator is not None and hasattr(calibrator, "transform"):
            try:
                out = calibrator.transform(np.asarray(out, dtype=float))
            except Exception as exc:
                logger.warning("Calibration transform failed during pyfunc predict: %s", exc)
    return np.asarray(out, dtype=float).ravel()


class StackingEnsemblePyfunc(mlflow.pyfunc.PythonModel if mlflow else object):
    """MLflow pyfunc wrapper around a stacking ensemble dict.

    Serialization:
        - ``save_context``: joblib-dumps the ensemble dict to ``ensemble.pkl``
        - ``load_context``: joblib-loads it back

    Prediction:
        - ``predict``: runs base→meta pipeline, returns P(class=1)
    """

    ARTIFACT_FILENAME = "ensemble.pkl"

    def __init__(self, ensemble_dict: Optional[Dict[str, Any]] = None) -> None:
        self.ensemble_dict = ensemble_dict
        # ML-1: parity metadata accessible without unpickling the full ensemble
        self.parity_metadata: Optional[Dict[str, Any]] = None
        if ensemble_dict is not None:
            self.parity_metadata = ensemble_dict.get("parity_metadata")

    # --- MLflow PythonModel interface ---

    def load_context(self, context: Any) -> None:
        """Load the ensemble dict from the saved artifact."""
        artifact_path = Path(context.artifacts[self.ARTIFACT_FILENAME])
        self.ensemble_dict = joblib.load(artifact_path)
        # ML-1: extract parity metadata for inference-time validation
        self.parity_metadata = self.ensemble_dict.get("parity_metadata")
        logger.info(
            "StackingEnsemblePyfunc loaded: bases=%s, meta=%s, parity=%s",
            list(self.ensemble_dict.get("base_models", {}).keys()),
            self.ensemble_dict.get("meta_model_key", "unknown"),
            "present" if self.parity_metadata else "absent",
        )

    def predict(
        self,
        context,
        model_input: pd.DataFrame,
        params=None,
    ):
        """Run stacking ensemble inference.

        Args:
            context: MLflow context (unused at predict time).
            model_input: DataFrame of shape (n_samples, n_features).
            params: Optional parameters (unused).

        Returns:
            1-D array of P(class=1) probabilities.
        """
        if self.ensemble_dict is None:
            raise RuntimeError("Ensemble not loaded; call load_context first")
        return predict_stacking_ensemble_proba(self.ensemble_dict, model_input)


def log_stacking_ensemble_model(
    ensemble_dict: Dict[str, Any],
    artifact_path: str,
    registered_model_name: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Optional[Any]:
    """Serialize the ensemble and log/register it in MLflow.

    This creates a pyfunc model that wraps the ensemble dict. The raw
    ``ensemble.pkl`` is also available as an artifact so the inference
    service can load it directly for the ``StackingEnsembleAdapter``.

    Args:
        ensemble_dict: The ensemble result dict (base_models, meta_model, etc.).
        artifact_path: MLflow artifact path (e.g. ``"direction_ensemble_model"``).
        registered_model_name: Optional registry name for model promotion.
        output_dir: Local directory for the pkl artifact temp file.

    Returns:
        ``mlflow.models.ModelInfo`` or None on failure.
    """
    if mlflow is None or joblib is None:
        logger.warning("MLflow/joblib not available; skipping ensemble model logging")
        return None

    # Write ensemble pkl to a temp location
    out = Path(output_dir or "models")
    out.mkdir(parents=True, exist_ok=True)
    pkl_path = out / StackingEnsemblePyfunc.ARTIFACT_FILENAME
    joblib.dump(ensemble_dict, pkl_path)

    try:
        # Build an explicit signature + input example from the trained feature
        # schema. Documents the serving contract and silences the MLflow
        # "add type hints"/"no input example" warnings. Skipped if feature
        # names are unavailable (the predict type hint still suppresses the
        # primary warning).
        signature = None
        input_example = None
        feature_names = ensemble_dict.get("feature_names")
        if feature_names and infer_signature is not None:
            try:
                input_example = pd.DataFrame([{str(col): 0.0 for col in feature_names}])
                signature = infer_signature(input_example, np.zeros(1, dtype=float))
            except Exception as sig_err:  # pragma: no cover - defensive
                logger.warning("Could not build stacking ensemble signature: %s", sig_err)
                signature = None
                input_example = None

        model_info = mlflow.pyfunc.log_model(
            artifact_path=artifact_path,
            python_model=StackingEnsemblePyfunc(ensemble_dict),
            artifacts={StackingEnsemblePyfunc.ARTIFACT_FILENAME: str(pkl_path)},
            registered_model_name=registered_model_name,
            signature=signature,
            input_example=input_example,
        )
        # ML-32 G9: Ensure numeric version is populated. MLflow >= 2.10 sets
        # registered_model_version automatically, but fall back to MlflowClient
        # query if it's missing (older MLflow or edge-case).
        if registered_model_name and not getattr(model_info, "registered_model_version", None):
            try:
                from mlflow.tracking import MlflowClient
                _client = MlflowClient()
                _latest = _client.get_latest_versions(registered_model_name)
                if _latest:
                    model_info._registered_model_version = int(_latest[0].version)
                    logger.info(
                        "Resolved numeric version via MlflowClient: %s v%s",
                        registered_model_name,
                        model_info.registered_model_version,
                    )
            except Exception as _ver_err:
                logger.warning("Could not resolve numeric version: %s", _ver_err)
        logger.info(
            "Stacking ensemble registered: name=%s, uri=%s, version=%s",
            registered_model_name,
            model_info.model_uri,
            getattr(model_info, "registered_model_version", None),
        )
        return model_info
    except Exception as e:
        logger.warning("Failed to register stacking ensemble model: %s", e)
        return None
