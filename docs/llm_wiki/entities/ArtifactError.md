# ArtifactError

**Location:** `src/core/run_artifacts.py:40`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [run_artifacts](../modules/run_artifacts.md)

## Description

Raised when an artifact violates the store's safety contract.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ArtifactError (src/core/run_artifacts.py)"]
    n1["ValueError"]
    n2["_safe_relpath (src/core/run_artifacts.py)"]
    n3["ArtifactStore._import_tar (src/core/run_artifacts.py)"]
    n4["ArtifactStore._import_zip (src/core/run_artifacts.py)"]
    n5["ArtifactStore.create_bundle (src/core/run_artifacts.py)"]
    n6["ArtifactStore.import_archive (src/core/run_artifacts.py)"]
    n7["ArtifactStore.import_tree (src/core/run_artifacts.py)"]
    n8["ArtifactStore.load_bundle (src/core/run_artifacts.py)"]
    n9["ArtifactStore.reconstruct (src/core/run_artifacts.py)"]
    n10["tests/test_run_artifacts.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    click n0 "../modules/run_artifacts.md"
    click n2 "../modules/run_artifacts.md"
    click n3 "../modules/run_artifacts.md"
    click n4 "../modules/run_artifacts.md"
    click n5 "../modules/run_artifacts.md"
    click n6 "../modules/run_artifacts.md"
    click n7 "../modules/run_artifacts.md"
    click n8 "../modules/run_artifacts.md"
    click n9 "../modules/run_artifacts.md"
    click n10 "../modules/test_run_artifacts.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [run_artifacts](../modules/run_artifacts.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_safe_relpath` | call | [run_artifacts](../modules/run_artifacts.md) | 2 |
| `ArtifactStore._import_tar` | call | [run_artifacts](../modules/run_artifacts.md) | 6 |
| `ArtifactStore._import_zip` | call | [run_artifacts](../modules/run_artifacts.md) | 5 |
| `ArtifactStore.create_bundle` | call | [run_artifacts](../modules/run_artifacts.md) | 3 |
| `ArtifactStore.import_archive` | call | [run_artifacts](../modules/run_artifacts.md) | 2 |
| `ArtifactStore.import_tree` | call | [run_artifacts](../modules/run_artifacts.md) | 5 |
| `ArtifactStore.load_bundle` | call | [run_artifacts](../modules/run_artifacts.md) | 2 |
| `ArtifactStore.reconstruct` | call | [run_artifacts](../modules/run_artifacts.md) | 2 |
| `test_run_artifacts` | import | [test_run_artifacts](../modules/test_run_artifacts.md) | — |
