# CredentialDenied

**Location:** `src/core/scoped_credentials.py:46`
**Kind:** Class
**Bases:** `ScopedAuthError`
**Module:** [scoped_credentials](../modules/scoped_credentials.md)

## Description

The credential's scope or permissions do not allow this operation.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["CredentialDenied (src/core/scoped_credentials.py)"]
    n1["ScopedAuthError (src/core/scoped_credentials.py)"]
    n2["_decode (src/core/scoped_credentials.py)"]
    n3["issue_scoped_credential (src/core/scoped_credentials.py)"]
    n4["verify_scoped_credential (src/core/scoped_credentials.py)"]
    n5["tests/test_agent_api.py"]
    n6["tests/test_harness_contracts_g4.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/scoped_credentials.md"
    click n1 "../modules/scoped_credentials.md"
    click n2 "../modules/scoped_credentials.md"
    click n3 "../modules/scoped_credentials.md"
    click n4 "../modules/scoped_credentials.md"
    click n5 "../modules/test_agent_api.md"
    click n6 "../modules/test_harness_contracts_g4.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [scoped_credentials](../modules/scoped_credentials.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ScopedAuthError` | [scoped_credentials](../modules/scoped_credentials.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_decode` | call | [scoped_credentials](../modules/scoped_credentials.md) | 4 |
| `issue_scoped_credential` | call | [scoped_credentials](../modules/scoped_credentials.md) | 2 |
| `verify_scoped_credential` | call | [scoped_credentials](../modules/scoped_credentials.md) | 3 |
| `test_agent_api` | import | [test_agent_api](../modules/test_agent_api.md) | — |
| `test_harness_contracts_g4` | import | [test_harness_contracts_g4](../modules/test_harness_contracts_g4.md) | — |
