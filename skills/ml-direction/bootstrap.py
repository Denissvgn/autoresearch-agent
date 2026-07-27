"""Bootstrap for the ``ml-direction`` skill (ARC-011 P5-002).

Renders the session workspace by delegating to the proven
``scripts/autotuner/setup.py`` with ``--models direction``. This is the
Phase-5 migration target for the workspace-prep logic that the orchestrator
previously embedded in the agent prompt (P5-007): the ``BootstrapRunner``
invokes this once at session start, so the orchestrator becomes purely loop +
guards and the ``prepare.py`` / ``train.yaml`` literals leave its prompt.

ABI (P5-005 / X-004 §6): JSON on stdin, JSON on stdout, exit 0/non-zero::

    {
      "workspace": "<abs path>",     # session workspace to render into
      "mode": "live" | "dry",        # dry = no side effects
      "skill_params": {              # canonical session params (P2-017)
        "subject_id": "DOGE_USDT",
        "variant": "15m",
        ...
      }
    }

The emitted JSON echoes the rendered file list so the ``BootstrapRunner`` can
hash + index them into the ``session_bootstrap.v1`` artifact (P5-006).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _setup_py_path() -> Path:
    """Resolve ``scripts/autotuner/setup.py`` relative to the repo root.

    The workspace root is conveyed via ``AUTORESEARCH_WORKSPACE_ROOT`` (set by
    the governed env allow-list); fall back to walking up from this file.
    """
    ws_root = os.environ.get("AUTORESEARCH_WORKSPACE_ROOT") or os.environ.get(
        "WORKSPACE_ROOT"
    )
    if ws_root:
        candidate = Path(ws_root) / "scripts" / "autotuner" / "setup.py"
        if candidate.is_file():
            return candidate
    # Walk up from this skill dir (skills/<id>/bootstrap.py) to the repo root.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "scripts" / "autotuner" / "setup.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "scripts/autotuner/setup.py not found (set AUTORESEARCH_WORKSPACE_ROOT)"
    )


def main() -> int:
    payload = json.load(sys.stdin)
    workspace = Path(payload["workspace"])
    mode = payload.get("mode", "live")
    skill_params = payload.get("skill_params") or {}
    instrument = skill_params.get("subject_id") or skill_params.get("instrument")
    timeframe = skill_params.get("variant") or skill_params.get("timeframe")
    if not instrument or not timeframe:
        json.dump(
            {"error": "subject_id and variant are required skill_params"},
            sys.stdout,
        )
        return 2

    workspace.mkdir(parents=True, exist_ok=True)
    if mode == "dry":
        # Dry mode: report what WOULD be rendered without invoking setup.py.
        # The BootstrapRunner runs this in an overlay tmpdir anyway, so a live
        # invocation is safe — but honoring ``mode=dry`` keeps the contract
        # explicit for reviewers inspecting the artifact.
        json.dump(
            {
                "rendered": ["train.yaml", "best_train.yaml", "results.tsv"],
                "mode": "dry",
                "note": "setup.py not invoked in dry mode",
            },
            sys.stdout,
        )
        return 0

    setup_py = _setup_py_path()
    repo_root = setup_py.parents[2]
    cmd = [
        sys.executable,
        str(setup_py),
        "--instrument",
        str(instrument),
        "--timeframe",
        str(timeframe),
        "--models",
        "direction",
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        json.dump(
            {
                "error": "setup.py failed",
                "returncode": completed.returncode,
                "stderr_tail": (completed.stderr or "")[-2000:],
            },
            sys.stdout,
        )
        return completed.returncode

    # Index what setup.py rendered. setup.py writes into
    # ``runs/autotuner/<instrument>_<timeframe>/`` — the canonical workspace
    # the orchestrator's ``config.workspace_path`` already points at.
    rendered_dir = repo_root / "runs" / "autotuner" / f"{instrument}_{timeframe}"
    rendered: list[str] = []
    if rendered_dir.is_dir():
        for path in sorted(rendered_dir.rglob("*")):
            if path.is_file():
                try:
                    rendered.append(path.relative_to(rendered_dir).as_posix())
                except ValueError:
                    pass
    json.dump({"rendered": rendered, "setup_stdout_tail": completed.stdout[-500:]}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
