"""AR-10: End-to-end replay tests for the res_a1ba6cbd520f failure mode.

Locks in the combined defensive behaviour of AR-1 + AR-3 + AR-5 + AR-6 + AR-7
against the realistic iteration shapes from the broken session.  Every test
uses the ``replay_iterations`` fixture (AR-9) as its data source rather than
hand-building rows.

Four scenarios:

1. D1 crash guard (AR-1): config_snapshot arrives as a dict — _record_iteration
   must not raise and must store it as a JSON string in the DB.

2. D4 inheritance + consistency (AR-3): promotion_proposal iteration without
   config_snapshot auto-inherits from iter-90; consistency report must drop the
   missing_config_snapshot blocker.

3. D3 phase-plan integrity (AR-5/AR-6): synthetic multi_seed_robustness and
   inference_parity_replay iterations (iters 95/97/99) must not advance their
   respective phases past the current position.

4. D7 stagnation nudge (AR-7): after 13 iterations at the same metric, the
   stagnation check must return a GLOBAL_STAGNATION nudge (not None).
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

# ---------------------------------------------------------------------------
# Stub Anthropic SDK (same pattern as other orchestrator tests)
# ---------------------------------------------------------------------------
try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = _stub

from src.core.orchestrator import AgentOrchestrator
from src.core.research_phase_plan import build_phase_state
from src.core.results_store import ResultsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metrics_of(row: Dict[str, Any]) -> Dict[str, Any]:
    """Deserialise the metrics_json column of an iteration row."""
    raw = row.get("metrics_json") or "{}"
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


def _iter_by_number(iterations: list, n: int) -> Dict[str, Any]:
    for row in iterations:
        if row["iteration"] == n:
            return row
    raise KeyError(f"No iteration {n}")


# ---------------------------------------------------------------------------
# Scenario 1 — D1 crash guard (AR-1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dict_config_snapshot_does_not_crash_session(
    replay_iterations,
) -> None:
    """AR-1 / D1: config_snapshot as a dict must be stored as a JSON string.

    The original crash in res_a1ba6cbd520f happened because
    ``canonical_config_payload`` received a dict and tried to call ``.read()``
    on it (treating it as a file-like object).  AR-1 coerces the dict to a JSON
    string in ``_record_iteration`` before any downstream consumer sees it.

    This test calls ``_record_iteration`` directly with the iter-102 marker
    shape from the fixture, which has ``config_snapshot`` as a dict in
    ``metrics`` and ``config_snapshot_as_dict`` at the top level.  The call
    must:
    - Complete without raising any exception.
    - Store ``config_snapshot`` in the DB as a JSON string (not null, not a
      dict).
    - The stored string must round-trip to the original dict value.
    """
    ctx = await replay_iterations()

    # Build the iter-102 marker from the raw fixture.
    raw_102 = next(
        it for it in ctx.raw["iterations"] if it["iteration"] == 102
    )
    # Use the dict directly (the D1 crash shape).
    dict_snapshot = raw_102["config_snapshot_as_dict"]
    marker: Dict[str, Any] = {
        "primary_metric": raw_102["primary_metric"],
        "metric_name": raw_102["metric_name"],
        "all_gates_passed": raw_102["all_gates_passed"],
        "decision": raw_102["decision"],
        "training_time_s": raw_102["training_time_s"],
        "search_phase": raw_102["search_phase"],
        "config_snapshot": dict_snapshot,   # <-- dict, not string (D1 shape)
        "description": raw_102["description"],
    }

    orch = AgentOrchestrator(ctx.store)

    # Use iter 103 (fixture seeds up to 102; using 102 would cause a PK collision).
    # AR-1 fix: must NOT raise (the original session crashed with AttributeError)
    await orch._record_iteration(
        ctx.session_id,
        103,
        marker,
        cumulative_cost=0.12,
    )

    row = await ctx.store.get_iteration(ctx.session_id, 103)
    assert row is not None, "_record_iteration must persist the iteration row (iter 103)"

    stored_snapshot = row.get("config_snapshot")
    assert stored_snapshot is not None, (
        "config_snapshot must not be null after AR-1 dict coercion"
    )
    assert isinstance(stored_snapshot, str), (
        "config_snapshot column must be a string after dict coercion"
    )

    # Round-trip: the stored JSON string must decode to the original dict.
    try:
        decoded = json.loads(stored_snapshot)
    except json.JSONDecodeError:
        decoded = None
    assert decoded == dict_snapshot, (
        "Stored config_snapshot must decode to the original dict value"
    )


# ---------------------------------------------------------------------------
# Scenario 2 — D4 inheritance + consistency (AR-3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promotion_family_inherits_snapshot_and_consistency_passes(
    replay_iterations,
) -> None:
    """AR-3 / D4: promotion_proposal iteration without config_snapshot auto-inherits.

    The fixture contains iter-90 with a real config_snapshot and iter-101
    (promotion_proposal, config_snapshot=null).  After calling _record_iteration
    for iter-101, the DB must show:
    - ``config_snapshot`` populated with the iter-90 snapshot.
    - ``config_snapshot_inherited_from_iteration == 90`` in metrics_json.
    - ``consistency_report_json`` must NOT contain ``missing_config_snapshot``
      in its blockers list.

    This reproduces the exact fix for the res_a1ba6cbd520f D4 defect where
    seven promotion-family iterations repeatedly failed with
    missing_config_snapshot because no inheritance was happening.
    """
    ctx = await replay_iterations()

    # Confirm iter-90 has a config_snapshot (the source for inheritance).
    iter_90_row = _iter_by_number(ctx.iterations, 90)
    snap_90 = iter_90_row["config_snapshot"]
    assert snap_90 is not None, "Fixture pre-condition: iter-90 must have config_snapshot"

    # Build the iter-101 marker from the raw fixture.
    # Use iter 103 as the insertion point (fixture seeds up to 102; 101 is
    # already seeded as a promotion_proposal with config_snapshot=null, which
    # is exactly the D4 defect shape, but we can't call _record_iteration on it
    # again without a PK collision).
    raw_101 = next(it for it in ctx.raw["iterations"] if it["iteration"] == 101)
    marker_103: Dict[str, Any] = {
        "primary_metric": raw_101["primary_metric"],
        "metric_name": raw_101["metric_name"],
        "all_gates_passed": raw_101["all_gates_passed"],
        "decision": raw_101["decision"],
        "training_time_s": raw_101["training_time_s"],
        "search_phase": raw_101["search_phase"],   # "promotion_proposal"
        "description": raw_101["description"],
        # Deliberately no "config_snapshot" key — the D4 defect shape.
    }
    assert "config_snapshot" not in marker_103, (
        "Fixture pre-condition: promotion_proposal marker must NOT carry config_snapshot"
    )

    orch = AgentOrchestrator(ctx.store)
    await orch._record_iteration(
        ctx.session_id,
        103,
        marker_103,
        cumulative_cost=0.11,
    )

    row_103 = await ctx.store.get_iteration(ctx.session_id, 103)
    assert row_103 is not None

    # AR-3: inherited config_snapshot must be present.
    inherited_snapshot = row_103.get("config_snapshot")
    assert inherited_snapshot is not None, (
        "AR-3 fix must populate config_snapshot from iter-90 for promotion_proposal"
    )
    assert inherited_snapshot == snap_90, (
        "Inherited config_snapshot must match iter-90's snapshot"
    )

    # AR-3: audit trail must record the source iteration.
    metrics_103 = _metrics_of(row_103)
    assert metrics_103.get("config_snapshot_inherited_from_iteration") == 90, (
        "metrics_json must record config_snapshot_inherited_from_iteration=90"
    )

    # AR-3: consistency report must lose the missing_config_snapshot blocker.
    consistency_raw = row_103.get("consistency_report_json")
    assert consistency_raw is not None, "consistency_report_json must be stored"
    report = json.loads(consistency_raw)
    assert "missing_config_snapshot" not in report.get("blockers", []), (
        "After inheritance, missing_config_snapshot must not appear in blockers. "
        f"Full blockers: {report.get('blockers', [])}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — D3 phase-plan integrity (AR-5 / AR-6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthetic_phase_emission_does_not_advance_phase_plan(
    replay_iterations,
) -> None:
    """AR-5/AR-6 / D3: synthetic promotion-family iterations must not advance phases.

    Fixture iterations 95 and 97 are synthetic multi_seed_robustness attempts
    (duplicate seed_trial run_ids, no training_time_s, metric unchanged from
    iter-90 prior best).  Iteration 99 is a synthetic inference_parity_replay
    that reuses the iter-90 mlflow_run_id.

    With the AR-5 artifact-bound evidence-key validation and AR-6 stagnation
    guard both active:
    - ``multi_seed_robustness`` must stay non-completed.
    - ``inference_parity_replay`` must stay non-completed.

    The original defect was that both phases advanced to 'completed' based on
    the presence of evidence keys alone, allowing the session to march through
    to promotion_proposal without any genuine training artefacts.
    """
    ctx = await replay_iterations()

    # Build phase state from the seeded iterations (iters 85–102 from fixture).
    state = build_phase_state(
        session={"id": ctx.session_id, "model_type": "direction"},
        iterations=ctx.iterations,
    )
    phase_statuses = {p["id"]: p["status"] for p in state["phases"]}

    # --- AR-5 / AR-6: synthetic multi_seed_robustness (iters 95/97) blocked ---
    assert phase_statuses["multi_seed_robustness"] != "completed", (
        "multi_seed_robustness must NOT be completed when only synthetic "
        "iterations (duplicate run_ids, no training) are present.\n"
        f"All phase statuses: {phase_statuses}"
    )

    # --- AR-5: synthetic inference_parity_replay (iter 99) blocked ---
    # iter-99 reuses run-tabular-90-de4f, which also appears in the tabular
    # sweep iterations. The artifact check must block this as a prior run_id.
    assert phase_statuses["inference_parity_replay"] != "completed", (
        "inference_parity_replay must NOT be completed when the parity "
        "iteration reuses a prior training run_id.\n"
        f"All phase statuses: {phase_statuses}"
    )

    # --- Prior phases (85-90) must be completed normally ---
    for phase_id in (
        "baseline_capture",
        "tabular_sweeps",
        "adaptive_feature_sweeps",
        "tsfm_sweeps",
        "calibration_replay_gates",
    ):
        assert phase_statuses[phase_id] == "completed", (
            f"Phase '{phase_id}' must be completed by real evidence-key "
            f"iterations 85-90. Got: {phase_statuses[phase_id]}"
        )

    # --- Verify the fixture D3 data integrity ---
    # Iter-95 seed_trials: all 5 entries share run-SAME-seed (synthetic).
    iter_95_row = _iter_by_number(ctx.iterations, 95)
    m95 = _metrics_of(iter_95_row)
    trials_95 = m95.get("seed_trials", [])
    run_ids_95 = {t.get("mlflow_run_id") for t in trials_95}
    assert len(run_ids_95) == 1 and "run-SAME-seed" in run_ids_95, (
        "Fixture pre-condition: iter-95 must have 5 seed_trials with identical run_ids"
    )

    # Iter-99 inference_parity: reuses iter-90 run_id.
    iter_99_row = _iter_by_number(ctx.iterations, 99)
    m99 = _metrics_of(iter_99_row)
    parity_run = (m99.get("inference_parity") or {}).get("mlflow_run_id")
    assert parity_run == "run-tabular-90-de4f", (
        "Fixture pre-condition: iter-99 must reuse the iter-90 tabular run_id"
    )


# ---------------------------------------------------------------------------
# Scenario 4 — D7 stagnation nudge (AR-7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stagnation_forces_terminate_after_window(
    replay_iterations,
) -> None:
    """AR-7 / D7: after window stagnant iterations the nudge fires.

    The fixture seeds iter-90 as the best iteration at metric 0.6394.
    Iterations 91-102 (12 iterations) are all at the same metric with no
    improvement (confirmed by fixture: all have primary_metric=0.6394).

    With default global_stagnation_window=12, calling
    _maybe_global_stagnation_terminate at iteration_count=103 produces a gap
    of 103-90=13 >= 12 and must return a non-None GLOBAL_STAGNATION message.

    This reproduces the D7 scenario where the broken session ran to iter ~102
    with no improvement and received no stagnation signal, eventually crashing
    instead of gracefully self-terminating.
    """
    ctx = await replay_iterations()

    # Fixture pre-condition: best_iteration=90, best_metric≈0.6394
    assert ctx.session["best_iteration"] == 90, (
        "Fixture pre-condition: best_iteration must be 90 after seeding"
    )
    assert abs(ctx.session["best_metric"] - 0.6394) < 1e-6, (
        "Fixture pre-condition: best_metric must be 0.6394"
    )

    orch = AgentOrchestrator(ctx.store)

    # gap = 103 - 90 = 13 >= default window 12 → stagnation fires
    result = await orch._maybe_global_stagnation_terminate(
        research_id=ctx.session_id,
        iteration_count=103,
    )

    assert result is not None, (
        "Gap of 13 iterations (103-90) at default window=12 must trigger "
        "the stagnation nudge"
    )
    assert "GLOBAL_STAGNATION" in result, (
        "Nudge message must contain 'GLOBAL_STAGNATION'"
    )
    assert "TERMINATE_REQUEST" in result, (
        "Nudge message must instruct the LLM to emit TERMINATE_REQUEST"
    )
    assert "0.6394" in result, (
        "Nudge message must reference the best metric value for context"
    )
    assert "90" in result, (
        "Nudge message must reference the best iteration number"
    )

    # Sanity: gap of 11 (102-91=11 < 12) must NOT fire.
    # Manually update best_iteration to 91 to simulate a "window-1" scenario.
    await ctx.store.update_session(
        ctx.session_id,
        best_iteration=91,
        best_metric=0.6394,
    )
    result_no_fire = await orch._maybe_global_stagnation_terminate(
        research_id=ctx.session_id,
        iteration_count=102,  # gap = 102 - 91 = 11 < 12
    )
    assert result_no_fire is None, (
        "Gap of 11 is below the window=12 threshold — must NOT fire"
    )

