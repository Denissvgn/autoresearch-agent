# SkillNotRegisteredError

**Location:** `src/core/skill_registry.py:56`
**Kind:** Class
**Bases:** `KeyError`
**Module:** [skill_registry](../modules/skill_registry.md)

## Description

Raised when a skill id is not present in the registry.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(skill_id: str, *, available: Iterable[str] = ()) -> None` | — | — |
| `__str__` | `() -> str` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillNotRegisteredError (src/core/skill_registry.py)"]
    n1["KeyError"]
    n2["src/api/research.py"]
    n3["src/api/skills.py"]
    n4["src/api/subjects.py"]
    n5["SkillRegistry.get (src/core/skill_registry.py)"]
    n6["tests/test_skill_loader.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    click n0 "../modules/skill_registry.md"
    click n2 "../modules/research.md"
    click n3 "../modules/src_api_skills.md"
    click n4 "../modules/subjects.md"
    click n5 "../modules/skill_registry.md"
    click n6 "../modules/test_skill_loader.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_registry](../modules/skill_registry.md) | 2 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `KeyError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `research` | import | [research](../modules/research.md) | — |
| `skills` | import | [src_api_skills](../modules/src_api_skills.md) | — |
| `subjects` | import | [subjects](../modules/subjects.md) | — |
| `SkillRegistry.get` | call | [skill_registry](../modules/skill_registry.md) | 1 |
| `test_skill_loader` | import | [test_skill_loader](../modules/test_skill_loader.md) | — |
