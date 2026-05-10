# FakeSessionManager

**Location:** `tests/test_api_auth.py:56`
**Bases:** —
**Module:** [test_api_auth](../modules/test_api_auth.md)

## Description

_Auto-generated from `FakeSessionManager` in `tests/test_api_auth.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `_active_pipelines` | `dict[str, object]` | `{...}` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `start_session` | `*(async)* ()` | — | — |
| `start_pipeline` | `*(async)* ()` | — | — |
| `stop_session` | `*(async)* (research_id: str)` | — | — |
| `stop_pipeline` | `*(async)* (pipeline_id: str)` | — | — |
| `pause_session` | `*(async)* (research_id: str)` | — | — |
| `resume_session` | `*(async)* (research_id: str)` | — | — |
| `continue_session` | `*(async)* (research_id: str)` | — | — |
| `resume_interrupted_session` | `*(async)* (research_id: str)` | — | — |
| `continue_pipeline` | `*(async)* (pipeline_id: str)` | — | — |
| `is_running` | `(research_id: str)` | — | — |

## Relationships

*No cross-module references detected.*
