# SkillLifecycleEvent

**Location:** `src/core/skill_lifecycle.py:61`
**Kind:** Enum
**Bases:** `str`, `Enum`
**Module:** [skill_lifecycle](../modules/skill_lifecycle.md)

## Description

Operator-initiated lifecycle events.

## Attributes

| Name | Declared value | Description |
|------|-------|-------------|
| `SUBMIT_FOR_REVIEW` | `'submit_for_review'` | — |
| `APPROVE` | `'approve'` | — |
| `DEPRECATE` | `'deprecate'` | — |
| `UN_RETIRE` | `'un_retire'` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillLifecycleEvent (src/core/skill_lifecycle.py)"]
    n1["Enum"]
    n2["str"]
    n3["IllegalLifecycleTransitionError.__init__ (src/core/skill_lifecycle.py)"]
    n4["is_legal_transition (src/core/skill_lifecycle.py)"]
    n5["SkillLifecycleMachine.transition (src/core/skill_lifecycle.py)"]
    n6["target_state (src/core/skill_lifecycle.py)"]
    n7["tests/test_skill_generator.py"]
    n8["tests/test_skill_lifecycle.py"]
    n0 --> n1
    n0 --> n2
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    click n0 "../modules/skill_lifecycle.md"
    click n3 "../modules/skill_lifecycle.md"
    click n4 "../modules/skill_lifecycle.md"
    click n5 "../modules/skill_lifecycle.md"
    click n6 "../modules/skill_lifecycle.md"
    click n7 "../modules/test_skill_generator.md"
    click n8 "../modules/test_skill_lifecycle.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_lifecycle](../modules/skill_lifecycle.md) | 0 | `APPROVE`, `DEPRECATE`, `SUBMIT_FOR_REVIEW`, `UN_RETIRE` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `Enum` | — |
| Base | `str` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `IllegalLifecycleTransitionError.__init__` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `is_legal_transition` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `SkillLifecycleMachine.transition` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `target_state` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `test_skill_generator` | import | [test_skill_generator](../modules/test_skill_generator.md) | — |
| `test_skill_lifecycle` | import | [test_skill_lifecycle](../modules/test_skill_lifecycle.md) | — |
