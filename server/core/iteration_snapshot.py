"""Server-owned immutable snapshots for autoresearch iteration attempts."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


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
        "artifact_hash": _first_present(
            marker,
            "artifact_hash",
            "model_artifact_hash",
        ),
        "mlflow_run_id": marker.get("mlflow_run_id"),
        "environment": _environment_metadata(),
    }
    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return snapshot


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
