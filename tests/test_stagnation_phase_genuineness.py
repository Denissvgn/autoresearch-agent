"""Tests for phase-genuineness check on the stagnation exemption.

Background: `stagnation_exempt_phases` (e.g. `promotion_proposal`,
`tsfm_sweeps`) suppresses the global stagnation termination. But if a
session reaches one of these phases ONLY via `auto_phase_evidence: True`
emitted by prepare.py (the infrastructure-fallback path), the agent is
still doing tabular HPO work, not real promotion/validation. The
exemption should not apply.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

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
    sys.modules["anthropic"] = _stub

from src.core.orchestrator import AgentOrchestrator
from src.core.results_store import ResultsStore


async def _seed_session_with_iterations(
    store: ResultsStore,
    session_id: str,
    *,
    workspace: Path,
    iterations: list[dict],
    current_phase: str,
) -> None:
    await store.create_session(
        session_id=session_id,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="genuine-test",
        workspace_path=str(workspace),
        max_iterations=30,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )

    for i, spec in enumerate(iterations, start=1):
        metrics = spec.get("metrics", {})
        await store.add_iteration(
            research_id=session_id,
            iteration=i,
            primary_metric=spec.get("primary_metric"),
            metric_name="composite_direction_score",
            all_gates_passed=True,
            decision=spec.get("decision", "discard"),
            description=f"iter {i}",
            config_snapshot="instrument: DOGE_USDT\n",
            metrics_json=json.dumps(metrics),
            training_time_s=120.0,
            search_phase=spec.get("phase", current_phase),
        )

    await store.update_session(
        session_id,
        current_phase=current_phase,
        phase_state_json=json.dumps({"current_phase": current_phase}),
    )


@pytest.mark.asyncio
async def test_auto_evidence_only_phase_is_not_genuine(tmp_path: Path) -> None:
    """When the only iterations in promotion_proposal carry
    auto_phase_evidence=True and no explicit promotion keys, the phase is
    treated as non-genuine and stagnation can fire.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    iterations = [
        {
            "primary_metric": 0.6435,
            "decision": "keep",
            "phase": "tabular_sweeps",
            "metrics": {"tabular_sweep_variant": "v1"},
        },
    ] + [
        {
            "primary_metric": 0.6435,
            "decision": "discard",
            "phase": "promotion_proposal",
            "metrics": {"auto_phase_evidence": True},
        }
        for _ in range(14)
    ]

    await _seed_session_with_iterations(
        store, "res_auto_only",
        workspace=workspace,
        iterations=iterations,
        current_phase="promotion_proposal",
    )

    orchestrator = AgentOrchestrator(store)
    genuine = await orchestrator._phase_advancement_is_genuine(
        "res_auto_only", "promotion_proposal",
    )
    assert genuine is False


@pytest.mark.asyncio
async def test_explicit_phase_key_makes_phase_genuine(tmp_path: Path) -> None:
    """When at least one iteration in the phase carries an agent-explicit
    phase key (e.g. development_promotion_metadata), the phase is genuine.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    iterations = [
        {
            "primary_metric": 0.6435,
            "decision": "keep",
            "phase": "promotion_proposal",
            "metrics": {
                "auto_phase_evidence": True,
                "development_promotion_metadata": {"owner": "tester"},
            },
        },
    ]

    await _seed_session_with_iterations(
        store, "res_real_phase",
        workspace=workspace,
        iterations=iterations,
        current_phase="promotion_proposal",
    )

    orchestrator = AgentOrchestrator(store)
    genuine = await orchestrator._phase_advancement_is_genuine(
        "res_real_phase", "promotion_proposal",
    )
    assert genuine is True


@pytest.mark.asyncio
async def test_no_iterations_in_phase_is_not_genuine(tmp_path: Path) -> None:
    """When there are no iterations carrying the current phase label, the
    phase advancement cannot be considered genuine.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _seed_session_with_iterations(
        store, "res_empty",
        workspace=workspace,
        iterations=[
            {
                "primary_metric": 0.6,
                "decision": "keep",
                "phase": "tabular_sweeps",
                "metrics": {},
            }
        ],
        current_phase="promotion_proposal",
    )

    orchestrator = AgentOrchestrator(store)
    genuine = await orchestrator._phase_advancement_is_genuine(
        "res_empty", "promotion_proposal",
    )
    assert genuine is False


