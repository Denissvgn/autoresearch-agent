# config Module

**Path:** `src/config.py`

## Description

Configuration for the autoresearch-agent service.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `config.vault_loader` | `get_vault_status`, `load_vault_only` |
| `functools` | `lru_cache` |
| `libs.config.config.vault_loader` | `get_vault_status`, `load_vault_only` |
| `logging` | `logging` |
| `os` | `os` |
| `pydantic` | `AliasChoices`, `Field`, `SecretStr` |
| `pydantic_settings` | `BaseSettings`, `SettingsConfigDict` |
| `typing` | `Any`, `List`, `Optional` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [Settings](../entities/Settings.md) | 77 | `BaseSettings` | Application settings loaded from environment variables. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_settings_env` | `() -> str` | — | — |
| `_vault_settings_source` | `() -> dict[str, Any]` | `@lru_cache(maxsize=1)` | Load service defaults from Vault only, leaving env/.env precedence intact. |
| `secret_value` | `(value: SecretStr | str | None) -> str | None` | — | Return a plain string for secret values at API/client boundaries. |
| `get_settings` | `() -> Settings` | `@lru_cache(maxsize=1)` | Return the cached service settings instance. |
| `get_vault_status` | `() -> dict[str, Any]` | — | Return Vault configuration status for health/debug endpoints. |
