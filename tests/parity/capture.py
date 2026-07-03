#!/usr/bin/env python3
"""ARC-011 X-002 parity fixture capture.

Regenerates the ``expected`` block of every parity case by invoking the real
source functions against the current code, then writes the normalized result
plus the originating git SHA back into each fixture JSON.

Run from the service root:

    python tests/parity/capture.py            # refuses on a dirty tree
    python tests/parity/capture.py --force    # allow dirty (e.g. while iterating)

Re-running against the same commit is idempotent (``expected`` and ``source_sha``
are unchanged). When a refactor intentionally changes behavior, re-run this
script on a clean tree at the new HEAD and commit the diff with the linked task.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PARITY_DIR))

from _engine import (  # type: ignore[import-not-found]  # sibling module
    HOST_CONFIGS_TOKEN,
    WORKSPACE_TOKEN,
    discover_cases,
    invoke,
    load_case,
    normalize,
)

REPO_ROOT = PARITY_DIR.parents[3]  # traio-platform repo root (where .git lives)


def _git(args: list[str]) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), *args], text=True
    ).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--force",
        action="store_true",
        help="allow capture even when the git tree is dirty",
    )
    args = ap.parse_args()

    dirty = _git(["status", "--porcelain"])
    if dirty and not args.force:
        sys.stderr.write(
            "Refusing to capture on a dirty git tree (the recorded source_sha "
            "would not match the working state).\n"
            "Commit/stash first, or re-run with --force:\n" + dirty + "\n"
        )
        return 2

    sha = _git(["rev-parse", "HEAD"])
    short = _git(["rev-parse", "--short", "HEAD"])
    cases = discover_cases(PARITY_DIR)
    print(f"Capturing {len(cases)} parity case(s) at {short}")

    with tempfile.TemporaryDirectory(prefix="arc011-parity-") as tmp:
        tmproot = Path(tmp)
        for case_id, case_path in cases:
            case = load_case(case_path)
            workspace = tmproot / case_id.replace("/", "_") / "ws"
            host_configs = tmproot / case_id.replace("/", "_") / "host_configs"
            workspace.mkdir(parents=True)
            host_configs.mkdir(parents=True)

            result = invoke(case, workspace, host_configs, tmproot / case_id.replace("/", "_"))
            mapping = {
                WORKSPACE_TOKEN: str(workspace),
                HOST_CONFIGS_TOKEN: str(host_configs),
            }
            case["expected"] = normalize(result, mapping)
            case["source_sha"] = sha
            case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
            print(f"  {case_id}")

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
