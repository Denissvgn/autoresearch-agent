from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from ..core.client import TraidClient
from ..core.context import RunContext
from ..core.errors import (
    ConfigurationError,
    DataSourceError,
    EvaluationError,
    RegistryError,
    TrainingError,
)
from ..data.datasets import time_split
from ..data.sources import DataIngestSource, enrich_with_vdmc
from ..models.sklearn import SklearnModel
from ..models.unified import UnifiedInstrumentModel
from ..registry.filesystem import FilesystemRegistry
from ..train.trainer import evaluate, fit
from ..integrations.indicators import compare_feature_parity
from ..eval.validation import rolling_backtest


def load_pipeline_config(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise ConfigurationError(f"Pipeline config not found: {file_path}")
    text = file_path.read_text(encoding="utf-8")
    try:
        if file_path.suffix.lower() in {".yaml", ".yml"}:
            import yaml  # type: ignore

            data = yaml.safe_load(text) or {}
        else:
            import json

            data = json.loads(text)
    except ConfigurationError:
        raise
    except Exception as exc:  # pragma: no cover - re-raised with context
        raise ConfigurationError(f"Failed to parse pipeline config: {file_path}") from exc
    if not isinstance(data, Mapping):
        raise ConfigurationError("Pipeline config root must be a mapping")
    return dict(data)


def execute_pipeline(
    cfg: Mapping[str, Any],
    *,
    client: TraidClient,
    run: RunContext,
    parity_baseline: Optional[str] = None,
    parity_tolerance: Optional[float] = None,
    backtest_window: Optional[int] = None,
    backtest_step: Optional[int] = None,
) -> dict[str, Any]:
    data_cfg = cfg.get("data")
    if not isinstance(data_cfg, Mapping):
        raise ConfigurationError("Pipeline config requires a 'data' section")
    instrument = str(data_cfg.get("instrument", "")).strip()
    timeframe = str(data_cfg.get("timeframe", "")).strip()
    if not instrument or not timeframe:
        raise ConfigurationError("data.instrument and data.timeframe are required")
    bars = int(data_cfg.get("bars", 5000))
    provider = data_cfg.get("provider")
    fetcher = _resolve_fetcher(data_cfg, seed=run.seed)
    df = _load_dataframe(
        data_cfg,
        instrument=instrument,
        timeframe=timeframe,
        bars=bars,
        provider=provider,
        fetcher=fetcher,
    )
    run.logger.info({"event": "data.loaded", "rows": len(df), "instrument": instrument, "timeframe": timeframe})
    events = client.observability.events

    transforms_cfg = cfg.get("transforms", [])
    df = _apply_transforms(df, transforms_cfg)

    target_col = str(cfg.get("target", "ret"))
    if target_col not in df.columns:
        df[target_col] = (df["close"].astype(float) / df["open"].astype(float)) - 1.0
        df[target_col] = df[target_col].fillna(0.0)

    features = cfg.get("features")
    if features is None:
        features = [c for c in df.columns if c.startswith("vdmc_")]
    if not isinstance(features, Iterable) or not list(features):
        raise ConfigurationError("Pipeline config must provide non-empty 'features'")
    feature_list = [str(f) for f in features]

    if parity_baseline:
        try:
            import pandas as pd

            baseline_df = pd.read_csv(parity_baseline)
        except Exception as exc:  # pragma: no cover - wrap pandas errors
            raise EvaluationError(f"Failed to load parity baseline: {exc}") from exc
        try:
            tol = parity_tolerance if parity_tolerance is not None else 0.0
            diffs = compare_feature_parity(
                df[feature_list],
                baseline_df,
                columns=feature_list,
                tolerance=tol,
            )
        except Exception as exc:
            raise EvaluationError(f"Feature parity comparison failed: {exc}") from exc
        run.log_artifact(
            {
                "columns": diffs,
                "tolerance": tol,
                "baseline_rows": int(len(baseline_df)),
                "current_rows": int(len(df)),
            },
            name="feature_parity.json",
        )
        events.feature_parity_checked(
            diffs,
            tolerance=tol,
            instrument=instrument,
            timeframe=timeframe,
            experiment=run.experiment,
            run_id=run.run_id,
        )
        if any(diff > tol for diff in diffs.values()):
            raise EvaluationError("Feature parity exceeds tolerance")

    split_cfg = cfg.get("split", {})
    if not isinstance(split_cfg, Mapping):
        raise ConfigurationError("split section must be a mapping")
    train_ratio = float(split_cfg.get("train", 0.7))
    val_ratio = float(split_cfg.get("val", 0.2))
    test_ratio = float(split_cfg.get("test", max(0.0, 1.0 - train_ratio - val_ratio)))
    if train_ratio <= 0.0 or val_ratio <= 0.0:
        raise ConfigurationError("train and val ratios must be positive")
    if train_ratio + val_ratio + test_ratio <= 0.99 or train_ratio + val_ratio + test_ratio > 1.01:
        total = train_ratio + val_ratio + test_ratio
        raise ConfigurationError(f"Split ratios must sum to 1.0 (got {total:.3f})")
    split = time_split(df, train=train_ratio, val=val_ratio, test=test_ratio)

    X_train, y_train = _frame_to_arrays(split.train, feature_list, target_col)
    X_val, y_val = _frame_to_arrays(split.val, feature_list, target_col)
    X_test, y_test = _frame_to_arrays(split.test, feature_list, target_col)

    model_cfg = cfg.get("model")
    if not isinstance(model_cfg, Mapping):
        raise ConfigurationError("model section must be provided")
    model_type = str(model_cfg.get("type", "")).strip()
    if not model_type:
        raise ConfigurationError("model.type is required")
    params = model_cfg.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, Mapping):
        raise ConfigurationError("model.params must be a mapping")
    task = str(model_cfg.get("task", "regression"))
    model = _build_model(model_type, params)

    try:
        fit(model, X_train, y_train)
    except Exception as exc:  # pragma: no cover - wrapped as TrainingError
        raise TrainingError(str(exc)) from exc

    eval_cfg = cfg.get("evaluate", {})
    metrics = None
    if isinstance(eval_cfg, Mapping):
        metrics_val = eval_cfg.get("metrics")
        if metrics_val is not None:
            if not isinstance(metrics_val, Iterable):
                raise ConfigurationError("evaluate.metrics must be a list")
            metrics = [str(m) for m in metrics_val]

    try:
        val_result = evaluate(model, X_val, y_val, task=task, metrics=metrics)
    except Exception as exc:  # pragma: no cover - wrapped as EvaluationError
        raise EvaluationError(str(exc)) from exc
    run.log_metrics({f"val_{k}": float(v) for k, v in val_result.metrics.items()})

    test_metrics: dict[str, float] = {}
    if len(y_test) > 0:
        try:
            test_result = evaluate(model, X_test, y_test, task=task, metrics=metrics)
        except Exception as exc:  # pragma: no cover - wrapped as EvaluationError
            raise EvaluationError(str(exc)) from exc
        test_metrics = {f"test_{k}": float(v) for k, v in test_result.metrics.items()}
        run.log_metrics(test_metrics)

    if backtest_window and target_col in split.test.columns:
        try:
            returns = split.test[target_col].astype(float).to_numpy()
            summary = rolling_backtest(returns, window_size=int(backtest_window), step=backtest_step)
            run.log_artifact(
                {
                    "metrics_mean": summary.metrics_mean,
                    "metrics_std": summary.metrics_std,
                    "windows": summary.windows,
                },
                name="rolling_backtest.json",
            )
            events.backtest_completed(
                {
                    "metrics_mean": summary.metrics_mean,
                    "metrics_std": summary.metrics_std,
                },
                window_size=int(backtest_window),
                step=backtest_step,
                instrument=instrument,
                timeframe=timeframe,
                experiment=run.experiment,
                run_id=run.run_id,
            )
        except Exception as exc:
            raise EvaluationError(f"Rolling backtest failed: {exc}") from exc

    run.log_artifact(dict(cfg), name="pipeline_config.json")

    registry_cfg = cfg.get("register")
    registry_payload: dict[str, Any] = {}
    if registry_cfg:
        if not isinstance(registry_cfg, Mapping):
            raise ConfigurationError("register section must be a mapping")
        name = str(registry_cfg.get("name", "")).strip()
        if not name:
            raise ConfigurationError("register.name is required")
        metadata = registry_cfg.get("metadata")
        tags = registry_cfg.get("tags")
        meta_dict: dict[str, Any] = {"source": "pipeline", "metrics": val_result.metrics}
        if isinstance(metadata, Mapping):
            meta_dict.update(metadata)
        if isinstance(tags, Mapping):
            meta_dict.setdefault("tags", {}).update({str(k): str(v) for k, v in tags.items()})
        registry = FilesystemRegistry(client.config.io_registry.root or "model-registry")
        unified = UnifiedInstrumentModel(
            model=model,
            features=feature_list,
            instrument=instrument,
            timeframe=timeframe,
            objective=str(cfg.get("objective", "rmse")),
            metrics=val_result.metrics,
        )
        try:
            version = registry.register(model=unified, name=name, metadata=meta_dict)
            stage = registry_cfg.get("stage")
            if stage:
                registry.promote(name, version, str(stage))
            entry = registry.get(name, version)
        except Exception as exc:  # pragma: no cover - wrapped as RegistryError
            raise RegistryError(str(exc)) from exc
        registry_payload = {
            "model_uri": f"fs://{entry.path}",
            "name": name,
            "version": version,
            "stage": str(registry_cfg.get("stage", "")) or None,
        }

    result: dict[str, Any] = {
        "metrics": {**{f"val_{k}": float(v) for k, v in val_result.metrics.items()}, **test_metrics},
        "features": feature_list,
    }
    if registry_payload:
        result.update(registry_payload)
    return result


