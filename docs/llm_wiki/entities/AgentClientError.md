# AgentClientError

**Location:** `src/agent_client.py:23`
**Kind:** Class
**Bases:** `Exception`
**Module:** [agent_client](../modules/agent_client.md)

## Description

An API or transport failure with a stable, redacted message.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(message: str, *, status: Optional[int] = None) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["AgentClientError (src/agent_client.py)"]
    n1["Exception"]
    n2["AgentAuthError (src/agent_client.py)"]
    n3["AgentConflictError (src/agent_client.py)"]
    n4["AgentLimitError (src/agent_client.py)"]
    n5["src/agent_cli.py"]
    n6["AgentClient._error (src/agent_client.py)"]
    n7["AgentClient._request (src/agent_client.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/agent_client.md"
    click n2 "../modules/agent_client.md"
    click n3 "../modules/agent_client.md"
    click n4 "../modules/agent_client.md"
    click n5 "../modules/agent_cli.md"
    click n6 "../modules/agent_client.md"
    click n7 "../modules/agent_client.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [agent_client](../modules/agent_client.md) | 1 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Exception` | — |
| Subclass | `AgentAuthError` | [agent_client](../modules/agent_client.md) |
| Subclass | `AgentConflictError` | [agent_client](../modules/agent_client.md) |
| Subclass | `AgentLimitError` | [agent_client](../modules/agent_client.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `agent_cli` | import | [agent_cli](../modules/agent_cli.md) | — |
| `AgentClient._error` | call | [agent_client](../modules/agent_client.md) | 1 |
| `AgentClient._error` | type_reference | [agent_client](../modules/agent_client.md) | — |
| `AgentClient._request` | call | [agent_client](../modules/agent_client.md) | 1 |
