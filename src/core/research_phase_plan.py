"""Phase-state helpers for autoresearch sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


# Direction-research phase plan.
#
# Each entry carries `min_iterations` (a soft floor enforced when phase advance
# depends purely on iteration cardinality, used by phases that do not emit a
# specific evidence key) and `max_iterations` (a hard ceiling used by the
# orchestrator loop guard to prevent the agent from burning the entire budget
# inside a single phase, see F7 in AUTORESEARCH-PHASE-COVERAGE-res_0efe45aaa28f.md).
#
# NOTE: `rl_finalist_retraining` is intentionally absent from direction
# research. That phase trains a downstream RL agent that consumes direction
# probabilities and belongs in the RL autotuner. Coupling it here forced the
# direction loop to wait on RL training and conflated failure modes.
DIRECTION_PHASES: List[Dict[str, Any]] = [
    {
        "id": "baseline_capture",
        "label": "Baseline Capture",
        "next_action": "Run the immutable baseline config and record the first server-owned attempt.",
        "min_iterations": 1,
        "max_iterations": 3,
    },
    {
        "id": "tabular_sweeps",
        "label": "Tabular Sweeps",
        "next_action": "Sweep bounded tabular roster, horizon, dead-zone, calibration, and threshold settings. Emit metrics.tabular_sweep_variant on each attempt so the phase advances.",
        "min_iterations": 6,
        "max_iterations": 40,
    },
    {
        "id": "adaptive_feature_sweeps",
        "label": "Adaptive Feature Sweeps",
        "next_action": "Compare adaptive support/resistance and cycle feature variants against the tabular baseline. Emit metrics.adaptive_features or adaptive_feature_version so the phase advances.",
        "min_iterations": 4,
        "max_iterations": 30,
    },
    {
        "id": "tsfm_sweeps",
        "label": "TS-FM Sweeps",
        "next_action": "Evaluate allowed TS-FM probability adapter candidates with tabular fallback preserved. Emit metrics.tsfm_adapter or tsfm_fallback_validation so the phase advances.",
        "min_iterations": 2,
        "max_iterations": 15,
    },
    {
        "id": "calibration_replay_gates",
        "label": "Calibration/Replay Gates",
        "next_action": "Run full calibration diagnostics and post-cost replay gates on finalists. Emit metrics.calibration_full_validation and metrics.economic_replay.",
        "min_iterations": 1,
        "max_iterations": 8,
    },
    {
        "id": "multi_seed_robustness",
        "label": "Multi-Seed Robustness",
        "next_action": "Confirm finalist stability across configured seed trials. Emit metrics.seed_trials or seeds_passed_gates.",
        "min_iterations": 1,
        "max_iterations": 6,
    },
    {
        "id": "inference_parity_replay",
        "label": "Inference Parity Replay",
        "next_action": "Validate feature parity, adapter loading, composite reload, latency, and rollback readiness. Emit metrics.inference_parity or inference_reload_validation.",
        "min_iterations": 1,
        "max_iterations": 4,
    },
    {
        "id": "promotion_proposal",
        "label": "Promotion Proposal",
        "next_action": "Prepare a development-scoped promotion proposal with ownership and rollback metadata.",
        "min_iterations": 0,
        "max_iterations": 4,
    },
]


FALLBACK_PHASES: List[Dict[str, Any]] = [
    {
        "id": "baseline_capture",
        "label": "Baseline Capture",
        "next_action": "Run the baseline config and record the first server-owned attempt.",
        "min_iterations": 1,
        "max_iterations": 3,
    },
    {
        "id": "hpo_screening",
        "label": "HPO Screening",
        "next_action": "Run or inspect bounded HPO trials when enabled.",
        "min_iterations": 1,
        "max_iterations": 20,
    },
    {
        "id": "validation",
        "label": "Validation",
        "next_action": "Validate candidate metrics and gates against the manifest budget.",
        "min_iterations": 2,
        "max_iterations": 10,
    },
    {
        "id": "promotion_proposal",
        "label": "Promotion Proposal",
        "next_action": "Prepare a development-scoped promotion proposal when gates pass.",
        "min_iterations": 0,
        "max_iterations": 4,
    },
]


def build_phase_state(
    *,
    session: Dict[str, Any],
    iterations: Iterable[Dict[str, Any]],
    hpo_studies: Optional[Iterable[Dict[str, Any]]] = None,
    promotions: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Derive an operator-facing phase plan and next action."""

    rows = list(iterations)
    studies = list(hpo_studies or [])
    promotion_rows = list(promotions or [])
    model_type = session.get("model_type")
    phases = DIRECTION_PHASES if model_type == "direction" else FALLBACK_PHASES

    completed = _completed_phase_ids(rows, studies, promotion_rows, model_type)
    blocked = _blocked_reason(rows)
    current_phase = _select_current_phase(phases, completed, blocked)
    next_action = _next_action(phases, current_phase, blocked)
    stalled_count = _count_stalled_iterations(rows, phases, current_phase)

    return {
        "schema_version": "autoresearch_phase_state.v1",
        "research_id": session.get("id"),
        "model_type": model_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_phase": current_phase,
        "next_action": next_action,
        "blocked": blocked is not None,
        "block_reason": blocked,
        "iterations_in_current_phase": stalled_count,
        "phases": [
            {
                **phase,
                "status": _phase_status(phase["id"], current_phase, completed, blocked, phases),
            }
            for phase in phases
        ],
    }