def build_synthetic_fetcher(*, seed: Optional[int] = None):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed or 0)

    def _fetcher(*, symbol: str, timeframe: str, limit: Optional[int] = None, start: Optional[str] = None, end: Optional[str] = None):
        bars = int(limit or 1000)
        start_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        if start:
            start_ts = datetime.fromisoformat(start)
            if start_ts.tzinfo is None:
                start_ts = start_ts.replace(tzinfo=timezone.utc)
        if end:
            end_ts = datetime.fromisoformat(end)
            if end_ts.tzinfo is None:
                end_ts = end_ts.replace(tzinfo=timezone.utc)
            start_ts = end_ts - timedelta(minutes=bars)
        ts = [start_ts + timedelta(minutes=i) for i in range(bars)]
        base = np.linspace(100.0, 110.0, bars)
        noise = rng.normal(0.0, 0.3, size=bars)
        close = base + noise
        openp = close - rng.normal(0.05, 0.02, size=bars)
        high = np.maximum(openp, close) + 0.1
        low = np.minimum(openp, close) - 0.1
        vol = rng.integers(100, 500, size=bars)
        df = pd.DataFrame(
            {
                "timestamp": ts,
                "open": openp,
                "high": high,
                "low": low,
                "close": close,
                "volume": vol,
            }
        )
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    return _fetcher


