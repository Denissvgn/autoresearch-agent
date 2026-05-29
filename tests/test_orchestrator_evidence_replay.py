"""DM-1 — evidence-replay link on a session-best dedup hit.

Iterations 8/10/11/12 of res_be66790e192e re-ran the iteration-7 best
config across calibration_replay_gates, multi_seed_robustness, and
inference_parity_replay — four wasted ~7-minute re-trains for a metric
that was already on disk. The orchestrator must, on a dedup hit where
(a) the canonical config matches the session's best and (b) the active
phase is in ``EVIDENCE_INHERITABLE_PHASES``, synthesise a marker that
inherits the prior iteration's phase-advancement evidence and skip the
training command altogether.

Mirrors the noop-inheritance test (``test_phase_evidence_dedup_inherit.py``)
in structure; the differences are the inheritable phase set and the
audit-field name (``evidence_replayed_from_iteration``).
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

from src.core.consistency_validator import _is_synthetic_promotion_iteration
from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.research_phase_plan import (
    EVIDENCE_INHERITABLE_PHASES,
    build_phase_state,
)
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


async def _seed_best_iteration(
    store: ResultsStore,
    *,
    sid: str,
    iteration: int,
    search_phase: str,
    advancement_payload: dict,
) -> None:
    """Seed the canonical session-best iteration with phase-advancement
    evidence already populated.

    ``advancement_payload`` carries the keys
    ``_PHASE_ADVANCEMENT_KEYS[search_phase]`` expects (e.g.
    ``inference_parity`` or ``seed_trials``) so the DM-1 replay branch
    has truthy evidence to inherit.
    """
    identity, ihash = _identity_hash()
    metrics = {
        "primary_metric": 0.3927,
        "metric_name": "composite_direction_score",
        "training_gates_passed": True,
        "all_gates_passed": True,
        "status": "completed",
        "mlflow_run_id": "run-iter7",
        "training_time_s": 415.7,
        **advancement_payload,
    }
    await store.add_iteration(
        research_id=sid,
        iteration=iteration,
        primary_metric=0.3927,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="keep",
        description="seed best",
        config_snapshot=_YAML,
        metrics_json=json.dumps(metrics),
        training_time_s=415.7,
        canonical_config_hash=identity.get("canonical_config_hash"),
        trial_identity_hash=ihash,
        trial_identity_json=json.dumps(identity),
        duplicate_reason=None,
        search_phase=search_phase,
        mlflow_run_id="run-iter7",
    )


# --------------------------------------------------------------------------- #
# Core: dedup re-run in an EVIDENCE_INHERITABLE phase replays the best's
# evidence instead of being rejected as a duplicate.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_dedup_in_inheritable_phase_replays_best_evidence(
    tmp_path: Path,
) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(store, "res_be66", ws)
    # iteration 7 IS the session best — full inference_parity evidence.
    await _seed_best_iteration(
        store,
        sid="res_be66",
        iteration=7,
        search_phase="calibration_replay_gates",
        advancement_payload={
            "inference_parity": {
                "feature_count_alignment_passed": True,
                "feature_name_alignment_passed": True,
                "model_roster_parity_passed": True,
                "mlflow_run_id": "run-iter7",
            },
        },
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id="res_be66",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=29,
        command=_CMD,
        config_snapshot=_YAML,
        planned_trial=None,
        current_phase="inference_parity_replay",
    )

    assert result is not None and marker is not None
    # Not the evidence-stripped rejection.
    assert marker["status"] == "completed"
    assert marker["decision"] == "keep"
    assert marker["outcome"] == "evidence_replayed"
    assert marker["search_phase"] == "inference_parity_replay"
    assert marker["evidence_replayed_from_iteration"] == 7
    assert marker["evidence_replayed_from_research_id"] == "res_be66"
    # Source iteration's MLflow run id carries forward so the
    # artifact-fingerprint guard finds the right training.log.
    assert marker["mlflow_run_id"] == "run-iter7"
    # The phase-advancement key is replayed at the marker's top level.
    assert "inference_parity" in marker
    assert marker["inference_parity"]["model_roster_parity_passed"] is True
    assert result.meta["policy_allowed"] is True
    assert result.meta["policy_operation"] == "evidence_replay.linked"
    # Synthetic block contains the replay-audit lines.
    assert "evidence_replayed_from_iteration" in result.content


# --------------------------------------------------------------------------- #
# Synthetic-iteration guard whitelists the evidence-replay marker.
# Without DM-1's exception, ``_is_synthetic_promotion_iteration`` would
# (correctly) flag the marker as synthetic (no training_time_s, identical
# metric, same mlflow_run_id) and block phase advancement.
# --------------------------------------------------------------------------- #
def test_synthetic_iteration_guard_whitelists_evidence_replay() -> None:
    prior = {"primary_metric": 0.3927, "mlflow_run_id": "run-iter7"}
    # Marker mirrors what _build_evidence_replay_link emits.
    replay_marker = {
        "primary_metric": 0.3927,
        "mlflow_run_id": "run-iter7",
        "training_time_s": None,  # no fresh training
        "evidence_replayed_from_iteration": 7,
        "evidence_replayed_from_research_id": "res_be66",
    }
    # Without the exception, all three synthetic-detection conditions are
    # met → would return "synthetic_phase_iteration_*". With DM-1's
    # whitelist, the guard returns None.
    blocker = _is_synthetic_promotion_iteration(
        replay_marker, prior, "inference_parity_replay",
    )
    assert blocker is None


def test_synthetic_iteration_guard_still_flags_unrelated_synthetic() -> None:
    """Regression: a marker without the evidence-replay sentinel that
    matches all three synthetic conditions must still be flagged. Guards
    against the DM-1 whitelist becoming a free pass."""
    prior = {"primary_metric": 0.3927, "mlflow_run_id": "run-iter7"}
    plain_synthetic = {
        "primary_metric": 0.3927,
        "mlflow_run_id": "run-iter7",
        "training_time_s": None,
        # No evidence_replayed_from_iteration sentinel.
    }
    blocker = _is_synthetic_promotion_iteration(
        plain_synthetic, prior, "multi_seed_robustness",
    )
    assert blocker == "synthetic_phase_iteration_multi_seed_robustness"


# --------------------------------------------------------------------------- #
# Negative: when the dispatched config-hash does NOT match the session
# best, the new branch must NOT fire — fall through to the existing
# rejected_duplicate path so genuine duplicates stay rejected.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_replay_branch_does_not_fire_when_config_hash_differs(
    tmp_path: Path,
) -> None:
    store = await _new_store(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    await _create_session(store, "res_xyz", ws)

    # Seed a DIFFERENT prior iteration with a different canonical hash —
    # we'll dispatch with _YAML so the hashes differ.
    other_identity = {
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "canonical_config_hash": "deadbeef-different-hash",
        "seed": "default",
        "validation_mode": "full",
        "data_split_id": "split-x",
    }
    other_payload = {
        "primary_metric": 0.40,
        "metric_name": "composite_direction_score",
        "training_gates_passed": True,
        "all_gates_passed": True,
        "status": "completed",
        "mlflow_run_id": "run-other",
        "training_time_s": 300.0,
        "inference_parity": {"model_roster_parity_passed": True},
    }
    # Re-derive the dispatched hash (build_trial_identity is deterministic
    # over _YAML/_CMD), then craft a duplicate row whose canonical hash
    # matches that — i.e. simulate a same-config prior. We then seed
    # ALSO a "best" pointer with a DIFFERENT hash so the replay branch's
    # ``best.canonical_config_hash == identity.canonical_config_hash``
    # check fails.
    identity, ihash = _identity_hash()
    # Duplicate row: same hash as the dispatch (so dedup detection fires)
    # but `best` is a different iteration with a different hash.
    await store.add_iteration(
        research_id="res_xyz",
        iteration=5,
        primary_metric=0.30,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="discard",
        description="prior same-config attempt",
        config_snapshot=_YAML,
        metrics_json=json.dumps({
            "primary_metric": 0.30,
            "status": "completed",
            "training_time_s": 200.0,
            "inference_parity": {"model_roster_parity_passed": True},
        }),
        training_time_s=200.0,
        canonical_config_hash=identity.get("canonical_config_hash"),
        trial_identity_hash=ihash,
        trial_identity_json=json.dumps(identity),
        duplicate_reason=None,
        search_phase="calibration_replay_gates",
        mlflow_run_id="run-prior",
    )
    # Best row carries a DIFFERENT canonical hash (a separate, better
    # config not matching the dispatch).
    await store.add_iteration(
        research_id="res_xyz",
        iteration=6,
        primary_metric=0.50,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision="keep",
        description="best (different config)",
        config_snapshot="other-yaml",
        metrics_json=json.dumps(other_payload),
        training_time_s=300.0,
        canonical_config_hash="deadbeef-different-hash",
        trial_identity_hash="deadbeef-hash-2",
        trial_identity_json=json.dumps(other_identity),
        duplicate_reason=None,
        search_phase="calibration_replay_gates",
        mlflow_run_id="run-other",
    )

    orchestrator = AgentOrchestrator(store)
    config = ResearchConfig(
        id="res_xyz",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
    )

    result, marker = await orchestrator._guard_duplicate_training_attempt(
        config=config,
        turn=7,
        command=_CMD,
        config_snapshot=_YAML,
        planned_trial=None,
        current_phase="inference_parity_replay",
    )

    # Dedup detects iter 5 (same hash). Best is iter 6 (different hash) →
    # DM-1 branch does NOT fire, falls through to rejected_duplicate.
    assert result is not None and marker is not None
    assert marker["status"] == "rejected_duplicate"
    assert result.meta["policy_operation"] == "duplicate_attempt.reject"


# --------------------------------------------------------------------------- #
# Sanity: EVIDENCE_INHERITABLE_PHASES is the conservative set the plan
# specified — keep it locked so a future expansion is an explicit code
# review rather than a silent ratchet.
# --------------------------------------------------------------------------- #
def test_evidence_inheritable_phases_locked() -> None:
    assert EVIDENCE_INHERITABLE_PHASES == frozenset({
        "calibration_replay_gates",
        "multi_seed_robustness",
        "inference_parity_replay",
    })
