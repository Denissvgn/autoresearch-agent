"""Production observability helpers for autoresearch operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, cast

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    generate_latest,
)
from prometheus_client.core import (
    CounterMetricFamily,
    GaugeMetricFamily,
    SummaryMetricFamily,
)

OBSERVABILITY_SCHEMA_VERSION = "autoresearch_observability.v1"
PROMETHEUS_CONTENT_TYPE = CONTENT_TYPE_LATEST


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
    """Render a snapshot with prometheus-client's standard exposition writer."""

    return generate_prometheus_latest(snapshot).decode("utf-8")


def generate_prometheus_latest(snapshot: Mapping[str, Any]) -> bytes:
    """Return default process metrics plus autoresearch snapshot metrics."""

    return generate_latest(REGISTRY) + generate_latest(_snapshot_registry(snapshot))


def log_research_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **context: Any,
) -> None:
    """Emit a structured JSON log with common research trace fields."""

    payload: dict[str, Any] = {
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


class _SnapshotCollector:
    def __init__(self, snapshot: Mapping[str, Any]) -> None:
        self.snapshot = snapshot

    def collect(self) -> Iterable[Any]:
        yield _gauge_metric(
            "autoresearch_active_sessions",
            "Active in-process research sessions.",
            [],
            [([], self.snapshot.get("active_sessions"))],
        )
        yield _count_family(
            "autoresearch_sessions",
            "Research sessions by status and model type.",
            self.snapshot.get("sessions", {}).get("by_status"),
            ("model_type", "status"),
        )
        yield _count_family(
            "autoresearch_pipelines",
            "Research pipelines by status and current phase.",
            self.snapshot.get("pipelines", {}).get("by_status"),
            ("phase", "status"),
        )
        yield _count_family(
            "autoresearch_planned_trials",
            "Structured search trials by status and search phase.",
            self.snapshot.get("planned_trials", {}).get("by_status"),
            ("search_phase", "status"),
        )
        yield _count_family(
            "autoresearch_attempts_total",
            "Recorded training attempts by outcome and model type.",
            self.snapshot.get("attempts", {}).get("by_outcome"),
            ("model_type", "outcome"),
            metric_type="counter",
        )
        yield _training_duration_family(self.snapshot)
        yield from _cost_families(self.snapshot)
        yield _count_family(
            "autoresearch_promotion_blocked_total",
            "Blocked promotion decisions by scope and reason.",
            self.snapshot.get("promotions", {}).get("blocked_by_reason"),
            ("reason", "scope"),
            metric_type="counter",
        )
        yield _count_family(
            "autoresearch_rl_replay_total",
            "RL economic replay status by model type.",
            self.snapshot.get("rl_replay", {}).get("by_status"),
            ("model_type", "status"),
            metric_type="counter",
        )
        yield _count_family(
            "autoresearch_runtime_commands_total",
            "Runtime command records by status.",
            self.snapshot.get("runtime_commands", {}).get("by_status"),
            ("status",),
            metric_type="counter",
        )
        yield _count_family(
            "autoresearch_command_policy_rejections_total",
            "Command policy rejections by operation.",
            self.snapshot.get("command_policy", {}).get("rejections_by_operation"),
            ("operation",),
            metric_type="counter",
        )


def _snapshot_registry(snapshot: Mapping[str, Any]) -> CollectorRegistry:
    registry = CollectorRegistry()
    registry.register(cast(Any, _SnapshotCollector(snapshot)))
    return registry


def _gauge_metric(
    name: str,
    help_text: str,
    label_names: list[str],
    samples: Iterable[tuple[list[str], Any]],
) -> GaugeMetricFamily:
    metric = GaugeMetricFamily(name, help_text, labels=label_names)
    for labels, value in samples:
        metric.add_metric(labels, _as_float(value))
    return metric


def _count_family(
    name: str,
    help_text: str,
    rows: Any,
    label_names: tuple[str, ...],
    *,
    metric_type: str = "gauge",
) -> GaugeMetricFamily | CounterMetricFamily:
    family_name = name[:-6] if metric_type == "counter" and name.endswith("_total") else name
    if metric_type == "counter":
        counter = CounterMetricFamily(family_name, help_text, labels=list(label_names))
        _add_count_samples(counter, rows, label_names)
        return counter

    gauge = GaugeMetricFamily(name, help_text, labels=list(label_names))
    _add_count_samples(gauge, rows, label_names)
    return gauge


def _add_count_samples(
    metric: CounterMetricFamily | GaugeMetricFamily,
    rows: Any,
    label_names: tuple[str, ...],
) -> None:
    emitted = False
    for row in _iter_rows(rows):
        labels = [
            str(row.get(label) if row.get(label) is not None else "unknown")
            for label in label_names
        ]
        metric.add_metric(labels, _as_float(row.get("count", 0)))
        emitted = True
    if not emitted:
        metric.add_metric(["none" for _ in label_names], 0.0)


def _training_duration_family(snapshot: Mapping[str, Any]) -> SummaryMetricFamily:
    metric = SummaryMetricFamily(
        "autoresearch_training_duration_seconds",
        "Training duration summary.",
        labels=["model_type", "outcome"],
    )
    emitted = False
    for row in _iter_rows(snapshot.get("attempts", {}).get("training_duration_seconds")):
        metric.add_metric(
            [str(row.get("model_type") or "unknown"), str(row.get("outcome") or "unknown")],
            count_value=_as_int(row.get("count", 0)),
            sum_value=_as_float(row.get("sum", 0)),
        )
        emitted = True
    if not emitted:
        metric.add_metric(["none", "none"], count_value=0, sum_value=0.0)
    return metric


def _cost_families(
    snapshot: Mapping[str, Any],
) -> Iterable[CounterMetricFamily | GaugeMetricFamily]:
    cost = snapshot.get("api_cost", {})
    total = CounterMetricFamily(
        "autoresearch_api_cost_usd",
        "Total recorded API cost in USD.",
        labels=[],
    )
    total.add_metric([], _as_float(cost.get("total_usd", 0)))
    yield total

    by_model = GaugeMetricFamily(
        "autoresearch_api_cost_usd_by_model",
        "Total API cost by model type.",
        labels=["model_type"],
    )
    emitted = False
    for row in _iter_rows(cost.get("by_model_type")):
        by_model.add_metric(
            [str(row.get("model_type") or "unknown")],
            _as_float(row.get("value", 0)),
        )
        emitted = True
    if not emitted:
        by_model.add_metric(["none"], 0.0)
    yield by_model


def _iter_rows(rows: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping):
                yield row


def _as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
