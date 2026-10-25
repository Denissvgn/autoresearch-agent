# ManifestValidationError

**Location:** `src/core/skill_manifest.py:1255`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

Raised when a manifest fails structural validation. Wraps a pydantic
``ValidationError`` with a field-specific, human-readable summary (P2-001
AC #3).

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(message: str, *, errors: Optional[list[Mapping[str, Any]]] = None) -> None` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ManifestValidationError (src/core/skill_manifest.py)"]
    n1["ValueError"]
    n2["ManifestVersionError (src/core/skill_manifest.py)"]
    n3["src/api/research.py"]
    n4["src/core/skill_generator.py"]
    n5["_resolve_caps (src/core/skill_loader.py)"]
    n6["_wrap_validation_error (src/core/skill_loader.py)"]
    n7["load_skill_manifest (src/core/skill_loader.py)"]
    n8["tests/test_significance.py"]
    n9["tests/test_skill_loader.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/skill_manifest.md"
    click n2 "../modules/skill_manifest.md"
    click n3 "../modules/research.md"
    click n4 "../modules/skill_generator.md"
    click n5 "../modules/skill_loader.md"
    click n6 "../modules/skill_loader.md"
    click n7 "../modules/skill_loader.md"
    click n8 "../modules/test_significance.md"
    click n9 "../modules/test_skill_loader.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 1 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |
| Subclass | `ManifestVersionError` | [skill_manifest](../modules/skill_manifest.md) |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `research` | import | [research](../modules/research.md) | — |
| `skill_generator` | import | [skill_generator](../modules/skill_generator.md) | — |
| `_resolve_caps` | call | [skill_loader](../modules/skill_loader.md) | 3 |
| `_wrap_validation_error` | call | [skill_loader](../modules/skill_loader.md) | 1 |
| `_wrap_validation_error` | type_reference | [skill_loader](../modules/skill_loader.md) | — |
| `load_skill_manifest` | call | [skill_loader](../modules/skill_loader.md) | 3 |
| `test_significance` | import | [test_significance](../modules/test_significance.md) | — |
| `test_skill_loader` | import | [test_skill_loader](../modules/test_skill_loader.md) | — |
