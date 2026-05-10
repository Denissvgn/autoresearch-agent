# ConfigPromoter

**Location:** `src/core/config_promoter.py:82`
**Bases:** —
**Module:** [config_promoter](../modules/config_promoter.md)

## Description

Handles preview and confirmation of config promotion to host.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(store: ResultsStore) -> None` | — | — |
| `preview` | `*(async)* (research_id: str) -> Dict[str, Any]` | — | Dry-run promotion: returns the diff/preview without writing. |
| `confirm` | `*(async)* (research_id: str) -> Dict[str, Any]` | — | Execute the promotion: write best config to host bind mount. |
| `_confirm_scoped_promotion` | `*(async)* (research_id: str) -> Dict[str, Any]` | — | Record a paper/canary/production stage decision without rewriting dev config. |
| `_mlflow_service_auth_headers` | `() -> dict[str, str] | None` | — | — |
| `_composite_version_key` | `(model_type: str) -> str | None` | `@staticmethod` | — |
| `_model_version_components` | `(metrics_payload: Dict[str, Any]) -> tuple[str | None, Any]` | `@staticmethod` | — |
| `_model_version_tag` | `(metrics_payload: Dict[str, Any]) -> str` | `@classmethod` | — |
| `_promote_production_composite` | `*(async)* () -> Dict[str, Any]` | — | Promote the authoritative mlflow-service composite to production. |
| `_build_scoped_promotion_metadata` | `*(async)* () -> Dict[str, Any]` | — | Create an auditable decision artifact for non-development scopes. |
| `rollback` | `*(async)* () -> Dict[str, Any]` | — | Restore the latest development promotion for an instrument/timeframe. |
| `_build_development_promotion_metadata` | `() -> Dict[str, Any]` | — | Create the auditable development promotion decision artifact. |
| `_finalize_development_promotion_metadata` | `() -> Dict[str, Any]` | — | — |
| `_finalize_scoped_promotion_metadata` | `() -> Dict[str, Any]` | — | — |
| `_normalize_promotion_scope` | `(scope: str | None) -> str` | `@staticmethod` | — |
| `_required_prior_scopes` | `(scope: str) -> list[str]` | `@staticmethod` | — |
| `_latest_promotion_record` | `*(async)* () -> Optional[Dict[str, Any]]` | — | — |
| `_compact_promotion_record` | `(promotion: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]` | `@staticmethod` | — |
| `_decision_chain` | `() -> list[Dict[str, Any]]` | — | — |
| `_rollback_targets` | `() -> Dict[str, Optional[str]]` | — | — |
| `_approval_record` | `(approval: Optional[Dict[str, Any]]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_production_gate_bundle_summary` | `(scope: str) -> Dict[str, Any]` | `@staticmethod` | — |
| `_promotion_scope_evidence` | `() -> Dict[str, Any]` | — | — |
| `_promotion_evidence_container` | `(metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_first_mapping` | `() -> Dict[str, Any]` | `@staticmethod` | — |
| `_truthy_status` | `(container: Dict[str, Any]) -> bool` | `@staticmethod` | — |
| `_model_card_evidence` | `(metrics_payload: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_feature_readiness_evidence` | `(metrics_payload: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_paper_validation_evidence` | `(metrics_payload: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_canary_validation_evidence` | `(metrics_payload: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_inference_scope_evidence` | `(development_metadata: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_live_risk_limits_evidence` | `(metrics_payload: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_monitoring_alerts_evidence` | `(metrics_payload: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_rl_oos_scope_evidence` | `(metrics_payload: Dict[str, Any], development_metadata: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_rl_economic_replay_scope_evidence` | `(metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_numeric_value` | `() -> Optional[float]` | `@staticmethod` | — |
| `_best_iteration_payload` | `(best_iteration: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_attempt_snapshot_payload` | `(best_iteration: Dict[str, Any], metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_live_production_requested` | `(payload: Dict[str, Any]) -> bool` | `@staticmethod` | — |
| `_check_statuses` | `(gate_bundle_evaluation: Dict[str, Any]) -> list[dict[str, Any]]` | `@staticmethod` | — |
| `_registry_metadata` | `(best_iteration: Dict[str, Any], metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_composite_metadata` | `(metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_metadata_sidecar_path` | `(target_path: str, iteration: int) -> str` | `@staticmethod` | — |
| `_rollback_snapshot_path` | `() -> str` | `@staticmethod` | — |
| `_rollback_metadata_sidecar_path` | `(target_path: str, promotion_id: int) -> str` | `@staticmethod` | — |
| `_sha256_text` | `(value: str) -> str` | `@staticmethod` | — |
| `_write_text_file` | `*(async)* (path: str, content: str) -> None` | `@staticmethod` | Atomic write: tmp file → fsync → os.replace. |
| `_build_rollback_readiness` | `() -> Dict[str, Any]` | — | — |
| `_build_smoke_validation` | `() -> Dict[str, Any]` | — | — |
| `_best_iteration_with_preflight` | `(best_iteration: Dict[str, Any]) -> Dict[str, Any]` | — | — |
| `_inference_payload` | `(metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_tsfm_fallback_validation` | `(metrics_payload: Dict[str, Any]) -> Dict[str, Any]` | — | — |
| `_evaluate_gate_bundle` | `(model_type: str, best_iteration: Dict[str, Any]) -> Dict[str, Any]` | — | Evaluate the best iteration against the development gate bundle. |
| `_apply_pipeline_feature_replay_policy` | `() -> tuple[Dict[str, Any], Dict[str, Any]]` | `@staticmethod` | Do not require standalone economic replay for pipeline feature phases. |
| `_waive_missing_replay_check` | `(check: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_warn_missing_replay_check` | `(check: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_resolve_artifacts_dir` | `(workspace_path: str, model_type: str, instrument: str, timeframe: str) -> Optional[str]` | — | Find the directory containing trained model .pkl files. |
| `_update_composite_versions` | `*(async)* (instrument: str, model_type: str, version_tag: str) -> None` | — | PATCH the composite in mlflow-service with the new model version. |
| `_extract_strategy_market` | `(yaml_str: str) -> tuple` | `@staticmethod` | Extract agent_strategy and trading_mode from a YAML config string. |
| `_get_target_path` | `(model_type: str, instrument: str, timeframe: str, strategy: str = 'BALA', market_type: str = 'stock') -> str` | `@staticmethod` | Determine the host config file path for promotion. |

## Relationships

- **imported_by**: [pipeline_controller](../modules/pipeline_controller.md)
- **imported_by**: [main](../modules/main.md)
- **imported_by**: [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md)
- **imported_by**: [test_pipeline_promotion](../modules/test_pipeline_promotion.md)
