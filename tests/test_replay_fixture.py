"""AR-9: Smoke tests for the replay_iterations fixture infrastructure.

Verifies that:
- The JSON fixture file is well-formed and parseable.
- The replay_iterations factory creates a seeded ResultsStore.
- The seeded iterations have the correct shapes for each defect scenario.
- The fixture correctly exposes the four key broken-session iterations
  (90, 95, 101, 102) that are the focus of the AR-9/AR-10 work.
- Phase-completion iterations (85-90) cause build_phase_state to correctly
  place the current_phase at multi_seed_robustness (not an earlier phase).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.core.research_phase_plan import build_phase_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_by_number(iterations: list, n: int) -> Dict[str, Any]:
    """Return the iteration row whose ``iteration`` column == n."""
    for row in iterations:
        if row["iteration"] == n:
            return row
    raise KeyError(f"No iteration {n} in seeded store")


def _metrics_of(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("metrics_json") or "{}"
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


# ---------------------------------------------------------------------------
# 1. JSON fixture file structure
# ---------------------------------------------------------------------------


def test_fixture_file_exists() -> None:
    """The JSON fixture file must exist under tests/fixtures/."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "res_a1ba6cbd520f_minimal.json"
    )
    assert fixture_path.is_file(), (
        f"Fixture file not found at {fixture_path}"
    )


def test_fixture_json_is_valid() -> None:
    """The JSON file must parse without error."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "res_a1ba6cbd520f_minimal.json"
    )
    data = json.loads(fixture_path.read_text())
    assert "session" in data
    assert "iterations" in data
    assert isinstance(data["iterations"], list)
    assert len(data["iterations"]) > 0


def test_fixture_contains_required_session_fields() -> None:
    """Session config must have all fields required by create_session."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "res_a1ba6cbd520f_minimal.json"
    )
    session = json.loads(fixture_path.read_text())["session"]
    for field in ("id", "instrument", "timeframe", "model_type", "tag",
                  "max_iterations", "max_budget_usd"):
        assert field in session, f"Required field '{field}' missing from session config"


def test_fixture_contains_key_broken_iterations() -> None:
    """The four defect-focused iterations (90, 95, 101, 102) must be present."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "res_a1ba6cbd520f_minimal.json"
    )
    iterations = json.loads(fixture_path.read_text())["iterations"]
    nums = {it["iteration"] for it in iterations}
    for required in (90, 95, 101, 102):
        assert required in nums, (
            f"Iteration {required} must be in the minimal fixture"
        )


def test_fixture_iter102_exposes_config_snapshot_as_dict() -> None:
    """Iter 102 must have config_snapshot_as_dict for AR-10 D1 crash tests."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "res_a1ba6cbd520f_minimal.json"
    )
    iterations = json.loads(fixture_path.read_text())["iterations"]
    iter_102 = next(it for it in iterations if it["iteration"] == 102)
    assert "config_snapshot_as_dict" in iter_102, (
        "iter 102 must carry config_snapshot_as_dict for the D1 crash scenario"
    )
    assert isinstance(iter_102["config_snapshot_as_dict"], dict)


# ---------------------------------------------------------------------------
# 2. replay_iterations factory — DB seeding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replay_iterations_seeds_session(replay_iterations) -> None:
    """Factory creates a session with the correct ID and instrument."""
    ctx = await replay_iterations()
    assert ctx.session_id == "res_a1ba6cbd520f_minimal"
    assert ctx.session["instrument"] == "DOGE_USDT"
    assert ctx.session["model_type"] == "direction"


