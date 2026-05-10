# pipeline_controller Module

**Path:** `src/core/pipeline_controller.py`

## Description

ML-63: Pipeline controller — orchestrates direction → volatility → rl in sequence.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `datetime` | `datetime`, `timezone` |
| `json` | `json` |
| `logging` | `logging` |
| `src.config` | `settings` |
| `src.core.config_promoter` | `ConfigPromoter` |
| `src.core.results_store` | `ResultsStore` |
| `src.ws.events` | `broadcaster` |
| `time` | `time` |
| `typing` | `Any`, `Dict`, `List`, `Optional` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [PipelinePromotionBlocked](../entities/PipelinePromotionBlocked.md) | 82 | `RuntimeError` | Raised when a phase trains successfully but promotion gates block it. |
| [PipelineConfig](../entities/PipelineConfig.md) | 102 | — | Configuration for a pipeline run. |
| [PipelineController](../entities/PipelineController.md) | 163 | — | Orchestrates sequential direction → volatility → rl research. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_promotion_blockers` | `(preview: Optional[Dict[str, Any]]) -> list[str]` | — | Collect human-inspectable blockers from a ConfigPromoter preview. |
| `_promotion_preview_summary` | `(preview: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]` | — | Keep blocked-promotion diagnostics inspectable without storing configs. |
