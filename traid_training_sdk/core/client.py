from __future__ import annotations

import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
import time
from pathlib import Path
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Optional, TYPE_CHECKING

try:  # pragma: no cover - optional dependency
    import torch
except ImportError:  # pragma: no cover - torch may be missing
    torch = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from .config import SdkConfig
else:
    from .config import SdkConfig

from .config import from_env as config_from_env, from_file, load_default_config, merge
from .context import RunContext, new_run_context
from .errors import ConfigurationError, NotAvailableSDK, NotImplementedSDK
from .logging import get_logger
from ..observability import ObservabilityServices, build_observability
from ..integrations.feature_flags import FeatureFlags, build_feature_flags
from ..security.secrets import SecretManager, build_secret_manager
from ..tracking.experiments import RunStore
from ..data.sources import DataIngestSource
from ..data.rl import materialize_rl_dataset
from ..data.datasets import time_split
from ..instruments.naming import autotrain_model_name, model_name
from ..integrations.composite import (
    ComponentRef,
    assemble_composite_manifest,
    persist_composite_manifest,
)
from ..integrations.indicators import build_direction_feature_set
from ..integrations.inference_compat import validate_unified_model
from ..integrations.ensemble_trainer import train_direction as run_ensemble_direction
from ..integrations.rl_trainer import train_rl_agent as run_rl_training
from ..models.rl import RLModelArtifact
from ..models.quantization import quantize_model
from ..models.unified import UnifiedInstrumentModel
from ..models.base import joblib_load
from ..registry.filesystem import FilesystemRegistry
from ..train.autotune import TrialResult, tune
from ..train.candidates import Candidate, default_candidates
from ..train.orchestrators import load_orchestrator
from ..train.objectives import resolve_objective


