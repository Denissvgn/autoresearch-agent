# _OnePerTurnScriptedProvider

**Location:** `tests/test_domain_conformance.py:647`
**Kind:** Class
**Bases:** —
**Module:** [test_domain_conformance](../modules/test_domain_conformance.md)

## Description

Issues one candidate command per turn (the sequential execution path).

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(commands: list[str]) -> None` | — | — |
| `messages_create` | *(async)* `(*, model, system, messages, tools, max_tokens, temperature = None, stop_sequences = None)` | — | — |
| `complete` | *(async)* `(*, model, prompt, max_tokens, system = None) -> str` | — | — |
| `estimate_cost` | `(model, usage) -> float` | — | — |
| `capabilities` | `()` | — | — |
| `classify_error` | `(exc)` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_domain_conformance](../modules/test_domain_conformance.md) | 6 | — |
