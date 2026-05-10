# test_pipeline_promotion Module

**Path:** `tests/test_pipeline_promotion.py`

## Description

_Auto-generated from `tests/test_pipeline_promotion.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core` | `config_promoter`, `pipeline_controller` |
| `src.core.config_promoter` | `ConfigPromoter` |
| `src.core.development_gate_bundle` | `DEFAULT_GATE_BUNDLE_RELATIVE_PATH` |
| `src.core.pipeline_controller` | `PipelineConfig`, `PipelineController` |
| `src.core.results_store` | `ResultsStore` |
| `typing` | `Any` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [FakeSessionManager](../entities/test_pipeline_promotion_FakeSessionManager.md) | 16 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_write_gate_bundle` | `(root: Path) -> None` | — | — |
| `_supervised_metrics` | `() -> dict[str, Any]` | — | — |
| `_rl_metrics_missing_replay` | `() -> dict[str, Any]` | — | — |
| `_create_pipeline` | `*(async)* (store: ResultsStore, pipeline_id: str) -> None` | — | — |
| `test_pipeline_phase_promotes_through_config_promoter_and_records_metadata` | `*(async)* (tmp_path: Path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_pipeline_rl_phase_missing_replay_is_promotion_blocked` | `*(async)* (tmp_path: Path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_pipeline_feature_phase_not_blocked_only_for_missing_economic_replay` | `*(async)* (tmp_path: Path, monkeypatch, model_type: str)` | `@pytest.mark.asyncio`, `@pytest.mark.parametrize('model_type', ['direction', 'volatility'])` | — |
