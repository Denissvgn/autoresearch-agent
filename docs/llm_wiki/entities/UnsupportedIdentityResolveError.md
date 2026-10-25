# UnsupportedIdentityResolveError

**Location:** `src/core/iteration_snapshot.py:53`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [iteration_snapshot](../modules/iteration_snapshot.md)

## Description

Raised when an identity resolver mode is declared but unsupported.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["UnsupportedIdentityResolveError (src/core/iteration_snapshot.py)"]
    n1["ValueError"]
    n2["build_trial_identity (src/core/iteration_snapshot.py)"]
    n3["src/core/orchestrator.py"]
    n4["tests/test_domain_semantics_extension.py"]
    n5["tests/test_observation_identity.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/iteration_snapshot.md"
    click n2 "../modules/iteration_snapshot.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/test_domain_semantics_extension.md"
    click n5 "../modules/test_observation_identity.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [iteration_snapshot](../modules/iteration_snapshot.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `build_trial_identity` | call | [iteration_snapshot](../modules/iteration_snapshot.md) | 1 |
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `test_domain_semantics_extension` | import | [test_domain_semantics_extension](../modules/test_domain_semantics_extension.md) | — |
| `test_observation_identity` | import | [test_observation_identity](../modules/test_observation_identity.md) | — |
