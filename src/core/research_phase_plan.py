"""Phase-state helpers for autoresearch sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


DIRECTION_PHASES: List[Dict[str, str]] = [
    {
        "id": "baseline_capture",
        "label": "Baseline Capture",
        "next_action": "Run the immutable baseline config and record the first server-owned attempt.",
    },
    {
        "id": "tabular_sweeps",
        "label": "Tabular Sweeps",
        "next_action": "Sweep bounded tabular roster, horizon, dead-zone, calibration, and threshold settings.",
    },
    {
        "id": "adaptive_feature_sweeps",
        "label": "Adaptive Feature Sweeps",
        "next_action": "Compare adaptive support/resistance and cycle feature variants against the tabular baseline.",
    },
    {
        "id": "tsfm_sweeps",
        "label": "TS-FM Sweeps",
        "next_action": "Evaluate allowed TS-FM probability adapter candidates with tabular fallback preserved.",
    },
    {
        "id": "calibration_replay_gates",
        "label": "Calibration/Replay Gates",
        "next_action": "Run full calibration diagnostics and post-cost replay gates on finalists.",
    },
    {
        "id": "rl_finalist_retraining",
        "label": "RL Finalist Retraining",
        "next_action": "Retrain RL finalists only with honest candidate direction probability streams.",
    },
    {
        "id": "multi_seed_robustness",
        "label": "Multi-Seed Robustness",
        "next_action": "Confirm finalist stability across configured seed trials.",
    },
    {
        "id": "inference_parity_replay",
        "label": "Inference Parity Replay",
        "next_action": "Validate feature parity, adapter loading, composite reload, latency, and rollback readiness.",
    },
    {
        "id": "promotion_proposal",
        "label": "Promotion Proposal",
        "next_action": "Prepare a development-scoped promotion proposal with ownership and rollback metadata.",
    },
]


FALLBACK_PHASES: List[Dict[str, str]] = [
    {
        "id": "baseline_capture",
        "label": "Baseline Capture",
        "next_action": "Run the baseline config and record the first server-owned attempt.",
    },
    {
        "id": "hpo_screening",
        "label": "HPO Screening",
        "next_action": "Run or inspect bounded HPO trials when enabled.",
    },
    {
        "id": "validation",
        "label": "Validation",
        "next_action": "Validate candidate metrics and gates against the manifest budget.",
    },
    {
        "id": "promotion_proposal",
        "label": "Promotion Proposal",
        "next_action": "Prepare a development-scoped promotion proposal when gates pass.",
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


# Maps each phase id to the metrics_json evidence keys whose presence in an
# iteration marks that phase as having produced output.  Mirrors the logic in
# _completed_phase_ids() so both stay in sync.
_PHASE_ADVANCEMENT_KEYS: Dict[str, tuple] = {
    "baseline_capture": (),
    "tabular_sweeps": (),
    "hpo_screening": (),
    "validation": (),
    "adaptive_feature_sweeps": ("adaptive_features", "adaptive_feature_version"),
    "tsfm_sweeps": ("tsfm", "tsfm_adapter", "tsfm_fallback_validation"),
    "calibration_replay_gates": ("calibration_full_validation", "economic_replay"),
    "rl_finalist_retraining": ("rl_oos", "direction_probability_provenance"),
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
    completed: set[str] = set()
    if iterations:
        completed.add("baseline_capture")
    if hpo_studies:
        completed.add("hpo_screening")
    if len(iterations) >= 2:
        completed.add("tabular_sweeps")
        completed.add("validation")
    if any(_has_metric(it, "adaptive_features", "adaptive_feature_version") for it in iterations):
        completed.add("adaptive_feature_sweeps")
    if any(_has_metric(it, "tsfm", "tsfm_adapter", "tsfm_fallback_validation") for it in iterations):
        completed.add("tsfm_sweeps")
    if any(_has_metric(it, "calibration_full_validation", "economic_replay") for it in iterations):
        completed.add("calibration_replay_gates")
    if any(_has_metric(it, "rl_oos", "direction_probability_provenance") for it in iterations):
        completed.add("rl_finalist_retraining")
    if any(_has_metric(it, "seed_trials", "n_seed_trials", "seeds_passed_gates") for it in iterations):
        completed.add("multi_seed_robustness")
    if any(_has_metric(it, "inference_parity", "inference_reload_validation") for it in iterations):
        completed.add("inference_parity_replay")
    if _has_promotion_evidence(iterations, promotions):
        completed.add("promotion_proposal")
    return completed


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
    phases: List[Dict[str, str]],
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
    phases: List[Dict[str, str]],
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
    phases: List[Dict[str, str]],
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
    phases: List[Dict[str, str]],
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
