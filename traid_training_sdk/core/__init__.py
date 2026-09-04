"""Core SDK primitives (stubs for Sprint 0)."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .client import TraidClient
    from .context import RunContext


def __getattr__(name: str) -> Any:
    if name == "TraidClient":
        from .client import TraidClient

        return TraidClient
    if name == "RunContext":
        from .context import RunContext

        return RunContext
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["TraidClient", "RunContext"]
