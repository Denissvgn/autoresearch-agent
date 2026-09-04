"""Portable MLflow pyfunc wrapper for best-base model serving (Option A).

Solves the ``ModuleNotFoundError: No module named 'src.training.ensemble'``
problem that occurs when an ``_MLPWrapper`` (or any custom class from the
ensemble-trainer codebase) is serialized via ``mlflow.sklearn.log_model()``.

Instead of relying on cloudpickle (which embeds the module path
``src.training.ensemble.stacking_trainer._MLPWrapper``), this wrapper:

1. Detects the model type at save time.
2. For MLP (``_MLPWrapper``): extracts the PyTorch state dict + config
   and saves them as native artifacts (``state_dict.pt`` + ``model_config.json``).
3. For standard sklearn-compatible models (LGB, XGB, RF, LogReg): uses joblib.
4. Registers the model as ``mlflow.pyfunc.log_model()`` with a self-contained
   ``PythonModel`` that reconstructs the model from native artifacts — no
   dependency on the ensemble-trainer module at load time.

Usage at training time::

    from training.ensemble.best_base_pyfunc import log_best_base_model

    model_info = log_best_base_model(
        model=production_model,
        model_key="mlp",
        artifact_path="direction_model",
        registered_model_name="direction_model_BTCUSDT",
        output_dir=Path("models"),
    )
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SKLEARN_PKL = "sklearn_model.pkl"
_TORCH_STATE = "state_dict.pt"
_MODEL_CONFIG = "model_config.json"
_CALIBRATOR_PKL = "calibrator.pkl"
_CALIBRATION_DIAGNOSTICS = "calibration_diagnostics.json"


# ---------------------------------------------------------------------------
# Helper: detect if model is an _MLPWrapper
# ---------------------------------------------------------------------------

def _is_mlp_wrapper(model: Any) -> bool:
    """Check if the model is an _MLPWrapper without importing it."""
    cls_name = type(model).__name__
    return cls_name == "_MLPWrapper"


def _extract_mlp_artifacts(
    model: Any,
    output_dir: Path,
    feature_columns: Optional[List[str]] = None,
    calibrator: Optional[Any] = None,
    calibration_diagnostics: Optional[Dict[str, Any]] = None,
    feature_schema_hash: Optional[str] = None,
    feature_schema_flags: Optional[Dict[str, Any]] = None,
    selected_feature_names_hash: Optional[str] = None,
) -> Dict[str, str]:
    """Extract PyTorch state dict and config from an _MLPWrapper.

    Returns a dict of ``{artifact_key: local_path}`` for MLflow pyfunc logging.
    """
    import torch

    inner_model = getattr(model, "_model", None)
    if inner_model is None:
        raise ValueError("_MLPWrapper._model is None — model was not fitted")

    # Get the actual nn.Sequential from TorchMLPModel
    nn_model = getattr(inner_model, "_model", None)
    if nn_model is None:
        raise ValueError("TorchMLPModel._model is None — model was not fitted")

    # Save PyTorch state dict
    state_path = output_dir / _TORCH_STATE
    torch.save(nn_model.state_dict(), str(state_path))

    # Save reconstruction config
    config = {
        "model_type": "mlp",
        "hidden_sizes": list(model.hidden_sizes),
        "learning_rate": model.learning_rate,
        "epochs": model.epochs,
        "batch_size": model.batch_size,
        "random_state": model.random_state,
        "early_stopping": model.early_stopping,
        "patience": model.patience,
        # Architecture info needed for reconstruction
        "n_features": inner_model._n_features,
        "n_classes": inner_model._n_classes,
        "task": inner_model.task,
        "feature_columns": list(feature_columns) if feature_columns is not None else None,
        "feature_schema_hash": feature_schema_hash,
        "feature_schema_flags": feature_schema_flags or {},
        "selected_feature_names_hash": selected_feature_names_hash,
        "has_calibrator": calibrator is not None,
    }

    # Save scaler state if present
    scaler_X = getattr(inner_model, "_scaler_X", None)
    if scaler_X is not None:
        scaler_path = output_dir / "scaler_X.pkl"
        joblib.dump(scaler_X, scaler_path)
        config["has_scaler_X"] = True
    else:
        config["has_scaler_X"] = False

    config_path = output_dir / _MODEL_CONFIG
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    artifacts = {
        "state_dict": str(state_path),
        "model_config": str(config_path),
    }
    if config["has_scaler_X"]:
        artifacts["scaler_X"] = str(output_dir / "scaler_X.pkl")

    artifacts.update(
        _extract_calibration_artifacts(
            output_dir,
            calibrator=calibrator,
            calibration_diagnostics=calibration_diagnostics,
        )
    )

    return artifacts


def _extract_sklearn_artifacts(
    model: Any,
    output_dir: Path,
    feature_columns: Optional[List[str]] = None,
    calibrator: Optional[Any] = None,
    calibration_diagnostics: Optional[Dict[str, Any]] = None,
    feature_schema_hash: Optional[str] = None,
    feature_schema_flags: Optional[Dict[str, Any]] = None,
    selected_feature_names_hash: Optional[str] = None,
) -> Dict[str, str]:
    """Save a standard sklearn-compatible model via joblib.

    Returns a dict of ``{artifact_key: local_path}``.
    """
    pkl_path = output_dir / _SKLEARN_PKL
    joblib.dump(model, pkl_path)

    if feature_columns is None and hasattr(model, "feature_names_in_"):
        feature_columns = [str(c) for c in getattr(model, "feature_names_in_")]

    config = {
        "model_type": "sklearn",
        "class_name": type(model).__name__,
        "feature_columns": list(feature_columns) if feature_columns is not None else None,
        "feature_schema_hash": feature_schema_hash,
        "feature_schema_flags": feature_schema_flags or {},
        "selected_feature_names_hash": selected_feature_names_hash,
        "has_calibrator": calibrator is not None,
    }
    config_path = output_dir / _MODEL_CONFIG
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    artifacts = {
        "sklearn_model": str(pkl_path),
        "model_config": str(config_path),
    }
    artifacts.update(
        _extract_calibration_artifacts(
            output_dir,
            calibrator=calibrator,
            calibration_diagnostics=calibration_diagnostics,
        )
    )
    return artifacts


def _extract_calibration_artifacts(
    output_dir: Path,
    *,
    calibrator: Optional[Any],
    calibration_diagnostics: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Persist optional best-base calibration artifacts."""
    artifacts: Dict[str, str] = {}
    if calibrator is not None:
        cal_path = output_dir / _CALIBRATOR_PKL
        joblib.dump(calibrator, cal_path)
        artifacts["calibrator"] = str(cal_path)
    if calibration_diagnostics is not None:
        diag_path = output_dir / _CALIBRATION_DIAGNOSTICS
        with open(diag_path, "w") as f:
            json.dump(calibration_diagnostics, f, indent=2)
        artifacts["calibration_diagnostics"] = str(diag_path)
    return artifacts


