# research_manifest Module

**Path:** `src/core/research_manifest.py`

## Description

Immutable research-session manifests for autoresearch runs.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `datetime` | `datetime`, `timezone` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `pydantic` | `BaseModel`, `ConfigDict`, `Field`, `field_validator`, `model_validator` |
| `src.config` | `settings` |
| `src.core.service_preflight` | `build_not_run_preflight`, `sanitize_service_url` |
| `typing` | `Any`, `Dict`, `Optional` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ResearchSessionManifest](../entities/ResearchSessionManifest.md) | 16 | `BaseModel` | Complete immutable manifest for one autonomous research session. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_research_manifest` | `() -> ResearchSessionManifest` | — | Build and validate a complete manifest from request/server state. |
| `manifest_pretty_json` | `(manifest: ResearchSessionManifest) -> str` | — | — |
| `_default_objective` | `(model_type: str) -> str` | — | — |
| `_default_model_family` | `(model_type: str) -> str` | — | — |
| `_deep_merge` | `(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]` | — | — |
