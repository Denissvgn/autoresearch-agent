# development_gate_bundle Module

**Path:** `src/core/development_gate_bundle.py`

## Description

Development gate bundle evaluation for autoresearch promotions.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `pathlib` | `Path` |
| `typing` | `Any`, `Dict`, `Iterable` |
| `yaml` | `yaml` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `load_gate_bundle` | `(workspace_root: str | Path) -> dict[str, Any]` | — | Load the versioned development gate bundle from the workspace. |
| `load_production_gate_bundle` | `(workspace_root: str | Path) -> dict[str, Any]` | — | Load the versioned production-scope promotion gate bundle. |
| `_load_bundle` | `(path: Path) -> dict[str, Any]` | — | — |
| `evaluate_development_gate_bundle` | `() -> dict[str, Any]` | — | Evaluate a best autoresearch iteration against the gate bundle. |
| `_iteration_payload` | `(best_iteration: dict[str, Any]) -> dict[str, Any]` | — | — |
| `_waivers` | `(payload: dict[str, Any]) -> set[str]` | — | — |
| `_evaluate_rl_development_gate_bundle` | `() -> dict[str, Any]` | — | Evaluate server-owned RL promotion gates for development promotion. |
| `_dict_at` | `(root: Any) -> dict[str, Any]` | — | — |
| `_dict_or_list` | `(root: Any) -> Any` | — | — |
| `_first_dict` | `() -> dict[str, Any]` | — | — |
| `_first_number` | `() -> float | None` | — | — |
| `_max_number` | `() -> float | None` | — | — |
| `_append_blocker` | `(blockers: list[str], reason: str) -> None` | — | — |
| `_post_cost_replay_worsening_details` | `(replay: dict[str, Any], replay_gates: dict[str, Any]) -> dict[str, Any]` | — | Detect explicit post-cost replay worsening versus baseline evidence. |
| `_evaluate_rl_economic_replay_gates` | `() -> None` | — | Evaluate first-class RL post-cost economic replay evidence. |
| `_rl_economic_replay_payload` | `(payload: dict[str, Any]) -> dict[str, Any]` | — | — |
| `_rl_economic_replay_metrics` | `(replay: dict[str, Any]) -> dict[str, Any]` | — | — |
| `_rl_economic_metric_value` | `(metrics: dict[str, Any], name: str) -> float | None` | — | — |
| `_requested_promotion_scope` | `(payload: dict[str, Any]) -> str` | — | — |
| `_live_production_promotion_requested` | `(payload: dict[str, Any]) -> bool` | — | — |
| `_evaluate_rollback_readiness_gates` | `() -> None` | — | Evaluate rollback readiness evidence for development promotion. |
| `_evaluate_signal_health_gates` | `() -> None` | — | Evaluate development direction-signal health monitoring evidence. |
| `_evaluate_inference_reload_gates` | `() -> None` | — | Evaluate DPU-073 inference reload/parity validation evidence. |
| `_evaluate_smoke_validation_gates` | `() -> None` | — | Evaluate smoke or paper validation evidence before promotion. |
| `_evaluate_inference_parity_gates` | `() -> None` | — | Evaluate required inference parity evidence for development promotion. |
| `_bool_field` | `(container: dict[str, Any]) -> bool` | — | — |
| `_is_tsfm_candidate` | `(payload: dict[str, Any], inference: dict[str, Any]) -> bool` | — | — |
| `_evaluate_rl_oos_gates` | `() -> None` | — | Evaluate DPU-063 RL OOS gate evidence when a candidate is a finalist. |
| `_evaluate_rl_feature_provenance_gate` | `() -> None` | — | — |
| `_rl_channel_provenance` | `(payload: dict[str, Any], rl_oos: dict[str, Any], channel: str) -> dict[str, Any]` | — | — |
| `_rl_feature_bundle_hash` | `(payload: dict[str, Any], rl_oos: dict[str, Any]) -> str | None` | — | — |
| `_rl_required_provenance_fields_missing` | `(provenance: dict[str, Any]) -> list[str]` | — | — |
| `_present_value` | `(value: Any) -> bool` | — | — |
| `_rl_unsafe_feature_details` | `(provenance: dict[str, Any]) -> dict[str, Any]` | — | — |
| `_rl_stale_or_leaked_details` | `(provenance: dict[str, Any]) -> dict[str, Any]` | — | — |
| `_provenance_status_values` | `(provenance: dict[str, Any]) -> list[str]` | — | — |
| `_string_list` | `(value: Any) -> list[str]` | — | — |
| `_truthy` | `(value: Any) -> bool` | — | — |
| `_boolean_gate` | `() -> None` | — | — |
| `_rl_nested_validation_present` | `(rl_oos: dict[str, Any]) -> bool` | — | — |
| `_rl_metric_value` | `(metrics: dict[str, Any], name: str) -> float | None` | — | — |
| `_rl_multi_seed_present` | `(rl_oos: dict[str, Any]) -> bool` | — | — |
| `_numeric_gate` | `() -> None` | — | — |
