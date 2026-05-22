"""Fix D/G: terminal-phase contract.

The terminal phase (`promotion_proposal`) used to stay `in_progress` forever
once reached — even with its evidence satisfied — because `_phase_status`
special-cased the current phase. `incomplete_phase_ids` then always listed it
and the end-turn guard nudged the agent into another doomed experiment. These
tests pin the corrected behaviour and the separated in-phase / stall counters.
"""
from __future__ import annotations

from src.core.research_phase_plan import (
    DIRECTION_PHASES,
    _next_action,
    _phase_status,
    build_phase_state,
    incomplete_phase_ids,
)


def _terminal_id() -> str:
    return DIRECTION_PHASES[-1]["id"]


def test_terminal_phase_completed_when_evidence_satisfied() -> None:
    terminal = _terminal_id()
    completed = {p["id"] for p in DIRECTION_PHASES}  # everything done
    # _select_current_phase returns the terminal phase when all are complete.
    assert _phase_status(terminal, terminal, completed, None, DIRECTION_PHASES) == "completed"


def test_terminal_phase_blocked_takes_priority() -> None:
    terminal = _terminal_id()
    completed = {p["id"] for p in DIRECTION_PHASES}
    assert (
        _phase_status(terminal, terminal, completed, "weak_calibration", DIRECTION_PHASES)
        == "blocked"
    )


def test_terminal_phase_in_progress_when_not_yet_complete() -> None:
    terminal = _terminal_id()
    # Terminal is current but NOT in the completed set → still in_progress.
    assert _phase_status(terminal, terminal, set(), None, DIRECTION_PHASES) == "in_progress"


def test_next_action_directs_stop_when_all_complete() -> None:
    action = _next_action(
        DIRECTION_PHASES, _terminal_id(), None, all_phases_complete=True
    )
    assert "TERMINATE_REQUEST" in action
    assert "STOP" in action.upper()
    assert "do not run more" in action.lower() or "do not run another" in action.lower()


def test_in_phase_counter_excludes_other_phases() -> None:
    """iterations_in_current_phase counts only rows tagged to the current
    phase — not every iteration in the session (the old, misleading behaviour
    that fed the agent's 'exceeded cap' panic)."""
    session = {"id": "res_test", "model_type": "direction"}
    iterations = [
        {"iteration": 1, "search_phase": "baseline_capture", "primary_metric": 0.5,
         "all_gates_passed": True, "decision": "keep"},
        {"iteration": 2, "search_phase": "tabular_sweeps", "primary_metric": 0.6,
         "all_gates_passed": True, "decision": "keep",
         "metrics_json": '{"tabular_sweep_variant": "v1"}'},
        {"iteration": 3, "search_phase": "tabular_sweeps", "primary_metric": 0.61,
         "all_gates_passed": True, "decision": "keep",
         "metrics_json": '{"tabular_sweep_variant": "v2"}'},
    ]
    state = build_phase_state(session=session, iterations=iterations)
    current = state["current_phase"]
    expected_in_phase = sum(
        1 for it in iterations if (it.get("search_phase") or "") == current
    )
    assert state["iterations_in_current_phase"] == expected_in_phase
    assert state["iterations_in_current_phase"] != len(iterations)
    # The stall signal is preserved under its own key.
    assert "stalled_iterations" in state
    assert "all_phases_complete" in state


def test_incomplete_phase_ids_empty_when_terminal_complete() -> None:
    """When the terminal phase reports completed, incomplete_phase_ids is empty
    so the end-turn guard honours a clean stop."""
    phases = [
        {"id": "a", "label": "A", "status": "completed"},
        {"id": "b", "label": "B", "status": "completed"},
    ]
    assert incomplete_phase_ids({"phases": phases}) == []
    phases[1]["status"] = "in_progress"
    assert incomplete_phase_ids({"phases": phases}) == ["b"]
