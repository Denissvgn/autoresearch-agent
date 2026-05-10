# config_promoter Module

**Path:** `src/core/config_promoter.py`

## Description

Config promoter — previews and writes winning configs to the host bind mount.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `datetime` | `datetime`, `timezone` |
| `hashlib` | `hashlib` |
| `httpx` | `httpx` |
| `json` | `json` |
| `logging` | `logging` |
| `os` | `os` |
| `pathlib` | `Path` |
| `src.config` | `secret_value`, `settings` |
| `src.core.consistency_validator` | `build_consistency_report` |
| `src.core.development_gate_bundle` | `evaluate_development_gate_bundle`, `load_gate_bundle`, `load_production_gate_bundle` |
| `src.core.development_inference_validation` | `build_development_inference_validation` |
| `src.core.development_signal_health` | `build_development_signal_health` |
| `src.core.results_store` | `ResultsStore` |
| `subprocess` | `subprocess` |
| `tempfile` | `tempfile` |
| `typing` | `Any`, `Dict`, `Optional` |
| `yaml` | `yaml` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ConfigPromoter](../entities/ConfigPromoter.md) | 82 | — | Handles preview and confirmation of config promotion to host. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_atomic_write_text` | `(path: str, content: str) -> None` | — | Sync helper: tmp+fsync+os.replace atomic write. |
