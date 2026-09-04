from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, Union


@dataclass(frozen=True)
class RegistryEntry:
    name: str
    version: int
    path: Union[Path, str]
    meta_path: Union[Path, str]


class ModelRegistry(Protocol):
    def register(self, *, model, name: str, metadata: dict | None = None) -> int:  # pragma: no cover - protocol
        ...

    def list(self, name: str) -> Sequence[int]:  # pragma: no cover - protocol
        ...

    def get(self, name: str, version: int) -> RegistryEntry:  # pragma: no cover - protocol
        ...

    def promote(self, name: str, version: int, stage: str) -> None:  # pragma: no cover - protocol
        ...
