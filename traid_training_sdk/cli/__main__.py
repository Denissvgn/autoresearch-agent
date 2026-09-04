from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from .. import TraidClient
from ..core.errors import (
    ConfigurationError,
    DataSourceError,
    EvaluationError,
    IOErrorSDK,
    NotAvailableSDK,
    NotImplementedSDK,
    RegistryError,
    RunLifecycleError,
    SdkError,
    TrainingError,
)
from .pipeline import build_synthetic_fetcher, execute_pipeline, load_pipeline_config


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _get_env_var(var_name: str) -> Optional[str]:
    """Get environment variable with TRAID_SDK_ prefix."""
    return os.environ.get(f"TRAID_SDK_{var_name}")


def _get_env_bool(var_name: str) -> Optional[bool]:
    """Get boolean environment variable with TRAID_SDK_ prefix."""
    value = _get_env_var(var_name)
    return _coerce_bool(value) if value is not None else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="traid-train",
        description="CLI entrypoint for Traid Model Training SDK",
    )
    parser.add_argument("--profile", help="Configuration profile override", default=None)
    parser.add_argument(
        "--config-file",
        dest="config_file",
        help="Path to SDK config file (JSON/YAML)",
        default=None,
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit command output as JSON",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    auto_parser = subparsers.add_parser(
        "auto",
        help="Run instrument-first autotrain workflow",
        description="Tune and register the best model for a given instrument/timeframe",
    )
    auto_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit command output as JSON",
    )
    auto_parser.add_argument(
        "--config",
        help="Path to AutoTrain YAML/JSON config (CLI overrides config; config overrides defaults)",
        default=None,
    )
    auto_parser.add_argument(
        "--instrument",
        help="Instrument spec e.g. binance:BTCUSDT",
        default=None,
    )
    auto_parser.add_argument(
        "--tf",
        "--timeframe",
        dest="timeframe",
        help="Timeframe (e.g. 1m)",
        default=None,
    )
    auto_parser.add_argument(
        "--bars",
        type=int,
        default=None,
        help="Number of historical bars to fetch (defaults to config or 5000)",
    )
    auto_parser.add_argument(
        "--objective",
        default=None,
        help="Optimization objective (rmse, sharpe, ...)",
    )
    auto_parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="Trial budget for tuning (defaults to config or 20)",
    )
    auto_parser.add_argument(
        "--timeout",
        default=None,
        help="Timeout budget (seconds or duration like 30m)",
    )
    auto_parser.add_argument(
        "--initial-balance",
        type=float,
        dest="initial_balance",
        default=None,
        help="Initial capital for trading metrics (passed to budget)",
    )
    auto_parser.add_argument(
        "--include",
        help="Comma-separated candidate filter (e.g. LinearRegression,RandomForestRegressor). Can also be set via TRAID_SDK_INCLUDE env var.",
        default=None,
    )
    auto_parser.add_argument(
        "--direction-backend",
        choices=["sdk", "ensemble"],
        default=None,
        help="Direction trainer backend: 'sdk' (in-process sklearn) or 'ensemble' (ensemble-trainer service). Can also be set via TRAID_SDK_DIRECTION_BACKEND env var. Default: sdk",
    )
    auto_parser.add_argument(
        "--rl-auto-data",
        dest="rl_auto_data",
        action="store_true",
        help="Automatically materialize RL enriched dataset when missing. Can also be set via TRAID_SDK_RL_AUTO_DATA=true env var. Default: enabled",
    )
    auto_parser.add_argument(
        "--no-rl-auto-data",
        dest="rl_auto_data",
        action="store_false",
        help="Disable automatic RL dataset materialization. Overrides TRAID_SDK_RL_AUTO_DATA env var.",
    )
    auto_parser.add_argument(
        "--orchestrator",
        default=None,
        help="Override orchestrator backend (local, ray, k8s, or plugin name)",
    )
    auto_parser.add_argument(
        "--experiment",
        default=None,
        help="Experiment name for run tracking (defaults to autotrain)",
    )
    auto_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Attach run tag (key=value). Can be repeated",
    )
    auto_parser.add_argument(
        "--mock-data",
        dest="mock_data",
        action="store_true",
        help="Use synthetic bars instead of live data (local quickstart)",
    )
    auto_parser.add_argument(
        "--no-mock-data",
        dest="mock_data",
        action="store_false",
        help="Disable synthetic bars even if enabled via config",
    )
    auto_parser.set_defaults(mock_data=None, rl_auto_data=None)
    auto_parser.epilog = "Precedence: CLI flags override config entries; config overrides defaults."
    auto_parser.set_defaults(handler=_handle_auto)

    run_parser = subparsers.add_parser(
        "run",
        help="Execute a YAML pipeline definition",
        description="Load a pipeline config and run classical training/eval/registration",
    )
    run_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit command output as JSON",
    )
    run_parser.add_argument(
        "pipeline",
        help="Path to pipeline YAML/JSON config",
    )
    run_parser.add_argument(
        "--experiment",
        default="pipeline",
        help="Experiment name for run tracking",
    )
    run_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Attach run tag (key=value). Can be repeated",
    )
    run_parser.add_argument(
        "--parity-baseline",
        default=None,
        help="Path to baseline CSV for feature parity comparison",
    )
    run_parser.add_argument(
        "--parity-tolerance",
        type=float,
        default=1e-4,
        help="Tolerance for feature parity mean absolute diff (default 1e-4)",
    )
    run_parser.add_argument(
        "--backtest-window",
        type=int,
        default=None,
        help="Window size for rolling backtest on returns",
    )
    run_parser.add_argument(
        "--backtest-step",
        type=int,
        default=None,
        help="Step size between rolling backtest windows",
    )
    run_parser.set_defaults(handler=_handle_run)

    register_parser = subparsers.add_parser(
        "register",
        help="Register a model artifact from disk",
        description="Register a saved UnifiedInstrumentModel artifact to the configured registry",
    )
    register_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit command output as JSON",
    )
    register_parser.add_argument("--artifact", required=True, help="Path to model artifact (joblib)")
    register_parser.add_argument("--name", required=True, help="Registry model name")
    register_parser.add_argument("--stage", default=None, help="Optional stage to promote (e.g. staging)")
    register_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Tag metadata key=value (repeated)",
    )
    register_parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        help="Additional metadata key=value entries",
    )
    register_parser.add_argument(
        "--format",
        default="unified",
        choices=["unified"],
        help="Artifact format (default: unified)",
    )
    register_parser.set_defaults(handler=_handle_register)

    return parser


