from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..autotune import TrialResult
from ...core.errors import NotAvailableSDK
from ...models.base import ModelProtocol


@dataclass(frozen=True)
class RayOrchestrator:
    def __post_init__(self) -> None:
        try:
            import ray  # type: ignore  # noqa: F401
        except Exception as exc:  # pragma: no cover - optional dependency
            raise NotAvailableSDK(
                "Ray is not available. Install traid-training-sdk[ray] and configure Ray Tune."
            ) from exc

    def tune(self, **kwargs: Any) -> tuple[ModelProtocol, dict[str, float], list[TrialResult]]:  # pragma: no cover - would delegate to ray tune in future
        raise NotAvailableSDK(
            "Ray orchestrator is a stub in this build. Upgrade to a release with Ray integration."
        )
