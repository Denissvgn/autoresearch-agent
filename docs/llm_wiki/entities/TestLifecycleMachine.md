# TestLifecycleMachine

**Location:** `tests/test_skill_lifecycle.py:123`
**Kind:** Class
**Bases:** —
**Module:** [test_skill_lifecycle](../modules/test_skill_lifecycle.md)

## Description

_Auto-generated from `TestLifecycleMachine` in `tests/test_skill_lifecycle.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_full_happy_path` | *(async)* `()` | `@pytest.mark.asyncio` | — |
| `test_illegal_transition_raises` | *(async)* `()` | `@pytest.mark.asyncio` | — |
| `test_audit_action_vocabulary` | *(async)* `()` | `@pytest.mark.asyncio` | — |
| `test_unregistered_defaults_to_stable` | *(async)* `()` | `@pytest.mark.asyncio` | — |
| `test_concurrent_transitions_serialized` | *(async)* `()` | `@pytest.mark.asyncio` | Two concurrent transitions on the same skill do not race — the lock |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_skill_lifecycle](../modules/test_skill_lifecycle.md) | 5 | — |