def phase_state_json(state: Dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True)


def phases_for_model(model_type: Optional[str]) -> List[Dict[str, Any]]:
    """Return the canonical phase list for the given model_type."""
    return DIRECTION_PHASES if model_type == "direction" else FALLBACK_PHASES


def incomplete_phase_ids(state: Dict[str, Any]) -> List[str]:
    """Return phase ids whose status is not 'completed' in a built state."""
    phases = state.get("phases") or []
    return [
        str(p.get("id"))
        for p in phases
        if isinstance(p, dict) and p.get("status") != "completed" and p.get("id")
    ]


def phase_cap_exceeded(
    state: Dict[str, Any],
    iterations_in_phase: int,
) -> bool:
    """True when the active phase's `max_iterations` cap has been reached.

    F7 hook: orchestrator passes how many iterations have been recorded under
    the current phase via search_phase tagging; once that exceeds the cap, the
    orchestrator should nudge the LLM to advance even if it has not yet
    emitted the phase's evidence key.
    """
    current_id = state.get("current_phase")
    if not current_id:
        return False
    phases = state.get("phases") or []
    for phase in phases:
        if isinstance(phase, dict) and phase.get("id") == current_id:
            cap = phase.get("max_iterations")
            if isinstance(cap, int) and cap > 0:
                return iterations_in_phase >= cap
            return False
    return False


# Maps each phase id to the metrics_json evidence keys whose presence in an
# iteration marks that phase as having produced output.  Mirrors the logic in
# _completed_phase_ids() so both stay in sync.
#
# F3: `tabular_sweeps` previously had no evidence key and so was marked done by
# pure cardinality. We now require an explicit `tabular_sweep_variant`
# (or any of the historical canonical knobs `roster_preset`,
# `direction_pct_threshold`, `deadzone_width`, `calibration_method`) in the
# config or metrics payload, so the phase only completes when the LLM has
# actually explored the sweep space.
_PHASE_ADVANCEMENT_KEYS: Dict[str, tuple] = {
    "baseline_capture": (),
    "tabular_sweeps": (
        "tabular_sweep_variant",
        "roster_preset",
        "direction_pct_threshold",
        "deadzone_width",
        "calibration_method",
    ),
    "hpo_screening": (),
    "validation": (),
    "adaptive_feature_sweeps": ("adaptive_features", "adaptive_feature_version"),
    "tsfm_sweeps": ("tsfm", "tsfm_adapter", "tsfm_fallback_validation"),
    "calibration_replay_gates": ("calibration_full_validation", "economic_replay"),
    "multi_seed_robustness": ("seed_trials", "n_seed_trials", "seeds_passed_gates"),
    "inference_parity_replay": ("inference_parity", "inference_reload_validation"),
    "promotion_proposal": (
        "development_promotion_metadata",
        "promotion_allowed",
        "promotion_consistency_report",
        "promotion_decision",
        "promotion_metadata",
        "promotion_preview_ready",
        "promotion_scope",
        "scoped_promotion_metadata",
    ),
}


