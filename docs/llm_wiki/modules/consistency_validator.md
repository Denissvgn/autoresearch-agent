# consistency_validator Module

**Path:** `src/core/consistency_validator.py`

## Description

Cross-service consistency validation for autoresearch candidates.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `datetime` | `datetime`, `timezone` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `typing` | `Any`, `Dict`, `Iterable`, `Optional` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_consistency_report` | `() -> Dict[str, Any]` | — | Build a readable cross-service candidate consistency report. |
| `consistency_report_json` | `(report: Dict[str, Any]) -> str` | — | — |
| `parse_consistency_report` | `(raw: Any) -> Optional[Dict[str, Any]]` | — | — |
| `_calibration_payload` | `(metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]` | — | — |
| `_nested_bool` | `(container: Any, path: Iterable[str]) -> Optional[bool]` | — | — |
| `_all_true` | `(container: Dict[str, Any], keys: Iterable[str]) -> Optional[bool]` | — | — |
| `_first_present` | `(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Any` | — | — |
| `_sha256_text` | `(value: Optional[str]) -> Optional[str]` | — | — |
| `_dedupe` | `(values: Iterable[str]) -> list[str]` | — | — |
| `_dict_at` | `(root: Any) -> Dict[str, Any]` | — | — |
| `_first_dict` | `() -> Dict[str, Any]` | — | — |
| `_first_number` | `() -> Optional[float]` | — | — |
| `_rl_channel_provenance` | `(metrics: Dict[str, Any], rl_oos: Dict[str, Any], channel: str) -> Dict[str, Any]` | — | — |
| `_rl_feature_bundle_hash` | `(metrics: Dict[str, Any], rl_oos: Dict[str, Any]) -> Optional[str]` | — | — |
| `_rl_economic_replay_payload` | `(metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]` | — | — |
| `_rl_replay_assumptions_present` | `(replay: Dict[str, Any]) -> bool` | — | — |
| `_rl_replay_worse_than_baseline` | `(replay: Dict[str, Any]) -> list[Dict[str, Any]]` | — | — |
| `_rl_nested_validation_present` | `(rl_oos: Dict[str, Any]) -> bool` | — | — |
| `_rl_multi_seed_present` | `(rl_oos: Dict[str, Any]) -> bool` | — | — |
| `_rl_required_metrics_present` | `(rl_oos: Dict[str, Any]) -> bool` | — | — |
| `_rl_metric_value` | `(metrics: Dict[str, Any], name: str) -> Optional[float]` | — | — |
| `_rl_unsafe_feature_provenance` | `(provenance: Dict[str, Any]) -> bool` | — | — |
| `_string_list` | `(value: Any) -> list[str]` | — | — |
| `_truthy` | `(value: Any) -> bool` | — | — |
