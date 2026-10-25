# harness_conformance Module

**Path:** `src/core/harness_conformance.py`

## Description

Reusable harness conformance suite and a deterministic fake adapter.

Integration authors run ``run_conformance`` against their adapter before
connecting it to the kernel. The fake adapter is deterministic and can be
built to violate exactly one rule at a time, so the suite's own checks are
specified by failing examples.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `src.core.harness_adapter` | `HarnessAdapter`, `HarnessRegistry`, `request_pause`, `request_resume`, `request_steer` |
| `src.core.harness_contract` | `ATTACH_MODE_CONTINUATION`, `ATTACH_MODE_NATIVE_RESUME`, `CAPABILITY_PAUSE`, `CAPABILITY_RESUME`, `CAPABILITY_STEERING`, `HARNESS_CONTRACT_VERSION`, `OPTIONAL_CAPABILITIES`, `HarnessContractError`, `HarnessLifecycleError`, `HarnessVersionError`, `UnsupportedCapabilityError` |
| `typing` | `Any`, `Iterator`, `Mapping`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/harness_adapter.py"]
    n1["src/core/harness_conformance.py"]
    n2["src/core/harness_contract.py"]
    n3["src/core/harness_qualification.py"]
    n4["tests/test_builtin_harness.py"]
    n5["tests/test_harness_sdk.py"]
    n0 --> n2
    n1 --> n0
    n1 --> n2
    n3 --> n0
    n3 --> n1
    n3 --> n2
    n4 --> n0
    n4 --> n1
    n4 --> n2
    n5 --> n0
    n5 --> n1
    n5 --> n2
    click n0 "../modules/harness_adapter.md"
    click n1 "../modules/harness_conformance.md"
    click n2 "../modules/harness_contract.md"
    click n3 "../modules/harness_qualification.md"
    click n4 "../modules/test_builtin_harness.md"
    click n5 "../modules/test_harness_sdk.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [harness_qualification](../modules/harness_qualification.md) |
| Inbound | [test_builtin_harness](../modules/test_builtin_harness.md) |
| Inbound | [test_harness_sdk](../modules/test_harness_sdk.md) |
| Outbound | [harness_adapter](../modules/harness_adapter.md) |
| Outbound | [harness_contract](../modules/harness_contract.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [FakeHarnessAdapter](../entities/FakeHarnessAdapter.md) | 34 | — | A deterministic harness adapter for specification and testing. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `run_conformance` | `(adapter: HarnessAdapter, *, start_request: Mapping[str, Any] \| None = None) -> list[str]` | — | Conformance findings for one adapter; empty means conforming. |
