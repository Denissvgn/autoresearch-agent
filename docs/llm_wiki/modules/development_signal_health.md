# development_signal_health Module

**Path:** `src/core/development_signal_health.py`

## Description

Development direction-signal health summaries for promotion metadata.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `math` | `math` |
| `typing` | `Any`, `Dict`, `Iterable` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_development_signal_health` | `(metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | — | Build observable direction-signal health metrics for development promotion. |
| `_probability_summary` | `(probabilities: list[float]) -> Dict[str, Any]` | — | — |
| `_build_drift` | `() -> Dict[str, Any]` | — | — |
| `_build_alerts` | `() -> list[dict[str, Any]]` | — | — |
| `_binary_entropy` | `(probability: float) -> float` | — | — |
| `_base_disagreement` | `(values: Any) -> float | None` | — | — |
| `_psi` | `(current: list[float], training: list[float]) -> float` | — | — |
| `_kl` | `(current: list[float], training: list[float]) -> float` | — | — |
| `_normalize_histogram` | `(values: list[float]) -> list[float]` | — | — |
| `_number_list` | `() -> list[float]` | — | — |
| `_dict_at` | `(root: Any) -> Dict[str, Any]` | — | — |
| `_first_dict` | `() -> Dict[str, Any]` | — | — |
| `_first_number` | `() -> float | None` | — | — |
| `_first_bool` | `() -> bool | None` | — | — |
