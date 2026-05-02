"""Server-owned immutable snapshots for autoresearch iteration attempts."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml


TRIAL_IDENTITY_SCHEMA_VERSION = "autoresearch_trial_identity.v1"


def build_iteration_attempt_snapshot(
    *,
    research_id: str,
    iteration: int,
    turn: int,
    command: str,
    config_snapshot: Optional[str],
    workspace: str,
    marker: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a server-owned attempt snapshot for one trial."""

    marker = marker or {}
    config_hash = marker.get("canonical_config_hash") or canonical_config_hash(
        config_snapshot
    )
    snapshot = {
        "schema_version": "autoresearch_iteration_attempt.v1",
        "research_id": research_id,
        "iteration": iteration,
        "turn": turn,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": marker.get("status") or "pending",
        "command": command,
        "api_request": {
            "tool": "bash",
            "command": command,
        },
        "config_snapshot": config_snapshot,
        "config_snapshot_sha256": _sha256_text(config_snapshot),
        "canonical_config_hash": config_hash,
        "trial_identity": marker.get("trial_identity"),
        "trial_identity_hash": marker.get("trial_identity_hash"),
        "workspace": workspace,
        "data_hash": _first_present(
            marker,
            "data_hash",
            "dataset_hash",
            "data_artifact_hash",
        ),
        "feature_schema_hash": _first_present(
            marker,
            "feature_schema_hash",
            "schema_hash",
        ),
        "obs_spec_hash": _first_present(
            marker,
            "obs_spec_hash",
            "observation_spec_hash",
        ),
        "rl_economic_replay_artifact_path": _first_present(
            marker,
            "rl_economic_replay_artifact_path",
            "economic_replay_artifact_path",
        ),
        "rl_economic_replay_artifact_hash": _first_present(
            marker,
            "rl_economic_replay_artifact_hash",
            "economic_replay_artifact_hash",
        ),
        "artifact_hash": _first_present(
            marker,
            "artifact_hash",
            "model_artifact_hash",
        ),
        "mlflow_run_id": marker.get("mlflow_run_id"),
        "runtime_command": marker.get("runtime_command"),
        "environment": _environment_metadata(),
    }
    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return snapshot


def canonical_config_hash(config_snapshot: Optional[str]) -> Optional[str]:
    """Hash config content after semantic YAML/JSON canonicalization."""

    canonical = canonical_config_payload(config_snapshot)
    if canonical is None:
        return None
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def canonical_config_payload(config_snapshot: Optional[str]) -> Any:
    """Return a stable representation of a config snapshot."""

    if config_snapshot is None:
        return None
    try:
        loaded = yaml.safe_load(config_snapshot)
    except yaml.YAMLError:
        loaded = None
    if loaded is None:
        stripped = config_snapshot.strip()
        return {"raw_text": stripped} if stripped else {}
    return _canonicalize(loaded)


def build_trial_identity(
    *,
    instrument: str,
    timeframe: str,
    model_type: str,
    command: Optional[str],
    config_snapshot: Optional[str],
    quick_mode: bool,
    marker: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a duplicate-detection identity for one planned/training attempt."""

    marker = marker or {}
    config_payload = canonical_config_payload(config_snapshot)
    identity = {
        "schema_version": TRIAL_IDENTITY_SCHEMA_VERSION,
        "instrument": instrument,
        "timeframe": timeframe,
        "model_type": model_type,
        "canonical_config_hash": canonical_config_hash(config_snapshot),
        "seed": _resolve_seed(
            command=command,
            config_payload=config_payload,
            marker=marker,
        ),
        "validation_mode": _resolve_validation_mode(
            command=command,
            quick_mode=quick_mode,
            marker=marker,
        ),
        "data_split_id": _resolve_data_split_id(config_payload),
    }
    return identity


def trial_identity_hash(identity: Mapping[str, Any]) -> Optional[str]:
    """Return a stable SHA-256 hash for a trial identity."""

    if not identity.get("canonical_config_hash"):
        return None
    payload = _canonicalize(dict(identity))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_iteration_attempt_snapshot(
    *,
    workspace: str,
    snapshot: Dict[str, Any],
) -> str:
    """Persist an attempt snapshot JSON file under the session workspace."""

    path = Path(workspace) / "server_snapshots" / (
        f"iteration_{snapshot['iteration']:04d}_attempt.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(path)


def _environment_metadata() -> Dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
    }


def _sha256_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _snapshot_hash(snapshot: Dict[str, Any]) -> str:
    payload = dict(snapshot)
    payload.pop("snapshot_hash", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _first_present(container: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = container.get(key)
        if value is not None:
            return value
    return None


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _argv(command: Optional[str]) -> list[str]:
    if not command:
        return []
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _command_arg(command: Optional[str], flag: str) -> Optional[str]:
    argv = _argv(command)
    if flag not in argv:
        return None
    index = argv.index(flag) + 1
    if index >= len(argv):
        return None
    return argv[index]


def _resolve_seed(
    *,
    command: Optional[str],
    config_payload: Any,
    marker: Mapping[str, Any],
) -> Any:
    seed_override = _command_arg(command, "--seed")
    if seed_override is not None:
        return _coerce_scalar(seed_override)
    for key in ("seed", "seed_used", "random_seed"):
        if marker.get(key) is not None:
            return marker[key]
    training_seed = _nested_get(config_payload, ("training", "seed"))
    if training_seed is not None:
        return training_seed
    top_level_seed = _nested_get(config_payload, ("seed",))
    if top_level_seed is not None:
        return top_level_seed
    return "default"


def _resolve_validation_mode(
    *,
    command: Optional[str],
    quick_mode: bool,
    marker: Mapping[str, Any],
) -> str:
    if command:
        return "quick" if "--quick" in _argv(command) else "full"
    marker_mode = marker.get("validation_mode") or marker.get("run_mode")
    if marker_mode in {"quick", "full"}:
        return str(marker_mode)
    return "quick" if quick_mode else "full"


def _resolve_data_split_id(config_payload: Any) -> str:
    if not isinstance(config_payload, Mapping):
        return "default"

    explicit = _first_nested(
        config_payload,
        (
            ("data_split_id",),
            ("split_id",),
            ("dataset_hash",),
            ("data_hash",),
            ("training", "data_split_id"),
            ("training", "split_id"),
            ("data", "split_id"),
            ("data", "dataset_hash"),
            ("dataset", "split_id"),
            ("dataset", "dataset_hash"),
        ),
    )
    if explicit is not None:
        return str(explicit)

    split_fields: Dict[str, Any] = {}
    for key in (
        "walkforward_n_folds",
        "wf_n_folds",
        "wf_train_bars",
        "wf_test_bars",
        "wf_embargo_bars",
        "wf_anchor",
        "purge_multiplier",
        "execution_lag",
    ):
        value = _nested_get(config_payload, (key,))
        if value is not None:
            split_fields[key] = value
    if not split_fields:
        return "default"
    encoded = json.dumps(
        _canonicalize(split_fields),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _first_nested(container: Any, paths: tuple[tuple[str, ...], ...]) -> Any:
    for path in paths:
        value = _nested_get(container, path)
        if value is not None:
            return value
    return None


def _nested_get(container: Any, path: tuple[str, ...]) -> Any:
    value = container
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def _coerce_scalar(value: str) -> Any:
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
