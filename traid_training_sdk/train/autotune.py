from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from ..eval.metrics import compute_classification_metrics, compute_regression_metrics, compute_trading_metrics
from ..models.base import ModelProtocol
from ..models.pipeline import Pipeline
from .candidates import Candidate
from .objectives import ObjectiveMode, resolve_objective


@dataclass(frozen=True)
class TrialResult:
    candidate: str
    params: dict[str, Any]
    metrics: dict[str, float]
    score: float
    feature_params: dict[str, Any] = field(default_factory=dict)


def _score_from_metrics(metrics: dict[str, float], metric_key: str) -> float:
    return float(metrics.get(metric_key, float("nan")))


def _prepare_inputs(X_data: Any, y_data: Any) -> tuple[Any, Any]:
    """Align indices when possible and convert pandas objects to numpy arrays."""
    X_curr = X_data
    y_curr = y_data
    if hasattr(X_data, "index") and hasattr(y_data, "reindex"):
        aligned = y_data.reindex(X_data.index)
        if hasattr(aligned, "isna"):
            mask = ~aligned.isna()
            if not bool(mask.all()):
                aligned = aligned[mask]
                if hasattr(X_data, "loc"):
                    X_curr = X_data.loc[aligned.index]
        y_curr = aligned
    if hasattr(X_curr, "select_dtypes"):
        import numpy as np
        X_curr = X_curr.select_dtypes(include=[np.number])
    X_out = X_curr.to_numpy() if hasattr(X_curr, "to_numpy") else X_curr
    y_out = y_curr.to_numpy() if hasattr(y_curr, "to_numpy") else y_curr
    return X_out, y_out


