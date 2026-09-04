from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from ..eval.metrics import compute_classification_metrics, compute_regression_metrics
from ..models.base import ModelProtocol


@dataclass(frozen=True)
class EvalResult:
    metrics: dict[str, float]


def _run_callbacks(callbacks: Optional[Iterable[Any]], event: str, **kwargs) -> None:
    if not callbacks:
        return
    for cb in callbacks:
        fn = getattr(cb, f"on_{event}", None)
        if callable(fn):
            fn(**kwargs)


def fit(
    model: ModelProtocol,
    X_train,
    y_train,
    *,
    eval_data: Optional[tuple[Any, Any]] = None,
    callbacks: Optional[Iterable[Any]] = None,
) -> ModelProtocol:
    _run_callbacks(callbacks, "fit_start", model=model)
    model.fit(X_train, y_train)
    _run_callbacks(callbacks, "fit_end", model=model)
    return model


def evaluate(
    model: ModelProtocol,
    X,
    y,
    *,
    task: str = "regression",
    metrics: Optional[list[str]] = None,
) -> EvalResult:
    y_pred = model.predict(X)
    if task == "classification":
        y_proba = None
        if hasattr(model, "predict_proba"):
            try:
                y_proba = model.predict_proba(X)
            except Exception:
                y_proba = None
        m = compute_classification_metrics(y_true=y, y_pred=y_pred, y_proba=y_proba, metrics=metrics)
    else:
        m = compute_regression_metrics(y_true=y, y_pred=y_pred, metrics=metrics)
    return EvalResult(metrics=m)