def _completed_phase_ids(
    iterations: List[Dict[str, Any]],
    hpo_studies: List[Dict[str, Any]],
    promotions: List[Dict[str, Any]],
    model_type: Optional[str],
) -> set[str]:
    """Mark phases complete using a hybrid contract:

    1. Any phase listed in ``_PHASE_ADVANCEMENT_KEYS`` is complete iff at least
       one iteration emitted that evidence key (in metrics or config).
    2. Phases without evidence keys (baseline_capture, hpo_screening,
       validation) fall back to cardinality with a stricter minimum than the
       legacy `>=2` rule. Baseline still completes on the first attempt;
       validation requires at least two attempts.
    3. F3 fix: `tabular_sweeps` no longer auto-completes after 2 iterations.
       It now requires either an explicit sweep variant key or the
       per-phase ``min_iterations`` floor matched by attempts that explicitly
       tagged ``search_phase == "tabular_sweeps"``. This prevents the phase
       plan from racing ahead of the LLM's actual exploration.
    """

    completed: set[str] = set()
    if iterations:
        completed.add("baseline_capture")
    if hpo_studies:
        completed.add("hpo_screening")
    if len(iterations) >= 2:
        completed.add("validation")

    # Tabular sweeps: evidence key OR phase-tagged minimum effort.
    tabular_iters = _iterations_in_phase(iterations, "tabular_sweeps")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["tabular_sweeps"]) for it in iterations):
        completed.add("tabular_sweeps")
    elif len(tabular_iters) >= 6:
        completed.add("tabular_sweeps")

    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["adaptive_feature_sweeps"]) for it in iterations):
        completed.add("adaptive_feature_sweeps")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["tsfm_sweeps"]) for it in iterations):
        completed.add("tsfm_sweeps")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["calibration_replay_gates"]) for it in iterations):
        completed.add("calibration_replay_gates")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["multi_seed_robustness"]) for it in iterations):
        completed.add("multi_seed_robustness")
    if any(_has_metric(it, *_PHASE_ADVANCEMENT_KEYS["inference_parity_replay"]) for it in iterations):
        completed.add("inference_parity_replay")
    if _has_promotion_evidence(iterations, promotions):
        completed.add("promotion_proposal")
    return completed


def _iterations_in_phase(
    iterations: List[Dict[str, Any]],
    phase_id: str,
) -> List[Dict[str, Any]]:
    """Return iterations whose ``search_phase`` column matches ``phase_id``.

    Iterations without a phase tag are ignored. The orchestrator started
    stamping ``search_phase`` on every record in F2; older sessions will
    return empty lists here and fall through to evidence-key checks.
    """
    return [it for it in iterations if (it.get("search_phase") or "") == phase_id]


def _has_promotion_evidence(
    iterations: List[Dict[str, Any]],
    promotions: List[Dict[str, Any]],
) -> bool:
    if promotions:
        return True
    evidence_keys = (
        "development_promotion_metadata",
        "promotion_allowed",
        "promotion_consistency_report",
        "promotion_decision",
        "promotion_metadata",
        "promotion_preview_ready",
        "promotion_scope",
        "scoped_promotion_metadata",
    )
    return any(_has_metric(row, *evidence_keys) for row in iterations)


