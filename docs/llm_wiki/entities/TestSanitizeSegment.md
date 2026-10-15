# TestSanitizeSegment

**Location:** `tests/test_skill_paths.py:89`
**Kind:** Class
**Bases:** —
**Module:** [test_skill_paths](../modules/test_skill_paths.md)

## Description

_Auto-generated from `TestSanitizeSegment` in `tests/test_skill_paths.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_rejects_unsafe_segments` | `(bad: str)` | `@pytest.mark.parametrize('bad', ['', '.', '..', 'a/b', 'a\\b', 'a\x00b'])` | — |
| `test_accepts_ordinary_segments` | `()` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_skill_paths](../modules/test_skill_paths.md) | 2 | — |
