"""Result artifact preservation for autoresearch iterations."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

from src.core import fs_safety
from src.core.artifact_reference import (
    ARTIFACT_REFERENCE_KEYS,
    normalize_artifact_references_in_mapping,
    normalize_optional_artifact_ref,
)

RESULT_ARTIFACT_SCHEMA_VERSION = "autoresearch_result_artifact.v1"

_NESTED_RESULT_KEYS = (
    "metrics",
    "gate_results",
    "walkforward",
    "config",
    "calibration_full_validation",
    "calibration_diagnostics",
    "economic_replay",
    "economic_replay_regime_gated",
    "replay",
    "replay_gates",
    "aggregate",
    "folds",
    "fold_metrics",
    "inference",
    "inference_parity",
    "inference_validation",
    "requested_base_models",
    "surviving_base_models",
    "pruned_base_models",
    "model_roster",
    "feature_schema",
    "feature_schema_flags",
    "parity_metadata",
    "feature_provenance",
    "adaptive_features",
    "tsfm_adapter",
    "tsfm_fallback_validation",
    "tsfm_adapter_metadata",
    "tsfm_adapter_configs",
    "tsfm_adapter_artifact_paths",
)

_TOP_LEVEL_RESULT_KEYS = (
    "model_path",
    "model_registry_name",
    "model_version",
    "ensemble_model_registry_name",
    "ensemble_model_version",
    "serving_model_registry_name",
    "serving_model_version",
    "mlflow_run_id",
    "n_features",
    "artifact_hash",
    "model_artifact_hash",
    "feature_schema_hash",
    "selected_feature_names_hash",
    "data_hash",
    "dataset_hash",
    "adaptive_levels_enabled",
    "adaptive_levels_version",
    "adaptive_feature_version",
    "adaptive_feature_noop_reason",
    "mlflow_logging_status",
    "mlflow_setup_error",
    "candidate_family",
    "model_family",
    "is_tsfm_candidate",
    "tsfm_candidate",
)

_SERVER_OWNED_KEYS = {
    "status",
    "primary_metric",
    "metric_name",
    "direction",
    "training_gates_passed",
    "all_gates_passed",
    "training_time_s",
    "decision",
    "description",
    "config_snapshot",
    "search_phase",
    "trial_identity",
    "trial_identity_hash",
    "canonical_config_hash",
    "runtime_command",
    "planned_trial_id",
    "planned_trial_index",
    "results_json_path",
    "result_artifact_consume_source",
}


def enrich_marker_from_result_artifact(
    *,
    marker: MutableMapping[str, Any],
    workspace: str,
    iteration: int,
    logger: Any = None,
) -> Optional[dict[str, Any]]:
    """Copy and merge a result artifact referenced by a marker.

    The mutable ``results.json`` handoff file is copied into
    ``server_snapshots`` before its promotion evidence is merged into the
    marker. Invalid paths are ignored rather than failing iteration recording.
    """

    raw_path = marker.get("results_json_path")
    if not raw_path:
        return None

    workspace_path = Path(workspace).expanduser().resolve(strict=False)
    raw_source = _resolve_source_path(raw_path, workspace_path)
    if raw_source is None:
        _log_debug(logger, "Ignoring invalid results_json_path %r", raw_path)
        marker.pop("results_json_path", None)
        return None
    # Lexical containment first: the import below never follows links, so the
    # copy-in path must already be inside the workspace without traversal.
    normalized = Path(os.path.normpath(raw_source))
    try:
        source_rel = normalized.relative_to(workspace_path)
    except ValueError:
        source_rel = None
    if source_rel is None or ".." in source_rel.parts:
        _log_debug(logger, "Ignoring results_json_path outside workspace: %s", raw_source)
        marker.pop("results_json_path", None)
        return None
    source = normalized.resolve(strict=False)
    if not _is_allowed_source(source, workspace_path):
        _log_debug(logger, "Ignoring results_json_path outside workspace: %s", source)
        marker.pop("results_json_path", None)
        return None
    if not source.exists() or not source.is_file():
        _log_debug(logger, "Ignoring missing results_json_path: %s", source)
        marker.pop("results_json_path", None)
        return None

    target = workspace_path / "server_snapshots" / f"iteration_{iteration:04d}_results.json"
    try:
        # Strict import: regular, single-link, opened no-follow — a planted
        # link must not alias a shared file into the snapshot. The snapshot
        # target is replaced descriptor-relative, never through a link.
        data = fs_safety.read_regular_file(str(workspace_path), source_rel.as_posix())
        fs_safety.safe_write_bytes(
            str(workspace_path),
            f"server_snapshots/iteration_{iteration:04d}_results.json",
            data,
        )
        digest = hashlib.sha256(data).hexdigest()
        payload = json.loads(data)
    except (
        fs_safety.FilesystemSafetyError,
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        _log_debug(logger, "Failed to preserve result artifact %s: %s", source, exc)
        return None

    if isinstance(payload, dict):
        merge_result_payload(marker, payload)
        normalize_artifact_references_in_mapping(marker)

    metadata = {
        "result_artifact_schema_version": RESULT_ARTIFACT_SCHEMA_VERSION,
        "result_artifact_path": str(target),
        "result_artifact_sha256": digest,
        "result_artifact_source_path": str(source),
    }
    marker.update(metadata)

    if _should_consume_source(marker, source, workspace_path):
        try:
            os.remove(source)
        except FileNotFoundError:
            pass
        except OSError as exc:
            _log_debug(logger, "Failed to consume result artifact source %s: %s", source, exc)

    return metadata


def merge_result_payload(
    marker: MutableMapping[str, Any],
    payload: Mapping[str, Any],
) -> None:
    """Merge promotion-relevant rich result evidence into a marker."""

    for key in _NESTED_RESULT_KEYS:
        if key not in payload:
            continue
        marker_value = marker.get(key)
        result_value = payload[key]
        # Issue 6 root-cause: an explicit None in results.json must not blow
        # away a value the marker already carries (parse_prepare_output may
        # have computed it). The enricher's intent is to *add* evidence, not
        # nullify computed marker fields.
        if result_value is None and marker_value is not None:
            continue
        if isinstance(marker_value, dict) and isinstance(result_value, Mapping):
            marker[key] = _deep_merge_result_wins(marker_value, result_value)
        else:
            marker[key] = deepcopy(result_value)

    for key in _TOP_LEVEL_RESULT_KEYS:
        if key not in payload or key in _SERVER_OWNED_KEYS:
            continue
        raw_value = payload[key]
        # Issue 6 root-cause (see above): trainer's results.json may emit a
        # top-level field as explicit null when it isn't applicable; do not
        # let that null overwrite a non-None marker value derived from the
        # parsed --- block (e.g. adaptive_feature_noop_reason: "adaptive_
        # features_unavailable").
        if raw_value is None and marker.get(key) is not None:
            continue
        value = deepcopy(raw_value)
        if key in ARTIFACT_REFERENCE_KEYS:
            value = normalize_optional_artifact_ref(value)
        marker[key] = value

    _add_flat_aliases(marker, payload)


def _resolve_source_path(raw_path: Any, workspace_path: Path) -> Optional[Path]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return workspace_path / path


def _is_allowed_source(source: Path, workspace_path: Path) -> bool:
    try:
        relative = source.relative_to(workspace_path)
    except ValueError:
        return False
    return "server_snapshots" not in relative.parts


def _should_consume_source(
    marker: Mapping[str, Any],
    source: Path,
    workspace_path: Path,
) -> bool:
    raw = marker.get("result_artifact_consume_source")
    if isinstance(raw, bool):
        if raw:
            return True
    elif isinstance(raw, str) and raw.strip().lower() in {"1", "true", "yes"}:
        return True

    try:
        relative = source.relative_to(workspace_path)
    except ValueError:
        return False
    return relative.name == "results.json" or ".consumed." in relative.name


def _add_flat_aliases(
    marker: MutableMapping[str, Any],
    payload: Mapping[str, Any],
) -> None:
    metrics = _dict_at(payload, "metrics")
    walkforward = _dict_at(payload, "walkforward")
    config = _dict_at(payload, "config")
    gates = _dict_at(payload, "gate_results")

    aliases = {
        "auc": (metrics.get("auc"), gates.get("direction_auc")),
        "walkforward_auc": (
            walkforward.get("walkforward_mean_auc"),
            metrics.get("walkforward_auc"),
        ),
        "walkforward_cv": (
            walkforward.get("walkforward_auc_cv"),
            metrics.get("walkforward_auc_cv"),
        ),
        "meta_auc_oof": (metrics.get("meta_auc_oof"),),
        "signal_rate": (
            config.get("operating_signal_rate"),
            gates.get("operating_signal_rate"),
            metrics.get("signal_rate"),
        ),
        "operating_signal_rate": (
            config.get("operating_signal_rate"),
            gates.get("operating_signal_rate"),
            metrics.get("signal_rate"),
        ),
        "optimal_threshold": (
            config.get("optimal_threshold"),
            gates.get("optimal_threshold"),
        ),
        "prediction_horizon": (config.get("prediction_horizon"),),
        "positive_rate": (config.get("label_positive_rate"),),
        "atr_mult": (config.get("atr_mult"),),
        # P5: label-mode levers actually used by the run, surfaced flat for reliable
        # per-iteration config attribution and within-session dedup foresight.
        "label_mode": (config.get("label_mode"), metrics.get("label_mode")),
        "direction_pct_threshold": (config.get("direction_pct_threshold"),),
        "atr_barrier_mult": (config.get("atr_barrier_mult"),),
        "n_features": (payload.get("n_features"), metrics.get("n_features")),
        "candidate_family": (
            payload.get("candidate_family"),
            config.get("candidate_family"),
            metrics.get("candidate_family"),
        ),
        "model_family": (
            payload.get("model_family"),
            config.get("model_family"),
            metrics.get("model_family"),
        ),
        "is_tsfm_candidate": (
            payload.get("is_tsfm_candidate"),
            config.get("is_tsfm_candidate"),
            metrics.get("is_tsfm_candidate"),
        ),
        "tsfm_adapter": (
            payload.get("tsfm_adapter"),
            config.get("tsfm_adapter"),
            metrics.get("tsfm_adapter"),
        ),
        "tsfm_fallback_validation": (
            payload.get("tsfm_fallback_validation"),
            config.get("tsfm_fallback_validation"),
            metrics.get("tsfm_fallback_validation"),
        ),
        "tsfm_adapter_metadata": (
            payload.get("tsfm_adapter_metadata"),
            config.get("tsfm_adapter_metadata"),
            metrics.get("tsfm_adapter_metadata"),
        ),
    }
    for key, candidates in aliases.items():
        if key in marker and marker[key] not in (None, ""):
            continue
        value = _first_present(*candidates)
        if value is not None:
            marker[key] = value


def _deep_merge_result_wins(
    marker_value: Mapping[str, Any],
    result_value: Mapping[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(dict(marker_value))
    for key, value in result_value.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge_result_wins(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _dict_at(root: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = root.get(key)
    return value if isinstance(value, dict) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _log_debug(logger: Any, message: str, *args: Any) -> None:
    if logger is not None:
        logger.debug(message, *args)
