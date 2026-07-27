"""Bootstrap for the ``ml-volatility`` skill (ARC-011 P5-003).

Renders the session workspace by delegating to the proven
``scripts/autotuner/setup.py`` with ``--models volatility``. See
``skills/ml-direction/bootstrap.py`` for the full ABI/contract docstring — this
file differs only in the ``--models`` flag. The Phase-5 migration (P5-007)
moves the orchestrator's embedded ``setup.py`` prompt text out of the server
and into this skill-owned bootstrap.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _setup_py_path() -> Path:
    ws_root = os.environ.get("AUTORESEARCH_WORKSPACE_ROOT") or os.environ.get(
        "WORKSPACE_ROOT"
    )
    if ws_root:
        candidate = Path(ws_root) / "scripts" / "autotuner" / "setup.py"
        if candidate.is_file():
            return candidate
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
        "volatility",
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
