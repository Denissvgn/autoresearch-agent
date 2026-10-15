# test_insights_feedback Module

**Path:** `tests/test_insights_feedback.py`

## Description

Insights feedback loop tests (ARC-011 P5-027 / P5-028 / P5-029 / P5-030).

Covers:

* **P5-027** — completed-session insights append to ``knowledge/prior_findings/``
  as an idempotent markdown file (named with the research_id).
* **P5-028** — the ``auto_absorb_insights`` manifest flag is wired (default off).
* **P5-029** — the stale-knowledge computation: ``now - knowledge_last_reviewed >
  refresh_cadence_days`` → stale.
* **P5-030** — idempotency on research_id, filename safety, front-matter shape.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `datetime` | `datetime`, `timedelta`, `timezone` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core.insights_feedback` | `append_findings`, `prior_findings_path`, `render_findings_markdown` |
| `yaml` | `yaml` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/insights_feedback.py"]
    n1["tests/test_insights_feedback.py"]
    n1 --> n0
    click n0 "../modules/insights_feedback.md"
    click n1 "../modules/test_insights_feedback.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [insights_feedback](../modules/insights_feedback.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 2 | 1 |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [TestAppendFindings](../entities/TestAppendFindings.md) | 28 | — | — |
| [TestRenderFindings](../entities/TestRenderFindings.md) | 128 | — | — |
| [TestKnowledgeStale](../entities/TestKnowledgeStale.md) | 161 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_is_stale` | `(knowledge_last_reviewed: str \| None, refresh_cadence_days: int \| None, *, now: datetime) -> bool` | — | P5-029 helper: True when the knowledge corpus is past its refresh cadence. |
