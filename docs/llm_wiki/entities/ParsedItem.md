# _ParsedItem

**Location:** `src/core/execution_request.py:150`
**Kind:** Class
**Bases:** —
**Module:** [execution_request](../modules/execution_request.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

One ordered argv item: a flag with its normalized value, or a positional.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `flag` | `Optional[str]` | *required* | — |
| `value` | `Optional[str]` | *required* | — |
| `positional` | `Optional[str]` | *required* | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `render` | `() -> tuple[str, ...]` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_ParsedItem (src/core/execution_request.py)"]
    n1["_parse_arguments (src/core/execution_request.py)"]
    n1 --> n0
    click n0 "../modules/execution_request.md"
    click n1 "../modules/execution_request.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_request](../modules/execution_request.md) | 1 | `flag`, `positional`, `value` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_parse_arguments` | call | [execution_request](../modules/execution_request.md) | 2 |
| `_parse_arguments` | type_reference | [execution_request](../modules/execution_request.md) | — |
