# CapabilityDescriptor

**Location:** `src/core/execution_contracts.py:444`
**Kind:** Pydantic model
**Bases:** `VersionedContract`
**Module:** [execution_contracts](../modules/execution_contracts.md)

## Description

What a harness/driver can do — with explicit gaps, never silent ones.

``capabilities`` names what is supported; ``unsupported`` names what is
not, with a reason. Optional behaviors (pause, resume, mid-run input)
are absent from ``capabilities`` unless genuinely available: an
unsupported pause must not be equated with killing the process.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Validators

| Method | Scope | Fields | Mode | Options |
|--------|-------|--------|------|---------|
| `_capability_vocabulary` | model | — | after | — |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `schema_version` | `str` | `schema_version` | No | No | `CAPABILITY_DESCRIPTOR_SCHEMA_VERSION` | — | — | — |
| `integration` | `IntegrationDirection` | `integration` | Yes | No | — | — | — | — |
| `adapter_id` | `str` | `adapter_id` | Yes | No | — | min_length=1 | — | — |
| `protocol_version` | `str` | `protocol_version` | Yes | No | — | min_length=1 | — | — |
| `capabilities` | `list[str]` | `capabilities` | No | No | factory: `list` | — | — | — |
| `unsupported` | `dict[str, str]` | `unsupported` | No | No | factory: `dict` | — | — | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_capability_vocabulary` | `() -> 'CapabilityDescriptor'` | `@model_validator(mode='after')` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["CapabilityDescriptor (src/core/execution_contracts.py)"]
    n1["VersionedContract (src/core/execution_contracts.py)"]
    n2["CapabilityDescriptor._capability_vocabulary (src/core/execution_contracts.py)"]
    n3["ensure_capabilities_allowed (src/core/execution_contracts.py)"]
    n4["ensure_minimum_capabilities (src/core/execution_contracts.py)"]
    n5["_capabilities (tests/test_execution_contracts.py)"]
    n6["test_capability_descriptor_rejects_claimed_and_unsupported_overlap (tests/test_execution_contracts.py)"]
    n7["test_capability_descriptor_rejects_unknown_identifiers (tests/test_execution_contracts.py)"]
    n8["test_minimum_capabilities_pass_and_fail (tests/test_execution_contracts.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    click n0 "../modules/execution_contracts.md"
    click n1 "../modules/execution_contracts.md"
    click n2 "../modules/execution_contracts.md"
    click n3 "../modules/execution_contracts.md"
    click n4 "../modules/execution_contracts.md"
    click n5 "../modules/test_execution_contracts.md"
    click n6 "../modules/test_execution_contracts.md"
    click n7 "../modules/test_execution_contracts.md"
    click n8 "../modules/test_execution_contracts.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [execution_contracts](../modules/execution_contracts.md) | 1 | `adapter_id`, `capabilities`, `integration`, `protocol_version`, `schema_version`, `unsupported` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `VersionedContract` | [execution_contracts](../modules/execution_contracts.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `CapabilityDescriptor._capability_vocabulary` | type_reference | [execution_contracts](../modules/execution_contracts.md) | — |
| `ensure_capabilities_allowed` | type_reference | [execution_contracts](../modules/execution_contracts.md) | — |
| `ensure_minimum_capabilities` | type_reference | [execution_contracts](../modules/execution_contracts.md) | — |
| `_capabilities` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
| `test_capability_descriptor_rejects_claimed_and_unsupported_overlap` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
| `test_capability_descriptor_rejects_unknown_identifiers` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
| `test_minimum_capabilities_pass_and_fail` | call | [test_execution_contracts](../modules/test_execution_contracts.md) | 1 |
