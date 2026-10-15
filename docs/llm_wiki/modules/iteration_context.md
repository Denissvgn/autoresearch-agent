# iteration_context Module

**Path:** `src/core/iteration_context.py`

## Description

Compact iteration context digests for autoresearch agents.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `logging` | `logging` |
| `math` | `math` |
| `src.core.consistency_validator` | `parse_consistency_report` |
| `src.core.gate_status` | `training_gates_passed_from_iteration` |
| `typing` | `Any`, `Iterable`, `List`, `Mapping`, `Optional`, `Tuple` |
| `yaml` | `yaml` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/consistency_validator.py"]
    n1["src/core/gate_status.py"]
    n2["src/core/iteration_context.py"]
    n3["src/core/orchestrator.py"]
    n4["tests/test_cross_session_digest_hint.py"]
    n5["tests/test_exploration_markers.py"]
    n6["tests/test_iteration_context.py"]
    n7["tests/test_prompt_promotion_policy.py"]
    n0 --> n1
    n2 --> n0
    n2 --> n1
    n3 --> n0
    n3 --> n1
    n3 --> n2
    n4 --> n2
    n5 --> n2
    n6 --> n2
    n7 --> n2
    n7 --> n3
    click n0 "../modules/consistency_validator.md"
    click n1 "../modules/gate_status.md"
    click n2 "../modules/iteration_context.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/test_cross_session_digest_hint.md"
    click n5 "../modules/test_exploration_markers.md"
    click n6 "../modules/test_iteration_context.md"
    click n7 "../modules/test_prompt_promotion_policy.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [orchestrator](../modules/orchestrator.md) |
| Inbound | [test_cross_session_digest_hint](../modules/test_cross_session_digest_hint.md) |
| Inbound | [test_exploration_markers](../modules/test_exploration_markers.md) |
| Inbound | [test_iteration_context](../modules/test_iteration_context.md) |
| Inbound | [test_prompt_promotion_policy](../modules/test_prompt_promotion_policy.md) |
| Outbound | [consistency_validator](../modules/consistency_validator.md) |
| Outbound | [gate_status](../modules/gate_status.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 0 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `derive_exploration_markers` | `(model_type: str, current_config: Mapping[str, Any] \| None, baseline_config: Mapping[str, Any] \| None) -> dict[str, Any]` | — | Return phase-advancement markers this iter should emit, derived |
| `_resolve_dotted` | `(config: Mapping[str, Any], key: str) -> Any` | — | Resolve a possibly-dotted knob name against a (possibly nested) config. |
| `build_iteration_context_digest` | `(*, session: Mapping[str, Any], iterations: Iterable[Mapping[str, Any]], hpo_studies: Iterable[Mapping[str, Any]] = (), planned_trials: Iterable[Mapping[str, Any]] = (), phase_state: Optional[Mapping[str, Any]] = None, prior_session_summary: Optional[Iterable[Mapping[str, Any]]] = None, promotion_readiness: Optional[Iterable[Mapping[str, Any]]] = None, max_chars: int = 6000, recent_attempts: int = 5) -> str` | — | Build a deterministic, bounded digest of persisted iteration state. |
| `_best_line` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_attempt_line` | `(row: Mapping[str, Any]) -> str` | — | — |
| `_blockers_line` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_duplicate_line` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_tried_configs_lines` | `(iterations: List[Mapping[str, Any]]) -> List[str]` | — | Action 5: enumerate the distinct configs already attempted THIS session, |
| `_hpo_line` | `(studies: List[Mapping[str, Any]], trials: List[Mapping[str, Any]]) -> Optional[str]` | — | — |
| `_next_guidance` | `(iterations: List[Mapping[str, Any]]) -> str` | — | — |
| `_prior_session_tried_lines` | `(summary: List[Mapping[str, Any]], *, model_type: str = '') -> List[str]` | — | Render the "Tried in prior sessions" digest block. |
| `_select_representative_clusters` | `(rows: List[Mapping[str, Any]], model_type: str, max_entries: int) -> List[dict]` | — | Group rows into parameter-space clusters and pick a bounded, |
| `_parse_snapshot` | `(config_snapshot: Any) -> Optional[dict]` | — | Parse a YAML config_snapshot once. Returns the dict or None. |
| `_cluster_key` | `(parsed: Optional[dict], model_type: str) -> Optional[Tuple[Any, ...]]` | — | Build a hashable, bucketed cluster key from a parsed config. |
| `_bucket_value` | `(value: Any, width: 'float \| str \| None') -> Any` | — | Bucket a single value for clustering. Lists → tuple, numerics → |
| `_signature_from_parsed` | `(parsed: Optional[dict], model_type: str) -> Optional[str]` | — | Render the ``key=value, …`` signature from an already-parsed config. |
| `_extract_param_signature` | `(config_snapshot: Any, model_type: str) -> Optional[str]` | — | Back-compat wrapper: parse a raw snapshot then render its signature. |
| `_feature_availability_lines` | `(same_session_rows: List[Mapping[str, Any]], prior_summary: List[Mapping[str, Any]]) -> List[str]` | — | Detect persistent server-side feature unavailability across sessions. |
| `_row_blockers` | `(row: Mapping[str, Any]) -> List[str]` | — | — |
| `_parse_mapping` | `(raw: Any) -> dict[str, Any]` | — | — |
| `_unique` | `(values: Iterable[str]) -> List[str]` | — | — |
| `_number` | `(value: Any) -> Optional[float]` | — | — |
| `_fmt` | `(value: Optional[float]) -> str` | — | — |
| `_money` | `(value: Optional[float]) -> str` | — | — |
| `_yes_no` | `(value: Any) -> str` | — | — |
| `_short` | `(value: str, limit: int) -> str` | — | — |
| `_cap_text` | `(text: str, max_chars: int) -> str` | — | — |
