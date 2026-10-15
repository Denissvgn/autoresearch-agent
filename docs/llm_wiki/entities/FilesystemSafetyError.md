# FilesystemSafetyError

**Location:** `src/core/fs_safety.py:48`
**Kind:** Class
**Bases:** `Exception`
**Module:** [fs_safety](../modules/fs_safety.md)

## Description

A denied filesystem operation.

``operation`` names the denied operation (``write`` / ``read`` /
``copy`` / ``path``); the message repeats it alongside the path and the
reason so callers and logs identify exactly what was refused.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(operation: str, path: str, reason: str) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FilesystemSafetyError (src/core/fs_safety.py)"]
    n1["Exception"]
    n2["_copy_entry_at (src/core/fs_safety.py)"]
    n3["_open_parent_chain (src/core/fs_safety.py)"]
    n4["_open_root (src/core/fs_safety.py)"]
    n5["_relative_components (src/core/fs_safety.py)"]
    n6["_write_at (src/core/fs_safety.py)"]
    n7["read_regular_file (src/core/fs_safety.py)"]
    n8["tests/test_fs_safety.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    click n0 "../modules/fs_safety.md"
    click n2 "../modules/fs_safety.md"
    click n3 "../modules/fs_safety.md"
    click n4 "../modules/fs_safety.md"
    click n5 "../modules/fs_safety.md"
    click n6 "../modules/fs_safety.md"
    click n7 "../modules/fs_safety.md"
    click n8 "../modules/test_fs_safety.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [fs_safety](../modules/fs_safety.md) | 1 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Exception` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_copy_entry_at` | call | [fs_safety](../modules/fs_safety.md) | 3 |
| `_open_parent_chain` | call | [fs_safety](../modules/fs_safety.md) | 2 |
| `_open_root` | call | [fs_safety](../modules/fs_safety.md) | 1 |
| `_relative_components` | call | [fs_safety](../modules/fs_safety.md) | 2 |
| `_write_at` | call | [fs_safety](../modules/fs_safety.md) | 3 |
| `read_regular_file` | call | [fs_safety](../modules/fs_safety.md) | 3 |
| `test_fs_safety` | import | [test_fs_safety](../modules/test_fs_safety.md) | — |
