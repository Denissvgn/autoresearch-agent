from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..core.config import FeatureFlagsConfig


@dataclass(frozen=True)
class FeatureFlags:
    enabled: bool
    namespace: Optional[str]
    _client: Any = None

    def _call_flag_callable(
        self,
        func: Callable[..., Any],
        *,
        flag: str,
        default: Any,
        allow_default: bool,
    ) -> Any:
        namespace = self.namespace
        attempts: list[Callable[[], Any]] = []
        if namespace is not None and allow_default:
            attempts.append(lambda: func(flag, namespace=namespace, default=default))
        if namespace is not None:
            attempts.append(lambda: func(flag, namespace=namespace))
        if allow_default:
            attempts.append(lambda: func(flag, default=default))
        attempts.append(lambda: func(flag))
        for attempt in attempts:
            try:
                return attempt()
            except TypeError:
                continue
        raise TypeError("Unsupported feature flag client signature")

    def is_enabled(self, flag: str, *, default: bool = False) -> bool:
        if not self.enabled or self._client is None:
            return default
        client = self._client
        try:
            checker = getattr(client, "is_enabled", None)
            if callable(checker):
                result = self._call_flag_callable(checker, flag=flag, default=default, allow_default=True)
                return bool(result)
            getter = getattr(client, "get_flag", None)
            if callable(getter):
                result = self._call_flag_callable(getter, flag=flag, default=default, allow_default=True)
                return bool(result)
        except Exception:
            return default
        return default

    def get_variant(self, flag: str, *, default: Optional[str] = None) -> Optional[str]:
        if not self.enabled or self._client is None:
            return default
        client = self._client
        try:
            resolver = getattr(client, "get_variant", None)
            if callable(resolver):
                result = self._call_flag_callable(resolver, flag=flag, default=default, allow_default=True)
                return result if result is not None else default
            getter = getattr(client, "get_flag", None)
            if callable(getter):
                result = self._call_flag_callable(getter, flag=flag, default=default, allow_default=True)
                return result if isinstance(result, str) else default
        except Exception:
            return default
        return default


def build_feature_flags(config: FeatureFlagsConfig) -> FeatureFlags:
    if not config.enabled:
        return FeatureFlags(enabled=False, namespace=config.namespace, _client=None)
    try:
        module = importlib.import_module("libs.feature_flags")
    except Exception:
        return FeatureFlags(enabled=False, namespace=config.namespace, _client=None)

    client: Any = None
    namespace = config.namespace

    factory = getattr(module, "FeatureFlagsClient", None)
    if callable(factory):
        try:
            client = factory(namespace=namespace)
        except Exception:
            client = None
    else:
        client = module

    if client is None:
        return FeatureFlags(enabled=False, namespace=namespace, _client=None)
    return FeatureFlags(enabled=True, namespace=namespace, _client=client)


__all__ = ["FeatureFlags", "build_feature_flags"]
