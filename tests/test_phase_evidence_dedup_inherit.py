
"""Issue 5 — noop-phase evidence inheritance on a dedup hit.

`adaptive_feature_sweeps` advances on a single in-phase iteration carrying an
accepted noop (`adaptive_features_unavailable`). For an instrument where
adaptive features simply do not apply, that noop is *config-invariant* — only
the already-recorded config produces it, so a re-run to assert the evidence
dedups. Rejecting it with an evidence-stripped `rejected_duplicate` marker
wedges the phase forever. The orchestrator must instead inherit the accepted
evidence from the completed prior iteration so the phase advances, without the
agent having to perturb a research-irrelevant knob.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

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
    sys.modules["anthropic"] = cast(ModuleType, _stub)
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.research_phase_plan import build_phase_state
from src.core.results_store import ResultsStore

_YAML = (
    "instrument: DOGE_USDT\n"
    "timeframe: 15m\n"
    "direction_pct_threshold: 0.03\n"
    "horizon: 6\n"
)
_CMD = (
    ".venv/bin/python scripts/autotuner/direction/prepare.py "
    "--config /app/workspace/runs/autotuner/DOGE_USDT_15m/direction/train.yaml"
)
_NOOP = "adaptive_features_unavailable"


def _identity_hash():
    from src.core.iteration_snapshot import build_trial_identity, trial_identity_hash

    identity = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=_CMD,
        config_snapshot=_YAML,
        quick_mode=False,
        marker={},
    )
    return identity, trial_identity_hash(identity)


async def _new_store(tmp_path: Path) -> ResultsStore:
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    return store


async def _create_session(store: ResultsStore, sid: str, ws: Path) -> None:
    await store.create_session(
        session_id=sid,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag=sid,
        workspace_path=str(ws),
        max_iterations=40,
        max_budget_usd=100.0,
        quick_mode=False,
        focus_hint=None,
    )


async def _seed_iteration(
    store: ResultsStore,
    *,
    sid: str,
    iteration: int,
    search_phase: str,
    with_noop: bool,
    duplicate_reason: str | None = None,
) -> None:
    identity, ihash = _identity_hash()
    metrics = {
        "primary_metric": 0.61,
        "metric_name": "composite_direction_score",
        "training_gates_passed": True,
        "all_gates_passed": True,
        "status": "completed",
    }
    if with_noop:
        metrics["adaptive_feature_noop_reason"] = _NOOP
    await store.add_iteration(
        research_id=sid,
        iteration=iteration,
        primary_metric=0.61,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="keep",
        description="seed",
        config_snapshot=_YAML,
        metrics_json=json.dumps(metrics),
        training_time_s=120.0,
        canonical_config_hash=identity.get("canonical_config_hash"),
        trial_identity_hash=ihash,
        trial_identity_json=json.dumps(identity),
        duplicate_reason=duplicate_reason,
        search_phase=search_phase,
    )


# --------------------------------------------------------------------------- #
# Satisfiable-path sanity: a recorded in-phase noop iteration completes phase
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_recorded_noop_iteration_completes_phase(tmp_path: Path) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(store, "res_a", ws)
    await _seed_iteration(
        store,
        sid="res_a",
        iteration=38,
        search_phase="adaptive_feature_sweeps",
        with_noop=True,
    )

    session = await store.get_session("res_a")
    iterations = await store.get_iterations("res_a")
    state = build_phase_state(session=session, iterations=iterations)

    phases = {p["id"]: p["status"] for p in state["phases"]}
    assert phases["adaptive_feature_sweeps"] == "completed"


# --------------------------------------------------------------------------- #
# Core: dedup re-run in a noop phase inherits the accepted evidence
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_dedup_in_noop_phase_inherits_evidence(tmp_path: Path) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(store, "res_b0e2", ws)
    # iteration 38 already produced the config-invariant accepted noop.
    await _seed_iteration(
        store,
        sid="res_b0e2",
        iteration=38,
        search_phase="adaptive_feature_sweeps",
        with_noop=True,
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id="res_b0e2",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=39,
        command=_CMD,
        config_snapshot=_YAML,
        planned_trial=None,
        current_phase="adaptive_feature_sweeps",
    )

    assert result is not None and marker is not None
    # Not the evidence-stripped rejection.
    assert marker["status"] == "completed"
    assert marker["decision"] == "keep"
    assert marker["search_phase"] == "adaptive_feature_sweeps"
    assert marker["adaptive_feature_noop_reason"] == _NOOP
    assert marker["phase_evidence_linked_from_iteration"] == 38
    assert result.meta["policy_allowed"] is True
    assert result.meta["policy_operation"] == "phase_evidence.linked"
    assert "adaptive_feature_noop_reason" in result.content

    # The inherited marker, recorded as an iteration, advances the phase.
    iterations = await store.get_iterations("res_b0e2")
    inherited_row = {
        "search_phase": marker["search_phase"],
        "metrics_json": json.dumps(marker),
    }
    session = await store.get_session("res_b0e2")
    state = build_phase_state(
        session=session, iterations=iterations + [inherited_row]
    )
    phases = {p["id"]: p["status"] for p in state["phases"]}
    assert phases["adaptive_feature_sweeps"] == "completed"


# --------------------------------------------------------------------------- #
# Negative: a dwell-gated phase is NOT noop-inheritable
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_dwell_gated_phase_still_rejects(tmp_path: Path) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(store, "res_c", ws)
    await _seed_iteration(
        store,
        sid="res_c",
        iteration=10,
        search_phase="tsfm_sweeps",
        with_noop=True,  # even with a noop key present
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id="res_c",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=11,
        command=_CMD,
        config_snapshot=_YAML,
        planned_trial=None,
        current_phase="tsfm_sweeps",  # not in NOOP_INHERITABLE_PHASES
    )

    assert result is not None and marker is not None
    assert marker["status"] == "rejected_duplicate"
    assert result.meta["policy_operation"] == "duplicate_attempt.reject"


# --------------------------------------------------------------------------- #
# Negative: the only prior match is itself a rejected_duplicate → no inherit
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_no_inherit_when_prior_is_rejected_duplicate(
    tmp_path: Path,
) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(store, "res_d", ws)
    await _seed_iteration(
        store,
        sid="res_d",
        iteration=5,
        search_phase="adaptive_feature_sweeps",
        with_noop=False,
        duplicate_reason="prior rejected",
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id="res_d",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=6,
        command=_CMD,
        config_snapshot=_YAML,
        planned_trial=None,
        current_phase="adaptive_feature_sweeps",
    )

    assert result is not None and marker is not None
    assert marker["status"] == "rejected_duplicate"
    assert result.meta["policy_operation"] == "duplicate_attempt.reject"