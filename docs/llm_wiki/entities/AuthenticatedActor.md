# AuthenticatedActor

**Location:** `src/api/auth.py:37`
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
| `websocket_subprotocol` | `str | None` | `None` | — |
| `roles` | `tuple[str, Ellipsis]` | `...` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

- **used_by**: `_request_actor()` in [audit](../modules/audit.md)
