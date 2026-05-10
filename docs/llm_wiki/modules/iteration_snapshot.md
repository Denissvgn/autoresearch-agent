# iteration_snapshot Module

**Path:** `src/core/iteration_snapshot.py`

## Description

Server-owned immutable snapshots for autoresearch iteration attempts.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `datetime` | `datetime`, `timezone` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `platform` | `platform` |
| `shlex` | `shlex` |
| `typing` | `Any`, `Dict`, `Mapping`, `Optional` |
| `yaml` | `yaml` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `build_iteration_attempt_snapshot` | `() -> Dict[str, Any]` | — | Build a server-owned attempt snapshot for one trial. |
| `canonical_config_hash` | `(config_snapshot: Optional[str]) -> Optional[str]` | — | Hash config content after semantic YAML/JSON canonicalization. |
| `canonical_config_payload` | `(config_snapshot: Optional[str]) -> Any` | — | Return a stable representation of a config snapshot. |
| `build_trial_identity` | `() -> Dict[str, Any]` | — | Build a duplicate-detection identity for one planned/training attempt. |
| `trial_identity_hash` | `(identity: Mapping[str, Any]) -> Optional[str]` | — | Return a stable SHA-256 hash for a trial identity. |
| `write_iteration_attempt_snapshot` | `() -> str` | — | Persist an attempt snapshot JSON file under the session workspace. |
| `_environment_metadata` | `() -> Dict[str, Any]` | — | — |
| `_sha256_text` | `(value: Optional[str]) -> Optional[str]` | — | — |
| `_snapshot_hash` | `(snapshot: Dict[str, Any]) -> str` | — | — |
| `_first_present` | `(container: Dict[str, Any]) -> Any` | — | — |
| `_canonicalize` | `(value: Any) -> Any` | — | — |
| `_argv` | `(command: Optional[str]) -> list[str]` | — | — |
| `_command_arg` | `(command: Optional[str], flag: str) -> Optional[str]` | — | — |
| `_resolve_seed` | `() -> Any` | — | — |
| `_resolve_validation_mode` | `() -> str` | — | — |
| `_resolve_data_split_id` | `(config_payload: Any) -> str` | — | — |
| `_first_nested` | `(container: Any, paths: tuple[tuple[str, Ellipsis], Ellipsis]) -> Any` | — | — |
| `_nested_get` | `(container: Any, path: tuple[str, Ellipsis]) -> Any` | — | — |
| `_coerce_scalar` | `(value: str) -> Any` | — | — |
