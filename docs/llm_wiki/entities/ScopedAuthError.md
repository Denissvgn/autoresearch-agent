# ScopedAuthError

**Location:** `src/core/scoped_credentials.py:34`
**Kind:** Class
**Bases:** `Exception`
**Module:** [scoped_credentials](../modules/scoped_credentials.md)

## Description

A scoped credential was refused.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ScopedAuthError (src/core/scoped_credentials.py)"]
    n1["Exception"]
    n2["CredentialDenied (src/core/scoped_credentials.py)"]
    n3["CredentialExpired (src/core/scoped_credentials.py)"]
    n4["CredentialRevoked (src/core/scoped_credentials.py)"]
    n5["src/api/agent.py"]
    n6["src/api/harnesses.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/scoped_credentials.md"
    click n2 "../modules/scoped_credentials.md"
    click n3 "../modules/scoped_credentials.md"
    click n4 "../modules/scoped_credentials.md"
    click n5 "../modules/agent.md"
    click n6 "../modules/harnesses.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [scoped_credentials](../modules/scoped_credentials.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Exception` | — |
| Subclass | `CredentialDenied` | [scoped_credentials](../modules/scoped_credentials.md) |
| Subclass | `CredentialExpired` | [scoped_credentials](../modules/scoped_credentials.md) |
| Subclass | `CredentialRevoked` | [scoped_credentials](../modules/scoped_credentials.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `agent` | import | [agent](../modules/agent.md) | — |
| `harnesses` | import | [harnesses](../modules/harnesses.md) | — |
