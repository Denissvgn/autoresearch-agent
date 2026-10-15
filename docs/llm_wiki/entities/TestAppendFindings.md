# TestAppendFindings

**Location:** `tests/test_insights_feedback.py:28`
**Kind:** Class
**Bases:** —
**Module:** [test_insights_feedback](../modules/test_insights_feedback.md)

## Description

_Auto-generated from `TestAppendFindings` in `tests/test_insights_feedback.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_writes_markdown_with_frontmatter` | `(tmp_path: Path)` | — | — |
| `test_idempotent_on_research_id` | `(tmp_path: Path)` | — | Re-running with the same research_id overwrites the same file (safe |
| `test_distinct_research_ids_get_distinct_files` | `(tmp_path: Path)` | — | — |
| `test_filename_is_safe` | `(tmp_path: Path)` | — | Path-traversal / weird characters in subject/variant are sanitized. |
| `test_creates_prior_findings_dir_if_absent` | `(tmp_path: Path)` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_insights_feedback](../modules/test_insights_feedback.md) | 5 | — |
