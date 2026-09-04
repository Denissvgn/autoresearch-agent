from __future__ import annotations

from typing import Any, Protocol

from ..autotune import TrialResult
from ...models.base import ModelProtocol


class Orchestrator(Protocol):
    def tune(self, **kwargs: Any) -> tuple[ModelProtocol, dict[str, float], list[TrialResult]]:  # pragma: no cover - protocol definition
        ...

