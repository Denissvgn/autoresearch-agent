# ResourceLimits

**Location:** `src/core/execution_contracts.py:695`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [execution_contracts](../modules/execution_contracts.md)

## Description

OS-enforced resource ceilings for one attempt.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |
| `allow_inf_nan` | `False` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `wall_clock_s` | `int` | `wall_clock_s` | Yes | No | — | ge=1 | — | — |
| `memory_mb` | `int` | `memory_mb` | Yes | No | — | ge=1 | — | — |
| `max_processes` | `int` | `max_processes` | Yes | No | — | ge=1 | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ResourceLimits (src/core/execution_contracts.py)"]
    n1["BaseModel"]
    n2["_execution_request (tests/test_execution_contracts.py)"]
    n0 --> n1
    n2 --> n0
    click n0 "../modules/execution_contracts.md"
    click n2 "../modules/test_execution_contracts.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_contracts](../modules/execution_contracts.md) | 0 | `max_processes`, `memory_mb`, `wall_clock_s` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_execution_request` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
