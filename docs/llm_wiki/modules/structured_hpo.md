# structured_hpo Module

**Path:** `src/core/structured_hpo.py`

## Description

Structured HPO plan helpers for autoresearch sessions.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `copy` | `copy` |
| `datetime` | `datetime`, `timezone` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `pathlib` | `Path` |
| `typing` | `Any`, `Dict`, `Iterable`, `List`, `Mapping` |
| `yaml` | `yaml` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_structured_hpo_plan` | `() -> Dict[str, Any]` | — | Build a bounded HPO plan for manifest, DB, API, and UI state. |
| `hpo_plan_json` | `(plan: Dict[str, Any]) -> str` | — | — |
| `validate_config_patch` | `(model_type: str, config_patch: Mapping[str, Any]) -> Dict[str, Any]` | — | Validate a server-owned config patch against the approved knob surface. |
| `apply_config_patch` | `(base_config: Mapping[str, Any], config_patch: Mapping[str, Any]) -> Dict[str, Any]` | — | Return a train.yaml payload with a flat server-owned patch applied. |
| `materialize_planned_trials` | `(plan: Mapping[str, Any], workspace_path: str | Path) -> List[Dict[str, Any]]` | — | Write concrete planned trial train.yaml files under the workspace. |
| `_bounded_trials` | `(model_type: str, max_iterations: int, enable_hpo: bool, requested_trials: int) -> int` | — | — |
| `_budget_bounded_trials` | `(model_type: str, max_trials: int, max_budget_usd: float) -> int` | — | — |
| `_per_trial_budget_usd` | `(model_type: str) -> float` | — | — |
| `_search_space` | `(model_type: str) -> Dict[str, Any]` | — | — |
| `_planned_trials` | `() -> List[Dict[str, Any]]` | — | — |
| `_direction_trial_patches` | `() -> List[Dict[str, Any]]` | — | — |
| `_volatility_trial_patches` | `() -> List[Dict[str, Any]]` | — | — |
| `_direction_patch` | `() -> Dict[str, Any]` | — | — |
| `_volatility_patch` | `() -> Dict[str, Any]` | — | — |
| `_extend_unique_patches` | `(seeds: List[Dict[str, Any]], generated: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]` | — | — |
| `_roster_keys` | `(roster: str) -> List[str]` | — | — |
| `_atr_candidates` | `(atr_mult: float) -> List[float]` | — | — |
| `_trial_id` | `(index: int, patch: Mapping[str, Any], model_type: str) -> str` | — | — |
| `_workspace_path` | `(instrument: str, timeframe: str, model_type: str) -> str` | — | — |
| `_execution` | `(model_type: str, hpo_timesteps: int) -> Dict[str, Any]` | — | — |
| `_hash` | `(plan: Dict[str, Any]) -> str` | — | — |
