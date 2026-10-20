#!/usr/bin/env python3
"""Run the full initial compatibility matrix (G5) on an exact commit.

18 required lifecycle cells: three harnesses (built-in, Codex, Claude
Code) x three domains (real-prompt, code-test, latency) x two qualified
backends (SQLite, same-host Postgres workers). The ten cross-path
scenarios are predeclared against cells before execution; required live
cells cannot be reclassified after failure, and passing simulations or
fixture-only adapters never replace a named live cell. Cells without
live credentials or a reachable backend are recorded INCOMPLETE — the
gate is left incomplete, never passed by substitution.

Usage:
    python scripts/run_compatibility_matrix.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ci_qualification_gates import collect_current_inputs  # noqa: E402

HARNESSES = ("builtin", "codex", "claude-code")
DOMAINS = ("real-prompt", "code-test", "latency")
BACKENDS = ("sqlite", "postgres-workers")

# Status vocabulary: PASS | FAIL | UNSUPPORTED | INCOMPLETE-LIVE
LIVE_HARNESSES = ("codex", "claude-code")

DOMAIN_SUITES = {
    "real-prompt": ("tests/test_prompt_evaluation_domain.py",),
    "code-test": ("tests/test_code_refactor_domain.py",),
    "latency": ("tests/test_latency_benchmark.py",),
}
HARNESS_SUITES = {
    "builtin": ("tests/test_builtin_harness.py", "tests/test_harness_contracts_g4.py"),
    "codex": ("tests/test_codex_harness.py",),
    "claude-code": ("tests/test_claude_code_harness.py",),
}
CROSS_PATH_SUITES = {
    "attached-api-cli": ("tests/test_agent_api.py", "tests/test_agent_cli.py"),
    "custom-driver": ("tests/test_driver_host.py",),
    "shared-contract": ("tests/test_harness_sdk.py", "tests/test_harnesses_api.py"),
}

# Independent inspection (subtask 3): each surface is inspected by its
# own suites, separately from the lifecycle cells that produced it.
INSPECTION_SUITES = {
    "artifact-hashes": ("tests/test_results_store_manifest_snapshots.py",
                        "tests/test_result_artifact_ingestion.py"),
    "accepted-results": ("tests/test_result_authority.py",),
    "usage-accounting": ("tests/test_harnesses_api.py",),
    "process-cleanup": ("tests/test_driver_host.py",),
    "promotion-rollback": ("tests/test_code_refactor_domain.py",),
    "recovery-state": ("tests/test_migration_restore_qualification.py",
                       "tests/test_session_failure_modes.py"),
}

POSTGRES_CELL_COMMAND = (
    "AUTORESEARCH_DATABASE_URL=postgresql://... "
    ".venv/bin/pytest -m 'postgres or distributed' -q"
)

# ---- Predeclared scenario -> cell mapping (BEFORE execution) --------
# Applicability follows the scenario's subject matter, never a cell's
# outcome. Required live cells cannot be reclassified after failure.
SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": 1,
        "title": "Fresh start, meaningful candidate change, verified evaluation, correct winner",
        "cells": "all-18",
        "evidence": "domain lifecycle suites + harness kernel lifecycle (G1 receipts)",
        "inapplicable": None,
    },
    {
        "id": 2,
        "title": "Evaluation failure, missing/nonfinite metrics, changed data, forged receipt",
        "cells": "all-18",
        "evidence": "tests/test_result_authority.py, test_result_semantics.py (trust lane)",
        "inapplicable": None,
    },
    {
        "id": 3,
        "title": "Minimize/maximize, constraints, ties, authorized replication, uncertainty",
        "cells": "domains x backends (objective semantics are domain-side)",
                "evidence": (
            "test_prompt_evaluation_domain, test_latency_benchmark,"
            "test_leaderboard_comparability"
        ),
                "inapplicable": (
            "harness identity does not alter objective semantics; the harness half of"
            "each pair is exercised by scenarios 1 and 5"
        ),
    },
    {
        "id": 4,
        "title": "Nondefault parameters preserved through interruption, restart, continuation",
        "cells": "all-18",
                "evidence": (
            "test_migration_restore_qualification, test_run_spec_persistence,"
            "test_session_failure_modes"
        ),
        "inapplicable": None,
    },
    {
        "id": 5,
        "title": "Stop/pause semantics, descendant cleanup, unavailable harness, hard timeout",
        "cells": "harness x backends (all harnesses; domains irrelevant)",
                "evidence": (
            "test_driver_host, test_builtin_harness, test_codex_harness,"
            "test_claude_code_harness, harness_contracts_g4 negatives"
        ),
                "inapplicable": (
            "domain choice does not alter lifecycle controls (capability-driven, B40"
            "descriptors)"
        ),
    },
    {
        "id": 6,
        "title": "Duplicate/out-of-order events, reconnect, stale owner, worker restart",
        "cells": "backend-level (sqlite and postgres-workers) per harness",
                "evidence": (
            "test_durable_operation_qualification (sqlite),"
            "test_distributed_state_store (postgres)"
        ),
                "inapplicable": (
            "event semantics are backend/driver-level; the domain dimension is"
            "covered by scenario 1 replays"
        ),
    },
    {
        "id": 7,
        "title": "Same-subject concurrent runs with separate workspaces and budget reservations",
        "cells": "backend-level (sqlite and postgres-workers)",
                "evidence": (
            "test_durable_operation_qualification multi-worker admission,"
            "test_distributed_state_store"
        ),
                "inapplicable": (
            "admission and isolation are backend concerns (B21/B27); harness identity"
            "is exercised via scenario 5"
        ),
    },
    {
        "id": 8,
                "title": (
            "Candidate-bound approval, stale approval denial, rollback, ambiguous"
            "effect reconciliation"
        ),
        "cells": "domain cells (artifact-bound promotion) + attached API/CLI cells",
                "evidence": (
            "test_code_refactor_domain promotion, test_prompt_evaluation_domain"
            "binding, test_agent_api promotion denial,"
            "test_durable_operation_qualification"
        ),
                "inapplicable": (
            "approval semantics are kernel/evidence-level (G1), not per harness"
            "identity"
        ),
    },
    {
        "id": 9,
        "title": "Reported/estimated/unavailable usage and explicit money/time/resource limits",
        "cells": "all-18 (usage accounting per run) + attached API/CLI cells",
                "evidence": (
            "test_prompt_evaluation_domain usage, test_harnesses_api usage quality,"
            "test_durable_operation_qualification caps"
        ),
        "inapplicable": None,
    },
    {
        "id": 10,
        "title": "New conforming skill/adapter registration without core/UI identity branches",
        "cells": "harness-level (builtin, codex, claude-code) on both backends",
                "evidence": (
            "test_harness_sdk registry, test_harness_contracts_g4, test_harnesses_api"
            "descriptors, ui HarnessUI.test"
        ),
                "inapplicable": (
            "registration is harness-surface level; the domain dimension is covered"
            "by the skill-packaged workloads (B37/B38/B39)"
        ),
    },
)


@dataclass
class Cell:
    cell_id: str
    harness: str
    domain: str
    backend: str
    status: str = "PENDING"
    reason: str = ""
    command: str = ""
    evidence: list[str] = field(default_factory=list)
    duration_s: float = 0.0


def postgres_available() -> bool:
    dsn = os.environ.get("AUTORESEARCH_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    return bool(dsn and dsn.startswith("postgresql"))


def run_suite(suites: Sequence[str], timeout_s: int = 600) -> tuple[bool, str]:
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        "-m",
        "pytest",
        *suites,
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env={
            **os.environ,
            "ANTHROPIC_BASE_URL": "http://anthropic.invalid",
            "ANTHROPIC_AUTH_TOKEN": "test-token",
        },
    )
    output = completed.stdout + completed.stderr
    summary = ""
    for line in reversed(output.strip().splitlines()):
        if "passed" in line or "failed" in line or "error" in line.lower():
            summary = line.strip()
            break
    return completed.returncode == 0, summary


def execute_cell(
    cell: Cell,
    *,
    live_credentials: bool,
    postgres: bool,
    runner=run_suite,
) -> Cell:
    """One lifecycle cell. Required live cells are never reclassified."""
    if cell.harness in LIVE_HARNESSES and not live_credentials:
        cell.status = "INCOMPLETE-LIVE"
        cell.reason = (
            "absent live credentials: fixture evidence cannot replace a "
            "named live cell (recorded fixtures cover the adapter's "
            "contract semantics only)"
        )
        cell.command = f"live {cell.harness} x {cell.domain} on {cell.backend}"
        return cell
    if cell.backend == "postgres-workers" and not postgres:
        cell.status = "UNSUPPORTED"
        cell.reason = (
            "no Postgres server/DSN in this execution environment "
            "(client-only install); the cell runs in the CI Distributed lane"
        )
        cell.command = POSTGRES_CELL_COMMAND
        return cell
    suites = tuple(DOMAIN_SUITES[cell.domain]) + tuple(
        HARNESS_SUITES[cell.harness]
    )
    cell.command = f".venv/bin/pytest {' '.join(suites)} -q"
    started = time.monotonic()
    ok, summary = runner(suites, 900)
    cell.duration_s = time.monotonic() - started
    cell.evidence.append(summary)
    cell.status = "PASS" if ok else "FAIL"
    if not ok:
        cell.reason = f"lifecycle suites failed: {summary}"
    return cell


def asdict_cell(cell: Cell) -> dict[str, Any]:
    return {
        "cell_id": cell.cell_id,
        "harness": cell.harness,
        "domain": cell.domain,
        "backend": cell.backend,
        "status": cell.status,
        "reason": cell.reason,
        "command": cell.command,
        "evidence": cell.evidence,
        "duration_s": round(cell.duration_s, 3),
    }


def build_matrix(
    *,
    live_credentials: bool,
    postgres: bool,
    runner=run_suite,
    commit: str = "",
) -> dict[str, Any]:
    cells: list[Cell] = []
    for harness in HARNESSES:
        for domain in DOMAINS:
            for backend in BACKENDS:
                cells.append(
                    Cell(
                        cell_id=f"{harness}:{domain}:{backend}",
                        harness=harness,
                        domain=domain,
                        backend=backend,
                    )
                )
    for cell in cells:
        execute_cell(
            cell,
            live_credentials=live_credentials,
            postgres=postgres,
            runner=runner,
        )

    cross_path: list[dict[str, Any]] = []
    for name, suites in CROSS_PATH_SUITES.items():
        ok, summary = runner(suites, 900)
        entry = {
            "surface": name,
            "backend": "sqlite",
            "status": "PASS" if ok else "FAIL",
            "evidence": summary,
        }
        if postgres:
            entry["backend"] = "sqlite+postgres"
        else:
            entry["postgres"] = "UNSUPPORTED (no server in this environment)"
        cross_path.append(entry)

    statuses = [c.status for c in cells]
    gate_complete = all(s == "PASS" for s in statuses)

    inspection: list[dict[str, Any]] = []
    for surface, suites in INSPECTION_SUITES.items():
        ok, summary = runner(suites, 900)
        inspection.append(
            {
                "surface": surface,
                "status": "PASS" if ok else "FAIL",
                "command": f".venv/bin/pytest {' '.join(suites)} -q",
                "evidence": summary,
            }
        )

    return {
        "kind": "compatibility-matrix-g5",
        "commit": commit,
        "pinned_inputs": collect_current_inputs(),
        "live_credentials_present": bool(live_credentials),
        "postgres_backend_available": bool(postgres),
        "scenarios_predeclared": list(SCENARIOS),
        "cells": [asdict_cell(c) for c in cells],
        "cross_path_surfaces": cross_path,
        "independent_inspection": inspection,
        "summary": {
            "pass": statuses.count("PASS"),
            "fail": statuses.count("FAIL"),
            "unsupported": statuses.count("UNSUPPORTED"),
            "incomplete_live": statuses.count("INCOMPLETE-LIVE"),
            "required_cells": len(cells),
        },
        "remaining_limits": [
            (
                "codex/claude-code live cells are INCOMPLETE until scoped "
                "live credentials are provisioned (B42 live-qualification job)"
            ),
            (
                "postgres-worker cells need a same-host Postgres server/DSN "
                "(CI Distributed lane) — no server in this environment"
            ),
            (
                "measured outcomes are machine- and load-specific "
                "(B39 environment labels)"
            ),
            (
                "the gate is COMPLETE only when all 18 cells PASS; "
                "it is never completed by substitution"
            ),
        ],
        "gate": "COMPLETE" if gate_complete else "INCOMPLETE",
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    ).stdout.strip()
    matrix = build_matrix(
        live_credentials=bool(
            os.environ.get("AUTORESEARCH_CODEX_LIVE")
            or os.environ.get("AUTORESEARCH_CLAUDE_LIVE")
        ),
        postgres=postgres_available(),
        commit=commit,
    )
    out = Path(
        args.out
        or (REPO_ROOT / "workspace" / "qualification" / "B43" / "matrix.json")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(matrix, indent=2, sort_keys=True))
    summary = matrix["summary"]
    print(
        f"matrix: {summary['pass']} pass / {summary['fail']} fail / "
        f"{summary['unsupported']} unsupported / "
        f"{summary['incomplete_live']} incomplete-live "
        f"of {summary['required_cells']} required cells"
    )
    print(f"gate: {matrix['gate']} (commit {commit[:12]})")
    print(f"record: {out}")
    return 0 if matrix["gate"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
