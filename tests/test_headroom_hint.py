
"""DM-14 — per-phase ``headroom_hint`` surfaced in the state JSON +
appended to ``next_action`` when budget is tight.

Pins:

1. ``_phase_headroom_hint`` returns ``"high"`` for a fresh phase with
   no iterations touching its primary sweep keys.
2. ``_phase_headroom_hint`` returns ``"low"`` when ALL of the phase's
   primary sweep keys have been touched in this session.
3. ``_phase_headroom_hint`` returns ``"medium"`` for partial coverage
   AND for phases without a defined sweep-key list.
4. Every phase entry in ``build_phase_state``'s output carries the
   ``headroom_hint`` field.
5. ``_next_action`` appends a ``[headroom_hint: low — …]`` suffix when
   the active phase is low-headroom AND iterations_remaining < 30% of
   max_iterations.
6. The suffix is OMITTED when budget is ample (≥ 30% remaining) OR
   when ``iterations_remaining`` is None (no budget context).
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = cast(ModuleType, _stub)
from src.core.research_phase_plan import (  # noqa: E402
    _PHASE_PRIMARY_SWEEP_KEYS,
    _next_action,
    _phase_headroom_hint,
    build_phase_state,
)


# --------------------------------------------------------------------------- #
# Synthetic iteration rows.
# --------------------------------------------------------------------------- #
def _iter_with_config(config_keys: dict) -> dict:
    """Produce an iteration row whose ``metrics_json`` carries the
    supplied config keys at the ``config.*`` path. Matches the trainer's
    actual emission shape so ``_phase_headroom_hint`` reads it correctly."""
    return {
        "iteration": 1,
        "metrics_json": json.dumps({
            "primary_metric": 0.5,
            "config": dict(config_keys),
        }),
    }


def _iter_with_top_level_keys(keys: dict) -> dict:
    """Iteration row carrying the keys at metrics_json top level (the
    second emission shape the helper accepts — e.g. structured-HPO
    patches that surface keys directly)."""
    return {
        "iteration": 1,
        "metrics_json": json.dumps({"primary_metric": 0.5, **keys}),
    }


# --------------------------------------------------------------------------- #
# _phase_headroom_hint.
# --------------------------------------------------------------------------- #
def test_headroom_hint_high_for_fresh_phase() -> None:
    """No iterations → no keys touched → all phases are fresh."""
    assert _phase_headroom_hint("tabular_sweeps", []) == "high"
    assert _phase_headroom_hint("calibration_replay_gates", []) == "high"


def test_headroom_hint_low_when_all_sweep_keys_touched() -> None:
    """Cover every primary key for tabular_sweeps — hint must be ``low``."""
    keys = _PHASE_PRIMARY_SWEEP_KEYS["tabular_sweeps"]
    rows = [_iter_with_config({k: "anything"}) for k in keys]
    assert _phase_headroom_hint("tabular_sweeps", rows) == "low"


def test_headroom_hint_medium_for_partial_coverage() -> None:
    """One key out of four touched → partial → medium."""
    rows = [_iter_with_config({"direction_pct_threshold": 0.03})]
    assert _phase_headroom_hint("tabular_sweeps", rows) == "medium"


def test_headroom_hint_medium_for_phase_without_sweep_keys() -> None:
    """Phases like ``baseline_capture`` / ``inference_parity_replay``
    aren't in the sweep-keys map → default to medium so the suffix
    gate doesn't fire on phases where it would be meaningless."""
    assert _phase_headroom_hint("baseline_capture", []) == "medium"
    assert _phase_headroom_hint("inference_parity_replay", []) == "medium"


def test_headroom_hint_accepts_top_level_keys_too() -> None:
    """Iterations that surface the sweep key at metrics_json top level
    (instead of under ``config.*``) must still register as touched."""
    # Option A (2026-06-11): meta_model was removed from the phase's sweep
    # keys (score-inert — the meta-stacker is never served); the served
    # model's calibration_method is the phase's ONLY key now
    # (threshold_strategy / horizon_ensemble_* also removed as score-inert).
    rows = [_iter_with_top_level_keys({"calibration_method": "beta"})]
    # The single phase key registered as touched via a top-level
    # metrics_json key → full coverage → low. (Were top-level detection
    # broken, this would report "high".)
    assert _phase_headroom_hint("calibration_replay_gates", rows) == "low"


