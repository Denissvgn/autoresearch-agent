# PreflightCheck

**Location:** `src/core/preflight.py:50`
**Kind:** Class
**Bases:** `Protocol`
**Module:** [preflight](../modules/preflight.md)

## Description

A single service-dependency health check (ARC-011 P1-019).

A concrete check (``HTTPHealthCheck`` / ``TCPConnectCheck`` in P1-020)
implements this surface. ``run_service_preflight`` (P1-021) dispatches a
list of ``PreflightCheck`` instances via ``check(client)``.

The ``client`` arg is the shared ``httpx.AsyncClient`` for HTTP checks; TCP
checks ignore it (they open their own socket) — see ``TCPConnectCheck``.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `name` | `() -> str` | `@property` | — |
| `required` | `() -> bool` | `@property` | — |
| `check` | *(async)* `(client: httpx.AsyncClient \| None) -> dict[str, Any]` | — | Run the health check, returning a result dict shaped like |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["PreflightCheck (src/core/preflight.py)"]
    n1["Protocol"]
    n2["preflight_check_from_target (src/core/preflight.py)"]
    n3["src/core/skill_runtime.py"]
    n4["tests/test_preflight.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/preflight.md"
    click n2 "../modules/preflight.md"
    click n3 "../modules/skill_runtime.md"
    click n4 "../modules/test_preflight.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [preflight](../modules/preflight.md) | 3 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Protocol` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `preflight_check_from_target` | type_reference | [preflight](../modules/preflight.md) | — |
| `skill_runtime` | import | [skill_runtime](../modules/skill_runtime.md) | — |
| `test_preflight` | import | [test_preflight](../modules/test_preflight.md) | — |
