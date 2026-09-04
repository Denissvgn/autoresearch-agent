from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

from ..core.errors import NotImplementedSDK


class ModelProtocol(Protocol):
    def fit(self, X, y, **kwargs) -> "ModelProtocol":  # pragma: no cover - protocol
        ...

    def predict(self, X):  # pragma: no cover - protocol
        ...

    def predict_proba(self, X):  # pragma: no cover - protocol
        raise NotImplementedSDK("predict_proba is not supported")

    def save(self, path: str | Path) -> None:  # pragma: no cover - protocol
        ...

    @classmethod
    def load(cls, path: str | Path) -> "ModelProtocol":  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class ModelInfo:
    task: str  # "regression" | "classification"
    name: str
    target: str
    features: list[str]


def joblib_save(obj: Any, path: str | Path) -> None:
    from joblib import dump

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    dump(obj, p)


def joblib_load(path: str | Path) -> Any:
    from joblib import load

    return load(Path(path))

