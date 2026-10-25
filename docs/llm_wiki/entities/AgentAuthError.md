# AgentAuthError

**Location:** `src/agent_client.py:31`
**Kind:** Class
**Bases:** `AgentClientError`
**Module:** [agent_client](../modules/agent_client.md)

## Description

The scoped credential was refused (or missing).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["AgentAuthError (src/agent_client.py)"]
    n1["AgentClientError (src/agent_client.py)"]
    n2["src/agent_cli.py"]
    n3["AgentClient._error (src/agent_client.py)"]
    n4["resolve_credential (src/agent_client.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/agent_client.md"
    click n1 "../modules/agent_client.md"
    click n2 "../modules/agent_cli.md"
    click n3 "../modules/agent_client.md"
    click n4 "../modules/agent_client.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [agent_client](../modules/agent_client.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `AgentClientError` | [agent_client](../modules/agent_client.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `agent_cli` | import | [agent_cli](../modules/agent_cli.md) | — |
| `AgentClient._error` | call | [agent_client](../modules/agent_client.md) | 1 |
| `resolve_credential` | call | [agent_client](../modules/agent_client.md) | 1 |
