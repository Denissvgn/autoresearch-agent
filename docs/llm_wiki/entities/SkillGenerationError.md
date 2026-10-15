# SkillGenerationError

**Location:** `src/core/skill_generator.py:97`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [skill_generator](../modules/skill_generator.md)

## Description

Raised when a draft cannot be generated (LLM failure, schema invalid, …).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SkillGenerationError (src/core/skill_generator.py)"]
    n1["ValueError"]
    n2["src/api/skills.py"]
    n3["src/cli.py"]
    n4["_extract_json (src/core/skill_generator.py)"]
    n5["SkillGenerator._lint_python (src/core/skill_generator.py)"]
    n6["SkillGenerator._validate_manifest (src/core/skill_generator.py)"]
    n7["SkillGenerator.generate (src/core/skill_generator.py)"]
    n8["tests/test_skill_generator.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    click n0 "../modules/skill_generator.md"
    click n2 "../modules/src_api_skills.md"
    click n3 "../modules/cli.md"
    click n4 "../modules/skill_generator.md"
    click n5 "../modules/skill_generator.md"
    click n6 "../modules/skill_generator.md"
    click n7 "../modules/skill_generator.md"
    click n8 "../modules/test_skill_generator.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_generator](../modules/skill_generator.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `skills` | import | [src_api_skills](../modules/src_api_skills.md) | — |
| `cli` | import | [cli](../modules/cli.md) | — |
| `_extract_json` | call | [skill_generator](../modules/skill_generator.md) | 3 |
| `SkillGenerator._lint_python` | call | [skill_generator](../modules/skill_generator.md) | 1 |
| `SkillGenerator._validate_manifest` | call | [skill_generator](../modules/skill_generator.md) | 1 |
| `SkillGenerator.generate` | call | [skill_generator](../modules/skill_generator.md) | 4 |
| `test_skill_generator` | import | [test_skill_generator](../modules/test_skill_generator.md) | — |