def test_headroom_hint_handles_malformed_metrics_json() -> None:
    """A row with non-JSON / non-dict metrics_json must not crash —
    diagnostic helper must be defensive."""
    rows: list[dict[str, Any]] = [

        {"iteration": 1, "metrics_json": "not-valid-json"},
        {"iteration": 2, "metrics_json": None},
        {"iteration": 3},  # no metrics_json at all
    ]
    assert _phase_headroom_hint("tabular_sweeps", rows) == "high"


# --------------------------------------------------------------------------- #
# build_phase_state surfaces headroom_hint per phase.
# --------------------------------------------------------------------------- #
def test_phase_entries_carry_headroom_hint() -> None:
    session = {"id": "res_test", "model_type": "direction", "max_iterations": 50}
    state = build_phase_state(session=session, iterations=[])
    assert state["phases"], "phase list empty"
    for phase in state["phases"]:
        assert "headroom_hint" in phase, phase["id"]
        assert phase["headroom_hint"] in {"low", "medium", "high"}


def test_phase_entries_reflect_partial_coverage_via_state() -> None:
    """End-to-end: feed iterations that touch one sweep key for
    tabular_sweeps; assert the state's tabular_sweeps entry reports
    headroom_hint = medium while other phases stay at their defaults."""
    session = {"id": "res_test", "model_type": "direction", "max_iterations": 50}
    rows = [_iter_with_config({"direction_pct_threshold": 0.04})]
    state = build_phase_state(session=session, iterations=rows)
    hints = {p["id"]: p["headroom_hint"] for p in state["phases"]}
    assert hints["tabular_sweeps"] == "medium"
    # Phases not in the sweep-keys map default to medium too.
    assert hints["baseline_capture"] == "medium"
    # calibration_replay_gates uses different sweep keys — its hint should
    # still be "high" since the iteration didn't touch any of them.
    assert hints["calibration_replay_gates"] == "high"


# --------------------------------------------------------------------------- #
# _next_action appends the headroom suffix when budget tight + hint low.
# --------------------------------------------------------------------------- #
def _direction_phases_stub():
    """Minimal phase list mirroring research_phase_plan.DIRECTION_PHASES
    for unit-test isolation."""
    return [
        {"id": "tabular_sweeps", "next_action": "Sweep tabular settings."},
        {"id": "calibration_replay_gates", "next_action": "Run cal/replay gates."},
    ]


def test_next_action_appends_low_hint_suffix_when_budget_tight() -> None:
    """Active phase is low-headroom AND only 20% of budget remaining →
    suffix must appear."""
    action = _next_action(
        _direction_phases_stub(),
        current_phase="tabular_sweeps",
        blocked=None,
        headroom_hint="low",
        iterations_remaining=10,
        max_iterations=50,
    )
    assert "[headroom_hint: low" in action
    assert "consider advancing" in action


def test_next_action_omits_suffix_when_budget_ample() -> None:
    """Low-headroom hint but plenty of budget remaining → no suffix
    (early-session agent shouldn't skip phases on a low hint alone)."""
    action = _next_action(
        _direction_phases_stub(),
        current_phase="tabular_sweeps",
        blocked=None,
        headroom_hint="low",
        iterations_remaining=40,
        max_iterations=50,
    )
    assert "headroom_hint" not in action


def test_next_action_omits_suffix_when_hint_not_low() -> None:
    """High / medium hints don't trigger the suffix even at tight budget."""
    for hint in ("high", "medium"):
        action = _next_action(
            _direction_phases_stub(),
            current_phase="tabular_sweeps",
            blocked=None,
            headroom_hint=hint,
            iterations_remaining=5,
            max_iterations=50,
        )
        assert "headroom_hint" not in action, hint


def test_next_action_omits_suffix_when_no_budget_context() -> None:
    """``iterations_remaining=None`` (e.g. when build_phase_state was
    called from a path that doesn't know the budget) must skip the
    suffix gate — the per-phase ``headroom_hint`` field still surfaces
    on the state, just no nudge in the action text."""
    action = _next_action(
        _direction_phases_stub(),
        current_phase="tabular_sweeps",
        blocked=None,
        headroom_hint="low",
        iterations_remaining=None,
        max_iterations=50,
    )
    assert "headroom_hint" not in action


def test_next_action_suffix_combines_with_blocker_advisory() -> None:
    """When a blocker is present AND the active phase is low-headroom
    AND budget is tight, both notes appear — blocker first, hint after."""
    action = _next_action(
        _direction_phases_stub(),
        current_phase="tabular_sweeps",
        blocked="some_consistency_blocker",
        headroom_hint="low",
        iterations_remaining=10,
        max_iterations=50,
    )
    assert "some_consistency_blocker" in action
    assert "[headroom_hint: low" in action