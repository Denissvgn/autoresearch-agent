# ResearchSessionManifest

**Location:** `src/core/research_manifest.py:16`
**Bases:** `BaseModel`
**Module:** [research_manifest](../modules/research_manifest.md)

## Description

Complete immutable manifest for one autonomous research session.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `schema_version` | `str` | `'research_session_manifest.v1'` | — |
| `research_id` | `str` | *required* | — |
| `created_at` | `str` | `Field(...)` | — |
| `instrument` | `str` | *required* | — |
| `timeframe` | `str` | *required* | — |
| `model_type` | `str` | `Field(...)` | — |
| `objective` | `str` | *required* | — |
| `model_family` | `str` | *required* | — |
| `data_window` | `Dict[str, Any]` | *required* | — |
| `baseline_config` | `Dict[str, Any]` | *required* | — |
| `roster` | `Dict[str, Any]` | *required* | — |
| `tsfm` | `Dict[str, Any]` | *required* | — |
| `adaptive_features` | `Dict[str, Any]` | *required* | — |
| `split_ids` | `Dict[str, Any]` | *required* | — |
| `cost_model` | `Dict[str, Any]` | *required* | — |
| `gate_bundle` | `Dict[str, Any]` | *required* | — |
| `budget` | `Dict[str, Any]` | *required* | — |
| `max_iterations` | `int` | `Field(...)` | — |
| `timeout_s` | `int` | `Field(...)` | — |
| `mlflow_experiment` | `str` | *required* | — |
| `promotion_policy` | `Dict[str, Any]` | *required* | — |
| `service_urls` | `Dict[str, str]` | *required* | — |
| `preflight` | `Dict[str, Any]` | *required* | — |
| `runtime` | `Dict[str, Any]` | *required* | — |
| `hpo` | `Dict[str, Any]` | `Field(...)` | — |
| `focus_hint` | `Optional[str]` | `None` | — |
| `manifest_hash` | `Optional[str]` | `None` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_not_blank` | `(value: str) -> str` | `@field_validator('instrument', 'timeframe', 'objective', 'model_family')`, `@classmethod` | — |
| `_require_manifest_sections` | `() -> 'ResearchSessionManifest'` | `@model_validator(mode='after')` | — |
| `canonical_json` | `() -> str` | — | — |
| `with_hash` | `() -> 'ResearchSessionManifest'` | — | — |

## Relationships

*No cross-module references detected.*