def tune(
    *,
    candidates: list[Candidate],
    X_train,
    y_train,
    X_val,
    y_val,
    objective: str = "rmse",
    trials: int = 20,
    timeout_seconds: Optional[float] = None,
    seed: Optional[int] = None,
    enable_pbt: bool = False,
    pbt_perturb: float = 0.1,
    feature_gen: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None,
) -> tuple[ModelProtocol, dict[str, float], list[TrialResult]]:
    if not candidates:
        from ..core.errors import ConfigurationError
        raise ConfigurationError("NO_CANDIDATES: at least one candidate must be provided for tuning")
    
    rng = random.Random(seed or 0)
    metric_key, mode = resolve_objective(objective)
    best_score = float("inf") if mode == "min" else -float("inf")
    best_model: Optional[ModelProtocol] = None
    best_metrics: dict[str, float] = {}
    best_feature_params: dict[str, Any] = {}
    leaderboard: list[TrialResult] = []
    
    # Cache for feature generation: hash(json(params)) -> (X_train_feat, X_val_feat)
    feature_cache: dict[str, tuple[Any, Any]] = {}

    start = time.time()
    for i in range(trials):
        if timeout_seconds is not None and (time.time() - start) > timeout_seconds:
            break
        cand = candidates[i % len(candidates)]
        params = cand.sample_params(rng)
        
        # Feature parameter sampling
        feature_params = {}
        if feature_gen is not None:
            feature_params = cand.sample_feature_params(rng)
            
        # Resolve data
        X_tr_curr, X_val_curr = X_train, X_val
        
        if feature_gen is not None:
            # Check cache
            fp_key = json.dumps(feature_params, sort_keys=True)
            if fp_key in feature_cache:
                X_tr_curr, X_val_curr = feature_cache[fp_key]
            else:
                # Generate features
                # We assume X_train/X_val are DataFrames when feature_gen is used
                try:
                    X_tr_curr = feature_gen(X_train, **feature_params)
                    X_val_curr = feature_gen(X_val, **feature_params)
                    feature_cache[fp_key] = (X_tr_curr, X_val_curr)
                except Exception:
                    # If feature gen fails (e.g. invalid params), skip trial
                    continue

        model = cand.make_model(params)
        try:
            X_train_ready, y_train_ready = _prepare_inputs(X_tr_curr, y_train)
            X_val_ready, y_val_ready = _prepare_inputs(X_val_curr, y_val)
            model.fit(X_train_ready, y_train_ready)
            if cand.task == "classification":
                metrics = compute_classification_metrics(y_true=y_val_ready, y_pred=model.predict(X_val_ready), metrics=["accuracy", "f1", "roc_auc"])
            else:
                y_pred = model.predict(X_val_ready)
                metrics = compute_regression_metrics(y_true=y_val_ready, y_pred=y_pred, metrics=["rmse", "mae", "r2"])
                metrics.update(
                    compute_trading_metrics(y_true_returns=y_val_ready, y_pred_returns=y_pred)
                )
            score = _score_from_metrics(metrics, metric_key)
            leaderboard.append(TrialResult(candidate=cand.name, params=params, feature_params=feature_params, metrics=metrics, score=score))
            
            is_better = (score < best_score) if mode == "min" else (score > best_score)
            if is_better and not np.isnan(score):
                best_score = score
                best_model = model
                best_metrics = metrics
                best_feature_params = feature_params
        except Exception:
            # Model training failure
            continue

    # Minimal PBT: run one extra perturbed trial from best-so-far
    if enable_pbt and leaderboard:
        best_trial = min(leaderboard, key=lambda tr: tr.score) if mode == "min" else max(leaderboard, key=lambda tr: tr.score)
        try:
            cand = next(c for c in candidates if c.name == best_trial.candidate)
        except StopIteration:
            cand = candidates[0]
        params = dict(best_trial.params)
        feature_params = dict(best_trial.feature_params)
        
        # Perturb model params
        for k, v in list(params.items()):
            if isinstance(v, (int, float)):
                params[k] = v * (1.0 + pbt_perturb)
                
        # Re-resolve data for best feature params (or perturbed if we supported that)
        X_tr_curr, X_val_curr = X_train, X_val
        if feature_gen is not None:
            fp_key = json.dumps(feature_params, sort_keys=True)
            if fp_key in feature_cache:
                X_tr_curr, X_val_curr = feature_cache[fp_key]
            else:
                X_tr_curr = feature_gen(X_train, **feature_params)
                X_val_curr = feature_gen(X_val, **feature_params)

        model = cand.make_model(params)
        try:
            X_train_ready, y_train_ready = _prepare_inputs(X_tr_curr, y_train)
            X_val_ready, y_val_ready = _prepare_inputs(X_val_curr, y_val)
            model.fit(X_train_ready, y_train_ready)
            if cand.task == "classification":
                metrics = compute_classification_metrics(y_true=y_val_ready, y_pred=model.predict(X_val_ready), metrics=["accuracy", "f1", "roc_auc"])
            else:
                y_pred = model.predict(X_val_ready)
                metrics = compute_regression_metrics(y_true=y_val_ready, y_pred=y_pred, metrics=["rmse", "mae", "r2"])
                metrics.update(compute_trading_metrics(y_true_returns=y_val_ready, y_pred_returns=y_pred))
            score = _score_from_metrics(metrics, metric_key)
            leaderboard.append(TrialResult(candidate=cand.name, params=params, feature_params=feature_params, metrics=metrics, score=score))
            is_better = (score < best_score) if mode == "min" else (score > best_score)
            if is_better and not np.isnan(score):
                best_score = score
                best_model = model
                best_metrics = metrics
                best_feature_params = feature_params
        except Exception:
            pass

    if best_model is None:
        # Fallback: run first candidate with default params
        cand = candidates[0]
        params = cand.sample_params(rng)
        feature_params = {}
        if feature_gen is not None:
            feature_params = cand.sample_feature_params(rng)
            X_tr_curr = feature_gen(X_train, **feature_params)
            X_val_curr = feature_gen(X_val, **feature_params)
        else:
            X_tr_curr, X_val_curr = X_train, X_val
            
        model = cand.make_model(params)
        X_train_ready, y_train_ready = _prepare_inputs(X_tr_curr, y_train)
        X_val_ready, y_val_ready = _prepare_inputs(X_val_curr, y_val)
        model.fit(X_train_ready, y_train_ready)
        best_model = model
        best_feature_params = feature_params
        if cand.task == "classification":
            best_metrics = compute_classification_metrics(y_true=y_val_ready, y_pred=model.predict(X_val_ready))
        else:
            preds = model.predict(X_val_ready)
            best_metrics = compute_regression_metrics(y_true=y_val_ready, y_pred=preds)

    # Wrap in Pipeline if feature generation was used
    if feature_gen is not None:
        pipeline = Pipeline(model=best_model, feature_gen=feature_gen, feature_params=best_feature_params)
        feature_df = None
        try:
            fp_key = json.dumps(best_feature_params, sort_keys=True)
            cached = feature_cache.get(fp_key) if fp_key else None
        except TypeError:
            cached = None
        if cached:
            feature_df = cached[0]
        else:
            try:
                feature_df = feature_gen(X_train, **best_feature_params)
            except Exception:
                feature_df = None
        if feature_df is not None:
            pipeline._feature_cols = list(feature_df.columns)
        best_model = pipeline

    return best_model, best_metrics, leaderboard