@pytest.mark.asyncio
async def test_replay_iterations_seeds_all_iterations(replay_iterations) -> None:
    """All iterations in the JSON file are written to the DB."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "res_a1ba6cbd520f_minimal.json"
    )
    expected_count = len(json.loads(fixture_path.read_text())["iterations"])
    ctx = await replay_iterations()
    assert len(ctx.iterations) == expected_count, (
        f"Expected {expected_count} iterations in DB, got {len(ctx.iterations)}"
    )


@pytest.mark.asyncio
async def test_replay_iterations_exposes_raw_fixture(replay_iterations) -> None:
    """ReplayContext.raw must contain the full parsed JSON fixture."""
    ctx = await replay_iterations()
    assert "session" in ctx.raw
    assert "iterations" in ctx.raw
    # config_snapshot_as_dict must be accessible via raw
    raw_102 = next(
        it for it in ctx.raw["iterations"] if it["iteration"] == 102
    )
    assert isinstance(raw_102["config_snapshot_as_dict"], dict)


@pytest.mark.asyncio
async def test_replay_iterations_stores_metrics_json(replay_iterations) -> None:
    """Iteration metrics are stored as JSON-serialized strings in the DB."""
    ctx = await replay_iterations()
    iter_90 = _iter_by_number(ctx.iterations, 90)
    metrics = _metrics_of(iter_90)
    assert metrics.get("primary_metric") == pytest.approx(0.6394)
    assert metrics.get("mlflow_run_id") == "run-tabular-90-de4f"
    assert metrics.get("tabular_sweep_variant") == "v4"


@pytest.mark.asyncio
async def test_replay_iterations_iter95_has_synthetic_seed_trials(
    replay_iterations,
) -> None:
    """Iter 95 (D3 defect): seed_trials all share the same mlflow_run_id."""
    ctx = await replay_iterations()
    iter_95 = _iter_by_number(ctx.iterations, 95)
    metrics = _metrics_of(iter_95)
    trials = metrics.get("seed_trials", [])
    assert len(trials) == 5
    run_ids = {t.get("mlflow_run_id") for t in trials}
    assert len(run_ids) == 1, (
        "iter 95 must have duplicate run_ids in seed_trials (D3 synthetic emission)"
    )


@pytest.mark.asyncio
async def test_replay_iterations_iter101_has_no_config_snapshot(
    replay_iterations,
) -> None:
    """Iter 101 (D4 defect): config_snapshot is null in the DB."""
    ctx = await replay_iterations()
    iter_101 = _iter_by_number(ctx.iterations, 101)
    assert iter_101.get("config_snapshot") is None, (
        "iter 101 must have config_snapshot=null (D4 defect scenario)"
    )
    assert iter_101.get("search_phase") == "promotion_proposal"


@pytest.mark.asyncio
async def test_replay_iterations_iter90_has_real_training_data(
    replay_iterations,
) -> None:
    """Iter 90: the real training iteration — config_snapshot + mlflow_run_id + training_time_s present."""
    ctx = await replay_iterations()
    iter_90 = _iter_by_number(ctx.iterations, 90)
    assert iter_90["config_snapshot"] is not None, (
        "iter 90 must have a config_snapshot (it ran real training)"
    )
    assert iter_90["mlflow_run_id"] == "run-tabular-90-de4f"
    assert iter_90["training_time_s"] == pytest.approx(185.3)
    assert iter_90["primary_metric"] == pytest.approx(0.6394)


# ---------------------------------------------------------------------------
# 3. Phase-plan correctness with the fixture data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replay_fixture_phase_plan_reaches_multi_seed_robustness(
    replay_iterations,
) -> None:
    """Phase plan computed from fixture iterations must reach multi_seed_robustness.

    Iterations 85-90 provide evidence keys that complete all prior phases
    (baseline_capture, tabular_sweeps, adaptive_feature_sweeps, tsfm_sweeps,
    calibration_replay_gates).  The synthetic multi_seed_robustness iterations
    (95/97) must NOT advance that phase (duplicate run_ids), so
    current_phase should be multi_seed_robustness.
    """
    ctx = await replay_iterations()

    state = build_phase_state(
        session={"id": ctx.session_id, "model_type": "direction"},
        iterations=ctx.iterations,
    )

    phase_statuses = {p["id"]: p["status"] for p in state["phases"]}

    # All prior phases must be completed by the evidence-key iters 85-90.
    for completed_phase in (
        "baseline_capture",
        "tabular_sweeps",
        "adaptive_feature_sweeps",
        "tsfm_sweeps",
        "calibration_replay_gates",
    ):
        assert phase_statuses[completed_phase] == "completed", (
            f"Phase '{completed_phase}' should be completed by fixture prior iters"
        )

    # Synthetic multi_seed_robustness must NOT be completed (duplicate run_ids).
    assert phase_statuses["multi_seed_robustness"] != "completed", (
        "multi_seed_robustness must stay in_progress/pending — synthetic iters "
        "with duplicate run_ids must not advance the phase"
    )


@pytest.mark.asyncio
async def test_replay_fixture_best_metric_is_iter90(replay_iterations) -> None:
    """Session best_metric must be set to iter-90's metric (0.6394) by the DB."""
    ctx = await replay_iterations()
    # best_metric is set by add_iteration for keep decisions
    assert ctx.session["best_metric"] == pytest.approx(0.6394), (
        "Session best_metric must be 0.6394 (iter-90 keep decision)"
    )
    assert ctx.session["best_iteration"] == 90


# ---------------------------------------------------------------------------
# 4. Non-default fixture names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replay_iterations_accepts_custom_fixture_name(
    replay_iterations, tmp_path: Path
) -> None:
    """Fixture factory must raise FileNotFoundError for a nonexistent fixture name."""
    with pytest.raises(FileNotFoundError):
        await replay_iterations("fixture_that_does_not_exist")
