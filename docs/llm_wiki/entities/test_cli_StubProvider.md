# _StubProvider

**Location:** `tests/test_cli.py:74`
**Kind:** Class
**Bases:** —
**Module:** [test_cli](../modules/test_cli.md)

## Description

Deterministic LLMProvider.complete stand-in.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(response: str) -> None` | — | — |
| `complete` | *(async)* `(*, model, prompt, max_tokens, system = None) -> str` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["_StubProvider (tests/test_cli.py)"]
    n1["_run_cli (tests/test_cli.py)"]
    n2["test_new_skill_invalid_llm_output_blocks_without_writing (tests/test_cli.py)"]
    n1 --> n0
    n2 --> n0
    click n0 "../modules/test_cli.md"
    click n1 "../modules/test_cli.md"
    click n2 "../modules/test_cli.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_cli](../modules/test_cli.md) | 2 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_run_cli` | call | [test_cli](../modules/test_cli.md) | 1 |
| `test_new_skill_invalid_llm_output_blocks_without_writing` | call | [test_cli](../modules/test_cli.md) | 1 |
