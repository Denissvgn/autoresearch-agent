
"""Tests for the baseline_capture cross-session dedup bypass.

When the agent is in `baseline_capture` phase and submits a config whose
canonical_config_hash matches a prior session's recorded baseline (the
expected case, since the phase contract says "run the immutable baseline"),
the orchestrator should INHERIT the prior metric instead of rejecting the
attempt. Same-session duplicates remain rejected.
"""
from __future__ import annotations

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
from src.core.results_store import ResultsStore

_BASELINE_YAML = (
    "instrument: DOGE_USDT\n"
    "timeframe: 15m\n"
    "direction_pct_threshold: 0.03\n"
    "horizon: 6\n"
)
_CMD = (
    ".venv/bin/python scripts/autotuner/direction/prepare.py "
    "--config /app/workspace/runs/autotuner/DOGE_USDT_15m/direction/train.yaml"
)


async def _seed_prior_baseline(
    store: ResultsStore,
    *,
    workspace: Path,
    metric: float = 0.6435,
) -> str:
    """Create a prior session with one recorded baseline iteration."""
    prior_id = "res_prior_baseline"
    await store.create_session(
        session_id=prior_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="prior",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    from src.core.iteration_snapshot import build_trial_identity, trial_identity_hash

    identity = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        quick_mode=False,
        marker={},
    )
    ihash = trial_identity_hash(identity)

    import json
    await store.add_iteration(
        research_id=prior_id,
        iteration=1,
        primary_metric=metric,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="keep",
        description="prior baseline",
        config_snapshot=_BASELINE_YAML,
        metrics_json=json.dumps(
            {
                "primary_metric": metric,
                "metric_name": "composite_direction_score",
                "training_gates_passed": True,
                "all_gates_passed": True,
            }
        ),
        training_time_s=120.0,
        canonical_config_hash=identity.get("canonical_config_hash"),
        trial_identity_hash=ihash,
        trial_identity_json=json.dumps(identity),
        search_phase="baseline_capture",
    )
    return prior_id


@pytest.mark.asyncio
async def test_baseline_capture_inherits_cross_session_baseline(
    tmp_path: Path,
) -> None:
    """When phase=baseline_capture and a prior session has the same config,
    the orchestrator returns a baseline-link result (not a rejection).
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    prior_id = await _seed_prior_baseline(store, workspace=workspace)

    new_id = "res_new_session"
    await store.create_session(
        session_id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="new",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=1,
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        planned_trial=None,
        current_phase="baseline_capture",
    )

    assert result is not None
    assert marker is not None
    assert marker["decision"] == "keep"
    assert marker["primary_metric"] == 0.6435
    assert marker["status"] == "completed"
    assert marker["baseline_linked_from_research_id"] == prior_id
    assert marker["baseline_linked_from_iteration"] == 1
    assert result.meta["policy_allowed"] is True
    assert result.meta["policy_operation"] == "baseline.linked"
    assert "baseline_linked_from_research_id" in result.content


@pytest.mark.asyncio
async def test_baseline_link_inherits_passed_gates_from_prior_metrics_json(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fix A regression: training_gates_passed lives in metrics_json, not as
    a top-level column on the iteration row. The synthetic baseline-link
    marker must read it from metrics_json so the canonical/legacy flags
    agree and no Conflicting gate aliases warning is emitted.
    """
    import logging

    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    prior_id = await _seed_prior_baseline(store, workspace=workspace)

    new_id = "res_new_a"
    await store.create_session(
        session_id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="new-a",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    caplog.set_level(logging.WARNING)
    _, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=1,
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        planned_trial=None,
        current_phase="baseline_capture",
    )

    assert marker is not None
    assert marker["training_gates_passed"] is True
    assert marker["all_gates_passed"] is True
    assert marker["decision"] == "keep"

    conflict_warnings = [
        rec for rec in caplog.records
        if "Conflicting gate aliases" in rec.getMessage()
    ]
    assert not conflict_warnings, (
        "expected no conflict warning, got: "
        + "; ".join(rec.getMessage() for rec in conflict_warnings)
    )


