# RecoveryReport

**Location:** `src/core/run_restore.py:56`
**Kind:** Class
**Bases:** —
**Module:** [run_restore](../modules/run_restore.md)

**Decorators:** `@dataclass`

## Description

The assessment outcome for one restore request.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `kind` | `str` | *required* | — |
| `session_id` | `str` | *required* | — |
| `ready` | `bool` | *required* | — |
| `contract` | `Dict[str, Any]` | `field(default_factory=dict)` | — |
| `lineage` | `Dict[str, Any]` | `field(default_factory=dict)` | — |
| `blockers` | `List[RecoveryBlocker]` | `field(default_factory=list)` | — |
| `notes` | `List[str]` | `field(default_factory=list)` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `as_dict` | `() -> Dict[str, Any]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["RecoveryReport (src/core/run_restore.py)"]
    n1["assess_recovery (src/core/run_restore.py)"]
    n2["raise_unless_ready (src/core/run_restore.py)"]
    n3["RecoveryRequired.__init__ (src/core/run_restore.py)"]
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
| [run_restore](../modules/run_restore.md) | 1 | `blockers`, `contract`, `kind`, `lineage`, `notes`, `ready`, `session_id` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `assess_recovery` | call | [run_restore](../modules/run_restore.md) | 1 |
| `assess_recovery` | type_reference | [run_restore](../modules/run_restore.md) | — |
| `raise_unless_ready` | type_reference | [run_restore](../modules/run_restore.md) | — |
| `RecoveryRequired.__init__` | type_reference | [run_restore](../modules/run_restore.md) | — |
