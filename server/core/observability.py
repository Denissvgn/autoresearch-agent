"""Production observability helpers for autoresearch operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

OBSERVABILITY_SCHEMA_VERSION = "autoresearch_observability.v1"
PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


ALERT_SUGGESTIONS: list[dict[str, Any]] = [
    {
        "name": "AutoresearchRunawayCost",
        "severity": "critical",
        "metric": "autoresearch_api_cost_usd_total",
        "expr": "increase(autoresearch_api_cost_usd_total[1h]) > 50",
        "description": "API spend increased sharply for production research.",
    },
    {
        "name": "AutoresearchRepeatedCommandRejections",
        "severity": "warning",
        "metric": "autoresearch_command_policy_rejections_total",
        "expr": "increase(autoresearch_command_policy_rejections_total[15m]) >= 3",
        "description": "The agent repeatedly attempted commands rejected by policy.",
    },
    {
        "name": "AutoresearchHighFailureRate",
        "severity": "warning",
        "metric": "autoresearch_attempts_total",
        "expr": (
            'sum(autoresearch_attempts_total{outcome="failed"}) '
            "/ clamp_min(sum(autoresearch_attempts_total), 1) > 0.3"
        ),
        "description": "More than 30% of recorded research attempts are failing.",
    },
    {
        "name": "AutoresearchMissingRlReplayArtifacts",
        "severity": "critical",
        "metric": "autoresearch_rl_replay_total",
        "expr": 'autoresearch_rl_replay_total{status="missing"} > 0',
        "description": "At least one RL candidate is missing economic replay evidence.",
    },
    {
        "name": "AutoresearchBlockedProductionPromotions",
        "severity": "critical",
        "metric": "autoresearch_promotion_blocked_total",
        "expr": 'autoresearch_promotion_blocked_total{scope="production"} > 0',
        "description": "A production promotion is blocked by server-owned gates.",
    },
]


def empty_observability_snapshot(*, active_sessions: int = 0) -> dict[str, Any]:
    """Return a valid empty snapshot while the store is still starting."""

    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "active_sessions": active_sessions,
        "sessions": {"by_status": [], "by_model_type": []},
        "pipelines": {"by_status": []},
        "planned_trials": {"by_status": []},
        "attempts": {"by_outcome": [], "training_duration_seconds": []},
        "api_cost": {"total_usd": 0.0, "by_model_type": []},
        "promotions": {"by_scope": [], "blocked_by_reason": []},
        "rl_replay": {"by_status": []},
        "runtime_commands": {"by_status": []},
        "command_policy": {"rejections_by_operation": []},
        "alert_suggestions": alert_suggestions(),
    }


def alert_suggestions() -> list[dict[str, Any]]:
    """Return Prometheus alert suggestions for production research operations."""

    return [dict(item) for item in ALERT_SUGGESTIONS]


def format_prometheus(snapshot: Mapping[str, Any]) -> str:
    """Render an observability snapshot in Prometheus text exposition format."""

    lines: list[str] = [
        "# HELP autoresearch_active_sessions Active in-process research sessions.",
        "# TYPE autoresearch_active_sessions gauge",
        f"autoresearch_active_sessions {_number(snapshot.get('active_sessions'))}",
    ]
    _append_count_family(
        lines,
        "autoresearch_sessions",
        "Research sessions by status and model type.",
        snapshot.get("sessions", {}).get("by_status"),
        ("status", "model_type"),
    )
    _append_count_family(
        lines,
        "autoresearch_pipelines",
        "Research pipelines by status and current phase.",
        snapshot.get("pipelines", {}).get("by_status"),
        ("status", "phase"),
    )
    _append_count_family(
        lines,
        "autoresearch_planned_trials",
        "Structured search trials by status and search phase.",
        snapshot.get("planned_trials", {}).get("by_status"),
        ("status", "search_phase"),
    )
    _append_count_family(
        lines,
        "autoresearch_attempts_total",
        "Recorded training attempts by outcome and model type.",
        snapshot.get("attempts", {}).get("by_outcome"),
        ("outcome", "model_type"),
        metric_type="counter",
    )
    _append_training_duration(lines, snapshot)
    _append_cost(lines, snapshot)
    _append_count_family(
        lines,
        "autoresearch_promotion_blocked_total",
        "Blocked promotion decisions by scope and reason.",
        snapshot.get("promotions", {}).get("blocked_by_reason"),
        ("scope", "reason"),
        metric_type="counter",
    )
    _append_count_family(
        lines,
        "autoresearch_rl_replay_total",
        "RL economic replay status by model type.",
        snapshot.get("rl_replay", {}).get("by_status"),
        ("status", "model_type"),
        metric_type="counter",
    )
    _append_count_family(
        lines,
        "autoresearch_runtime_commands_total",
        "Runtime command records by status.",
        snapshot.get("runtime_commands", {}).get("by_status"),
        ("status",),
        metric_type="counter",
    )
    _append_count_family(
        lines,
        "autoresearch_command_policy_rejections_total",
        "Command policy rejections by operation.",
        snapshot.get("command_policy", {}).get("rejections_by_operation"),
        ("operation",),
        metric_type="counter",
    )
    return "\n".join(lines) + "\n"


def log_research_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **context: Any,
) -> None:
    """Emit a structured JSON log with common research trace fields."""

    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    for key, value in context.items():
        if value is not None:
            payload[key] = value
    payload.setdefault("research_id", None)
    payload.setdefault("pipeline_id", None)
    payload.setdefault("phase", None)
    payload.setdefault("trial_id", None)
    payload.setdefault("promotion_id", None)
    extra = {
        "research_id": payload.get("research_id"),
        "pipeline_id": payload.get("pipeline_id"),
        "phase": payload.get("phase"),
        "trial_id": payload.get("trial_id"),
        "promotion_id": payload.get("promotion_id"),
        "autoresearch_event": event,
    }
    logger.log(level, "autoresearch_event %s", _json(payload), extra=extra)


def _append_count_family(
    lines: list[str],
    name: str,
    help_text: str,
    rows: Any,
    label_names: tuple[str, ...],
    *,
    metric_type: str = "gauge",
) -> None:
    lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} {metric_type}"))
    emitted = False
    for row in _iter_rows(rows):
        labels = {
            label: row.get(label) if row.get(label) is not None else "unknown"
            for label in label_names
        }
        lines.append(_sample(name, labels, row.get("count", 0)))
        emitted = True
    if not emitted:
        labels = {label: "none" for label in label_names}
        lines.append(_sample(name, labels, 0))


def _append_training_duration(lines: list[str], snapshot: Mapping[str, Any]) -> None:
    rows = snapshot.get("attempts", {}).get("training_duration_seconds")
    lines.extend(
        (
            "# HELP autoresearch_training_duration_seconds Training duration summary.",
            "# TYPE autoresearch_training_duration_seconds summary",
        )
    )
    emitted = False
    for row in _iter_rows(rows):
        labels = {
            "model_type": row.get("model_type") or "unknown",
            "outcome": row.get("outcome") or "unknown",
        }
        lines.append(
            _sample(
                "autoresearch_training_duration_seconds_sum",
                labels,
                row.get("sum", 0),
            )
        )
        lines.append(
            _sample(
                "autoresearch_training_duration_seconds_count",
                labels,
                row.get("count", 0),
            )
        )
        emitted = True
    if not emitted:
        labels = {"model_type": "none", "outcome": "none"}
        lines.append(_sample("autoresearch_training_duration_seconds_sum", labels, 0))
        lines.append(_sample("autoresearch_training_duration_seconds_count", labels, 0))


def _append_cost(lines: list[str], snapshot: Mapping[str, Any]) -> None:
    cost = snapshot.get("api_cost", {})
    lines.extend(
        (
            "# HELP autoresearch_api_cost_usd_total Total recorded API cost in USD.",
            "# TYPE autoresearch_api_cost_usd_total counter",
            _sample("autoresearch_api_cost_usd_total", {}, cost.get("total_usd", 0)),
        )
    )
    lines.extend(
        (
            "# HELP autoresearch_api_cost_usd_by_model Total API cost by model type.",
            "# TYPE autoresearch_api_cost_usd_by_model gauge",
        )
    )
    emitted = False
    for row in _iter_rows(cost.get("by_model_type")):
        lines.append(
            _sample(
                "autoresearch_api_cost_usd_by_model",
                {"model_type": row.get("model_type") or "unknown"},
                row.get("value", 0),
            )
        )
        emitted = True
    if not emitted:
        lines.append(
            _sample("autoresearch_api_cost_usd_by_model", {"model_type": "none"}, 0)
        )


def _iter_rows(rows: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping):
                yield row


def _sample(name: str, labels: Mapping[str, Any], value: Any) -> str:
    suffix = ""
    if labels:
        parts = [
            f'{key}="{_escape_label(value)}"'
            for key, value in sorted(labels.items())
        ]
        suffix = "{" + ",".join(parts) + "}"
    return f"{name}{suffix} {_number(value)}"


def _escape_label(value: Any) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value: Any) -> str:
    try:
        if value is None:
            return "0"
        numeric = float(value)
    except (TypeError, ValueError):
        return "0"
    if numeric.is_integer():
        return str(int(numeric))
    return format(numeric, ".12g")


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
