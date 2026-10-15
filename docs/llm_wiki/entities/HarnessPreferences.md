# HarnessPreferences

**Location:** `src/core/execution_contracts.py:993`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [execution_contracts](../modules/execution_contracts.md)

## Description

Harness-level convenience defaults. Advisory only.

Preferences fill gaps that no higher layer resolved and can never widen
authority: they are bounded by operator constraints exactly like explicit
inputs, and they do not supply domain parameter values.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |
| `allow_inf_nan` | `False` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `max_concurrency` | `Optional[int]` | `max_concurrency` | No | Yes | `None` | ge=1 | — | — |
| `timeout_s` | `Optional[int]` | `timeout_s` | No | Yes | `None` | ge=1 | — | — |
| `model_roles` | `dict[str, str]` | `model_roles` | No | No | factory: `dict` | — | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["HarnessPreferences (src/core/execution_contracts.py)"]
    n1["BaseModel"]
    n2["resolve_run_inputs (src/core/execution_contracts.py)"]
    n3["test_harness_preferences_cannot_widen_authority (tests/test_execution_contracts.py)"]
    n4["test_model_roles_prefer_skill_defaults_over_preferences (tests/test_execution_contracts.py)"]
    n5["test_precedence_chain_for_budget_fields (tests/test_execution_contracts.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/execution_contracts.md"
    click n2 "../modules/execution_contracts.md"
    click n3 "../modules/test_execution_contracts.md"
    click n4 "../modules/test_execution_contracts.md"
    click n5 "../modules/test_execution_contracts.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_contracts](../modules/execution_contracts.md) | 0 | `max_concurrency`, `model_roles`, `timeout_s` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `resolve_run_inputs` | call | [execution_contracts](../modules/execution_contracts.md) | 1 |
| `resolve_run_inputs` | type_reference | [execution_contracts](../modules/execution_contracts.md) | — |
| `test_harness_preferences_cannot_widen_authority` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
| `test_model_roles_prefer_skill_defaults_over_preferences` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
| `test_precedence_chain_for_budget_fields` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
