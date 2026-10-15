# development_inference_validation Module

**Path:** `src/core/development_inference_validation.py`

## Description

Inference reload/parity validation summaries for development promotion.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `typing` | `Any`, `Dict` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/config_promoter.py"]
    n1["src/core/development_inference_validation.py"]
    n0 --> n1
    click n0 "../modules/config_promoter.md"
    click n1 "../modules/development_inference_validation.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [config_promoter](../modules/config_promoter.md) |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_development_inference_validation` | `(*, metrics_payload: Dict[str, Any], rollback_readiness: Dict[str, Any], smoke_validation: Dict[str, Any]) -> Dict[str, Any]` | — | Normalize DPU-073 inference parity and reload evidence. |
| `_first_dict` | `(*values: Any) -> Dict[str, Any]` | — | — |
| `_bool_field` | `(container: Dict[str, Any], *keys: str) -> bool` | — | — |
| `_is_tsfm_candidate` | `(metrics_payload: Dict[str, Any], inference: Dict[str, Any]) -> bool` | — | — |
