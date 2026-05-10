# development_inference_validation Module

**Path:** `src/core/development_inference_validation.py`

## Description

Inference reload/parity validation summaries for development promotion.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `typing` | `Any`, `Dict` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_development_inference_validation` | `() -> Dict[str, Any]` | — | Normalize DPU-073 inference parity and reload evidence. |
| `_first_dict` | `() -> Dict[str, Any]` | — | — |
| `_bool_field` | `(container: Dict[str, Any]) -> bool` | — | — |
| `_is_tsfm_candidate` | `(metrics_payload: Dict[str, Any], inference: Dict[str, Any]) -> bool` | — | — |
