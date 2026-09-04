from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..autotune import TrialResult
from ...core.errors import NotAvailableSDK
from ...models.base import ModelProtocol


@dataclass(frozen=True)
class KubernetesOrchestrator:
    def __post_init__(self) -> None:
        try:
            import kubernetes  # type: ignore  # noqa: F401
        except Exception as exc:  # pragma: no cover - optional dependency guard
            raise NotAvailableSDK(
                "Kubernetes client not available. Install traid-training-sdk[k8s] and configure cluster access."
            ) from exc

    def tune(self, **kwargs: Any) -> tuple[ModelProtocol, dict[str, float], list[TrialResult]]:  # pragma: no cover - placeholder for future implementation
        raise NotAvailableSDK(
            "Kubernetes orchestrator is not implemented yet. Stay tuned for future releases."
        )
