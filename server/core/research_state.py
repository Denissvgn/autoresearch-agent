"""Operator-facing autoresearch state summaries."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from server.core.consistency_validator import parse_consistency_report
from server.core.observability import alert_suggestions
from server.core.research_phase_plan import build_phase_state


def build_research_state(
    *,
    session: Dict[str, Any],
    iterations: Iterable[Dict[str, Any]],
    hpo_studies: Iterable[Dict[str, Any]],
    promotions: Iterable[Dict[str, Any]],
    planned_trials: Iterable[Dict[str, Any]] = (),
    audit_events: Iterable[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    """Build a reconstructable state payload without reading workspace files."""

    iteration_rows = list(iterations)
    study_rows = [_decode_hpo_study(row) for row in hpo_studies]
    planned_trial_rows = [_decode_planned_trial(row) for row in planned_trials]
    promotion_rows = list(promotions)
    audit_event_rows = list(audit_events)
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
        "production_operations": _production_operations_summary(
            session=session,
            iterations=iteration_rows,
            promotions=promotion_rows,
            latest_promotion=latest_promotion,
            audit_events=audit_event_rows,
        ),
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
        "rl_profit_score": _rl_profit_score(metrics),
        "rl_economic_replay": _rl_economic_replay_summary(metrics, snapshot),
        "feature_readiness_metrics": _feature_readiness_metrics(metrics),
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
            entry = {
                "iteration": summary["iteration"],
                "artifact_hash": summary["artifact_hash"],
            }
            replay = summary.get("rl_economic_replay")
            if isinstance(replay, dict) and replay.get("artifact_hash"):
                entry["rl_economic_replay_artifact_hash"] = replay["artifact_hash"]
            artifacts.append(entry)
    return artifacts


def _rl_profit_score(metrics: Dict[str, Any]) -> Optional[float]:
    replay = _rl_economic_replay(metrics)
    value = (
        replay.get("rl_profit_score")
        if replay
        else metrics.get("rl_profit_score")
    )
    return _first_number(value, metrics.get("composite_rl_score"))


def _rl_economic_replay_summary(
    metrics: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    replay = _rl_economic_replay(metrics)
    if not replay:
        return None
    replay_metrics = (
        replay.get("metrics")
        if isinstance(replay.get("metrics"), dict)
        else replay.get("post_cost_metrics")
        if isinstance(replay.get("post_cost_metrics"), dict)
        else {}
    )
    return {
        "schema_version": replay.get("schema_version"),
        "rl_profit_score": _first_number(
            replay.get("rl_profit_score"),
            metrics.get("rl_profit_score"),
        ),
        "post_cost_return": _first_number(
            replay_metrics.get("post_cost_return"),
            replay_metrics.get("mean_oos_return"),
            metrics.get("mean_oos_return"),
        ),
        "max_drawdown": _first_number(
            replay_metrics.get("max_drawdown"),
            replay_metrics.get("mean_oos_drawdown"),
            metrics.get("mean_oos_drawdown"),
        ),
        "sharpe": _first_number(
            replay_metrics.get("sharpe"),
            replay_metrics.get("mean_oos_sharpe"),
            metrics.get("mean_oos_sharpe"),
        ),
        "artifact_path": (
            replay.get("artifact_path")
            or metrics.get("rl_economic_replay_artifact_path")
            or snapshot.get("rl_economic_replay_artifact_path")
        ),
        "artifact_hash": (
            replay.get("artifact_hash")
            or replay.get("replay_artifact_hash")
            or metrics.get("rl_economic_replay_artifact_hash")
            or snapshot.get("rl_economic_replay_artifact_hash")
        ),
    }


def _feature_readiness_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    gate_results = metrics.get("gate_results")
    gate_results = gate_results if isinstance(gate_results, dict) else {}
    config = metrics.get("config")
    config = config if isinstance(config, dict) else {}
    calibration = config.get("calibration_full_validation")
    calibration = calibration if isinstance(calibration, dict) else {}
    selected = calibration.get("selected")
    selected = selected if isinstance(selected, dict) else {}
    selected_metrics = selected.get("metrics")
    selected_metrics = selected_metrics if isinstance(selected_metrics, dict) else {}
    result = {
        "auc": _first_number(gate_results.get("direction_auc"), metrics.get("auc")),
        "ece": _first_number(selected_metrics.get("ece"), metrics.get("ece_calibrated")),
        "brier_score": _first_number(
            selected_metrics.get("brier_score"),
            metrics.get("brier_score_calibrated"),
        ),
        "signal_rate": _first_number(
            gate_results.get("operating_signal_rate"),
            metrics.get("signal_rate"),
        ),
    }
    return {key: value for key, value in result.items() if value is not None}


def _rl_economic_replay(metrics: Dict[str, Any]) -> Dict[str, Any]:
    rl_oos = metrics.get("rl_oos") if isinstance(metrics.get("rl_oos"), dict) else {}
    replay = (
        metrics.get("rl_economic_replay")
        or metrics.get("economic_replay")
        or metrics.get("replay")
        or rl_oos.get("rl_economic_replay")
        or rl_oos.get("economic_replay")
    )
    return replay if isinstance(replay, dict) else {}


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


_PROMOTION_SCOPES = ("development", "paper", "canary", "production")
_BLOCKER_LABELS = {
    "development_promotion_not_allowed": "Development promotion gates have not passed.",
    "inference_reload_failed": "Inference reload or parity validation failed.",
    "missing_canary_duration": "Canary validation duration is missing or too short.",
    "missing_canary_promotion": "A canary promotion record is required first.",
    "missing_development_promotion": "A development promotion record is required first.",
    "missing_direction_feature_provenance": "Direction feature provenance is missing.",
    "missing_economic_replay": "Economic replay evidence is missing.",
    "missing_feature_readiness": "Direction and volatility feature readiness evidence is missing.",
    "missing_inference_parity": "Inference parity evidence is missing.",
    "missing_live_risk_limits": "Production risk limits are not configured.",
    "missing_model_card": "A reviewed model card is required.",
    "missing_monitoring_alerts": "Production monitoring and alerts are not configured.",
    "missing_multi_seed_rl_validation": "Multi-seed RL validation is missing.",
    "missing_nested_validation": "Nested or blocked-time RL validation is missing.",
    "missing_paper_promotion": "A paper promotion record is required first.",
    "missing_paper_validation": "Paper trading validation evidence is missing.",
    "missing_production_approval": "Production approval is required.",
    "missing_rl_economic_replay": "RL economic replay evidence is missing.",
    "missing_rl_feature_bundle_hash": "The RL feature bundle hash is missing.",
    "missing_rl_oos_metrics": "RL out-of-sample metrics are missing.",
    "missing_rl_oos_provenance": "RL OOS and feature provenance evidence is missing.",
    "missing_rollback_target": "Rollback target is missing.",
    "missing_scope_approval": "Promotion approval is required for this scope.",
    "missing_volatility_feature_provenance": "Volatility feature provenance is missing.",
    "stale_or_leaked_feature_provenance": "Feature provenance is stale or leaked.",
}


def _production_operations_summary(
    *,
    session: Dict[str, Any],
    iterations: List[Dict[str, Any]],
    promotions: List[Dict[str, Any]],
    latest_promotion: Optional[Dict[str, Any]],
    audit_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    best_row = _best_candidate_row(iterations)
    metrics = _parse_json(best_row.get("metrics_json")) if best_row else {}
    metrics = metrics if isinstance(metrics, dict) else {}
    snapshot = _parse_json(best_row.get("attempt_snapshot_json")) if best_row else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    if not snapshot and isinstance(metrics.get("attempt_snapshot"), dict):
        snapshot = metrics["attempt_snapshot"]

    promotion_blockers = _promotion_blockers(session, latest_promotion)
    scope_status = _promotion_scope_status(
        session=session,
        promotions=promotions,
        best_row=best_row,
        promotion_blockers=promotion_blockers,
    )
    rl_replay = _rl_replay_status(metrics, snapshot)
    feature_readiness = _supervised_feature_readiness_status(
        session=session,
        metrics=metrics,
    )
    rl_oos = _rl_oos_provenance_status(
        model_type=session.get("model_type"),
        metrics=metrics,
    )
    inference = _inference_parity_status(metrics, latest_promotion)
    rollback = _rollback_status(
        latest_promotion=latest_promotion,
        metrics=metrics,
    )
    warnings = _operations_warnings(
        session=session,
        promotion_blockers=promotion_blockers,
        scope_status=scope_status,
        rl_replay=rl_replay,
        feature_readiness=feature_readiness,
        rl_oos=rl_oos,
        inference=inference,
        rollback=rollback,
    )

    return {
        "schema_version": "autoresearch_production_operations.v1",
        "research_id": session.get("id"),
        "model_type": session.get("model_type"),
        "candidate": _operations_candidate(best_row, metrics, snapshot),
        "promotion": {
            "blocked": bool(promotion_blockers),
            "blockers": promotion_blockers,
            "blocker_details": _blocker_details(promotion_blockers),
            "latest_scope": (
                latest_promotion.get("scope") if latest_promotion else None
            ),
            "latest_record": _compact_promotion(latest_promotion),
            "scopes": scope_status,
        },
        "warnings": warnings,
        "rl_profit": rl_replay,
        "feature_readiness": feature_readiness,
        "oos_provenance": rl_oos,
        "inference_parity": inference,
        "rollback": rollback,
        "observability": {
            "metrics_endpoint": "/metrics",
            "alert_suggestions": alert_suggestions(),
            "trace_fields": [
                "research_id",
                "pipeline_id",
                "phase",
                "trial_id",
                "promotion_id",
            ],
        },
        "audit_events": _compact_audit_events(audit_events),
    }


def _best_candidate_row(iterations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not iterations:
        return None
    candidates = [row for row in iterations if row.get("primary_metric") is not None]
    passing = [row for row in candidates if row.get("all_gates_passed")]
    pool = passing or candidates
    if pool:
        return max(pool, key=lambda row: row.get("primary_metric") or float("-inf"))
    return iterations[-1]


def _operations_candidate(
    row: Optional[Dict[str, Any]],
    metrics: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "iteration": row.get("iteration"),
        "primary_metric": row.get("primary_metric"),
        "metric_name": row.get("metric_name"),
        "all_gates_passed": bool(row.get("all_gates_passed")),
        "decision": row.get("decision"),
        "search_phase": row.get("search_phase") or metrics.get("search_phase"),
        "config_snapshot_sha256": snapshot.get("config_snapshot_sha256"),
        "attempt_snapshot_hash": row.get("attempt_snapshot_hash")
        or snapshot.get("snapshot_hash"),
        "artifact_hash": snapshot.get("artifact_hash")
        or metrics.get("artifact_hash")
        or metrics.get("model_artifact_hash"),
        "mlflow_run_id": row.get("mlflow_run_id") or metrics.get("mlflow_run_id"),
    }


def _promotion_blockers(
    session: Dict[str, Any],
    latest_promotion: Optional[Dict[str, Any]],
) -> List[str]:
    blockers: List[str] = []
    for value in (
        session.get("promotion_blockers"),
        _parse_json(session.get("promotion_blockers_json")),
    ):
        if isinstance(value, list):
            blockers.extend(str(item) for item in value if item)

    preview = session.get("promotion_preview")
    if preview is None:
        preview = _parse_json(session.get("promotion_preview_json"))
    if isinstance(preview, dict):
        raw = preview.get("blockers") or preview.get("promotion_blockers")
        if isinstance(raw, list):
            blockers.extend(str(item) for item in raw if item)

    metadata = (latest_promotion or {}).get("promotion_metadata") or {}
    if isinstance(metadata, dict) and metadata.get("promotion_allowed") is False:
        raw = metadata.get("blockers")
        if isinstance(raw, list):
            blockers.extend(str(item) for item in raw if item)
    return _unique_strings(blockers)


def _promotion_scope_status(
    *,
    session: Dict[str, Any],
    promotions: List[Dict[str, Any]],
    best_row: Optional[Dict[str, Any]],
    promotion_blockers: List[str],
) -> List[Dict[str, Any]]:
    matching = _matching_promotions(session, promotions)
    latest_by_scope: Dict[str, Dict[str, Any]] = {}
    for promotion in matching:
        scope = str(promotion.get("scope") or "development")
        if scope not in latest_by_scope:
            latest_by_scope[scope] = promotion

    promoted_scopes = set(latest_by_scope)
    summaries: List[Dict[str, Any]] = []
    for scope in _PROMOTION_SCOPES:
        promotion = latest_by_scope.get(scope)
        required = _required_prior_scopes(scope)
        missing_prior = [
            prior for prior in required if prior not in promoted_scopes
        ]
        blockers: List[str] = []
        status = "pending"
        ready = False
        if promotion:
            metadata = promotion.get("promotion_metadata") or {}
            metadata_blockers = metadata.get("blockers") if isinstance(metadata, dict) else []
            blockers = [
                str(item) for item in metadata_blockers
                if item
            ] if isinstance(metadata_blockers, list) else []
            if metadata.get("promotion_allowed") is False:
                status = "blocked"
            elif promotion.get("rolled_back_at"):
                status = "rolled_back"
            else:
                status = "promoted"
                ready = True
        elif missing_prior:
            status = "blocked"
            blockers = [f"missing_{prior}_promotion" for prior in missing_prior]
        elif scope == "development":
            if promotion_blockers:
                status = "blocked"
                blockers = list(promotion_blockers)
            elif best_row and best_row.get("all_gates_passed"):
                status = "ready"
                ready = True
            elif best_row:
                status = "blocked"
                blockers = ["candidate_gates_not_passed"]
            else:
                status = "pending"
        else:
            status = "needs_approval"
            blockers = [f"missing_{scope}_approval"]

        summaries.append(
            {
                "scope": scope,
                "status": status,
                "ready": ready,
                "requires_approval": scope != "development",
                "required_prior_scopes": required,
                "blockers": blockers,
                "blocker_details": _blocker_details(blockers),
                "promotion": _compact_promotion(promotion),
            }
        )
    return summaries


def _matching_promotions(
    session: Dict[str, Any],
    promotions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    sid = session.get("id")
    model_type = session.get("model_type")
    instrument = session.get("instrument")
    timeframe = session.get("timeframe")

    def match(row: Dict[str, Any]) -> bool:
        if sid and row.get("research_id") == sid:
            return True
        return bool(
            model_type
            and instrument
            and timeframe
            and row.get("model_type") == model_type
            and row.get("instrument") == instrument
            and row.get("timeframe") == timeframe
        )

    rows = [row for row in promotions if match(row)]
    rows.sort(key=lambda row: row.get("promoted_at") or "", reverse=True)
    return rows


def _required_prior_scopes(scope: str) -> List[str]:
    if scope == "paper":
        return ["development"]
    if scope == "canary":
        return ["development", "paper"]
    if scope == "production":
        return ["development", "paper", "canary"]
    return []


def _compact_promotion(promotion: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not promotion:
        return None
    metadata = promotion.get("promotion_metadata") or {}
    return {
        "id": promotion.get("id"),
        "scope": promotion.get("scope"),
        "research_id": promotion.get("research_id"),
        "iteration": promotion.get("iteration"),
        "target_path": promotion.get("target_path"),
        "metadata_path": promotion.get("metadata_path"),
        "promoted_at": promotion.get("promoted_at"),
        "rolled_back_at": promotion.get("rolled_back_at"),
        "promotion_allowed": (
            metadata.get("promotion_allowed") if isinstance(metadata, dict) else None
        ),
        "rollback_target": (
            metadata.get("rollback_target")
            or (metadata.get("rollback_readiness") or {}).get("rollback_target")
            if isinstance(metadata, dict)
            else None
        ),
    }


def _rl_replay_status(
    metrics: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    replay = _rl_economic_replay_summary(metrics, snapshot)
    if not replay:
        return {
            "status": "missing",
            "score": _first_number(metrics.get("rl_profit_score")),
            "missing": ["rl_economic_replay"],
            "metrics": {},
            "artifact_path": None,
            "artifact_hash": None,
        }
    missing = []
    if replay.get("rl_profit_score") is None:
        missing.append("rl_profit_score")
    if not replay.get("artifact_hash"):
        missing.append("artifact_hash")
    status = "passed" if not missing else "blocked"
    return {
        "status": status,
        "score": replay.get("rl_profit_score"),
        "missing": missing,
        "metrics": {
            key: replay.get(key)
            for key in ("post_cost_return", "max_drawdown", "sharpe")
            if replay.get(key) is not None
        },
        "artifact_path": replay.get("artifact_path"),
        "artifact_hash": replay.get("artifact_hash"),
        "schema_version": replay.get("schema_version"),
    }


def _supervised_feature_readiness_status(
    *,
    session: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    evidence = _first_mapping(
        metrics.get("supervised_feature_readiness"),
        metrics.get("feature_readiness"),
        metrics.get("feature_readiness_report"),
        _first_mapping(
            metrics.get("promotion_evidence"),
            metrics.get("deployment_evidence"),
            metrics.get("production_evidence"),
        ).get("feature_readiness"),
    )
    summary = {
        "direction": _feature_channel_status(
            "direction",
            _first_mapping(
                evidence.get("direction"),
                evidence.get("direction_model"),
                metrics.get("direction_feature_readiness"),
            ),
            metrics,
            session.get("model_type"),
        ),
        "volatility": _feature_channel_status(
            "volatility",
            _first_mapping(
                evidence.get("volatility"),
                evidence.get("volatility_model"),
                metrics.get("volatility_feature_readiness"),
            ),
            metrics,
            session.get("model_type"),
        ),
    }
    statuses = {value["status"] for value in summary.values()}
    if statuses == {"passed"}:
        status = "passed"
    elif "blocked" in statuses or "missing" in statuses:
        status = "blocked"
    else:
        status = "partial"
    return {"status": status, **summary}


def _feature_channel_status(
    channel: str,
    evidence: Dict[str, Any],
    metrics: Dict[str, Any],
    model_type: Any,
) -> Dict[str, Any]:
    readiness_metrics = _feature_readiness_metrics(metrics) if model_type == channel else {}
    for key in ("auc", "ece", "brier_score", "signal_rate"):
        value = evidence.get(key)
        if value is not None:
            readiness_metrics[key] = value
    passed = _truthy_status(evidence)
    explicit_failed = any(
        evidence.get(key) is False
        for key in ("passed", "pass", "valid", "validated", "complete")
    )
    if passed:
        status = "passed"
    elif explicit_failed:
        status = "blocked"
    elif readiness_metrics:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "passed": passed,
        "metrics": readiness_metrics,
        "details": evidence,
    }


def _rl_oos_provenance_status(
    *,
    model_type: Any,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    if model_type != "rl":
        return {
            "status": "not_applicable",
            "required": False,
            "blockers": [],
        }
    rl_oos = metrics.get("rl_oos") if isinstance(metrics.get("rl_oos"), dict) else {}
    direction = _rl_channel_provenance(metrics, rl_oos, "direction")
    volatility = _rl_channel_provenance(metrics, rl_oos, "volatility")
    feature_bundle_hash = _rl_feature_bundle_hash(metrics, rl_oos)
    nested_validation = _truthy(
        rl_oos.get("nested_validation_used"),
        rl_oos.get("blocked_time_validation_used"),
        rl_oos.get("validation_mode") in {"nested", "blocked_time", "blocked-time"},
    )
    multi_seed = _truthy(
        rl_oos.get("multi_seed"),
        _first_number(rl_oos.get("n_seed_trials")) is not None
        and (_first_number(rl_oos.get("n_seed_trials")) or 0) > 1,
    )
    blockers = []
    if not rl_oos:
        blockers.append("missing_rl_oos_provenance")
    if not direction:
        blockers.append("missing_direction_feature_provenance")
    if not volatility:
        blockers.append("missing_volatility_feature_provenance")
    if not feature_bundle_hash:
        blockers.append("missing_rl_feature_bundle_hash")
    if not nested_validation:
        blockers.append("missing_nested_validation")
    if not multi_seed:
        blockers.append("missing_multi_seed_rl_validation")

    return {
        "status": "passed" if not blockers else "blocked",
        "required": True,
        "blockers": blockers,
        "blocker_details": _blocker_details(blockers),
        "feature_bundle_hash": feature_bundle_hash,
        "nested_validation": nested_validation,
        "multi_seed": multi_seed,
        "direction": _compact_provenance(direction),
        "volatility": _compact_provenance(volatility),
        "details": rl_oos,
    }


def _rl_channel_provenance(
    metrics: Dict[str, Any],
    rl_oos: Dict[str, Any],
    channel: str,
) -> Dict[str, Any]:
    feature_provenance = _first_mapping(
        rl_oos.get("feature_provenance"),
        rl_oos.get("feature_provenance_by_channel"),
        metrics.get("feature_provenance"),
        metrics.get("feature_provenance_by_channel"),
    )
    probability_provenance = _first_mapping(
        rl_oos.get("probability_provenance"),
        metrics.get("probability_provenance"),
    )
    return _first_mapping(
        rl_oos.get(f"{channel}_probability_provenance"),
        rl_oos.get(f"{channel}_feature_provenance"),
        metrics.get(f"{channel}_probability_provenance"),
        metrics.get(f"{channel}_feature_provenance"),
        feature_provenance.get(channel),
        probability_provenance.get(channel),
    )


def _rl_feature_bundle_hash(
    metrics: Dict[str, Any],
    rl_oos: Dict[str, Any],
) -> Any:
    feature_bundle = _first_mapping(
        rl_oos.get("feature_bundle"),
        metrics.get("feature_bundle"),
    )
    rl_dataset = _first_mapping(
        rl_oos.get("rl_dataset"),
        metrics.get("rl_dataset"),
    )
    return (
        rl_oos.get("feature_bundle_hash")
        or rl_oos.get("rl_feature_bundle_hash")
        or rl_oos.get("dataset_hash")
        or rl_oos.get("enriched_dataset_hash")
        or metrics.get("feature_bundle_hash")
        or metrics.get("rl_feature_bundle_hash")
        or feature_bundle.get("hash")
        or rl_dataset.get("feature_bundle_hash")
    )


def _compact_provenance(provenance: Dict[str, Any]) -> Dict[str, Any]:
    if not provenance:
        return {"status": "missing"}
    status = provenance.get("status") or provenance.get("provenance_status")
    coverage = _first_number(
        provenance.get("honest_coverage"),
        provenance.get("oof_available_coverage"),
        provenance.get("oof_coverage"),
    )
    return {
        "status": status or ("passed" if coverage is not None else "recorded"),
        "coverage": coverage,
        "source": provenance.get("source") or provenance.get("dataset_source"),
        "hash": provenance.get("hash")
        or provenance.get("feature_hash")
        or provenance.get("provenance_hash"),
        "details": provenance,
    }


def _inference_parity_status(
    metrics: Dict[str, Any],
    latest_promotion: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    metadata = (latest_promotion or {}).get("promotion_metadata") or {}
    parity = _first_mapping(
        metrics.get("inference_reload_validation"),
        metrics.get("inference_parity"),
        metrics.get("rl_inference_parity"),
        metadata.get("inference_reload_validation") if isinstance(metadata, dict) else None,
    )
    passed = _truthy_status(parity)
    failed_checks = parity.get("failed_checks")
    if not isinstance(failed_checks, list):
        failed_checks = []
    status = "passed" if passed else "missing" if not parity else "blocked"
    return {
        "status": status,
        "passed": passed,
        "failed_checks": failed_checks,
        "details": parity,
    }


def _rollback_status(
    *,
    latest_promotion: Optional[Dict[str, Any]],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    metadata = (latest_promotion or {}).get("promotion_metadata") or {}
    readiness = _first_mapping(
        metadata.get("rollback_readiness") if isinstance(metadata, dict) else None,
        metrics.get("rollback_readiness"),
        metrics.get("rollback"),
        metrics.get("rollback_plan"),
    )
    target = (
        _rollback_target(latest_promotion)
        or readiness.get("rollback_target")
        or readiness.get("previous_config_snapshot_path")
        or metrics.get("rollback_target")
    )
    status = "ready" if target else "missing"
    if latest_promotion and latest_promotion.get("rolled_back_at"):
        status = "rolled_back"
    return {
        "status": status,
        "target": target,
        "readiness": readiness,
        "rolled_back_at": latest_promotion.get("rolled_back_at") if latest_promotion else None,
    }


def _operations_warnings(
    *,
    session: Dict[str, Any],
    promotion_blockers: List[str],
    scope_status: List[Dict[str, Any]],
    rl_replay: Dict[str, Any],
    feature_readiness: Dict[str, Any],
    rl_oos: Dict[str, Any],
    inference: Dict[str, Any],
    rollback: Dict[str, Any],
) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []

    def add(code: str, severity: str, message: str, details: Any = None) -> None:
        warnings.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "details": details,
            }
        )

    production_scope = next(
        (item for item in scope_status if item.get("scope") == "production"),
        {},
    )
    development_scope = next(
        (item for item in scope_status if item.get("scope") == "development"),
        {},
    )
    if development_scope.get("status") in {"ready", "promoted"} and production_scope.get("status") != "promoted":
        add(
            "development_only_candidate",
            "warning",
            "Candidate is development-scoped until paper, canary, and production gates pass.",
        )
    if promotion_blockers:
        add(
            "blocked_promotion",
            "critical",
            "Promotion is blocked by server-owned gates.",
            _blocker_details(promotion_blockers),
        )
    if session.get("model_type") == "rl" and rl_replay.get("status") != "passed":
        add(
            "missing_rl_economic_replay",
            "critical",
            "RL policy is missing passing economic replay evidence.",
            rl_replay,
        )
    if inference.get("status") != "passed":
        add(
            "missing_inference_parity",
            "critical",
            "Inference parity or reload evidence is missing.",
            inference,
        )
    if session.get("model_type") == "rl" and rl_oos.get("status") != "passed":
        add(
            "missing_rl_oos_provenance",
            "critical",
            "RL OOS validation or feature provenance is incomplete.",
            rl_oos.get("blocker_details"),
        )
    if feature_readiness.get("status") == "blocked":
        add(
            "missing_feature_readiness",
            "warning",
            "Direction and volatility feature readiness is incomplete.",
            feature_readiness,
        )
    if rollback.get("status") == "missing":
        add(
            "missing_rollback_target",
            "warning",
            "Rollback target has not been recorded.",
        )
    return warnings


def _compact_audit_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compact = []
    for event in events[:12]:
        metadata = event.get("request_metadata") or {}
        metadata = metadata if isinstance(metadata, dict) else {}
        compact.append(
            {
                "event_id": event.get("event_id"),
                "timestamp": event.get("timestamp"),
                "actor_id": event.get("actor_id"),
                "action": event.get("action"),
                "outcome": event.get("outcome"),
                "research_id": event.get("research_id"),
                "pipeline_id": event.get("pipeline_id"),
                "scope": metadata.get("scope"),
                "error_message": event.get("error_message"),
            }
        )
    return compact


def _blocker_details(blockers: List[str]) -> List[Dict[str, str]]:
    return [
        {
            "code": blocker,
            "label": _BLOCKER_LABELS.get(blocker, _humanize_code(blocker)),
        }
        for blocker in blockers
    ]


def _humanize_code(value: str) -> str:
    text = value.replace("_", " ").strip()
    return text[:1].upper() + text[1:] + "." if text else "Unknown blocker."


def _unique_strings(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _first_mapping(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _truthy_status(container: Dict[str, Any]) -> bool:
    if not isinstance(container, dict):
        return False
    if any(
        container.get(key) is True
        for key in (
            "passed",
            "pass",
            "valid",
            "validated",
            "approved",
            "complete",
            "configured",
            "duration_passed",
            "min_duration_passed",
        )
    ):
        return True
    status = container.get("status")
    return isinstance(status, str) and status.strip().lower() in {
        "pass",
        "passed",
        "success",
        "succeeded",
        "approved",
        "complete",
        "configured",
        "ready",
    }


def _truthy(*values: Any) -> bool:
    return any(value is True for value in values)


def _parse_json(raw: Any) -> Any:
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def _first_number(*values: Any) -> Optional[float]:
    for value in values:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


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
