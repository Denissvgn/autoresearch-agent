# RecoveryBlocker

**Location:** `src/core/run_restore.py:44`
**Kind:** Class
**Bases:** —
**Module:** [run_restore](../modules/run_restore.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

One reason a restore cannot satisfy the pinned contract.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `code` | `str` | *required* | — |
| `detail` | `str` | *required* | — |
| `remediation` | `str` | *required* | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `as_dict` | `() -> Dict[str, str]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["RecoveryBlocker (src/core/run_restore.py)"]
    n1["_artifact_blockers (src/core/run_restore.py)"]
    n2["_secret_blockers (src/core/run_restore.py)"]
    n3["assess_recovery (src/core/run_restore.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    click n0 "../modules/run_restore.md"
    click n1 "../modules/run_restore.md"
    click n2 "../modules/run_restore.md"
    click n3 "../modules/run_restore.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [run_restore](../modules/run_restore.md) | 1 | `code`, `detail`, `remediation` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_artifact_blockers` | call | [run_restore](../modules/run_restore.md) | 1 |
| `_artifact_blockers` | type_reference | [run_restore](../modules/run_restore.md) | — |
| `_secret_blockers` | call | [run_restore](../modules/run_restore.md) | 1 |
| `_secret_blockers` | type_reference | [run_restore](../modules/run_restore.md) | — |
| `assess_recovery` | call | [run_restore](../modules/run_restore.md) | 3 |
