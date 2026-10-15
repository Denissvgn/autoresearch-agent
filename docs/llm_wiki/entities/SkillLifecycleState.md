# SkillLifecycleState

**Location:** `src/core/skill_lifecycle.py:42`
**Kind:** Enum
**Bases:** `str`, `Enum`
**Module:** [skill_lifecycle](../modules/skill_lifecycle.md)

## Description

The four lifecycle states a skill package moves through (ARC-011 §8.7).

## Attributes

| Name | Declared value | Description |
|------|-------|-------------|
| `DRAFT` | `'draft'` | — |
| `REVIEWED` | `'reviewed'` | — |
| `STABLE` | `'stable'` | — |
| `DEPRECATED` | `'deprecated'` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `default_for_installed` | `() -> 'SkillLifecycleState'` | `@classmethod` | Operator-installed skills (dropped under ``skills/<id>/``) start here. |
| `default_for_draft` | `() -> 'SkillLifecycleState'` | `@classmethod` | Generator output (under ``skills/_drafts/<id>/``) starts here. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillLifecycleState (src/core/skill_lifecycle.py)"]
    n1["Enum"]
    n2["str"]
    n3["IllegalLifecycleTransitionError.__init__ (src/core/skill_lifecycle.py)"]
    n4["is_legal_transition (src/core/skill_lifecycle.py)"]
    n5["selectable_for (src/core/skill_lifecycle.py)"]
    n6["SkillLifecycleMachine.get_state (src/core/skill_lifecycle.py)"]
    n7["SkillLifecycleMachine.register (src/core/skill_lifecycle.py)"]
    n8["SkillLifecycleState.default_for_draft (src/core/skill_lifecycle.py)"]
    n9["SkillLifecycleState.default_for_installed (src/core/skill_lifecycle.py)"]
    n10["target_state (src/core/skill_lifecycle.py)"]
    n11["tests/test_skill_generator.py"]
    n12["tests/test_skill_lifecycle.py"]
    n0 --> n1
    n0 --> n2
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    n11 --> n0
    n12 --> n0
    click n0 "../modules/skill_lifecycle.md"
    click n3 "../modules/skill_lifecycle.md"
    click n4 "../modules/skill_lifecycle.md"
    click n5 "../modules/skill_lifecycle.md"
    click n6 "../modules/skill_lifecycle.md"
    click n7 "../modules/skill_lifecycle.md"
    click n8 "../modules/skill_lifecycle.md"
    click n9 "../modules/skill_lifecycle.md"
    click n10 "../modules/skill_lifecycle.md"
    click n11 "../modules/test_skill_generator.md"
    click n12 "../modules/test_skill_lifecycle.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_lifecycle](../modules/skill_lifecycle.md) | 2 | `DEPRECATED`, `DRAFT`, `REVIEWED`, `STABLE` |

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
| `selectable_for` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `SkillLifecycleMachine.get_state` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `SkillLifecycleMachine.register` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `SkillLifecycleState.default_for_draft` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `SkillLifecycleState.default_for_installed` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `target_state` | type_reference | [skill_lifecycle](../modules/skill_lifecycle.md) | — |
| `test_skill_generator` | import | [test_skill_generator](../modules/test_skill_generator.md) | — |
| `test_skill_lifecycle` | import | [test_skill_lifecycle](../modules/test_skill_lifecycle.md) | — |
