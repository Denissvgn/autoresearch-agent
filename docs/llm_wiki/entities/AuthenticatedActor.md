# AuthenticatedActor

**Location:** `src/api/auth.py:53`
**Kind:** Class
**Bases:** —
**Module:** [auth](../modules/auth.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Authenticated caller context used for audit metadata.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `subject` | `str` | *required* | — |
| `actor_id` | `str` | *required* | — |
| `mechanism` | `str` | *required* | — |
| `websocket_subprotocol` | `str \| None` | `None` | — |
| `roles` | `tuple[str, ...]` | `()` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["AuthenticatedActor (src/api/auth.py)"]
    n1["_request_actor (src/api/audit.py)"]
    n2["_authenticate_identity_token (src/api/auth.py)"]
    n3["_authenticate_token (src/api/auth.py)"]
    n4["require_api_auth (src/api/auth.py)"]
    n5["require_websocket_auth (src/api/auth.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/auth.md"
    click n1 "../modules/audit.md"
    click n2 "../modules/auth.md"
    click n3 "../modules/auth.md"
    click n4 "../modules/auth.md"
    click n5 "../modules/auth.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [auth](../modules/auth.md) | 0 | `actor_id`, `mechanism`, `roles`, `subject`, `websocket_subprotocol` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_request_actor` | type_reference | [audit](../modules/audit.md) | — |
| `_authenticate_identity_token` | call | [auth](../modules/auth.md) | 1 |
| `_authenticate_identity_token` | type_reference | [auth](../modules/auth.md) | — |
| `_authenticate_token` | call | [auth](../modules/auth.md) | 1 |
| `_authenticate_token` | type_reference | [auth](../modules/auth.md) | — |
| `require_api_auth` | type_reference | [auth](../modules/auth.md) | — |
| `require_websocket_auth` | type_reference | [auth](../modules/auth.md) | — |