def _select_current_phase(
    phases: List[Dict[str, Any]],
    completed: set[str],
    blocked: Optional[str],
) -> str:
    # Always select the first incomplete phase, regardless of any consistency
    # blocker on the last iteration.  Blockers are surfaced in next_action as
    # advisory context rather than overriding the phase pointer, so the LLM
    # always receives forward-looking phase guidance.
    for phase in phases:
        if phase["id"] not in completed:
            return phase["id"]
    return phases[-1]["id"]


def _phase_status(
    phase_id: str,
    current_phase: str,
    completed: set[str],
    blocked: Optional[str],
    phases: List[Dict[str, Any]],
) -> str:
    if phase_id in completed and phase_id != current_phase:
        return "completed"
    if phase_id == current_phase:
        # Mark "blocked" only when we are at the terminal promotion phase and
        # consistency gates are preventing promotion.  Mid-pipeline phases
        # stay "in_progress" so the agent receives forward-looking guidance
        # rather than a dead-end blocked status.
        is_terminal = bool(phases) and phase_id == phases[-1]["id"]
        if blocked and is_terminal:
            return "blocked"
        return "in_progress"
    return "pending"


def _next_action(
    phases: List[Dict[str, Any]],
    current_phase: str,
    blocked: Optional[str],
) -> str:
    is_terminal = bool(phases) and current_phase == phases[-1]["id"]
    base = next(
        (p["next_action"] for p in phases if p["id"] == current_phase),
        "Inspect session state.",
    )
    if not blocked:
        return base
    if is_terminal:
        # At the final phase the blocker IS the primary concern — promotion
        # cannot proceed until it is resolved.
        return f"{base} Resolve consistency blockers first: {blocked}"
    # Mid-pipeline: append as an advisory note.  The phase's own action
    # takes priority so the agent knows WHAT to run next.
    return f"{base} (Advisory — last attempt has consistency notes: {blocked})"


def _count_stalled_iterations(
    rows: List[Dict[str, Any]],
    phases: List[Dict[str, Any]],
    current_phase: str,
) -> int:
    """Return how many consecutive trailing iterations produced no later-phase evidence.

    When this count is high the agent is stuck: it keeps running experiments
    for the current phase without producing the metrics keys that would advance
    the phase plan forward.  Callers can surface this as a stall warning in the
    iteration context digest.
    """
    current_idx = next(
        (i for i, p in enumerate(phases) if p["id"] == current_phase),
        len(phases) - 1,
    )
    # Collect all advancement keys for phases strictly AFTER the current one.
    later_keys: tuple = tuple(
        key
        for phase in phases[current_idx + 1 :]
        for key in _PHASE_ADVANCEMENT_KEYS.get(phase["id"], ())
    )
    if not later_keys:
        # Already at the terminal phase — every iteration contributed here.
        return len(rows)

    count = 0
    for row in reversed(rows):
        if _has_metric(row, *later_keys):
            break
        count += 1
    return count


def _blocked_reason(iterations: List[Dict[str, Any]]) -> Optional[str]:
    if not iterations:
        return None
    latest = iterations[-1]
    report = _parse_json(latest.get("consistency_report_json"))
    if isinstance(report, dict) and report.get("passed") is False:
        blockers = report.get("blockers") or []
        if blockers:
            return "Consistency gate failed: " + ", ".join(str(b) for b in blockers[:4])
    return None


def _has_metric(iteration: Dict[str, Any], *keys: str) -> bool:
    payload = _parse_json(iteration.get("metrics_json"))
    if not isinstance(payload, dict):
        return False
    containers = [payload]
    config = payload.get("config")
    if isinstance(config, dict):
        containers.append(config)
    return any(any(key in container for key in keys) for container in containers)


def _parse_json(raw: Any) -> Any:
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw
