"""Operator-facing autoresearch state summaries."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from server.core.consistency_validator import parse_consistency_report
from server.core.research_phase_plan import build_phase_state


def build_research_state(
    *,
    session: Dict[str, Any],
    iterations: Iterable[Dict[str, Any]],
    hpo_studies: Iterable[Dict[str, Any]],
    promotions: Iterable[Dict[str, Any]],
    planned_trials: Iterable[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    """Build a reconstructable state payload without reading workspace files."""

    iteration_rows = list(iterations)
    study_rows = [_decode_hpo_study(row) for row in hpo_studies]
    planned_trial_rows = [_decode_planned_trial(row) for row in planned_trials]
    promotion_rows = list(promotions)
    executed_iteration_rows = [
        row for row in iteration_rows
        if not _is_duplicate_rejection(row)
    ]
    phase_state = _session_phase_state(session) or build_phase_state(
        session=session,
        iterations=iteration_rows,
        hpo_studies=study_rows,
        promotions=promotion_rows,
    )
    top_candidates = _top_candidates(iteration_rows)
    failed = _failed_or_pruned(iteration_rows)
    latest_promotion = _latest_promotion(session, promotion_rows)

    return {
        "schema_version": "autoresearch_state.v1",
        "research_id": session.get("id"),
        "model_type": session.get("model_type"),
        "status": session.get("status"),
        "current_phase": phase_state.get("current_phase"),
        "next_action": phase_state.get("next_action"),
        "phase_state": phase_state,
        "top_candidates": top_candidates,
        "failed_pruned_configs": failed,
        "duplicate_rejections": _duplicate_rejections(iteration_rows),
        "gate_failure_reasons": _gate_failure_reasons(iteration_rows),
        "budget_usage": {
            "api_cost_usd": session.get("total_api_cost_usd") or 0.0,
            "max_budget_usd": session.get("max_budget_usd"),
            "iterations_used": len(executed_iteration_rows),
            "max_iterations": session.get("max_iterations"),
        },
        "hpo_studies": study_rows,
        "hpo_study_ids": [row.get("study_id") or row.get("id") for row in study_rows],
        "planned_trials": planned_trial_rows,
        "search_plan": _search_plan_summary(study_rows, planned_trial_rows),
        "artifact_hashes": _artifact_hashes(iteration_rows),
        "mlflow_links": _mlflow_links(iteration_rows),
        "promoted_version": latest_promotion,
        "rollback_target": _rollback_target(latest_promotion),
        "smoke_status": _metadata_field(latest_promotion, "smoke_validation"),
        "paper_status": _paper_status(latest_promotion),
    }


def _session_phase_state(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = session.get("phase_state_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return raw if isinstance(raw, dict) else None


def _top_candidates(iterations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = [
        row for row in iterations
        if row.get("primary_metric") is not None
        and row.get("decision") in {"keep", "improve", "hpo_screening"}
    ]
    candidates.sort(key=lambda row: row.get("primary_metric") or float("-inf"), reverse=True)
    return [_candidate_summary(row) for row in candidates[:5]]


def _failed_or_pruned(iterations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for row in iterations:
        if _is_duplicate_rejection(row):
            continue
        metrics = _parse_json(row.get("metrics_json")) or {}
        status = metrics.get("status")
        if row.get("decision") == "discard" or status in {"failed", "error", "timeout", "pruned", "crash"}:
            rows.append(_candidate_summary(row))
    return rows


def _candidate_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    metrics = _parse_json(row.get("metrics_json")) or {}
    snapshot = _parse_json(row.get("attempt_snapshot_json")) or metrics.get("attempt_snapshot") or {}
    report = parse_consistency_report(row.get("consistency_report_json"))
    return {
        "iteration": row.get("iteration"),
        "iteration_row_id": row.get("id"),
        "primary_metric": row.get("primary_metric"),
        "metric_name": row.get("metric_name"),
        "decision": row.get("decision"),
        "status": metrics.get("status"),
        "all_gates_passed": bool(row.get("all_gates_passed")),
        "mlflow_run_id": row.get("mlflow_run_id") or metrics.get("mlflow_run_id"),
        "artifact_hash": snapshot.get("artifact_hash") or metrics.get("artifact_hash"),
        "attempt_snapshot_hash": row.get("attempt_snapshot_hash"),
        "canonical_config_hash": (
            row.get("canonical_config_hash")
            or metrics.get("canonical_config_hash")
            or snapshot.get("canonical_config_hash")
        ),
        "trial_identity_hash": (
            row.get("trial_identity_hash")
            or metrics.get("trial_identity_hash")
            or snapshot.get("trial_identity_hash")
        ),
        "trial_identity": _trial_identity(row, metrics, snapshot),
        "duplicate_reason": (
            row.get("duplicate_reason") or metrics.get("duplicate_reason")
        ),
        "duplicate_of": _duplicate_of(row, metrics),
        "consistency_passed": report.get("passed") if report else None,
        "gate_failure_reasons": (report.get("blockers") if report else []),
        "search_phase": row.get("search_phase") or metrics.get("search_phase"),
    }


def _duplicate_rejections(iterations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for row in iterations:
        if _is_duplicate_rejection(row):
            rows.append(_candidate_summary(row))
    return rows


def _is_duplicate_rejection(row: Dict[str, Any]) -> bool:
    metrics = _parse_json(row.get("metrics_json")) or {}
    return bool(
        row.get("duplicate_reason")
        or metrics.get("status") == "rejected_duplicate"
    )


def _gate_failure_reasons(iterations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reasons = []
    for row in iterations:
        report = parse_consistency_report(row.get("consistency_report_json"))
        blockers = report.get("blockers") if report else []
        if blockers:
            reasons.append({"iteration": row.get("iteration"), "blockers": blockers})
    return reasons


def _artifact_hashes(iterations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    artifacts = []
    for row in iterations:
        summary = _candidate_summary(row)
        if summary.get("artifact_hash"):
            artifacts.append(
                {
                    "iteration": summary["iteration"],
                    "artifact_hash": summary["artifact_hash"],
                }
            )
    return artifacts


def _mlflow_links(iterations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    links = []
    for row in iterations:
        metrics = _parse_json(row.get("metrics_json")) or {}
        run_id = row.get("mlflow_run_id") or metrics.get("mlflow_run_id")
        if run_id:
            links.append({"iteration": row.get("iteration"), "mlflow_run_id": run_id})
    return links


def _latest_promotion(
    session: Dict[str, Any],
    promotions: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    sid = session.get("id")
    rows = [row for row in promotions if row.get("research_id") == sid]
    if not rows:
        return None
    rows.sort(key=lambda row: row.get("promoted_at") or "", reverse=True)
    return rows[0]


def _rollback_target(promotion: Optional[Dict[str, Any]]) -> Any:
    if not promotion:
        return None
    metadata = promotion.get("promotion_metadata") or {}
    return metadata.get("rollback_target")


def _metadata_field(promotion: Optional[Dict[str, Any]], key: str) -> Any:
    if not promotion:
        return None
    metadata = promotion.get("promotion_metadata") or {}
    return metadata.get(key)


def _paper_status(promotion: Optional[Dict[str, Any]]) -> Any:
    smoke = _metadata_field(promotion, "smoke_validation")
    if isinstance(smoke, dict):
        return smoke.get("paper_validation")
    return None


def _decode_hpo_study(row: Dict[str, Any]) -> Dict[str, Any]:
    decoded = dict(row)
    for source, target in (
        ("top_trials_json", "top_trials"),
        ("search_space_json", "search_space"),
        ("budget_json", "budget"),
    ):
        raw = decoded.get(source)
        if raw and target not in decoded:
            decoded[target] = _parse_json(raw)
    return decoded


def _decode_planned_trial(row: Dict[str, Any]) -> Dict[str, Any]:
    decoded = dict(row)
    raw = decoded.get("config_patch_json")
    if raw and "config_patch" not in decoded:
        decoded["config_patch"] = _parse_json(raw) or {}
    raw_identity = decoded.get("trial_identity_json")
    if raw_identity and "trial_identity" not in decoded:
        decoded["trial_identity"] = _parse_json(raw_identity)
    return decoded


def _search_plan_summary(
    hpo_studies: List[Dict[str, Any]],
    planned_trials: List[Dict[str, Any]],
) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    for trial in planned_trials:
        status = str(trial.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "study_count": len(hpo_studies),
        "planned_trial_count": sum(
            count for status, count in status_counts.items()
            if status != "manual_review"
        ),
        "manual_review_count": status_counts.get("manual_review", 0),
        "status_counts": status_counts,
        "search_spaces": [
            {
                "study_id": row.get("study_id") or row.get("id"),
                "search_space": row.get("search_space") or {},
                "budget": row.get("budget") or {},
            }
            for row in hpo_studies
        ],
    }


def _parse_json(raw: Any) -> Any:
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def _trial_identity(
    row: Dict[str, Any],
    metrics: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    raw = row.get("trial_identity_json")
    parsed = _parse_json(raw)
    if isinstance(parsed, dict):
        return parsed
    identity = metrics.get("trial_identity")
    if isinstance(identity, dict):
        return identity
    identity = snapshot.get("trial_identity")
    return identity if isinstance(identity, dict) else None


def _duplicate_of(
    row: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    research_id = row.get("duplicate_of_research_id") or metrics.get(
        "duplicate_of_research_id"
    )
    iteration = row.get("duplicate_of_iteration") or metrics.get(
        "duplicate_of_iteration"
    )
    if research_id is None and iteration is None:
        return None
    return {"research_id": research_id, "iteration": iteration}