def _load_autotrain_config(path: str) -> dict[str, Any]:
    cfg = load_pipeline_config(path)
    section = cfg.get("autotrain", cfg)
    if not isinstance(section, Mapping):
        raise ConfigurationError("AutoTrain config must be a mapping (under 'autotrain').")

    result: dict[str, Any] = {}

    def _normalized_str(key: str) -> Optional[str]:
        value = section.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    instrument = _normalized_str("instrument")
    if instrument:
        result["instrument"] = instrument

    timeframe = _normalized_str("timeframe") or _normalized_str("tf")
    if timeframe:
        result["timeframe"] = timeframe

    bars_value = section.get("bars")
    if bars_value is not None:
        try:
            result["bars"] = int(bars_value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("autotrain.bars must be an integer") from exc

    objective = _normalized_str("objective")
    if objective:
        result["objective"] = objective

    include_raw = section.get("include")
    include_list: Optional[list[str]] = None
    if include_raw is not None:
        if isinstance(include_raw, str):
            include_list = _split_csv(include_raw) or []
        elif isinstance(include_raw, Iterable):
            include_list = [str(item).strip() for item in include_raw if str(item).strip()]
        else:
            raise ConfigurationError("autotrain.include must be a string or list")
    if include_list:
        result["include"] = include_list

    direction_backend = _normalized_str("direction_backend")
    if direction_backend:
        backend_normalized = direction_backend.lower()
        if backend_normalized not in {"sdk", "ensemble"}:
            raise ConfigurationError("autotrain.direction_backend must be 'sdk' or 'ensemble'")
        result["direction_backend"] = backend_normalized

    orchestrator = _normalized_str("orchestrator")
    if orchestrator:
        result["orchestrator"] = orchestrator

    budget: dict[str, Any] = {}
    budget_raw = section.get("budget")
    if budget_raw is not None:
        if not isinstance(budget_raw, Mapping):
            raise ConfigurationError("autotrain.budget must be a mapping")
        for key, value in budget_raw.items():
            if key == "trials":
                try:
                    trials = int(value)
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError("budget.trials must be an integer") from exc
                if trials < 1:
                    raise ConfigurationError("budget.trials must be >= 1")
                budget["trials"] = trials
            elif key == "timeout":
                if isinstance(value, (int, float)):
                    budget["timeout"] = float(value)
                else:
                    duration = _parse_duration(str(value))
                    if duration is None:
                        raise ConfigurationError("budget.timeout cannot be empty")
                    budget["timeout"] = duration
            elif key == "initial_balance":
                try:
                    budget["initial_balance"] = float(value)
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError("budget.initial_balance must be numeric") from exc
            else:
                budget[key] = value

    if "initial_balance" not in budget and section.get("initial_balance") is not None:
        try:
            budget["initial_balance"] = float(section["initial_balance"])
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("autotrain.initial_balance must be numeric") from exc

    if budget:
        result["budget"] = budget

    experiment = _normalized_str("experiment")
    if experiment:
        result["experiment"] = experiment

    rl_auto_data_raw = section.get("rl_auto_data")
    if rl_auto_data_raw is not None:
        rl_auto_flag = _coerce_bool(rl_auto_data_raw)
        if rl_auto_flag is None:
            raise ConfigurationError("autotrain.rl_auto_data must be a boolean value")
        result["rl_auto_data"] = rl_auto_flag

    tags_raw = section.get("tags")
    tags: dict[str, str] = {}
    if isinstance(tags_raw, Mapping):
        tags = {
            str(key).strip(): str(value).strip()
            for key, value in tags_raw.items()
            if str(key).strip()
        }
    elif isinstance(tags_raw, str):
        tag_items = [item.strip() for item in tags_raw.split(",") if item.strip()]
        tags = _parse_tags(tag_items)
    elif isinstance(tags_raw, Iterable) and not isinstance(tags_raw, (bytes, str, Mapping)):
        tags = _parse_tags([str(item).strip() for item in tags_raw if str(item).strip()])
    if tags:
        result["tags"] = tags

    mock_data = _coerce_bool(section.get("mock_data"))
    if mock_data is not None:
        result["mock_data"] = mock_data

    rl_raw = section.get("rl_config") or section.get("rl")
    if isinstance(rl_raw, Mapping):
        result["rl_config"] = dict(rl_raw)

    return result


def _handle_auto(args, client: TraidClient) -> dict[str, Any]:
    config_values: dict[str, Any] = {}
    if args.config:
        config_values = _load_autotrain_config(args.config)

    include_cli = _split_csv(args.include)
    include_config = config_values.get("include")
    include_env = _split_csv(_get_env_var("INCLUDE"))
    include = include_cli if include_cli is not None else (include_env if include_env is not None else include_config)

    instrument = args.instrument or config_values.get("instrument")
    timeframe = args.timeframe or config_values.get("timeframe")
    if not instrument or not timeframe:
        raise ConfigurationError("Provide instrument/timeframe via CLI or autotrain config.")

    bars_value = args.bars if args.bars is not None else config_values.get("bars")
    bars = int(bars_value) if bars_value is not None else 5000
    if bars <= 0:
        raise ConfigurationError("bars must be a positive integer")

    objective = args.objective or config_values.get("objective") or "rmse"
    
    # Direction backend with precedence: CLI > env > config > default
    direction_backend_option = (
        args.direction_backend or 
        _get_env_var("DIRECTION_BACKEND") or 
        config_values.get("direction_backend")
    )
    direction_backend_value = "sdk"
    if direction_backend_option:
        direction_backend_value = str(direction_backend_option).lower()
        if direction_backend_value not in {"sdk", "ensemble"}:
            raise ConfigurationError("direction_backend must be 'sdk' or 'ensemble'")

    budget: dict[str, Any] = dict(config_values.get("budget", {}))
    if args.trials is not None:
        budget["trials"] = max(1, args.trials)
    elif "trials" not in budget:
        budget["trials"] = 20

    timeout_seconds = _parse_duration(args.timeout)
    if timeout_seconds is not None:
        budget["timeout"] = timeout_seconds

    if args.initial_balance is not None:
        budget["initial_balance"] = args.initial_balance

    tags_cfg_raw = config_values.get("tags")
    tags: dict[str, str] = {}
    if isinstance(tags_cfg_raw, Mapping):
        tags = {str(k): str(v) for k, v in tags_cfg_raw.items() if str(k)}
    tags_cli = _parse_tags(args.tag)
    tags.update(tags_cli)

    experiment = args.experiment or config_values.get("experiment") or "autotrain"

    orchestrator = args.orchestrator or config_values.get("orchestrator")

    rl_config = getattr(args, "rl_config", None) or config_values.get("rl_config")

    # RL auto-data with precedence: CLI > env > config > default
    rl_auto_data_value = True  # default is True
    rl_auto_data_config = config_values.get("rl_auto_data")
    if rl_auto_data_config is not None:
        rl_auto_data_value = bool(rl_auto_data_config)
    
    # Environment variable overrides config
    rl_auto_data_env = _get_env_bool("RL_AUTO_DATA")
    if rl_auto_data_env is not None:
        rl_auto_data_value = rl_auto_data_env
    
    # CLI overrides env and config
    if args.rl_auto_data is True:
        rl_auto_data_value = True
    elif args.rl_auto_data is False:
        rl_auto_data_value = False

    mock_config = config_values.get("mock_data")
    use_mock_data = bool(mock_config) if mock_config is not None else False
    if args.mock_data is True:
        use_mock_data = True
    elif args.mock_data is False:
        use_mock_data = False

    fetcher = build_synthetic_fetcher(seed=client.config.seed) if use_mock_data else None
    result = client.autotrain(
        instrument=instrument,
        timeframe=timeframe,
        bars=max(100, bars),
        objective=objective,
        budget=budget,
        include=include,
        direction_backend=direction_backend_value,
        fetcher=fetcher,
        orchestrator=orchestrator,
        rl_config=rl_config,
        rl_auto_data=rl_auto_data_value,
        experiment=experiment,
        tags=tags or None,
    )
    run_id = result.get("run_id")
    if run_id:
        run_dir = Path(client.config.io_runs_root) / run_id
        result.setdefault("run_dir", str(run_dir))
        result.setdefault("metrics_path", str(run_dir / "run.json"))
        result.setdefault("artifacts_path", str(run_dir / "artifacts"))
    if run_id:
        client.logger.info({"event": "cli.auto.completed", "run_id": run_id, "model_uri": result["model_uri"]})
    if tags:
        result.setdefault("tags", {}).update(tags)
    return result


def _handle_run(args, client: TraidClient) -> dict[str, Any]:
    cfg = load_pipeline_config(args.pipeline)
    tags = _parse_tags(args.tag)
    with client.run(experiment=args.experiment, tags=tags) as run:
        outcome = execute_pipeline(
            cfg,
            client=client,
            run=run,
            parity_baseline=args.parity_baseline,
            parity_tolerance=args.parity_tolerance,
            backtest_window=args.backtest_window,
            backtest_step=args.backtest_step,
        )
        run_dir = Path(client.config.io_runs_root) / run.run_id
        outcome.setdefault("run_id", run.run_id)
        outcome.setdefault("run_dir", str(run_dir))
        outcome.setdefault("metrics_path", str(run_dir / "run.json"))
        outcome.setdefault("artifacts_path", str(run_dir / "artifacts"))
        return outcome


def _handle_register(args, client: TraidClient) -> dict[str, Any]:
    from ..models.unified import UnifiedInstrumentModel
    from ..registry.filesystem import FilesystemRegistry

    artifact_path = Path(args.artifact)
    if not artifact_path.exists():
        raise ConfigurationError(f"Artifact not found: {artifact_path}")
    if args.format != "unified":
        raise ConfigurationError(f"Unsupported artifact format: {args.format}")

    try:
        model = UnifiedInstrumentModel.load(artifact_path)
    except Exception as exc:  # pragma: no cover - load failures mapped to IOErrorSDK
        raise IOErrorSDK(f"Failed to load artifact: {artifact_path}") from exc

    registry = FilesystemRegistry(client.config.io_registry.root or "model-registry")
    metadata = {
        "source": "cli.register",
        "metrics": model.metrics,
    }
    metadata.update(_parse_tags(args.metadata))
    tags = _parse_tags(args.tag)
    if tags:
        metadata.setdefault("tags", {}).update(tags)

    try:
        version = registry.register(model=model, name=args.name, metadata=metadata)
        if args.stage:
            registry.promote(args.name, version, args.stage)
        entry = registry.get(args.name, version)
    except Exception as exc:  # pragma: no cover - map to RegistryError
        raise RegistryError(str(exc)) from exc

    entry_path = Path(entry.path)
    result = {
        "model_uri": f"fs://{entry_path}",
        "name": args.name,
        "version": version,
        "stage": args.stage,
        "artifacts_path": str(entry_path.parent),
    }
    if tags:
        result["tags"] = tags
    return result


def _split_csv(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_tags(values: Iterable[str]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for raw in values or []:
        if not raw:
            continue
        key, sep, val = raw.partition("=")
        if not sep:
            tags[key.strip()] = "true"
        else:
            tags[key.strip()] = val.strip()
    return tags


def _parse_duration(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text.isdigit():
        return float(int(text))
    suffix_map = {"s": 1, "m": 60, "h": 3600}
    unit = text[-1]
    if unit in suffix_map:
        try:
            amount = float(text[:-1])
        except ValueError as exc:
            raise ConfigurationError(f"Invalid duration value: {value}") from exc
        return amount * suffix_map[unit]
    raise ConfigurationError(f"Unknown duration format: {value}")


_ERROR_CODES: dict[type[Exception], tuple[int, str]] = {
    ConfigurationError: (2, "Configuration error. Check --config-file and CLI arguments."),
    DataSourceError: (3, "Data source failed. Provide a fetcher or use --mock-data."),
    TrainingError: (4, "Training failed. Inspect logs and input data."),
    EvaluationError: (5, "Evaluation failed. Verify metrics and dataset integrity."),
    RegistryError: (6, "Registry operation failed. Check registry path and permissions."),
    RunLifecycleError: (7, "Run lifecycle error. Inspect run context configuration."),
    IOErrorSDK: (8, "I/O error. Ensure file paths and permissions are valid."),
    NotImplementedSDK: (9, "Feature not implemented in current SDK build."),
    NotAvailableSDK: (10, "Optional dependency unavailable. Install required extras."),
}


def _handle_exception(exc: Exception) -> int:
    for exc_type, (code, guidance) in _ERROR_CODES.items():
        if isinstance(exc, exc_type):
            print(f"error: {exc}", file=sys.stderr)
            print(f"hint: {guidance}", file=sys.stderr)
            return code
    print(f"unexpected error: {exc}", file=sys.stderr)
    return 1


def _emit(result: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    metrics = result.get("metrics")
    print("Command completed successfully.")
    if result.get("run_id"):
        print(f"Run ID: {result['run_id']}")
    if result.get("model_uri"):
        print(f"Model URI: {result['model_uri']}")
    if metrics:
        if isinstance(metrics, Mapping):
            top_items = list(metrics.items())[:5]
            joined = ", ".join(f"{k}={float(v):.4f}" for k, v in top_items)
            print(f"Metrics: {joined}")
    if result.get("metrics_path"):
        print(f"Metrics file: {result['metrics_path']}")
    if result.get("artifacts_path"):
        print(f"Artifacts: {result['artifacts_path']}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Optional[Callable[[Any, TraidClient], Mapping[str, Any]]] = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        client = TraidClient.from_env(profile=args.profile, config_file=args.config_file)
        result = handler(args, client)
        _emit(result, as_json=args.as_json)
        return 0
    except KeyboardInterrupt:
        print("Aborted.", file=sys.stderr)
        return 130
    except SdkError as exc:
        return _handle_exception(exc)
    except Exception as exc:  # pragma: no cover - last resort
        return _handle_exception(exc)


if __name__ == "__main__":
    sys.exit(main())