def _resolve_fetcher(cfg: Mapping[str, Any], *, seed: Optional[int]) -> Optional[Any]:
    if cfg.get("mock") in {"synthetic", "synthetic-bars"}:
        return build_synthetic_fetcher(seed=seed)
    fetcher_path = cfg.get("fetcher")
    if fetcher_path:
        if not isinstance(fetcher_path, str):
            raise ConfigurationError("data.fetcher must be a string import path")
        module_name, _, attr = fetcher_path.partition(":")
        if not attr:
            module_name, attr = fetcher_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        fetcher = getattr(module, attr)
        if not callable(fetcher):
            raise ConfigurationError(f"Resolved fetcher is not callable: {fetcher_path}")
        return fetcher
    return None


def _load_dataframe(
    cfg: Mapping[str, Any],
    *,
    instrument: str,
    timeframe: str,
    bars: int,
    provider: Optional[str],
    fetcher,
):
    csv_path = cfg.get("csv") or cfg.get("csv_path")
    if csv_path:
        try:
            import pandas as pd
        except Exception as exc:  # pragma: no cover - wrapped as DataSourceError
            raise DataSourceError("pandas is required to load CSV datasets") from exc
        path = Path(str(csv_path))
        if not path.exists():
            raise DataSourceError(f"CSV dataset not found: {path}")
        df = pd.read_csv(path)
        if "timestamp" not in df.columns:
            raise DataSourceError("CSV must include a 'timestamp' column")
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df.sort_values("timestamp", inplace=True)
        if bars:
            df = df.tail(bars).reset_index(drop=True)
        return df

    source = DataIngestSource.from_spec(instrument, timeframe, provider=provider, fetcher=fetcher)
    try:
        df = source.limit(bars).to_dataframe()
    except Exception as exc:  # pragma: no cover - wrapped as DataSourceError
        raise DataSourceError(str(exc)) from exc
    return df


def _apply_transforms(df, transforms) -> Any:
    if not transforms:
        return enrich_with_vdmc(df)
    out = df
    if isinstance(transforms, (str, bytes)):
        items = [transforms]
    elif isinstance(transforms, Iterable):
        items = list(transforms)
    else:
        items = [transforms]
    for item in items:
        name = item
        if isinstance(item, Mapping):
            name = item.get("type")
        if isinstance(name, str) and name.lower() in {"vdmc", "enrich_vdmc"}:
            out = enrich_with_vdmc(out)
    if "vdmc_p_buy" not in out.columns:
        out = enrich_with_vdmc(out)
    return out


def _frame_to_arrays(frame, features: list[str], target: str):
    X = frame[features].to_numpy()
    y = frame[target].to_numpy()
    return X, y


def _build_model(model_type: str, params: Mapping[str, Any]):
    if model_type.startswith("sklearn:"):
        _, _, class_name = model_type.partition(":")
        return SklearnModel(class_name or "LinearRegression", params=dict(params))
    if model_type == "sklearn":
        return SklearnModel("LinearRegression", params=dict(params))
    raise ConfigurationError(f"Unsupported model.type: {model_type}")
