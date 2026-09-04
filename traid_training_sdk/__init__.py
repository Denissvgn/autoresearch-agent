"""
Traid Model Training SDK — foundation package.

Public surface in Sprint 0 is intentionally minimal. The only
guarantees are that the package imports and basic stubs exist.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .core.client import TraidClient


def __getattr__(name: str) -> Any:
    if name == "TraidClient":
        from .core.client import TraidClient

        return TraidClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["TraidClient"]
