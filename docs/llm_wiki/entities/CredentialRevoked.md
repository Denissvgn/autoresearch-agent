# CredentialRevoked

**Location:** `src/core/scoped_credentials.py:42`
**Kind:** Class
**Bases:** `ScopedAuthError`
**Module:** [scoped_credentials](../modules/scoped_credentials.md)

## Description

The credential was explicitly revoked.

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["CredentialRevoked (src/core/scoped_credentials.py)"]
    n1["ScopedAuthError (src/core/scoped_credentials.py)"]
    n2["verify_scoped_credential (src/core/scoped_credentials.py)"]
    n0 --> n1
    n2 --> n0
    click n0 "../modules/scoped_credentials.md"
    click n1 "../modules/scoped_credentials.md"
    click n2 "../modules/scoped_credentials.md"
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
| `verify_scoped_credential` | call | [scoped_credentials](../modules/scoped_credentials.md) | 1 |
