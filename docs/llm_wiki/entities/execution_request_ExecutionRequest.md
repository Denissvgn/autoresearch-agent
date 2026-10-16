# ExecutionRequest

**Location:** `src/core/execution_request.py:87`
**Kind:** Class
**Bases:** —
**Module:** [execution_request](../modules/execution_request.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

The immutable, typed result of resolving one execution request.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `schema_version` | `str` | *required* | — |
| `operation` | `str` | *required* | — |
| `executable` | `str` | *required* | — |
| `exec_prefix` | `tuple[str, ...]` | *required* | — |
| `script` | `Optional[str]` | *required* | — |
| `arguments` | `tuple[str, ...]` | *required* | — |
| `argv` | `tuple[str, ...]` | *required* | — |
| `cwd` | `str` | *required* | — |
| `inputs` | `tuple[str, ...]` | *required* | — |
| `outputs` | `tuple[str, ...]` | *required* | — |
| `config_path` | `Optional[str]` | *required* | — |
| `timeout_s` | `int` | *required* | — |
| `fixed_arguments` | `tuple[str, ...]` | *required* | — |
| `execution_identity` | `Optional[Mapping[str, Any]]` | `None` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `to_meta` | `() -> dict[str, Any]` | — | JSON-safe provenance summary for tool metadata / markers. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ExecutionRequest (src/core/execution_request.py)"]
    n1["_allow (src/core/command_policy.py)"]
    n2["_authorize_python_request (src/core/command_policy.py)"]
    n3["_resolve_builtin (src/core/execution_request.py)"]
    n4["_resolve_python (src/core/execution_request.py)"]
    n5["resolve_execution_request (src/core/execution_request.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/execution_request.md"
    click n1 "../modules/command_policy.md"
    click n2 "../modules/command_policy.md"
    click n3 "../modules/execution_request.md"
    click n4 "../modules/execution_request.md"
    click n5 "../modules/execution_request.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_request](../modules/execution_request.md) | 1 | `arguments`, `argv`, `config_path`, `cwd`, `exec_prefix`, `executable`, `execution_identity`, `fixed_arguments`, `inputs`, `operation`, `outputs`, `schema_version` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_allow` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_authorize_python_request` | type_reference | [command_policy](../modules/command_policy.md) | — |
| `_resolve_builtin` | call | [execution_request](../modules/execution_request.md) | 1 |
| `_resolve_builtin` | type_reference | [execution_request](../modules/execution_request.md) | — |
| `_resolve_python` | call | [execution_request](../modules/execution_request.md) | 1 |
| `_resolve_python` | type_reference | [execution_request](../modules/execution_request.md) | — |
| `resolve_execution_request` | type_reference | [execution_request](../modules/execution_request.md) | — |
