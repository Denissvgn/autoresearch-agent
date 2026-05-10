# iteration_context Module

**Path:** `src/core/iteration_context.py`

## Description

Compact iteration context digests for autoresearch agents.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `src.core.consistency_validator` | `parse_consistency_report` |
| `typing` | `Any`, `Iterable`, `List`, `Mapping`, `Optional` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_iteration_context_digest` | `() -> str` | — | Build a deterministic, bounded digest of persisted iteration state. |
| `_best_line` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_attempt_line` | `(row: Mapping[str, Any]) -> str` | — | — |
| `_blockers_line` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_duplicate_line` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_hpo_line` | `(studies: List[Mapping[str, Any]], trials: List[Mapping[str, Any]]) -> Optional[str]` | — | — |
| `_next_guidance` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_row_blockers` | `(row: Mapping[str, Any]) -> List[str]` | — | — |
| `_parse_mapping` | `(raw: Any) -> dict[str, Any]` | — | — |
| `_unique` | `(values: Iterable[str]) -> List[str]` | — | — |
| `_number` | `(value: Any) -> Optional[float]` | — | — |
| `_fmt` | `(value: Optional[float]) -> str` | — | — |
| `_money` | `(value: Optional[float]) -> str` | — | — |
| `_yes_no` | `(value: Any) -> str` | — | — |
| `_short` | `(value: str, limit: int) -> str` | — | — |
| `_cap_text` | `(text: str, max_chars: int) -> str` | — | — |
