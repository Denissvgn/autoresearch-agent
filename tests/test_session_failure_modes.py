"""AR-10: End-to-end replay tests for the res_a1ba6cbd520f failure mode,
plus the ARC-012 Wave-2 session failure-semantics suite (P7-009/P7-010;
see the Wave-2 section at the bottom of this file).

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

import asyncio
import json
import sys
import time
import types
from pathlib import Path
from typing import Any, Dict

import httpx
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

from src.config import settings
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.research_phase_plan import build_phase_state
from src.core.results_store import ResultsStore
from src.core.skill_runtime import SkillConfigError
from src.core.state_machine import SessionEvent, SessionStateMachine

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

    # --- Prior phases (85-88, 90) must be completed normally ---
    # Gap 2: calibration_replay_gates is intentionally NOT in this list —
    # the fixture has a single in-phase calibration iter (iter 89) and the
    # floor was raised from 1 to 2, so the phase legitimately stays
    # in_progress. The other prior phases still complete via their
    # evidence keys.
    for phase_id in (
        "baseline_capture",
        "tabular_sweeps",
        "adaptive_feature_sweeps",
        "tsfm_sweeps",
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

    # The assistant's next compliant TERMINATE_REQUEST should end as a normal
    # completion whose terminal_reason points at the incomplete phase.
    phase_state = build_phase_state(
        session={"id": ctx.session_id, "model_type": "direction"},
        iterations=ctx.iterations,
    )
    await ctx.store.update_session(
        ctx.session_id,
        phase_state_json=json.dumps(phase_state),
    )
    terminal_reason = await orch._derive_terminal_reason(
        research_id=ctx.session_id,
        final_status="completed",
        iteration_count=103,
        total_cost=0.12,
        config=ResearchConfig(
            id=ctx.session_id,
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
            max_iterations=110,
            max_budget_usd=50.0,
        ),
        timed_out=False,
        policy_aborted=False,
    )
    # Gap 2: calibration_replay_gates floor was raised from 1 to 2, so the
    # fixture's single in-phase calibration iter (iter 89) no longer
    # completes the phase. With calibration_replay_gates now in_progress,
    # it becomes the agent's current_phase, and the terminal_reason
    # surfaces THAT phase instead of multi_seed_robustness. The test's
    # intent (stagnation termination identifies the in-progress phase)
    # is preserved; only the specific phase name changed.
    assert terminal_reason == (
        "agent_self_terminated_during_phase:calibration_replay_gates"
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


# ===========================================================================
# ARC-012 Wave 2 — failure semantics (P7-009 / P7-010 / P7-013)
#
# B2/S1 regressions: a background task that crashes must leave a terminal
# ``failed`` row (error_message + terminal_reason, never a zombie
# ``running``), and a start whose skill runtime cannot materialize must fail
# fast — 4xx at the API, ``SkillConfigError`` at the manager, no row, no
# spawned task — instead of 201-then-crash.
# ===========================================================================

import src.core.session_manager as session_manager_module  # noqa: E402
from src.api import research as research_module  # noqa: E402
from src.api.research import router as research_router  # noqa: E402
from src.ws.events import broadcaster  # noqa: E402

_API_TOKEN = "wave2-test-token"

_BUNDLED_SKILLS = {"prompt-engineering", "code-refactor", "db-config-tuning"}


class _ScriptedOrchestrator:
    """Fake orchestrator with a scripted ``run()`` outcome.

    Modes:
    * ``"crash"`` — raise before any iteration (the B2 shape: the raise
      happens before the orchestrator's own exception handler, exactly like
      ``materialize_skill_runtime`` in ``run()``).
    * ``"complete_then_crash"`` — transition COMPLETE via the state machine,
      then raise (the orchestrator already set a terminal status; the crash
      finalizer must NOT overwrite it).
    * ``"pause_then_crash"`` — transition PAUSED, then raise (a paused
      session whose task dies must still reach ``failed``).
    * ``"ok"`` — capture the config and return normally.
    """

    def __init__(self, store: Any, mode: str) -> None:
        self._store = store
        self._mode = mode
        self.captured_config: ResearchConfig | None = None

    async def run(self, config: ResearchConfig) -> None:
        self.captured_config = config
        if self._mode == "ok":
            return
        sm = SessionStateMachine(self._store, broadcaster)
        if self._mode == "complete_then_crash":
            await sm.transition(config.id, SessionEvent.COMPLETE)
            raise RuntimeError("crash after completion")
        if self._mode == "pause_then_crash":
            await sm.transition(config.id, SessionEvent.PAUSE)
            raise RuntimeError("crash while paused")
        raise SkillConfigError("session has no skill_id — scripted B2 crash")

    def request_stop(self, research_id: str) -> None:
        pass

    def request_pause(self, research_id: str) -> None:
        pass

    def request_resume(self, research_id: str) -> None:
        pass


async def _healthy_preflight(*, targets=None) -> Dict[str, Any]:
    return {
        "schema_version": "autoresearch_service_preflight.v1",
        "status": "ready",
        "required_ready": True,
        "override_allowed_unready": False,
        "services": {},
        "required_failures": [],
    }


async def _make_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str,
) -> tuple[ResultsStore, Any, _ScriptedOrchestrator]:
    """Real SessionManager over a real SQLite store; only the orchestrator
    and the preflight probe are scripted (same pattern as
    ``test_canonical_start_wiring``)."""
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspace"))
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "host_configs"))
    # ARC-012 P7-011: the skill bootstrap now runs at start; demo mode lets it
    # render its default eval set (these tests script the orchestrator, so
    # demo mode only affects the bootstrap input here).
    monkeypatch.setattr(settings, "demo_mode", True)
    fake = _ScriptedOrchestrator(None, mode)
    monkeypatch.setattr(
        session_manager_module,
        "AgentOrchestrator",
        lambda store, state_machine=None: fake,
    )
    monkeypatch.setattr(
        session_manager_module, "run_service_preflight", _healthy_preflight,
    )
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    fake._store = store
    manager = session_manager_module.SessionManager(store)
    return store, manager, fake


async def _start_skill_session(manager: Any, **overrides: Any) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = dict(
        instrument="default",
        timeframe="production",
        model_type="",
        skill_id="prompt-engineering",
        subject_id="default",
        variant="production",
        max_iterations=1,
    )
    kwargs.update(overrides)
    return await manager.start_session(**kwargs)


async def _await_terminal(
    store: ResultsStore, session_id: str, timeout_s: float = 2.0,
) -> Dict[str, Any] | None:
    """Poll until the row leaves running/paused (P7-009 AC: 'within seconds')."""
    deadline = time.monotonic() + timeout_s
    row = await store.get_session(session_id)
    while row is not None and time.monotonic() < deadline:
        if row.get("status") not in ("running", "paused", "pending"):
            return row
        await asyncio.sleep(0.01)
        row = await store.get_session(session_id)
    return row


# ---------------------------------------------------------------------------
# P7-009 — crashed background task reaches a terminal state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crashed_background_task_persists_failed_state(
    monkeypatch, tmp_path,
):
    """P7-009 AC: a session whose runtime raises before iterations shows
    ``failed`` + non-null ``error_message`` (the exact B2 zombie shape)."""
    store, manager, _ = await _make_manager(monkeypatch, tmp_path, "crash")
    try:
        session = await _start_skill_session(manager)
        row = await _await_terminal(store, session["id"])
        assert row is not None
        assert row["status"] == "failed", (
            f"crashed task left status={row['status']!r} (zombie)"
        )
        assert row["error_message"], "error_message must be persisted"
        assert "scripted B2 crash" in row["error_message"]
        assert row["terminal_reason"] == (
            "background_task_crashed:SkillConfigError"
        )
        assert row["completed_at"], "completed_at must be set on failure"
        assert manager.is_running(session["id"]) is False
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_crash_finalizer_never_overwrites_orchestrator_terminal_state(
    monkeypatch, tmp_path,
):
    """P7-009 AC: a session the orchestrator already completed is untouched —
    terminal finality beats the crash finalizer."""
    store, manager, _ = await _make_manager(
        monkeypatch, tmp_path, "complete_then_crash",
    )
    try:
        session = await _start_skill_session(manager)
        row = await _await_terminal(store, session["id"])
        assert row is not None
        assert row["status"] == "completed"
        assert row["error_message"] is None
        assert row["terminal_reason"] is None
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_paused_session_crash_marks_failed(monkeypatch, tmp_path):
    """P7-009: the crash of a *paused* session's task also reaches ``failed``
    (the ``paused → failing → failed`` state-machine edge)."""
    store, manager, _ = await _make_manager(monkeypatch, tmp_path, "pause_then_crash")
    try:
        session = await _start_skill_session(manager)
        row = await _await_terminal(store, session["id"])
        assert row is not None
        assert row["status"] == "failed"
        assert "crash while paused" in (row["error_message"] or "")
        assert row["terminal_reason"] == "background_task_crashed:RuntimeError"
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_normally_finished_task_is_untouched(monkeypatch, tmp_path):
    """A task that completes without an escaping exception never triggers the
    crash finalizer (no exception → no callback work)."""
    store, manager, fake = await _make_manager(monkeypatch, tmp_path, "ok")
    try:
        session = await _start_skill_session(manager)
        await asyncio.sleep(0.05)
        assert fake.captured_config is not None
        row = await store.get_session(session["id"])
        assert row is not None
        assert row["status"] == "running"  # fake wrote no terminal status
        assert row["error_message"] is None
    finally:
        await manager.shutdown()


# ---------------------------------------------------------------------------
# P7-010 — fail fast instead of 201-then-crash (manager level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_session_unknown_skill_fails_fast_without_row(
    monkeypatch, tmp_path,
):
    store, manager, _ = await _make_manager(monkeypatch, tmp_path, "ok")
    try:
        with pytest.raises(SkillConfigError, match="rejected by the skill registry"):
            await _start_skill_session(
                manager,
                skill_id="no-such-skill",
                subject_id="no-such-skill",
            )
        assert await store.list_sessions() == [], (
            "no DB row may exist for a session that never started"
        )
        assert manager.active_count == 0
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_start_session_legacy_model_type_only_refused(
    monkeypatch, tmp_path,
):
    """B2 repro at the manager level: ``model_type`` alone (no skill_id)
    cannot materialize a runtime — refused before any row/workspace."""
    store, manager, _ = await _make_manager(monkeypatch, tmp_path, "ok")
    try:
        with pytest.raises(SkillConfigError, match="no skill_id"):
            await manager.start_session(
                instrument="DOGE_USDT",
                timeframe="15m",
                model_type="direction",
                max_iterations=1,
            )
        assert await store.list_sessions() == []
    finally:
        await manager.shutdown()


# ---------------------------------------------------------------------------
# P7-010 — fail fast (API level): legacy trio → 404 naming the translated id,
# unknown skill → 404, valid skill → 201. No zombie rows.
# ---------------------------------------------------------------------------


async def _make_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str = "ok",
):
    from fastapi import FastAPI

    store, manager, fake = await _make_manager(monkeypatch, tmp_path, mode)
    monkeypatch.setattr(settings, "autoresearch_api_token", _API_TOKEN)
    research_module.init(manager, store)
    app = FastAPI()
    app.include_router(research_router, prefix="/api/v1")
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(
        transport=transport, base_url="http://wave2-test",
    )
    return store, manager, fake, client


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_API_TOKEN}"}


@pytest.mark.asyncio
async def test_api_legacy_model_type_start_returns_404_naming_translated_skill(
    monkeypatch, tmp_path,
):
    """P7-010 AC / D3: ``{"model_type": "direction"}`` is translated to
    ``ml-direction`` and then hits the same installed-skill check — 404
    ``skill_not_found`` naming the translated id + available skills, never a
    201 for a session that would crash on its first tick."""
    store, manager, _, client = await _make_api(monkeypatch, tmp_path)
    try:
        resp = await client.post(
            "/api/v1/research/start",
            headers=_auth(),
            json={
                "instrument": "DOGE_USDT",
                "timeframe": "15m",
                "model_type": "direction",
            },
        )
        assert resp.status_code == 404, resp.text
        detail = resp.json()["detail"]
        assert detail["error"] == "skill_not_found"
        assert detail["skill_id"] == "ml-direction"
        assert _BUNDLED_SKILLS <= set(detail["available"])
        assert await store.list_sessions() == []
    finally:
        await client.aclose()
        await manager.shutdown()


@pytest.mark.asyncio
async def test_api_unknown_skill_start_returns_404_without_row(
    monkeypatch, tmp_path,
):
    store, manager, _, client = await _make_api(monkeypatch, tmp_path)
    try:
        resp = await client.post(
            "/api/v1/research/start",
            headers=_auth(),
            json={"skill_id": "no-such-skill", "subject_id": "x", "variant": "y"},
        )
        assert resp.status_code == 404, resp.text
        detail = resp.json()["detail"]
        assert detail["error"] == "skill_not_found"
        assert detail["skill_id"] == "no-such-skill"
        assert await store.list_sessions() == []
    finally:
        await client.aclose()
        await manager.shutdown()


@pytest.mark.asyncio
async def test_api_valid_skill_start_still_returns_201(monkeypatch, tmp_path):
    """P7-010 AC: a valid skill still returns 201 with the dual-shape body."""
    store, manager, fake, client = await _make_api(monkeypatch, tmp_path)
    eval_set = tmp_path / "fixture_eval_set.jsonl"
    eval_set.write_text('{"input": "q", "expected": "a"}\n', encoding="utf-8")
    try:
        resp = await client.post(
            "/api/v1/research/start",
            headers=_auth(),
            json={
                "skill_id": "prompt-engineering", "max_iterations": 1,
                "skill_params": {"eval_set": str(eval_set)},
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["skill_id"] == "prompt-engineering"
        assert body["model_type"] == ""
        rows = await store.list_sessions()
        assert len(rows) == 1
        assert rows[0]["status"] == "running"
        assert rows[0]["error_message"] is None
        await asyncio.sleep(0.05)
        assert fake.captured_config is not None
        assert fake.captured_config.skill_id == "prompt-engineering"
    finally:
        await client.aclose()
        await manager.shutdown()

