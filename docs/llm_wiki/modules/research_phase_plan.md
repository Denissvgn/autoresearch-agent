# research_phase_plan Module

**Path:** `src/core/research_phase_plan.py`

## Description

Phase-state helpers for autoresearch sessions.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `datetime` | `datetime`, `timezone` |
| `json` | `json` |
| `typing` | `Any`, `Dict`, `Iterable`, `List`, `Optional` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_phase_state` | `() -> Dict[str, Any]` | — | Derive an operator-facing phase plan and next action. |
| `phase_state_json` | `(state: Dict[str, Any]) -> str` | — | — |
| `_completed_phase_ids` | `(iterations: List[Dict[str, Any]], hpo_studies: List[Dict[str, Any]], promotions: List[Dict[str, Any]], model_type: Optional[str]) -> set[str]` | — | — |
| `_has_promotion_evidence` | `(iterations: List[Dict[str, Any]], promotions: List[Dict[str, Any]]) -> bool` | — | — |
| `_select_current_phase` | `(phases: List[Dict[str, str]], completed: set[str], blocked: Optional[str]) -> str` | — | — |
| `_phase_status` | `(phase_id: str, current_phase: str, completed: set[str], blocked: Optional[str], phases: List[Dict[str, str]]) -> str` | — | — |
| `_next_action` | `(phases: List[Dict[str, str]], current_phase: str, blocked: Optional[str]) -> str` | — | — |
| `_count_stalled_iterations` | `(rows: List[Dict[str, Any]], phases: List[Dict[str, str]], current_phase: str) -> int` | — | Return how many consecutive trailing iterations produced no later-phase evidence. |
| `_blocked_reason` | `(iterations: List[Dict[str, Any]]) -> Optional[str]` | — | — |
| `_has_metric` | `(iteration: Dict[str, Any]) -> bool` | — | — |
| `_parse_json` | `(raw: Any) -> Any` | — | — |
