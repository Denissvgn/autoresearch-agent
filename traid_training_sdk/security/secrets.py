from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

from ..core.errors import ConfigurationError, NotAvailableSDK


class SecretProvider(Protocol):
    def get_secret(self, key: str) -> Optional[str]:  # pragma: no cover - protocol definition
        ...


@dataclass
class EnvSecretProvider:
    prefix: Optional[str] = None
    fallback: Optional[Mapping[str, str]] = None

    def get_secret(self, key: str) -> Optional[str]:
        candidates = []
        if self.prefix:
            candidates.append(f"{self.prefix}{key}")
        candidates.append(key)
        for candidate in candidates:
            if self.fallback and candidate in self.fallback:
                return self.fallback[candidate]
            if candidate in os.environ:
                return os.environ[candidate]
        return None


@dataclass
class VaultSecretProvider:
    addr: str
    mount: str
    namespace: Optional[str]
    token_env: str

    def __post_init__(self) -> None:
        try:
            import hvac  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency guarded in tests
            raise NotAvailableSDK("hvac is required for Vault secret provider") from exc
        self._hvac = hvac

    def _token(self) -> str:
        token = os.getenv(self.token_env)
        if not token:
            raise ConfigurationError(f"Vault token env var '{self.token_env}' is empty")
        return token

    def get_secret(self, key: str) -> Optional[str]:
        if ":" in key:
            path, field = key.split(":", 1)
        else:
            path, field = key, "value"
        client = self._hvac.Client(url=self.addr, token=self._token())
        if self.namespace:
            client.namespace = self.namespace
        try:
            result = client.secrets.kv.v2.read_secret_version(path=f"{self.mount}/{path}")
        except Exception as exc:  # pragma: no cover - runtime failure mapped to None
            raise ConfigurationError(f"Vault read failed for path '{path}'") from exc
        data = result.get("data", {}).get("data", {})
        return data.get(field)


@dataclass
class SecretManager:
    provider: SecretProvider

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = self.provider.get_secret(key)
        return val if val is not None else default

    def require(self, key: str) -> str:
        val = self.get(key)
        if val is None:
            raise ConfigurationError(f"Missing secret: {key}")
        return val


def mask_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    length = len(value)
    if length <= 4:
        return "*" * length
    head = value[:2]
    tail = value[-2:]
    return f"{head}{'*' * (length - 4)}{tail}"


def redact_mapping(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    sensitive_keys = {"secret", "token", "password", "key"}
    redacted: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, Mapping):
            redacted[k] = redact_mapping(v)
            continue
        if any(token in k.lower() for token in sensitive_keys):
            if v is None:
                redacted[k] = ""
            else:
                masked = mask_secret(str(v))
                if len(masked) > 2:
                    masked = "**" + masked[2:]
                redacted[k] = masked
        else:
            redacted[k] = v
    return redacted


def build_secret_manager(config, *, env: Optional[Mapping[str, str]] = None) -> SecretManager:
    provider_name = (config.provider or "env").lower()
    if provider_name == "env":
        provider = EnvSecretProvider(prefix=getattr(config, "env_prefix", None), fallback=env)
        return SecretManager(provider=provider)
    if provider_name == "vault":
        if not config.vault_addr:
            raise ConfigurationError("Vault provider requires vault_addr")
        provider = VaultSecretProvider(
            addr=config.vault_addr,
            mount=config.vault_mount or "secret",
            namespace=config.vault_namespace,
            token_env=config.vault_token_env or "VAULT_TOKEN",
        )
        return SecretManager(provider=provider)
    raise ConfigurationError(f"Unsupported secret provider: {config.provider}")
