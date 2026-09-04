from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping

try:  # pragma: no cover - optional dependency import guarded in tests
    from libs.event_bus.event_bus.producer import publish_event_with_retry  # type: ignore

    _EVENTS_AVAILABLE = True
except Exception:  # pragma: no cover
    publish_event_with_retry = None
    _EVENTS_AVAILABLE = False


async def _publish(event_type: str, payload: Mapping[str, Any]) -> bool:
    if publish_event_with_retry is None:  # pragma: no cover - fallback when dependency missing
        return False
    return await publish_event_with_retry(event_type, dict(payload))


def _run_background(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:  # pragma: no cover - loop already running (e.g. notebook environment)
        loop.create_task(coro)


@dataclass(frozen=True)
class LifecycleEmitter:
    enabled: bool
    service: str

    def emit(self, event_type: str, payload: Mapping[str, Any]) -> None:
        if not self.enabled or not _EVENTS_AVAILABLE:
            return
        enriched = {"service": self.service, **payload}
        _run_background(_publish(event_type, enriched))

    def autotrain_started(self, **labels: Any) -> None:
        run_id = labels.get("run_id")
        payload = {
            "event": "autotrain.started",
            "instrument": labels.get("instrument"),
            "timeframe": labels.get("timeframe"),
            "experiment": labels.get("experiment"),
            "run_id": run_id,
        }
        self.emit("traid.sdk.autotrain.started", payload)

    def autotrain_completed(self, metrics: Mapping[str, Any], duration_seconds: float, **labels: Any) -> None:
        payload = {
            "event": "autotrain.completed",
            "instrument": labels.get("instrument"),
            "timeframe": labels.get("timeframe"),
            "experiment": labels.get("experiment"),
            "run_id": labels.get("run_id"),
            "model_name": labels.get("model_name"),
            "duration_seconds": duration_seconds,
            "metrics": dict(metrics),
        }
        self.emit("traid.sdk.autotrain.completed", payload)

    def autotrain_failed(self, error: str, **labels: Any) -> None:
        payload = {
            "event": "autotrain.failed",
            "instrument": labels.get("instrument"),
            "timeframe": labels.get("timeframe"),
            "experiment": labels.get("experiment"),
            "run_id": labels.get("run_id"),
            "error": error,
        }
        self.emit("traid.sdk.autotrain.failed", payload)

    def model_registered(self, model_uri: str, version: int, **labels: Any) -> None:
        payload = {
            "event": "model.registered",
            "model_uri": model_uri,
            "model_name": labels.get("model_name"),
            "version": version,
            "run_id": labels.get("run_id"),
        }
        self.emit("traid.sdk.model.registered", payload)

    def leaderboard_updated(self, candidate: str, score: float, rank: int, **labels: Any) -> None:
        payload = {
            "event": "leaderboard.updated",
            "candidate": candidate,
            "score": float(score),
            "rank": rank,
            "instrument": labels.get("instrument"),
            "timeframe": labels.get("timeframe"),
            "experiment": labels.get("experiment"),
            "run_id": labels.get("run_id"),
        }
        self.emit("traid.sdk.leaderboard.updated", payload)

    def feature_parity_checked(self, diffs: Mapping[str, float], tolerance: float, **labels: Any) -> None:
        payload = {
            "event": "feature_parity.checked",
            "diffs": dict(diffs),
            "tolerance": float(tolerance),
            "instrument": labels.get("instrument"),
            "timeframe": labels.get("timeframe"),
            "experiment": labels.get("experiment"),
            "run_id": labels.get("run_id"),
        }
        self.emit("traid.sdk.feature_parity.checked", payload)

    def backtest_completed(self, summary: Mapping[str, Any], window_size: int, step: int | None, **labels: Any) -> None:
        payload = {
            "event": "backtest.completed",
            "summary": dict(summary),
            "window_size": window_size,
            "step": step,
            "instrument": labels.get("instrument"),
            "timeframe": labels.get("timeframe"),
            "experiment": labels.get("experiment"),
            "run_id": labels.get("run_id"),
        }
        self.emit("traid.sdk.backtest.completed", payload)
