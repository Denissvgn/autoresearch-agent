"""AR-3: Tests for auto-inheritance of config_snapshot on promotion-family phases.

Defect D4: during phases that validate/replay/promote an already-trained
artefact (multi_seed_robustness, inference_parity_replay,
calibration_replay_gates, promotion_proposal) the agent legitimately emits
no config_snapshot in the iteration marker because it never runs a fresh
training command.  The consistency validator always flags this as
``missing_config_snapshot``, making ``passed: False``.

Fix: ``_record_iteration`` now detects when the active phase is in
``_PROMOTION_FAMILY`` and the marker has no config_snapshot.  It then
queries ``get_latest_iteration_with_config_snapshot`` and inherits the
result, recording the source iteration number in
``config_snapshot_inherited_from_iteration`` for audit purposes.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

# ---------------------------------------------------------------------------
# Stub the Anthropic SDK (same pattern as test_runtime_recovery.py)
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
from src.core.results_store import ResultsStore


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _create_session(store: ResultsStore, *, session_id: str) -> None:
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag=session_id,
        quick_mode=True,
        max_iterations=10,
        max_budget_usd=5.0,
        focus_hint=None,
        workspace_path="/tmp/ws",
    )


def _keep_marker(config_snapshot: str) -> Dict[str, Any]:
    """Realistic 'keep' iteration marker that carries a config_snapshot."""
    return {
        "primary_metric": 0.65,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "iter 1 baseline",
        "config_snapshot": config_snapshot,
        "training_time_s": 42.1,
    }


def _promotion_marker(phase: str) -> Dict[str, Any]:
    """Promotion-family marker with no config_snapshot (the D4 scenario)."""
    return {
        "primary_metric": 0.65,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": f"promotion phase: {phase}",
        "search_phase": phase,
        # deliberately no config_snapshot
    }


# ---------------------------------------------------------------------------
# ResultsStore unit tests for the new helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_latest_iteration_with_config_snapshot_returns_most_recent(
    tmp_path: Path,
) -> None:
    """Basic happy-path: returns the highest-numbered iteration that has a snapshot."""
    store = ResultsStore(str(tmp_path / "db.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_snap_basic")

    await store.add_iteration(
        research_id="res_snap_basic",
        iteration=1,
        primary_metric=0.60,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json="{}",
        training_time_s=None,
    )
    await store.add_iteration(
        research_id="res_snap_basic",
        iteration=2,
        primary_metric=0.63,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="",
        config_snapshot="agent_strategy: CONS\n",
        metrics_json="{}",
        training_time_s=None,
    )
    # iter 3 has no snapshot
    await store.add_iteration(
        research_id="res_snap_basic",
        iteration=3,
        primary_metric=None,
        metric_name=None,
        all_gates_passed=False,
        decision="discard",
        description="",
        config_snapshot=None,
        metrics_json="{}",
        training_time_s=None,
    )

    result = await store.get_latest_iteration_with_config_snapshot("res_snap_basic")
    assert result is not None
    assert result["iteration"] == 2
    assert result["config_snapshot"] == "agent_strategy: CONS\n"


@pytest.mark.asyncio
async def test_get_latest_iteration_with_config_snapshot_returns_none_when_all_null(
    tmp_path: Path,
) -> None:
    """When every iteration has config_snapshot=NULL, the method returns None."""
    store = ResultsStore(str(tmp_path / "db_null.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_all_null")

    await store.add_iteration(
        research_id="res_all_null",
        iteration=1,
        primary_metric=0.50,
        metric_name="auc",
        all_gates_passed=False,
        decision="discard",
        description="",
        config_snapshot=None,
        metrics_json="{}",
        training_time_s=None,
    )

    result = await store.get_latest_iteration_with_config_snapshot("res_all_null")
    assert result is None


@pytest.mark.asyncio
async def test_get_latest_iteration_with_config_snapshot_returns_none_for_empty_session(
    tmp_path: Path,
) -> None:
    """Empty session (no iterations at all) → None, no error."""
    store = ResultsStore(str(tmp_path / "db_empty.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_empty_iters")

    result = await store.get_latest_iteration_with_config_snapshot("res_empty_iters")
    assert result is None


# ---------------------------------------------------------------------------
# _record_iteration integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promotion_iteration_inherits_config_snapshot_from_previous_keep(
    tmp_path: Path,
) -> None:
    """AR-3 core: promotion_proposal iter inherits iter-1 snapshot.

    Seeds iter 1 with a real config_snapshot, then calls _record_iteration for
    iter 2 with phase=promotion_proposal and no snapshot.  The iter-2 DB row
    must have the inherited snapshot, and metrics_json must record
    config_snapshot_inherited_from_iteration=1.
    """
    store = ResultsStore(str(tmp_path / "db_inherit.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_inherit")

    snapshot_text = "agent_strategy: BALA\nhorizon: 15\n"

    # Iter 1: real training run with config_snapshot
    await store.add_iteration(
        research_id="res_inherit",
        iteration=1,
        primary_metric=0.65,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="",
        config_snapshot=snapshot_text,
        metrics_json="{}",
        training_time_s=None,
    )

    # Iter 2: promotion_proposal phase, no config_snapshot
    marker2 = _promotion_marker("promotion_proposal")
    await AgentOrchestrator(store)._record_iteration(
        "res_inherit", 2, marker2, 0.05,
    )

    row = await store.get_iteration("res_inherit", 2)
    assert row is not None
    # config_snapshot column must be the inherited value
    assert row["config_snapshot"] == snapshot_text
    # metrics_json must carry the audit trail key
    metrics = json.loads(row["metrics_json"])
    assert metrics.get("config_snapshot_inherited_from_iteration") == 1


@pytest.mark.asyncio
async def test_promotion_iteration_inherits_from_most_recent_snapshot(
    tmp_path: Path,
) -> None:
    """Inheritance picks the HIGHEST-numbered iteration, not the first one."""
    store = ResultsStore(str(tmp_path / "db_latest.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_latest")

    snap_iter1 = "agent_strategy: BALA\nhorizon: 5\n"
    snap_iter3 = "agent_strategy: CONS\nhorizon: 15\n"

    await store.add_iteration(
        research_id="res_latest", iteration=1, primary_metric=0.60,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot=snap_iter1, metrics_json="{}",
        training_time_s=None,
    )
    await store.add_iteration(
        research_id="res_latest", iteration=2, primary_metric=0.61,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot=None, metrics_json="{}",
        training_time_s=None,
    )
    await store.add_iteration(
        research_id="res_latest", iteration=3, primary_metric=0.64,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot=snap_iter3, metrics_json="{}",
        training_time_s=None,
    )

    marker4 = _promotion_marker("multi_seed_robustness")
    await AgentOrchestrator(store)._record_iteration(
        "res_latest", 4, marker4, 0.10,
    )

    row = await store.get_iteration("res_latest", 4)
    assert row["config_snapshot"] == snap_iter3
    metrics = json.loads(row["metrics_json"])
    assert metrics.get("config_snapshot_inherited_from_iteration") == 3


@pytest.mark.asyncio
async def test_inheritance_not_applied_when_outside_promotion_family(
    tmp_path: Path,
) -> None:
    """tabular_sweeps is not in _PROMOTION_FAMILY: no inheritance occurs.

    Even if a previous iteration has a config_snapshot, a non-promotion-family
    phase must NOT inherit it.  The column stays NULL to preserve the
    cardinality contract that real sweeps must provide their own config.
    """
    store = ResultsStore(str(tmp_path / "db_no_inherit.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_no_inherit")

    await store.add_iteration(
        research_id="res_no_inherit", iteration=1, primary_metric=0.65,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot="agent_strategy: BALA\n",
        metrics_json="{}",
        training_time_s=None,
    )

    # Non-promotion-family phase, no config_snapshot
    marker2: Dict[str, Any] = {
        "primary_metric": 0.62,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "tabular sweep result",
        "search_phase": "tabular_sweeps",
        # no config_snapshot
    }
    await AgentOrchestrator(store)._record_iteration(
        "res_no_inherit", 2, marker2, 0.05,
    )

    row = await store.get_iteration("res_no_inherit", 2)
    # Must be NULL — tabular_sweeps must supply its own snapshot
    assert row["config_snapshot"] is None
    metrics = json.loads(row["metrics_json"])
    assert "config_snapshot_inherited_from_iteration" not in metrics


@pytest.mark.asyncio
async def test_inheritance_not_applied_when_no_previous_snapshot_exists(
    tmp_path: Path,
) -> None:
    """If no prior iteration has a snapshot, inheritance silently does nothing."""
    store = ResultsStore(str(tmp_path / "db_no_prior.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_no_prior")

    # First iteration ever, promotion phase, no prior snapshot available
    marker1 = _promotion_marker("promotion_proposal")
    await AgentOrchestrator(store)._record_iteration(
        "res_no_prior", 1, marker1, 0.01,
    )

    row = await store.get_iteration("res_no_prior", 1)
    assert row["config_snapshot"] is None
    metrics = json.loads(row["metrics_json"])
    assert "config_snapshot_inherited_from_iteration" not in metrics


@pytest.mark.asyncio
async def test_consistency_report_passes_after_inheritance(
    tmp_path: Path,
) -> None:
    """AR-3 acceptance: after inheritance the consistency report has no missing_config_snapshot blocker.

    Seeds a 'keep' iteration with a real config_snapshot, then calls
    _record_iteration for a promotion_proposal iteration without one.  The
    stored consistency_report_json must NOT contain 'missing_config_snapshot'
    in its blockers list.
    """
    store = ResultsStore(str(tmp_path / "db_consist.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_consist")

    await store.add_iteration(
        research_id="res_consist", iteration=1, primary_metric=0.65,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot="agent_strategy: BALA\nhorizon: 15\n",
        metrics_json="{}",
        training_time_s=None,
    )

    marker2 = _promotion_marker("promotion_proposal")
    await AgentOrchestrator(store)._record_iteration(
        "res_consist", 2, marker2, 0.05,
    )

    row = await store.get_iteration("res_consist", 2)
    consistency_raw = row.get("consistency_report_json")
    assert consistency_raw is not None, "consistency_report_json must be stored"
    report = json.loads(consistency_raw)

    assert "missing_config_snapshot" not in report.get("blockers", []), (
        f"missing_config_snapshot should not be a blocker after inheritance; "
        f"full blockers: {report.get('blockers')}"
    )


@pytest.mark.asyncio
async def test_all_promotion_family_phases_trigger_inheritance(
    tmp_path: Path,
) -> None:
    """All four phases in _PROMOTION_FAMILY must trigger inheritance.

    Feeds each phase in turn as a separate session so they're isolated.
    """
    phases = (
        "multi_seed_robustness",
        "inference_parity_replay",
        "calibration_replay_gates",
        "promotion_proposal",
    )
    snap = "agent_strategy: AGGR\nhorizon: 30\n"

    for i, phase in enumerate(phases):
        db_path = str(tmp_path / f"db_{phase}.sqlite")
        store = ResultsStore(db_path)
        await store.initialize()
        sid = f"res_{phase}"
        await _create_session(store, session_id=sid)

        # Seed one iteration with a snapshot
        await store.add_iteration(
            research_id=sid, iteration=1, primary_metric=0.64,
            metric_name="auc", all_gates_passed=True, decision="keep",
            description="", config_snapshot=snap, metrics_json="{}",
            training_time_s=None,
        )

        # Call _record_iteration for the promotion-family phase
        marker = _promotion_marker(phase)
        await AgentOrchestrator(store)._record_iteration(
            sid, 2, marker, 0.05,
        )

        row = await store.get_iteration(sid, 2)
        assert row["config_snapshot"] == snap, (
            f"Phase '{phase}' should have inherited config_snapshot"
        )
        metrics = json.loads(row["metrics_json"])
        assert metrics.get("config_snapshot_inherited_from_iteration") == 1, (
            f"Phase '{phase}' should record inheritance source"
        )


@pytest.mark.asyncio
async def test_existing_config_snapshot_not_overwritten(
    tmp_path: Path,
) -> None:
    """A promotion-family iter that already has a config_snapshot keeps its own."""
    store = ResultsStore(str(tmp_path / "db_no_overwrite.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_no_overwrite")

    prior_snap = "agent_strategy: BALA\nhorizon: 5\n"
    own_snap = "agent_strategy: CONS\nhorizon: 30\n"

    await store.add_iteration(
        research_id="res_no_overwrite", iteration=1, primary_metric=0.65,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot=prior_snap, metrics_json="{}",
        training_time_s=None,
    )

    marker2 = {
        "primary_metric": 0.66,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "promotion phase with own snapshot",
        "search_phase": "promotion_proposal",
        "config_snapshot": own_snap,  # agent provided its own snapshot
    }
    await AgentOrchestrator(store)._record_iteration(
        "res_no_overwrite", 2, marker2, 0.05,
    )

    row = await store.get_iteration("res_no_overwrite", 2)
    assert row["config_snapshot"] == own_snap, (
        "Existing config_snapshot must NOT be overwritten by inheritance"
    )
    metrics = json.loads(row["metrics_json"])
    assert "config_snapshot_inherited_from_iteration" not in metrics


@pytest.mark.asyncio
async def test_phase_from_session_phase_state_json_also_triggers_inheritance(
    tmp_path: Path,
) -> None:
    """Inheritance fires when active phase comes from session.phase_state_json.

    The marker has no ``search_phase`` key; the active phase is read from
    the session row's ``phase_state_json``.
    """
    store = ResultsStore(str(tmp_path / "db_from_state.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_from_state")

    snap = "agent_strategy: SCAL\nhorizon: 60\n"
    await store.add_iteration(
        research_id="res_from_state", iteration=1, primary_metric=0.70,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot=snap, metrics_json="{}",
        training_time_s=None,
    )

    # Inject phase_state_json into the session row
    phase_state = json.dumps({"current_phase": "calibration_replay_gates"})
    await store.update_session("res_from_state", phase_state_json=phase_state)

    # marker has NO search_phase — phase must be detected from session state
    marker2: Dict[str, Any] = {
        "primary_metric": 0.70,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "calibration replay",
        # no search_phase, no config_snapshot
    }
    await AgentOrchestrator(store)._record_iteration(
        "res_from_state", 2, marker2, 0.05,
    )

    row = await store.get_iteration("res_from_state", 2)
    assert row["config_snapshot"] == snap
    metrics = json.loads(row["metrics_json"])
    assert metrics.get("config_snapshot_inherited_from_iteration") == 1


@pytest.mark.asyncio
async def test_attach_consistency_report_persists_resolved_search_phase(
    tmp_path: Path,
) -> None:
    """Explicit iteration overwrites keep the phase column in sync.

    When the marker omits ``search_phase``, _attach_consistency_report resolves
    the active phase from ``session.phase_state_json``.  update_iteration must
    persist that resolved phase to both metrics_json and the search_phase
    column, otherwise later phase-state derivation loses the attribution.
    """
    store = ResultsStore(str(tmp_path / "db_update_phase.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_update_phase")

    await store.add_iteration(
        research_id="res_update_phase",
        iteration=1,
        primary_metric=0.65,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="",
        config_snapshot="agent_strategy: BALA\nhorizon: 15\n",
        metrics_json="{}",
        training_time_s=42.0,
    )
    await store.update_session(
        "res_update_phase",
        phase_state_json=json.dumps({"current_phase": "multi_seed_robustness"}),
    )

    marker: Dict[str, Any] = {
        "primary_metric": 0.65,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "explicit multi-seed overwrite",
        "seed_trials": [{"mlflow_run_id": "run-SAME"} for _ in range(5)],
        "n_seed_trials": 5,
    }

    orchestrator = AgentOrchestrator(store)
    await orchestrator._attach_consistency_report("res_update_phase", 1, marker)
    await store.update_iteration("res_update_phase", 1, marker)

    row = await store.get_iteration("res_update_phase", 1)
    assert row["search_phase"] == "multi_seed_robustness"

    metrics = json.loads(row["metrics_json"])
    assert metrics["search_phase"] == "multi_seed_robustness"

    report = json.loads(row["consistency_report_json"])
    assert "evidence_artifact_missing_for_multi_seed_robustness" in report.get(
        "blockers", []
    )


@pytest.mark.asyncio
async def test_record_iteration_stores_evidence_artifact_blocker_for_seed_trials(
    tmp_path: Path,
) -> None:
    """_record_iteration passes search_phase into consistency reports.

    Duplicate seed trial run IDs must appear as an operator-visible blocker in
    consistency_report_json, not only as hidden phase-state gating logic.
    """
    store = ResultsStore(str(tmp_path / "db_seed_blocker.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_seed_blocker")

    snap = "agent_strategy: BALA\nhorizon: 15\n"
    await store.add_iteration(
        research_id="res_seed_blocker", iteration=1, primary_metric=0.65,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot=snap, metrics_json="{}",
        training_time_s=42.0,
    )

    marker2: Dict[str, Any] = {
        "primary_metric": 0.65,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "synthetic multi-seed evidence",
        "search_phase": "multi_seed_robustness",
        "training_time_s": None,
        "seed_trials": [{"mlflow_run_id": "run-SAME"} for _ in range(5)],
        "n_seed_trials": 5,
        "seeds_passed_gates": True,
    }
    await AgentOrchestrator(store)._record_iteration(
        "res_seed_blocker", 2, marker2, 0.05,
    )

    row = await store.get_iteration("res_seed_blocker", 2)
    report = json.loads(row["consistency_report_json"])
    assert "missing_config_snapshot" not in report.get("blockers", [])
    assert "evidence_artifact_missing_for_multi_seed_robustness" in report.get(
        "blockers", []
    )

    session = await store.get_session("res_seed_blocker")
    phase_state = json.loads(session["phase_state_json"])
    assert phase_state["blocked"] is True
    assert "evidence_artifact_missing_for_multi_seed_robustness" in (
        phase_state["block_reason"] or ""
    )


@pytest.mark.asyncio
async def test_record_iteration_stores_evidence_artifact_blocker_for_calibration(
    tmp_path: Path,
) -> None:
    """Invalid calibration evidence is persisted in consistency_report_json."""
    store = ResultsStore(str(tmp_path / "db_cal_blocker.sqlite"))
    await store.initialize()
    await _create_session(store, session_id="res_cal_blocker")

    snap = "agent_strategy: BALA\nhorizon: 15\n"
    await store.add_iteration(
        research_id="res_cal_blocker", iteration=1, primary_metric=0.65,
        metric_name="auc", all_gates_passed=True, decision="keep",
        description="", config_snapshot=snap, metrics_json="{}",
        training_time_s=42.0,
    )

    marker2: Dict[str, Any] = {
        "primary_metric": 0.65,
        "metric_name": "auc",
        "all_gates_passed": True,
        "decision": "keep",
        "description": "calibration evidence missing selected run",
        "search_phase": "calibration_replay_gates",
        "training_time_s": None,
        "calibration_full_validation": {
            "selected": {"run_id": None, "metrics": {"ece": 0.02}},
        },
        "economic_replay": {"gates": {"all_gates_passed": True}},
    }
    await AgentOrchestrator(store)._record_iteration(
        "res_cal_blocker", 2, marker2, 0.05,
    )

    row = await store.get_iteration("res_cal_blocker", 2)
    report = json.loads(row["consistency_report_json"])
    assert "missing_config_snapshot" not in report.get("blockers", [])
    assert "evidence_artifact_missing_for_calibration_replay_gates" in report.get(
        "blockers", []
    )
