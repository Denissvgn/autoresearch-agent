"""Observability helpers for metrics and event emission."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.config import ObservabilityConfig
from .events import LifecycleEmitter
from .metrics import MetricsRecorder, build_metrics_recorder


@dataclass(frozen=True)
class ObservabilityServices:
    metrics: MetricsRecorder
    events: LifecycleEmitter


def build_observability(config: ObservabilityConfig) -> ObservabilityServices:
    metrics = build_metrics_recorder(enabled=config.metrics_enabled, service_name=config.service_name)
    events = LifecycleEmitter(enabled=config.events_enabled, service=config.service_name)
    return ObservabilityServices(metrics=metrics, events=events)


__all__ = ["ObservabilityServices", "build_observability"]

