# RequestHeaders

**Location:** `src/core/http_headers.py:31`
**Kind:** Class
**Bases:** —
**Module:** [http_headers](../modules/http_headers.md)

**Decorators:** `@dataclass(slots=True)`

## Description

Normalized inbound request headers.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `request_id` | `str` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["RequestHeaders (src/core/http_headers.py)"]
    n1["bind_request_headers (src/core/http_headers.py)"]
    n1 --> n0
    click n0 "../modules/http_headers.md"
    click n1 "../modules/http_headers.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [http_headers](../modules/http_headers.md) | 0 | `request_id` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `bind_request_headers` | call | [http_headers](../modules/http_headers.md) | 1 |
| `bind_request_headers` | type_reference | [http_headers](../modules/http_headers.md) | — |
