"""G5 compatibility matrix: structure and honesty guards.

The ten scenarios are predeclared against the 18 lifecycle cells; live
cells without credentials stay INCOMPLETE (fixtures never substitute);
unsupported backends never pass; failed live cells are never
reclassified; the gate is COMPLETE only when all 18 cells pass.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location(
    "run_compatibility_matrix",
    REPO_ROOT / "scripts" / "run_compatibility_matrix.py",
)
rcm = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules["run_compatibility_matrix"] = rcm
_SPEC.loader.exec_module(rcm)


def _fake_runner(ok=True, summary="10 passed in 1.0s"):
    calls = []

    def runner(suites, timeout_s):
        calls.append(tuple(suites))
        return ok, summary if ok else "3 failed in 1.0s"

    runner.calls = calls
    return runner


def test_predeclared_scenarios_are_complete():
    assert len(rcm.SCENARIOS) == 10
    for scenario in rcm.SCENARIOS:
        assert scenario["cells"], f"scenario {scenario['id']} lacks cells"
        assert scenario["evidence"], f"scenario {scenario['id']} lacks evidence"
        # a scoped mapping must justify its inapplicable pairs
        if not scenario["cells"].startswith("all-18"):
            assert scenario["inapplicable"], (
                f"scenario {scenario['id']} narrows cells without justification"
            )


def test_matrix_has_all_18_cells_with_unique_ids():
    matrix = rcm.build_matrix(
        live_credentials=False, postgres=False, runner=_fake_runner()
    )
    assert matrix["summary"]["required_cells"] == 18
    ids = [c["cell_id"] for c in matrix["cells"]]
    assert len(set(ids)) == 18
    assert len(rcm.HARNESSES) * len(rcm.DOMAINS) * len(rcm.BACKENDS) == 18


def test_fixtures_never_replace_a_named_live_cell():
    # a perfectly green fixture runner must not pass live cells
    matrix = rcm.build_matrix(
        live_credentials=False, postgres=False, runner=_fake_runner(ok=True)
    )
    for cell in matrix["cells"]:
        if cell["harness"] in rcm.LIVE_HARNESSES:
            assert cell["status"] == "INCOMPLETE-LIVE", cell
            assert "fixture" in cell["reason"]
    assert matrix["live_credentials_present"] is False
    assert matrix["gate"] == "INCOMPLETE"


def test_failed_live_cell_is_never_reclassified():
    matrix = rcm.build_matrix(
        live_credentials=True, postgres=False, runner=_fake_runner(ok=False)
    )
    for cell in matrix["cells"]:
        if cell["harness"] in rcm.LIVE_HARNESSES and cell["backend"] == "sqlite":
            # opted-in live cells ran and FAILED — still FAIL, not skipped
            assert cell["status"] == "FAIL", cell


def test_unsupported_backend_never_passes():
    matrix = rcm.build_matrix(
        live_credentials=True, postgres=False, runner=_fake_runner(ok=True)
    )
    for cell in matrix["cells"]:
        if cell["backend"] == "postgres-workers" and cell["harness"] not in (
            rcm.LIVE_HARNESSES
        ):
            assert cell["status"] == "UNSUPPORTED", cell
            assert "no Postgres" in cell["reason"]
    # with a backend present, the same cells execute and report honestly
    matrix = rcm.build_matrix(
        live_credentials=True, postgres=True, runner=_fake_runner(ok=True)
    )
    executed = [c for c in matrix["cells"] if c["backend"] == "postgres-workers"]
    assert all(c["status"] == "PASS" for c in executed)
    assert matrix["gate"] == "COMPLETE"


def test_gate_complete_requires_all_18_pass():
    matrix = rcm.build_matrix(
        live_credentials=True, postgres=True, runner=_fake_runner(ok=True)
    )
    assert matrix["summary"]["pass"] == 18
    assert matrix["gate"] == "COMPLETE"
    # a single failure leaves the gate incomplete with counts recorded
    matrix = rcm.build_matrix(
        live_credentials=True, postgres=True, runner=_fake_runner(ok=False)
    )
    assert matrix["summary"]["fail"] == 18
    assert matrix["gate"] == "INCOMPLETE"


def test_independent_inspection_covers_each_surface():
    matrix = rcm.build_matrix(
        live_credentials=False, postgres=False, runner=_fake_runner()
    )
    surfaces = {i["surface"] for i in matrix["independent_inspection"]}
    assert surfaces == {
        "artifact-hashes",
        "accepted-results",
        "usage-accounting",
        "process-cleanup",
        "promotion-rollback",
        "recovery-state",
    }
    for entry in matrix["independent_inspection"]:
        assert entry["command"].startswith(".venv/bin/pytest")
        assert entry["status"] in ("PASS", "FAIL")


def test_cross_path_surfaces_recorded_with_postgres_status():
    matrix = rcm.build_matrix(
        live_credentials=False, postgres=False, runner=_fake_runner()
    )
    names = {c["surface"] for c in matrix["cross_path_surfaces"]}
    assert names == {"attached-api-cli", "custom-driver", "shared-contract"}
    for entry in matrix["cross_path_surfaces"]:
        assert "UNSUPPORTED" in entry.get("postgres", "")