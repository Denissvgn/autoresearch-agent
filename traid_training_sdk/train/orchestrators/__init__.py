"""Orchestrator plugins and loaders."""

from __future__ import annotations

from importlib import import_module
import os
from importlib.metadata import entry_points
from typing import Dict, Iterable

from ...core.errors import ConfigurationError, NotAvailableSDK
from .base import Orchestrator
from .k8s import KubernetesOrchestrator
from .local import LocalOrchestrator
from .ray import RayOrchestrator


_BUILTIN: Dict[str, type[Orchestrator]] = {
    "local": LocalOrchestrator,
    "ray": RayOrchestrator,
    "k8s": KubernetesOrchestrator,
}


def _env_default_orchestrator() -> str | None:
    raw = os.getenv("TRAID_SDK_DEFAULT_ORCHESTRATOR")
    if not raw:
        return None
    cleaned = raw.strip().lower()
    return cleaned or None


def _iter_entry_points(group: str, name: str | None) -> Iterable:
    try:
        eps = entry_points()
    except Exception:  # pragma: no cover - importlib metadata failure
        return []
    if hasattr(eps, "select"):
        return eps.select(group=group, name=name)
    if hasattr(eps, "get"):
        candidates = eps.get(group, [])
    else:
        candidates = [ep for ep in eps if getattr(ep, "group", None) == group]
    return [ep for ep in candidates if name is None or getattr(ep, "name", None) == name]


def _friendly_hint(target: str) -> str:
    hints = {
        "ray": "Ray orchestrator unavailable. Install `traid-training-sdk[ray]` and configure Ray Tune.",
        "k8s": "Kubernetes orchestrator unavailable. Install `traid-training-sdk[k8s]` and provide cluster access.",
    }
    return hints.get(target, f"Orchestrator '{target}' is not available in this build.")


def _load_builtin(target: str) -> Orchestrator | None:
    impl = _BUILTIN.get(target)
    if impl is None:
        return None
    try:
        return impl()
    except NotAvailableSDK as exc:
        raise NotAvailableSDK(_friendly_hint(target)) from exc


def load_orchestrator(name: str | None) -> Orchestrator:
    target = (name or _env_default_orchestrator() or "local").lower()

    builtin = _load_builtin(target)
    if builtin is not None:
        return builtin

    for ep in _iter_entry_points("traid_training_sdk.orchestrators", target):  # pragma: no cover
        factory = ep.load()
        return factory()

    try:
        module = import_module(target)
        factory = getattr(module, "get_orchestrator")
        instance = factory()
        if instance is None:
            raise ConfigurationError(f"Orchestrator factory for '{target}' returned None")
        return instance
    except NotAvailableSDK:
        raise
    except Exception as exc:  # pragma: no cover
        raise ConfigurationError(f"Unknown orchestrator '{name or target}'") from exc


__all__ = ["load_orchestrator", "LocalOrchestrator", "RayOrchestrator", "KubernetesOrchestrator"]
