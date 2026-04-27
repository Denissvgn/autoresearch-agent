from __future__ import annotations

import json
from pathlib import Path

from server.core.iteration_snapshot import (
    build_iteration_attempt_snapshot,
    write_iteration_attempt_snapshot,
)


def test_iteration_attempt_snapshot_hashes_config_and_writes_file(tmp_path: Path):
    snapshot = build_iteration_attempt_snapshot(
        research_id="res_attempt",
        iteration=2,
        turn=7,
        command="python scripts/autotuner/direction/prepare.py",
        config_snapshot="agent_strategy: BALA\n",
        workspace=str(tmp_path),
        marker={
            "status": "failed",
            "artifact_hash": "artifact-sha",
            "feature_schema_hash": "feature-sha",
        },
    )

    assert snapshot["schema_version"] == "autoresearch_iteration_attempt.v1"
    assert snapshot["status"] == "failed"
    assert snapshot["artifact_hash"] == "artifact-sha"
    assert snapshot["feature_schema_hash"] == "feature-sha"
    assert snapshot["config_snapshot_sha256"]
    assert snapshot["snapshot_hash"]

    path = write_iteration_attempt_snapshot(workspace=str(tmp_path), snapshot=snapshot)
    persisted = json.loads(Path(path).read_text(encoding="utf-8"))
    assert persisted["snapshot_hash"] == snapshot["snapshot_hash"]
    assert Path(path).name == "iteration_0002_attempt.json"

