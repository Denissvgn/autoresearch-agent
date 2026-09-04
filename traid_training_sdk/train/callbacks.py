from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class Callback(Protocol):
    def on_fit_start(self, **kwargs) -> None:  # pragma: no cover - protocol
        ...

    def on_fit_end(self, **kwargs) -> None:  # pragma: no cover - protocol
        ...


@dataclass
class LogMetricsCallback:
    history: list[dict[str, Any]] | None = None

    def on_fit_start(self, **kwargs) -> None:  # no-op collection in Sprint 3
        self.history = []

    def on_fit_end(self, **kwargs) -> None:
        if self.history is not None:
            self.history.append({"event": "fit_end"})


@dataclass
class EarlyStoppingCallback:
    patience: int = 5

    def on_fit_start(self, **kwargs) -> None:  # non-iterative models: no-op
        return None

    def on_fit_end(self, **kwargs) -> None:
        return None


@dataclass
class CheckpointCallback:
    path: str

    def on_fit_start(self, **kwargs) -> None:
        return None

    def on_fit_end(self, **kwargs) -> None:
        model = kwargs.get("model")
        if model is not None and hasattr(model, "save"):
            model.save(self.path)

