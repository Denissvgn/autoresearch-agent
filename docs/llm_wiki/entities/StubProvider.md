# StubProvider

**Location:** `tests/test_skill_generator.py:43`
**Kind:** Class
**Bases:** —
**Module:** [test_skill_generator](../modules/test_skill_generator.md)

## Description

Deterministic stand-in for ``LLMProvider.complete``.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(response: str) -> None` | — | — |
| `complete` | *(async)* `(*, model: str, prompt: str, system: str \| None = None, max_tokens: int = 8192) -> str` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["StubProvider (tests/test_skill_generator.py)"]
    n1["TestCommandPolicyAudit.test_findings_attached_to_generated_draft (tests/test_skill_generator.py)"]
    n2["TestGenerateDraft.test_draft_lands_under_drafts_subdir (tests/test_skill_generator.py)"]
    n3["TestGenerateDraft.test_explicit_skill_id_overrides_llm (tests/test_skill_generator.py)"]
    n4["TestGenerateDraft.test_generates_full_draft (tests/test_skill_generator.py)"]
    n5["TestGenerateFailurePaths.test_bad_skill_id_rejected (tests/test_skill_generator.py)"]
    n6["TestGenerateFailurePaths.test_empty_output_raises (tests/test_skill_generator.py)"]
    n7["TestGenerateFailurePaths.test_invalid_manifest_raises_no_files_written (tests/test_skill_generator.py)"]
    n8["TestGenerateFailurePaths.test_non_json_output_raises (tests/test_skill_generator.py)"]
    n9["TestGenerateFailurePaths.test_syntax_error_bootstrap_raises (tests/test_skill_generator.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/test_skill_generator.md"
    click n1 "../modules/test_skill_generator.md"
    click n2 "../modules/test_skill_generator.md"
    click n3 "../modules/test_skill_generator.md"
    click n4 "../modules/test_skill_generator.md"
    click n5 "../modules/test_skill_generator.md"
    click n6 "../modules/test_skill_generator.md"
    click n7 "../modules/test_skill_generator.md"
    click n8 "../modules/test_skill_generator.md"
    click n9 "../modules/test_skill_generator.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_skill_generator](../modules/test_skill_generator.md) | 2 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `TestCommandPolicyAudit.test_findings_attached_to_generated_draft` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateDraft.test_draft_lands_under_drafts_subdir` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateDraft.test_explicit_skill_id_overrides_llm` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateDraft.test_generates_full_draft` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateFailurePaths.test_bad_skill_id_rejected` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateFailurePaths.test_empty_output_raises` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateFailurePaths.test_invalid_manifest_raises_no_files_written` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateFailurePaths.test_non_json_output_raises` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
| `TestGenerateFailurePaths.test_syntax_error_bootstrap_raises` | call | [test_skill_generator](../modules/test_skill_generator.md) | 1 |
