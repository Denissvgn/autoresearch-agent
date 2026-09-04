from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..autotune import TrialResult, tune
from ...models.base import ModelProtocol


@dataclass(frozen=True)
class LocalOrchestrator:
    def tune(self, **kwargs: Any) -> tuple[ModelProtocol, dict[str, float], list[TrialResult]]:
        return tune(**kwargs)

