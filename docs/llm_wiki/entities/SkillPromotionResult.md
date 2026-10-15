# SkillPromotionResult

**Location:** `src/core/promotion_target.py:599`
**Kind:** Class
**Bases:** —
**Module:** [promotion_target](../modules/promotion_target.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Outcome of a successful ``SkillRegistryPromotionTarget.promote`` call.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `skill_id` | `str` | *required* | — |
| `draft_path` | `str` | *required* | — |
| `stable_path` | `str` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillPromotionResult (src/core/promotion_target.py)"]
    n1["SkillRegistryPromotionTarget.promote (src/core/promotion_target.py)"]
    n1 --> n0
    click n0 "../modules/promotion_target.md"
    click n1 "../modules/promotion_target.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [promotion_target](../modules/promotion_target.md) | 0 | `draft_path`, `skill_id`, `stable_path` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `SkillRegistryPromotionTarget.promote` | call | [promotion_target](../modules/promotion_target.md) | 1 |
| `SkillRegistryPromotionTarget.promote` | type_reference | [promotion_target](../modules/promotion_target.md) | — |
