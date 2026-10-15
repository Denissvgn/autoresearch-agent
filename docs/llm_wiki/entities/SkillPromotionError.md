# SkillPromotionError

**Location:** `src/core/promotion_target.py:607`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [promotion_target](../modules/promotion_target.md)

## Description

Raised when a skill promotion precondition fails (P5-011).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillPromotionError (src/core/promotion_target.py)"]
    n1["ValueError"]
    n2["src/cli.py"]
    n3["SkillRegistryPromotionTarget.promote (src/core/promotion_target.py)"]
    n4["tests/test_skill_lifecycle.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/promotion_target.md"
    click n2 "../modules/cli.md"
    click n3 "../modules/promotion_target.md"
    click n4 "../modules/test_skill_lifecycle.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [promotion_target](../modules/promotion_target.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `cli` | import | [cli](../modules/cli.md) | — |
| `SkillRegistryPromotionTarget.promote` | call | [promotion_target](../modules/promotion_target.md) | 3 |
| `test_skill_lifecycle` | import | [test_skill_lifecycle](../modules/test_skill_lifecycle.md) | — |