# ---------------------------------------------------------------------------
# PythonModel wrapper — self-contained, no ensemble-trainer import needed
# ---------------------------------------------------------------------------

class BestBasePyfunc(mlflow.pyfunc.PythonModel if mlflow else object):
    """Portable MLflow PythonModel for the best-base stacking model.

    At load time, reads ``model_config.json`` to decide the reconstruction
    strategy (MLP vs sklearn) and rebuilds the model from native artifacts.
    """

    def load_context(self, context: Any) -> None:
        """Reconstruct the model from saved artifacts."""
        config_path = self._artifact_path(context, "model_config")
        with open(config_path) as f:
            self._config = json.load(f)
        self._feature_columns = self._config.get("feature_columns")
        self._calibrator = None
        self._calibration_diagnostics = None

        model_type = self._config.get("model_type", "sklearn")

        if model_type == "mlp":
            self._load_mlp(context)
        else:
            self._load_sklearn(context)

        artifacts = getattr(context, "artifacts", {}) or {}
        if "calibrator" in artifacts:
            self._calibrator = joblib.load(Path(artifacts["calibrator"]))
        if "calibration_diagnostics" in artifacts:
            with open(Path(artifacts["calibration_diagnostics"])) as f:
                self._calibration_diagnostics = json.load(f)

    @staticmethod
    def _artifact_path(context: Any, key: str) -> Path:
        artifacts = getattr(context, "artifacts", {}) or {}
        if key not in artifacts:
            raise ValueError(f"Missing '{key}' artifact for BestBasePyfunc")
        return Path(artifacts[key])

    def _coerce_input(self, model_input: Any) -> np.ndarray:
        """Validate and coerce model input while preserving trained column order."""
        feature_columns = getattr(self, "_feature_columns", None)
        if feature_columns:
            if hasattr(model_input, "columns"):
                actual = list(model_input.columns)
                expected = list(feature_columns)
                if actual != expected:
                    raise ValueError(
                        "Feature columns do not match trained schema: "
                        f"expected={expected}, actual={actual}"
                    )
                X = model_input[expected].to_numpy()
            else:
                X = np.asarray(model_input)
                if X.ndim == 1:
                    X = X.reshape(1, -1)
                if X.shape[1] != len(feature_columns):
                    raise ValueError(
                        "Feature matrix width does not match trained schema: "
                        f"expected={len(feature_columns)}, actual={X.shape[1]}"
                    )
        elif hasattr(model_input, "values"):
            X = (
                model_input.select_dtypes(include=[np.number]).values
                if hasattr(model_input, "select_dtypes")
                else model_input.values
            )
        else:
            X = np.asarray(model_input)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return X

    def _load_mlp(self, context: Any) -> None:
        """Reconstruct MLP from PyTorch state dict."""
        import torch
        import torch.nn as nn

        cfg = self._config
        n_features = cfg["n_features"]
        n_classes = cfg.get("n_classes", 2)
        hidden_sizes = cfg["hidden_sizes"]
        task = cfg.get("task", "classification")

        # Reconstruct nn.Sequential architecture
        layers: list = []
        prev_size = n_features
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.1),
            ])
            prev_size = hidden_size

        if task == "classification" and n_classes > 1:
            layers.append(nn.Linear(prev_size, n_classes))
            layers.append(nn.LogSoftmax(dim=1))
        else:
            layers.append(nn.Linear(prev_size, 1))

        self._nn_model = nn.Sequential(*layers)

        # Load state dict
        state_path = self._artifact_path(context, "state_dict")
        state_dict = torch.load(str(state_path), map_location="cpu", weights_only=True)
        self._nn_model.load_state_dict(state_dict)
        self._nn_model.eval()

        # Load scaler
        self._scaler_X = None
        if self._config.get("has_scaler_X"):
            scaler_path = self._artifact_path(context, "scaler_X")
            self._scaler_X = joblib.load(scaler_path)

        self._model_type = "mlp"
        logger.info(
            "BestBasePyfunc: loaded MLP (features=%d, classes=%d, hidden=%s)",
            n_features, n_classes, hidden_sizes,
        )

    def _load_sklearn(self, context: Any) -> None:
        """Load sklearn model from joblib pickle."""
        pkl_path = self._artifact_path(context, "sklearn_model")
        self._sklearn_model = joblib.load(pkl_path)
        self._model_type = "sklearn"
        logger.info(
            "BestBasePyfunc: loaded sklearn model (%s)",
            type(self._sklearn_model).__name__,
        )

    def predict(
        self,
        context,
        model_input: pd.DataFrame,
        params=None,
    ):
        """Return P(class=1) probabilities."""
        if self._model_type == "mlp":
            out = self._predict_mlp(model_input)
        else:
            out = self._predict_sklearn(model_input)
        return self._apply_calibration(out)

    def _apply_calibration(self, probs: np.ndarray) -> np.ndarray:
        """Apply an optional serialized best-base calibrator."""
        calibrator = getattr(self, "_calibrator", None)
        if calibrator is None:
            return np.asarray(probs, dtype=float).ravel()
        p = np.asarray(probs, dtype=float).ravel()
        try:
            if isinstance(calibrator, dict):
                method = calibrator.get("method")
                model = calibrator.get("model")
                if method == "isotonic":
                    return np.asarray(model.predict(p), dtype=float)
                if method == "platt":
                    p_clip = np.clip(p, 1e-5, 1.0 - 1e-5)
                    logits = np.log(p_clip / (1.0 - p_clip)).reshape(-1, 1)
                    return np.asarray(model.predict_proba(logits)[:, 1], dtype=float)
                if method == "constant":
                    return np.full_like(p, float(model), dtype=float)
            if hasattr(calibrator, "transform"):
                return np.asarray(calibrator.transform(p), dtype=float).ravel()
        except Exception as exc:
            logger.warning("BestBasePyfunc calibration failed: %s", exc)
        return p

    def _predict_mlp(self, model_input: Any) -> np.ndarray:
        """MLP inference: scale → forward pass → softmax → P(class=1)."""
        import torch

        X = self._coerce_input(model_input)
        X = X.astype(np.float32)

        # Scale if scaler exists
        if self._scaler_X is not None:
            X = self._scaler_X.transform(X)

        # Forward pass
        with torch.no_grad():
            tensor = torch.tensor(X, dtype=torch.float32)
            output = self._nn_model(tensor)

            # Log softmax → exp → probabilities
            if output.shape[1] >= 2:
                proba = torch.exp(output).numpy()
                return proba[:, 1]
            else:
                return torch.sigmoid(output).numpy().ravel()

    def _as_named_frame(self, X: np.ndarray) -> Any:
        """Restore the feature names the sklearn model was trained with.

        ``_coerce_input`` returns a bare ndarray, so a model fitted on a named
        DataFrame would emit sklearn's "X does not have valid feature names"
        warning on every prediction (and during log-time signature validation).
        Wrapping the matrix in a DataFrame with the trained column names matches
        the training schema and silences it. Falls back to the raw array when
        the model was fitted without feature names.
        """
        names = getattr(self._sklearn_model, "feature_names_in_", None)
        if names is not None and X.ndim == 2 and X.shape[1] == len(names):
            return pd.DataFrame(X, columns=list(names))
        return X

    def _predict_sklearn(self, model_input: Any) -> np.ndarray:
        """Sklearn inference: predict_proba → P(class=1)."""
        X = self._as_named_frame(self._coerce_input(model_input))

        if hasattr(self._sklearn_model, "predict_proba"):
            proba = self._sklearn_model.predict_proba(X)
            return proba[:, 1] if proba.ndim == 2 and proba.shape[1] >= 2 else proba.ravel()
        else:
            return np.clip(self._sklearn_model.predict(X), 0, 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_best_base_model(
    model: Any,
    model_key: str,
    artifact_path: str = "direction_model",
    registered_model_name: Optional[str] = None,
    output_dir: Optional[Path] = None,
    feature_columns: Optional[List[str]] = None,
    calibrator: Optional[Any] = None,
    calibration_diagnostics: Optional[Dict[str, Any]] = None,
    feature_schema_hash: Optional[str] = None,
    feature_schema_flags: Optional[Dict[str, Any]] = None,
    selected_feature_names_hash: Optional[str] = None,
) -> Optional[Any]:
    """Serialize the best-base model portably and register in MLflow.

    For MLP models: saves PyTorch state dict + config (no pickle of custom classes).
    For sklearn models: saves via joblib (standard, portable).

    Both are wrapped in a ``BestBasePyfunc`` PythonModel that MLflow can
    load in any environment without needing ensemble-trainer code.

    Args:
        model: The fitted production model (may be ``_MLPWrapper`` or sklearn).
        model_key: Model identifier (e.g. ``"mlp"``, ``"lgb"``, ``"xgb"``).
        artifact_path: MLflow artifact sub-path (e.g. ``"direction_model"``).
        registered_model_name: Optional MLflow registry name.
        output_dir: Local directory for staging artifacts.

    Returns:
        ``mlflow.models.ModelInfo`` on success, None on failure.
    """
    if mlflow is None or joblib is None:
        logger.warning("MLflow/joblib not available; skipping best-base model logging")
        return None

    out = Path(output_dir or "models") / "_pyfunc_staging"
    out.mkdir(parents=True, exist_ok=True)

    try:
        if _is_mlp_wrapper(model):
            logger.info("Saving MLP best-base model via native torch serialization")
            artifacts = _extract_mlp_artifacts(
                model,
                out,
                feature_columns=feature_columns,
                calibrator=calibrator,
                calibration_diagnostics=calibration_diagnostics,
                feature_schema_hash=feature_schema_hash,
                feature_schema_flags=feature_schema_flags,
                selected_feature_names_hash=selected_feature_names_hash,
            )
        else:
            logger.info("Saving sklearn best-base model (%s) via joblib", model_key)
            artifacts = _extract_sklearn_artifacts(
                model,
                out,
                feature_columns=feature_columns,
                calibrator=calibrator,
                calibration_diagnostics=calibration_diagnostics,
                feature_schema_hash=feature_schema_hash,
                feature_schema_flags=feature_schema_flags,
                selected_feature_names_hash=selected_feature_names_hash,
            )

        # Build an explicit signature + input example when the trained feature
        # schema is known. This documents the serving contract and silences the
        # MLflow "add type hints"/"no input example" warnings. If columns can't
        # be resolved we skip both (the predict type hint still suppresses the
        # primary warning).
        signature = None
        input_example = None
        resolved_columns = list(feature_columns) if feature_columns else None
        if resolved_columns is None:
            feat_in = getattr(model, "feature_names_in_", None)
            if feat_in is not None:
                resolved_columns = [str(c) for c in feat_in]
        if resolved_columns and infer_signature is not None:
            try:
                input_example = pd.DataFrame([{col: 0.0 for col in resolved_columns}])
                signature = infer_signature(input_example, np.zeros(1, dtype=float))
            except Exception as sig_err:  # pragma: no cover - defensive
                logger.warning("Could not build best-base model signature: %s", sig_err)
                signature = None
                input_example = None

        model_info = mlflow.pyfunc.log_model(
            artifact_path=artifact_path,
            python_model=BestBasePyfunc(),
            artifacts=artifacts,
            registered_model_name=registered_model_name,
            signature=signature,
            input_example=input_example,
        )
        # ML-32 G9: Ensure numeric version is populated (fallback for older MLflow).
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
            "Best-base model registered as pyfunc: name=%s, uri=%s, version=%s",
            registered_model_name,
            model_info.model_uri,
            getattr(model_info, "registered_model_version", None),
        )
        return model_info

    except Exception as e:
        logger.error("Failed to log best-base model as pyfunc: %s", e, exc_info=True)
        return None
