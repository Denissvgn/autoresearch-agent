from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class _NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self

    def inc(self, *_args, **_kwargs):
        return None

    def observe(self, *_args, **_kwargs):
        return None

    def set(self, *_args, **_kwargs):
        return None


try:  # pragma: no cover - optional dependency import guarded by tests
    from prometheus_client import Histogram
except Exception:  # pragma: no cover - fallback when prometheus not installed
    class Histogram(_NoopMetric):
        pass

try:  # pragma: no cover - optional shared library in minimal service images
    from libs.resilience.resilience.metrics import Counter, Gauge  # type: ignore
except Exception:  # pragma: no cover - fallback when resilience is unavailable
    class Counter(_NoopMetric):
        pass

    class Gauge(_NoopMetric):
        pass

_BASE_LABELS = ("service", "experiment", "instrument", "timeframe", "run_id", "model_name")

_AUTOTRAIN_RUNS = Counter(
    "traid_autotrain_runs_total",
    "AutoTrain lifecycle transitions",
    labelnames=_BASE_LABELS + ("status",),
)
_AUTOTRAIN_DURATION = Histogram(
    "traid_autotrain_duration_seconds",
    "AutoTrain run duration in seconds",
    labelnames=_BASE_LABELS,
    buckets=(5, 10, 30, 60, 120, 300, 600, 1200),
)
_AUTOTRAIN_TRIALS = Gauge(
    "traid_autotrain_trials_total",
    "Trials executed in autotrain run",
    labelnames=_BASE_LABELS,
)
_AUTOTRAIN_REGISTRY_LAT = Histogram(
    "traid_autotrain_registry_latency_ms",
    "Registry registration latency in milliseconds",
    labelnames=_BASE_LABELS,
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2500),
)
_AUTOTRAIN_RESOURCE_HIGHWATER = Gauge(
    "traid_autotrain_resource_highwater",
    "Resource high-water marks (memory_mb)",
    labelnames=_BASE_LABELS,
)
_AUTOTRAIN_LEADERBOARD_SCORE = Gauge(
    "traid_autotrain_leaderboard_score",
    "Leaderboard scores for autotrain candidates",
    labelnames=_BASE_LABELS + ("candidate", "rank"),
)


@dataclass(frozen=True)
class MetricsRecorder:
    enabled: bool
    service: str

    def _labels(self, **labels: Any) -> tuple[str, ...]:
        if not self.enabled:
            return tuple()
        resolved = {
            "service": self.service,
            "experiment": labels.get("experiment", "default"),
            "instrument": labels.get("instrument", "n/a"),
            "timeframe": labels.get("timeframe", "n/a"),
            "run_id": labels.get("run_id", "unknown"),
            "model_name": labels.get("model_name", "n/a"),
        }
        return tuple(resolved[k] for k in ("service", "experiment", "instrument", "timeframe", "run_id", "model_name"))

    def record_started(self, **labels: Any) -> None:
        if not self.enabled:
            return
        _AUTOTRAIN_RUNS.labels(*self._labels(**labels), "started").inc()

    def record_completed(self, duration_seconds: float, trials: int, **labels: Any) -> None:
        if not self.enabled:
            return
        base = self._labels(**labels)
        _AUTOTRAIN_RUNS.labels(*base, "completed").inc()
        _AUTOTRAIN_DURATION.labels(*base).observe(max(duration_seconds, 0.0))
        _AUTOTRAIN_TRIALS.labels(*base).set(float(trials))

    def record_failed(self, **labels: Any) -> None:
        if not self.enabled:
            return
        _AUTOTRAIN_RUNS.labels(*self._labels(**labels), "failed").inc()

    def observe_registry_latency(self, latency_ms: float, **labels: Any) -> None:
        if not self.enabled:
            return
        _AUTOTRAIN_REGISTRY_LAT.labels(*self._labels(**labels)).observe(max(latency_ms, 0.0))

    def record_resource_highwater(self, memory_mb: float, **labels: Any) -> None:
        if not self.enabled:
            return
        _AUTOTRAIN_RESOURCE_HIGHWATER.labels(*self._labels(**labels)).set(max(memory_mb, 0.0))

    def record_leaderboard_update(self, candidate: str, rank: int, score: float, **labels: Any) -> None:
        if not self.enabled:
            return
        _AUTOTRAIN_LEADERBOARD_SCORE.labels(*self._labels(**labels), candidate, str(rank)).set(float(score))


def build_metrics_recorder(*, enabled: bool, service_name: str) -> MetricsRecorder:
    return MetricsRecorder(enabled=enabled, service=service_name)
