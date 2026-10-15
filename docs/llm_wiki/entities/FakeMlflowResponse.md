# FakeMlflowResponse

**Location:** `tests/test_config_promoter_gate_bundle.py:687`
**Kind:** Class
**Bases:** —
**Module:** [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md)

## Description

_Auto-generated from `FakeMlflowResponse` in `tests/test_config_promoter_gate_bundle.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(status_code: int, payload: object) -> None` | — | — |
| `json` | `() -> object` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FakeMlflowResponse (tests/test_config_promoter_gate_bundle.py)"]
    n1["FakeMlflowAsyncClient.get (tests/test_config_promoter_gate_bundle.py)"]
    n2["FakeMlflowAsyncClient.post (tests/test_config_promoter_gate_bundle.py)"]
    n1 --> n0
    n2 --> n0
    click n0 "../modules/test_config_promoter_gate_bundle.md"
    click n1 "../modules/test_config_promoter_gate_bundle.md"
    click n2 "../modules/test_config_promoter_gate_bundle.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 2 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `FakeMlflowAsyncClient.get` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
| `FakeMlflowAsyncClient.post` | call | [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md) | 1 |