@pytest.mark.asyncio
async def test_baseline_link_inherits_failed_gates(
    tmp_path: Path,
) -> None:
    """Fix A: when the prior baseline genuinely failed, both flags propagate
    as False — agent must see the truthful state, not a synthetic pass.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    import json as _json

    prior_id = "res_prior_failed"
    await store.create_session(
        session_id=prior_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="prior-failed",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    from src.core.iteration_snapshot import build_trial_identity, trial_identity_hash

    identity = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        quick_mode=False,
        marker={},
    )
    ihash = trial_identity_hash(identity)

    await store.add_iteration(
        research_id=prior_id,
        iteration=1,
        primary_metric=0.4,
        metric_name="composite_direction_score",
        all_gates_passed=False,
        decision="keep",
        description="failed prior baseline",
        config_snapshot=_BASELINE_YAML,
        metrics_json=_json.dumps(
            {
                "primary_metric": 0.4,
                "metric_name": "composite_direction_score",
                "training_gates_passed": False,
                "all_gates_passed": False,
            }
        ),
        training_time_s=60.0,
        canonical_config_hash=identity.get("canonical_config_hash"),
        trial_identity_hash=ihash,
        trial_identity_json=_json.dumps(identity),
        search_phase="baseline_capture",
    )

    new_id = "res_new_b"
    await store.create_session(
        session_id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="new-b",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    _, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=1,
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        planned_trial=None,
        current_phase="baseline_capture",
    )

    assert marker is not None
    assert marker["training_gates_passed"] is False
    assert marker["all_gates_passed"] is False


@pytest.mark.asyncio
async def test_baseline_capture_same_session_duplicate_still_rejected(
    tmp_path: Path,
) -> None:
    """A duplicate within the same session is still rejected even in
    baseline_capture — re-running the same config in one session is waste.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    session_id = "res_self_dup"
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="self-dup",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    import json

    from src.core.iteration_snapshot import build_trial_identity, trial_identity_hash

    identity = build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        quick_mode=False,
        marker={},
    )
    ihash = trial_identity_hash(identity)
    await store.add_iteration(
        research_id=session_id,
        iteration=1,
        primary_metric=0.6435,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="keep",
        description="first attempt",
        config_snapshot=_BASELINE_YAML,
        metrics_json=json.dumps({"primary_metric": 0.6435}),
        training_time_s=120.0,
        canonical_config_hash=identity.get("canonical_config_hash"),
        trial_identity_hash=ihash,
        trial_identity_json=json.dumps(identity),
        search_phase="baseline_capture",
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=2,
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        planned_trial=None,
        current_phase="baseline_capture",
    )

    assert result is not None and marker is not None
    assert marker["status"] == "rejected_duplicate"
    assert marker["decision"] == "discard"
    assert result.meta["policy_operation"] == "duplicate_attempt.reject"


@pytest.mark.asyncio
async def test_baseline_capture_no_prior_returns_none(
    tmp_path: Path,
) -> None:
    """First-ever baseline (no prior session) is not flagged at all."""
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    session_id = "res_first"
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="first",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=1,
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        planned_trial=None,
        current_phase="baseline_capture",
    )

    assert result is None
    assert marker is None


@pytest.mark.asyncio
async def test_non_baseline_phase_still_rejects_cross_session(
    tmp_path: Path,
) -> None:
    """Cross-session duplicates outside baseline_capture remain rejected."""
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _seed_prior_baseline(store, workspace=workspace)

    new_id = "res_other_phase"
    await store.create_session(
        session_id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="other",
        workspace_path=str(workspace),
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id=new_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=1,
        command=_CMD,
        config_snapshot=_BASELINE_YAML,
        planned_trial=None,
        current_phase="tabular_sweeps",
    )

    assert result is not None and marker is not None
    assert marker["status"] == "rejected_duplicate"