def _is_discrete_target(values: np.ndarray) -> bool:
    arr = np.asarray(values)
    if arr.size == 0:
        return False
    kind = arr.dtype.kind
    if kind in {"U", "S", "O"}:
        return True
    if kind in {"b", "i", "u"}:
        unique = np.unique(arr)
        limit = max(20, max(1, arr.size // 10))
        return bool(unique.size <= limit)
    if kind == "f":
        return False
    return False



def _build_registry_metadata(
    *,
    objective: str,
    metric_key: str,
    mode: str,
    instrument: str,
    timeframe: str,
    initial_balance: int | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "objective": objective,
        "metric_key": metric_key,
        "mode": mode,
        "instrument": instrument,
        "timeframe": timeframe,
    }
    tags = {
        "instrument": instrument,
        "timeframe": timeframe,
    }
    if initial_balance is not None:
        metadata["initial_balance"] = initial_balance
        tags["initial_balance"] = str(initial_balance)
    metadata["tags"] = tags
    return metadata


def _should_validate_inference() -> bool:
    raw = os.getenv("TRAID_SDK_VALIDATE_INFERENCE")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _should_quantize(config: "SdkConfig") -> bool:
    flag = getattr(config, "enable_quantization", None)
    if flag is None:
        return False
    return bool(flag)


@dataclass(frozen=True)
class TraidClient:
    """
    Minimal training SDK client placeholder.

    Notes:
    - Sprint 0 only requires instantiation and a simple from_env().
    - Additional methods (e.g., run context manager) land in later sprints.
    """

    config: "SdkConfig"
    _secrets: "SecretManager | None" = field(default=None, repr=False, compare=False)
    _observability: "ObservabilityServices | None" = field(default=None, repr=False, compare=False)
    _flags: "FeatureFlags | None" = field(default=None, repr=False, compare=False)

    @staticmethod
    def _env_or_default(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
        return env if env is not None else os.environ

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
        *,
        profile: Optional[str] = None,
        config_file: Optional[str] = None,
    ) -> "TraidClient":
        """
        Create a client from configuration file and/or environment variables.

        Precedence: programmatic (profile arg) > env > file defaults.
        """
        base_cfg = load_default_config()
        if config_file:
            base_cfg = merge(base_cfg, from_file(config_file))
        env_cfg = config_from_env(env=cls._env_or_default(env))
        cfg = merge(base_cfg, env_cfg)
        if profile:
            cfg = cfg.model_copy(update={"profile": profile})

        # Initialize logger on creation
        logger = get_logger(
            "traid_training_sdk",
            level=cfg.logging.level,
            json_mode=cfg.logging.json,
        )
        logger.debug("TraidClient initialized")
        client = cls(config=cfg)
        object.__setattr__(client, "_secrets", build_secret_manager(cfg.secrets))
        object.__setattr__(client, "_observability", build_observability(cfg.observability))
        object.__setattr__(client, "_flags", build_feature_flags(cfg.feature_flags))
        return client

    @property
    def logger(self) -> Any:
        return get_logger(
            "traid_training_sdk",
            level=self.config.logging.level,
            json_mode=self.config.logging.json,
        )

    @property
    def secrets(self) -> SecretManager:
        if self._secrets is None:
            object.__setattr__(self, "_secrets", build_secret_manager(self.config.secrets))
        return self._secrets  # type: ignore[return-value]

    @property
    def observability(self) -> ObservabilityServices:
        if self._observability is None:
            object.__setattr__(self, "_observability", build_observability(self.config.observability))
        return self._observability  # type: ignore[return-value]

    @property
    def flags(self) -> FeatureFlags:
        if self._flags is None:
            object.__setattr__(self, "_flags", build_feature_flags(self.config.feature_flags))
        return self._flags  # type: ignore[return-value]

    @contextmanager
    def run(
        self,
        *,
        experiment: str,
        tags: Optional[Mapping[str, str]] = None,
        seed: Optional[int] = None,
    ) -> Iterator[RunContext]:
        ctx = new_run_context(
            seed=seed if seed is not None else self.config.seed,
            experiment=experiment,
            tags=tags,
            logger_level=self.config.logging.level,
            logger_json=self.config.logging.json,
        )
        runs_root = self.config.io_runs_root
        ctx.runs_root = runs_root
        store = RunStore(
            runs_root=Path(runs_root),
            run_id=ctx.run_id,
            experiment=ctx.experiment,
            seed=ctx.seed,
            tags=ctx.tags,
            started_at=ctx.started_at,
        )
        store.init()
        ctx._store = store
        try:
            self.logger.info({"event": "run.started", "tags": dict(tags or {})})
            yield ctx
            ctx.ended_at = datetime.now(tz=timezone.utc).isoformat()
            if ctx._store is not None:
                ctx._store.finalize()
            self.logger.info({"event": "run.completed"})
        except Exception:
            self.logger.error({"event": "run.failed"}, exc_info=True)
            raise

    def trainer(self) -> None:
        raise NotImplementedSDK("trainer() is provided in later sprints")

    def _train_direction_via_ensemble(
        self,
        *,
        run: RunContext,
        run_dir: Path,
        bars_df: Any,
        instrument: str,
        timeframe: str,
        objective: str,
    ) -> tuple[UnifiedInstrumentModel, dict[str, float], list[TrialResult], str, str]:
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        dataset_path = artifacts_dir / "direction_bars.parquet"
        bars_df.to_parquet(dataset_path)

        symbol_token = instrument.replace(":", "_").replace("/", "_").upper()
        if not symbol_token:
            symbol_token = "DIRECTION"
        model_filename = f"{symbol_token}_direction_model.pkl"
        output_dir = artifacts_dir / "ensemble_trainer"
        output_dir.mkdir(parents=True, exist_ok=True)

        ensemble_config = {
            "data_path": str(dataset_path),
            "output_dir": str(output_dir),
            "model_filename": model_filename,
            "environment": self.config.profile or "development",
            "instrument_symbol": symbol_token,
        }

        ensemble_result = run_ensemble_direction(ensemble_config)
        model_path = Path(ensemble_result["model_path"])
        if not model_path.is_absolute():
            model_path = (output_dir / model_path).resolve()
        if not model_path.exists():
            raise ConfigurationError(f"ensemble trainer returned missing model artifact: {model_path}")

        features = [str(name) for name in ensemble_result.get("feature_names", []) if str(name)]
        if not features:
            raise ConfigurationError("ensemble trainer returned empty feature_names")
        feature_columns = features
        try:
            ensemble_features = build_direction_feature_set(
                ds.drop(columns=["ret"], errors="ignore"),
                include={"ma": True, "vdmc": True},
                dropna=False,
            )
            ds[ensemble_features.columns] = ensemble_features
        except Exception:
            self.logger.warning("Failed to augment dataset with ensemble feature columns", exc_info=True)

        metrics = {str(k): float(v) for k, v in ensemble_result.get("metrics", {}).items() if isinstance(v, (int, float))}
        if config_dump := ensemble_result.get("config"):
            run.log_artifact(config_dump, name="ensemble_trainer_config.json")

        model = joblib_load(model_path)
        metric_key, mode = resolve_objective(objective)
        score_metric = metrics.get(metric_key)
        if score_metric is None:
            score_metric = next((float(v) for v in metrics.values() if isinstance(v, (int, float))), float("nan"))
        else:
            score_metric = float(score_metric)
        if not math.isnan(score_metric) and metric_key not in metrics:
            metrics[metric_key] = float(score_metric)

        leaderboard_score = 0.0 if math.isnan(score_metric) else float(score_metric)
        leaderboard = [
            TrialResult(
                candidate="ensemble_trainer",
                params={"backend": "ensemble"},
                metrics=dict(metrics),
                score=leaderboard_score,
            )
        ]

        unified = UnifiedInstrumentModel(
            model=model,
            features=feature_columns,
            instrument=instrument,
            timeframe=timeframe,
            objective=objective,
            metrics=metrics,
        )

        if _should_quantize(self.config):
            try:
                torch_module = unified._unwrap_torch_module(unified.model)
                if torch is not None and isinstance(torch_module, torch.nn.Module):
                    self.logger.info({"event": "quantization.started", "instrument": instrument})
                    quantized_module = quantize_model(torch_module)
                    if hasattr(unified.model, "_model"):
                        unified.model._model = quantized_module
                    else:
                        unified.model = quantized_module
                    self.logger.info({"event": "quantization.completed", "instrument": instrument})
                else:
                    self.logger.info({"event": "quantization.skipped", "reason": "non_pytorch_model"})
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.warning({"event": "quantization.failed", "error": str(exc)}, exc_info=True)

        return unified, metrics, leaderboard, metric_key, mode

    def autotrain(
        self,
        *,
        instrument: str,
        timeframe: str,
        bars: int = 5000,
        objective: str = "rmse",
        budget: dict | None = None,
        include: list[str] | None = None,
        direction_backend: str = "sdk",
        fetcher: Any = None,
        orchestrator: str | None = None,
        rl_config: dict[str, Any] | None = None,
        rl_auto_data: bool = True,
        experiment: str | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> dict:
        budget = budget or {"trials": 20}
        trials = int(budget.get("trials", 20))
        timeout_val = budget.get("timeout")
        timeout_seconds = None
        if isinstance(timeout_val, (int, float)):
            timeout_seconds = float(timeout_val)
        enable_pbt = bool(budget.get("enable_pbt", False))
        initial_balance_value = budget.get("initial_balance")
        initial_balance: int | None = None
        if initial_balance_value is not None:
            try:
                initial_balance = int(float(initial_balance_value))
                budget["initial_balance"] = initial_balance
            except (TypeError, ValueError):
                initial_balance = None

        runs_root_path = Path(self.config.io_runs_root)
        metrics = self.observability.metrics
        events = self.observability.events
        result: dict[str, Any] = {}

        run_tags: dict[str, str] = {"instrument": instrument, "timeframe": timeframe}
        if tags:
            run_tags.update({str(k): str(v) for k, v in tags.items() if str(k)})

        experiment_name = experiment or "autotrain"

        with self.run(experiment=experiment_name, tags=run_tags) as run:
            labels: dict[str, Any] = {
                "experiment": run.experiment,
                "instrument": instrument,
                "timeframe": timeframe,
                "run_id": run.run_id,
                "model_name": "",
            }
            if initial_balance is not None:
                labels["initial_balance"] = initial_balance
            metrics.record_started(**labels)
            events.autotrain_started(**labels)
            start_time = time.perf_counter()
            try:
                run_dir = runs_root_path / run.run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                src = DataIngestSource.from_spec(instrument, timeframe, fetcher=fetcher)
                bars_df = src.limit(bars).to_dataframe()
                ds = bars_df.copy()
                ds["ret"] = ds["close"] / ds["open"] - 1.0
                feature_columns: list[str] | None = None

                backend = (direction_backend or "sdk").lower()
                if backend not in {"sdk", "ensemble"}:
                    raise ConfigurationError(
                        "INVALID_DIRECTION_BACKEND: supported values are 'sdk' and 'ensemble'"
                    )

                if backend == "ensemble":
                    self.logger.info({"event": "direction.training.backend", "backend": "ensemble"})
                    unified, best_metrics, leaderboard, metric_key, mode = self._train_direction_via_ensemble(
                        run=run,
                        run_dir=run_dir,
                        bars_df=bars_df,
                        instrument=instrument,
                        timeframe=timeframe,
                        objective=objective,
                    )
                else:
                    split: Any = time_split(ds, train=0.8, val=0.2, test=0.0)
                    train_df = split.train.reset_index(drop=True)
                    val_df = split.val.reset_index(drop=True)
                    X_train = train_df.drop(columns=["ret"], errors="ignore")
                    y_train = train_df["ret"].reset_index(drop=True)
                    X_val = val_df.drop(columns=["ret"], errors="ignore")
                    y_val = val_df["ret"].reset_index(drop=True)
                    is_discrete = _is_discrete_target(y_train.to_numpy())
                    try:
                        dtype = str(y_train.dtype)
                    except Exception:
                        dtype = "unknown"
                    self.logger.info({
                        "event": "preflight.target_type",
                        "discrete": bool(is_discrete),
                        "dtype": dtype,
                        "n": int(y_train.size),
                    })

                    if include:
                        allow_classification = True
                        if not is_discrete:
                            requested = {str(name).split(":")[-1].lower() for name in include}
                            forbidden = {"logisticregression", "randomforestclassifier"}
                            if requested & forbidden:
                                raise ConfigurationError(
                                    "CLASSIFICATION_NOT_ALLOWED: target is continuous; remove classification models from --include"
                                )
                    else:
                        allow_classification = is_discrete
                        if not allow_classification:
                            self.logger.info("Continuous target detected; limiting to regression candidates.")
                    cands: list[Candidate] = default_candidates(include=include, allow_classification=allow_classification)
                    if not cands:
                        raise ConfigurationError(
                            "NO_DIRECTION_CANDIDATES: adjust --include filters or enable classification models"
                        )
                    orchestrator_impl = load_orchestrator(orchestrator)
                    feature_builder = partial(
                        build_direction_feature_set,
                        include={"ma": True, "vdmc": True},
                        dropna=True,
                    )
                    best_model, best_metrics, leaderboard = orchestrator_impl.tune(
                        candidates=cands,
                        X_train=X_train,
                        y_train=y_train,
                        X_val=X_val,
                        y_val=y_val,
                        objective=objective,
                        trials=trials,
                        timeout_seconds=timeout_seconds,
                        seed=self.config.seed or 0,
                        enable_pbt=enable_pbt,
                        feature_gen=feature_builder,
                    )

                    metric_key, mode = resolve_objective(objective)
                    feature_columns = getattr(best_model, "_feature_cols", None)
                    feature_params = getattr(best_model, "feature_params", {})
                    try:
                        tuned_features = build_direction_feature_set(
                            ds.drop(columns=["ret"], errors="ignore"),
                            include={"ma": True, "vdmc": True},
                            dropna=False,
                            **feature_params,
                        )
                        ds[tuned_features.columns] = tuned_features
                        feature_columns = list(tuned_features.columns)
                    except Exception:
                        self.logger.warning("Failed to materialize tuned indicator features", exc_info=True)
                    unified = UnifiedInstrumentModel(
                        model=best_model,
                        features=feature_columns,
                        instrument=instrument,
                        timeframe=timeframe,
                        objective=objective,
                        metrics=best_metrics,
                    )

                    if _should_quantize(self.config):
                        try:
                            torch_module = unified._unwrap_torch_module(unified.model)
                            if torch is not None and isinstance(torch_module, torch.nn.Module):
                                self.logger.info({"event": "quantization.started", "instrument": instrument})
                                quantized_module = quantize_model(torch_module)
                                if hasattr(unified.model, "_model"):
                                    unified.model._model = quantized_module
                                else:
                                    unified.model = quantized_module
                                self.logger.info({"event": "quantization.completed", "instrument": instrument})
                            else:
                                self.logger.info({"event": "quantization.skipped", "reason": "non_pytorch_model"})
                        except Exception as exc:  # pragma: no cover - defensive logging
                            self.logger.warning({"event": "quantization.failed", "error": str(exc)}, exc_info=True)

                rl_dataset_meta: dict[str, Any] | None = None

                for idx, entry in enumerate(leaderboard):
                    metrics.record_leaderboard_update(
                        candidate=entry.candidate,
                        rank=idx,
                        score=entry.score,
                        **labels,
                    )
                    events.leaderboard_updated(entry.candidate, entry.score, idx, **labels)

                if _should_validate_inference():
                    validate_unified_model(unified)

                reg_root = self.config.io_registry.root or "model-registry"
                registry = FilesystemRegistry(reg_root)
                direction_model_name = autotrain_model_name(instrument, timeframe, initial_balance)
                labels["model_name"] = direction_model_name
                registry_start = time.perf_counter()
                version = registry.register(
                    model=unified,
                    name=direction_model_name,
                    metadata=_build_registry_metadata(
                        objective=objective,
                        metric_key=metric_key,
                        mode=mode,
                        instrument=instrument,
                        timeframe=timeframe,
                        initial_balance=initial_balance,
                    ),
                )
                registry_latency = (time.perf_counter() - registry_start) * 1000.0
                metrics.observe_registry_latency(registry_latency, **labels)
                registry_entry = registry.get(direction_model_name, version)

                manifest_initial_balance = initial_balance if initial_balance is not None else 0
                direction_fs_uri = f"fs://{registry_entry.path}"
                manifest_components: dict[str, ComponentRef] = {
                    "direction": ComponentRef(model_name=direction_model_name, version=version, fs_uri=direction_fs_uri)
                }
                rl_manifest: dict[str, Any] | None = None

                if rl_config:
                    try:
                        rl_payload = dict(rl_config)
                        dataset_stats: dict[str, Any] = {}
                        rl_output_dir_value = rl_payload.get("output_dir")
                        rl_output_dir = Path(rl_output_dir_value) if rl_output_dir_value else run_dir / "artifacts" / "rl"
                        rl_output_dir.mkdir(parents=True, exist_ok=True)
                        rl_payload.setdefault("output_dir", str(rl_output_dir))

                        enriched_path_value = rl_payload.get("enriched_data_path")
                        if rl_auto_data:
                            if not enriched_path_value:
                                enriched_path_value = materialize_rl_dataset(
                                    ds,
                                    path=rl_output_dir / "rl_enriched.parquet",
                                    feature_columns=feature_columns,
                                    stats=dataset_stats,
                                )
                                rl_payload["enriched_data_path"] = enriched_path_value
                            else:
                                dataset_stats.update({
                                    "path": str(enriched_path_value),
                                })
                        elif not enriched_path_value:
                            raise ConfigurationError(
                                "RL_AUTO_DATA_DISABLED: provide rl_config.enriched_data_path when rl_auto_data is False"
                            )

                        if dataset_stats:
                            rl_dataset_meta = {
                                "path": dataset_stats.get("path", str(enriched_path_value)),
                                "rows": dataset_stats.get("rows"),
                                "columns": dataset_stats.get("columns"),
                            }
                            run.log_artifact({k: v for k, v in rl_dataset_meta.items() if v is not None}, name="rl_dataset.json")
                        rl_result = run_rl_training(rl_payload)
                        rl_initial_balance = int(float(rl_payload.get("initial_balance", manifest_initial_balance)))
                        rl_model_name = model_name("rl_agent", instrument, timeframe, rl_initial_balance)
                        rl_version = registry.register(
                            model=RLModelArtifact(rl_result["model_path"]),
                            name=rl_model_name,
                            metadata={
                                "source": "rl_trainer",
                                "instrument": instrument,
                                "timeframe": timeframe,
                                "initial_balance": rl_initial_balance,
                                "metrics": rl_result.get("evaluation_results", {}),
                            },
                        )
                        rl_entry = registry.get(rl_model_name, rl_version)
                        events.model_registered(f"fs://{rl_entry.path}", rl_version, **labels)
                        run.log_artifact(rl_result.get("evaluation_results", {}), name="rl_evaluation.json")
                        manifest_components["rl_agent"] = ComponentRef(
                            model_name=rl_model_name,
                            version=rl_version,
                            fs_uri=f"fs://{rl_entry.path}",
                        )
                        manifest_initial_balance = rl_initial_balance or manifest_initial_balance
                        rl_manifest = {
                            "model_name": rl_model_name,
                            "version": rl_version,
                            "metrics": rl_result.get("evaluation_results", {}),
                        }
                    except ConfigurationError:
                        raise
                    except NotAvailableSDK as exc:
                        self.logger.warning("RL training not available: %s", exc)
                    except Exception:
                        self.logger.error("RL training failed", exc_info=True)

                leaderboard_json = [
                    {"candidate": r.candidate, "params": r.params, "metrics": r.metrics, "score": r.score}
                    for r in leaderboard
                ]
                run.log_metrics({metric_key: best_metrics.get(metric_key, 0.0)})
                run.log_metrics(
                    {
                        f"val_{k}": float(v)
                        for k, v in best_metrics.items()
                        if isinstance(v, (int, float))
                    }
                )
                run.log_artifact({"objective": objective, "metric_key": metric_key, "mode": mode}, name="autotrain_meta.json")
                run.log_artifact({"leaderboard": leaderboard_json}, name="leaderboard.json")

                duration_seconds = time.perf_counter() - start_time
                metrics.record_completed(duration_seconds, len(leaderboard), **labels)
                events.model_registered(f"fs://{registry_entry.path}", version, **labels)
                events.autotrain_completed(best_metrics, duration_seconds, **labels)

                uri = f"fs://{registry_entry.path}"
                run_dir = runs_root_path / run.run_id
                manifest = assemble_composite_manifest(
                    instrument=instrument,
                    timeframe=timeframe,
                    initial_balance=manifest_initial_balance,
                    components=manifest_components,
                )
                manifest_hash = manifest.stable_hash()
                manifest_path = persist_composite_manifest(
                    manifest,
                    directory=run_dir / "artifacts",
                )
                if run._store is not None:
                    try:
                        rel = manifest_path.relative_to(run_dir)
                        rel_path = str(rel)
                    except ValueError:
                        rel_path = manifest_path.name
                    run._store.add_artifact(manifest_path.name, f"artifacts/{manifest_path.name}" if not rel_path.startswith("artifacts/") else rel_path)
                result = {
                    "model_uri": uri,
                    "name": direction_model_name,
                    "version": version,
                    "metrics": best_metrics,
                    "run_id": run.run_id,
                    "run_dir": str(run_dir),
                    "artifacts_path": str(run_dir / "artifacts"),
                    "metrics_path": str(run_dir / "run.json"),
                    "composite_manifest": str(manifest_path),
                    "composite_hash": manifest_hash,
                }
                if rl_manifest:
                    result["rl_model"] = rl_manifest
                if rl_dataset_meta:
                    result["rl_dataset"] = rl_dataset_meta
            except Exception as exc:
                metrics.record_failed(**labels)
                events.autotrain_failed(str(exc), **labels)
                raise

        return result