@pytest.mark.asyncio
async def test_non_auto_evidence_iteration_is_genuine(tmp_path: Path) -> None:
    """Any iteration in-phase without auto_phase_evidence is enough."""
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _seed_session_with_iterations(
        store, "res_real",
        workspace=workspace,
        iterations=[
            {
                "primary_metric": 0.62,
                "decision": "keep",
                "phase": "tsfm_sweeps",
                "metrics": {"tsfm_adapter": "moirai"},
            }
        ],
        current_phase="tsfm_sweeps",
    )

    orchestrator = AgentOrchestrator(store)
    assert await orchestrator._phase_advancement_is_genuine(
        "res_real", "tsfm_sweeps",
    ) is True


@pytest.mark.asyncio
async def test_gc_tsfm_fallback_validation_is_genuine(tmp_path: Path) -> None:
    """G-C: a tabular-only instrument emits only tsfm_fallback_validation
    (+auto_phase_evidence) in tsfm_sweeps. That server signal must count as
    genuine so stagnation is suppressed there.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _seed_session_with_iterations(
        store, "res_gc_tsfm",
        workspace=workspace,
        iterations=[
            {
                "primary_metric": 0.61,
                "decision": "discard",
                "phase": "tsfm_sweeps",
                "metrics": {
                    "auto_phase_evidence": True,
                    "tsfm_fallback_validation": True,
                },
            }
        ],
        current_phase="tsfm_sweeps",
    )

    orchestrator = AgentOrchestrator(store)
    assert await orchestrator._phase_advancement_is_genuine(
        "res_gc_tsfm", "tsfm_sweeps",
    ) is True


@pytest.mark.asyncio
async def test_gc_tsfm_structured_fallback_validation_is_genuine(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _seed_session_with_iterations(
        store, "res_gc_tsfm_structured",
        workspace=workspace,
        iterations=[
            {
                "primary_metric": 0.61,
                "decision": "discard",
                "phase": "tsfm_sweeps",
                "metrics": {
                    "auto_phase_evidence": True,
                    "tsfm_fallback_validation": {
                        "passed": True,
                        "reason": "tabular_candidate_family",
                        "candidate_family": "tabular",
                        "is_tsfm_candidate": False,
                    },
                },
            }
        ],
        current_phase="tsfm_sweeps",
    )

    orchestrator = AgentOrchestrator(store)
    assert await orchestrator._phase_advancement_is_genuine(
        "res_gc_tsfm_structured", "tsfm_sweeps",
    ) is True


@pytest.mark.asyncio
async def test_gc_tsfm_auto_only_without_fallback_not_genuine(
    tmp_path: Path,
) -> None:
    """G-C is scoped: tsfm_sweeps with auto_phase_evidence but NO
    tsfm_fallback_validation (and no tsfm/tsfm_adapter) stays non-genuine —
    anti-gaming preserved.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _seed_session_with_iterations(
        store, "res_gc_tsfm_neg",
        workspace=workspace,
        iterations=[
            {
                "primary_metric": 0.61,
                "decision": "discard",
                "phase": "tsfm_sweeps",
                "metrics": {"auto_phase_evidence": True},
            }
        ],
        current_phase="tsfm_sweeps",
    )

    orchestrator = AgentOrchestrator(store)
    assert await orchestrator._phase_advancement_is_genuine(
        "res_gc_tsfm_neg", "tsfm_sweeps",
    ) is False


@pytest.mark.asyncio
async def test_gc_fallback_key_outside_tsfm_is_ignored(tmp_path: Path) -> None:
    """The tsfm_fallback_validation recognition is scoped to tsfm_sweeps; the
    same key in another auto-only phase does not make it genuine.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _seed_session_with_iterations(
        store, "res_gc_scope",
        workspace=workspace,
        iterations=[
            {
                "primary_metric": 0.61,
                "decision": "discard",
                "phase": "promotion_proposal",
                "metrics": {
                    "auto_phase_evidence": True,
                    "tsfm_fallback_validation": True,
                },
            }
        ],
        current_phase="promotion_proposal",
    )

    orchestrator = AgentOrchestrator(store)
    assert await orchestrator._phase_advancement_is_genuine(
        "res_gc_scope", "promotion_proposal",
    ) is False
