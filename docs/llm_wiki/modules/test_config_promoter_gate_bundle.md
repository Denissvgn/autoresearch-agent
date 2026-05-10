# test_config_promoter_gate_bundle Module

**Path:** `tests/test_config_promoter_gate_bundle.py`

## Description

_Auto-generated from `tests/test_config_promoter_gate_bundle.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core` | `config_promoter` |
| `src.core.config_promoter` | `ConfigPromoter` |
| `src.core.development_gate_bundle` | `DEFAULT_GATE_BUNDLE_RELATIVE_PATH`, `PRODUCTION_GATE_BUNDLE_RELATIVE_PATH` |
| `src.core.results_store` | `ResultsStore` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [FakePromotionStore](../entities/FakePromotionStore.md) | 21 | — | — |
| [FakeMlflowResponse](../entities/FakeMlflowResponse.md) | 628 | — | — |
| [FakeMlflowAsyncClient](../entities/FakeMlflowAsyncClient.md) | 638 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_write_gate_bundle` | `(root: Path) -> None` | — | — |
| `_write_production_gate_bundle` | `(root: Path) -> None` | — | — |
| `_write_gate_bundle_with_rl` | `(root: Path) -> None` | — | — |
| `_write_gate_bundle_with_m7_controls` | `(root: Path) -> None` | — | — |
| `_write_gate_bundle_with_m7_remaining` | `(root: Path) -> None` | — | — |
| `_passing_metrics` | `() -> dict` | — | — |
| `_passing_rl_oos` | `() -> dict` | — | — |
| `_passing_rl_economic_replay` | `() -> dict` | — | — |
| `_passing_m7_remaining_metrics` | `() -> dict` | — | — |
| `_passing_rl_metrics` | `() -> dict` | — | — |
| `_production_scope_metrics` | `() -> dict` | — | — |
| `_approval` | `() -> dict` | — | — |
| `_promotion_row` | `(scope: str, promotion_id: int = 1) -> dict` | — | — |
| `_install_fake_mlflow_client` | `(monkeypatch) -> FakeMlflowAsyncClient` | — | — |
| `_best_iteration` | `(metrics: dict) -> dict` | — | — |
| `test_model_version_tag_prefers_serving_and_ensemble_fields` | `()` | — | — |
| `test_preview_includes_blocking_gate_bundle_result` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_weak_calibration_and_signal_saturation_exactly` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_unstable_fold_thresholds` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_worsening_post_cost_replay_even_if_replay_gates_pass` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_confirm_requires_development_gate_bundle_pass` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_allows_feature_candidate_without_economic_replay` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_confirm_requires_cross_service_consistency` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_confirm_records_promotion_when_bundle_passes` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_live_production_promotion_intent` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_missing_required_inference_parity` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_confirm_persists_development_metadata_with_results_store` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_production_scope_blocks_without_paper_and_canary` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_production_scope_records_full_decision_chain` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_production_scope_requires_mlflow_service_token` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_production_scope_fails_without_matching_composite_before_record` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_production_scope_fails_on_ambiguous_composite_before_record` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_paper_scope_remains_local_only` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_finalist_with_proxy_direction_rl_oos` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_accepts_finalist_with_honest_rl_oos` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_accepts_rl_candidate_with_honest_oos_provenance` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_rl_candidate_missing_economic_replay` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_rl_candidate_worsening_economic_replay` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_rl_candidate_missing_volatility_provenance` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_rl_candidate_with_volatility_fallback` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_rl_candidate_without_nested_or_multi_seed_oos` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_derives_addressable_rollback_and_smoke_readiness` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_confirm_writes_rollback_snapshot_and_rollback_restores_previous_config` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_tsfm_candidate_without_fallback_check` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_records_tsfm_fallback_check_when_present` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_emits_development_signal_health_metrics` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_blocks_missing_development_signal_health_metrics` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_preview_records_inference_reload_validation` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
| `test_confirm_blocks_reload_failure_before_replacing_prior_config` | `*(async)* (tmp_path, monkeypatch)` | `@pytest.mark.asyncio` | — |
