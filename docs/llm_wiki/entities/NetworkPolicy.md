# NetworkPolicy

**Location:** `src/core/execution_contracts.py:678`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [execution_contracts](../modules/execution_contracts.md)

## Description

Network authority for one attempt; deny is the default posture.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Validators

| Method | Scope | Fields | Mode | Options |
|--------|-------|--------|------|---------|
| `_allowlist_consistency` | model | — | after | — |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `mode` | `Literal['deny', 'allowlist']` | `mode` | No | No | `'deny'` | — | — | — |
| `allowed_hosts` | `list[str]` | `allowed_hosts` | No | No | factory: `list` | — | — | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_allowlist_consistency` | `() -> 'NetworkPolicy'` | `@model_validator(mode='after')` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["NetworkPolicy (src/core/execution_contracts.py)"]
    n1["BaseModel"]
    n2["NetworkPolicy._allowlist_consistency (src/core/execution_contracts.py)"]
    n3["_execution_request (tests/test_execution_contracts.py)"]
    n4["test_network_deny_rejects_allowed_hosts (tests/test_execution_contracts.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/execution_contracts.md"
    click n2 "../modules/execution_contracts.md"
    click n3 "../modules/test_execution_contracts.md"
    click n4 "../modules/test_execution_contracts.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_contracts](../modules/execution_contracts.md) | 1 | `allowed_hosts`, `mode` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `NetworkPolicy._allowlist_consistency` | type_reference | [execution_contracts](../modules/execution_contracts.md) | — |
| `_execution_request` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
| `test_network_deny_rejects_allowed_hosts` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
