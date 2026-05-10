# ResultsStore

**Location:** `src/core/results_store.py:527`
**Bases:** —
**Module:** [results_store](../modules/results_store.md)

## Description

Async SQLite store for experiment data.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(db_path: str) -> None` | — | — |
| `initialize` | `*(async)* () -> None` | — | — |
| `connection` | `*(async)* () -> AsyncIterator[aiosqlite.Connection]` | `@asynccontextmanager` | Yield the long-lived SQLite connection initialized at startup. |
| `close` | `*(async)* () -> None` | — | Flush and close the long-lived SQLite connection. |
| `ping` | `*(async)* () -> bool` | — | Return True when the persistent DB connection can answer a query. |
| `get_schema_version` | `*(async)* () -> int` | — | — |
| `begin_idempotency_record` | `*(async)* () -> Optional[Dict[str, Any]]` | — | Reserve an idempotency key or return the existing record. |
| `complete_idempotency_record` | `*(async)* () -> None` | — | — |
| `delete_idempotency_record` | `*(async)* () -> None` | — | — |
| `record_audit_event` | `*(async)* () -> Dict[str, Any]` | — | — |
| `list_audit_events` | `*(async)* () -> List[Dict[str, Any]]` | — | — |
| `create_session` | `*(async)* () -> Dict[str, Any]` | — | — |
| `get_session` | `*(async)* (session_id: str) -> Optional[Dict[str, Any]]` | — | — |
| `list_sessions` | `*(async)* (status: Optional[str] = None, model_type: Optional[str] = None, instrument: Optional[str] = None, status_in: Optional[Sequence[str]] = None, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]` | — | — |
| `count_sessions` | `*(async)* (status: Optional[str] = None, model_type: Optional[str] = None, instrument: Optional[str] = None, status_in: Optional[Sequence[str]] = None) -> int` | — | Phase 5.1: total count for paginated listings. |
| `record_runtime_command` | `*(async)* () -> Dict[str, Any]` | — | — |
| `finish_runtime_command` | `*(async)* (command_id: int) -> Optional[Dict[str, Any]]` | — | — |
| `list_runtime_commands` | `*(async)* () -> List[Dict[str, Any]]` | — | — |
| `collect_observability_metrics` | `*(async)* () -> Dict[str, Any]` | — | Collect production research metrics from persisted state. |
| `interrupt_runtime_commands` | `*(async)* () -> int` | — | — |
| `update_session` | `*(async)* (session_id: str) -> Optional[Dict[str, Any]]` | — | — |
| `delete_session` | `*(async)* (session_id: str) -> bool` | — | — |
| `add_iteration` | `*(async)* () -> Dict[str, Any]` | — | — |
| `get_iterations` | `*(async)* (research_id: str) -> List[Dict[str, Any]]` | — | — |
| `update_iteration` | `*(async)* (research_id: str, iteration: int, marker: Dict[str, Any]) -> None` | — | Overwrite an existing iteration with richer data from an explicit |
| `get_iteration` | `*(async)* (research_id: str, iteration: int) -> Optional[Dict[str, Any]]` | — | — |
| `find_duplicate_trial_identity` | `*(async)* () -> Optional[Dict[str, Any]]` | — | Return an existing attempt with the same trial identity hash. |
| `get_best_iteration` | `*(async)* (research_id: str) -> Optional[Dict[str, Any]]` | — | — |
| `add_hpo_study` | `*(async)* () -> Dict[str, Any]` | — | — |
| `record_hpo_study_plan` | `*(async)* () -> Dict[str, Any]` | — | Persist a planned structured HPO study before training starts. |
| `get_hpo_studies` | `*(async)* (research_id: str) -> List[Dict[str, Any]]` | — | — |
| `record_planned_trials` | `*(async)* () -> List[Dict[str, Any]]` | — | Persist server-owned planned trials before execution. |
| `record_planned_trial_manual_review` | `*(async)* () -> Dict[str, Any]` | — | Record an off-plan structured HPO proposal for operator review. |
| `get_planned_trials` | `*(async)* (research_id: str) -> List[Dict[str, Any]]` | — | — |
| `get_planned_trial` | `*(async)* (research_id: str, trial_id: str) -> Optional[Dict[str, Any]]` | — | — |
| `get_planned_trial_for_command` | `*(async)* (research_id: str, expected_command: str) -> Optional[Dict[str, Any]]` | — | — |
| `update_planned_trial_status` | `*(async)* () -> Optional[Dict[str, Any]]` | — | — |
| `_decode_planned_trial` | `(row: Dict[str, Any]) -> None` | `@staticmethod` | — |
| `record_promotion` | `*(async)* () -> Dict[str, Any]` | — | — |
| `list_promotions` | `*(async)* () -> List[Dict[str, Any]]` | — | — |
| `get_latest_development_promotion` | `*(async)* () -> Optional[Dict[str, Any]]` | — | — |
| `get_latest_promotion` | `*(async)* () -> Optional[Dict[str, Any]]` | — | — |
| `record_promotion_rollback` | `*(async)* () -> Optional[Dict[str, Any]]` | — | — |
| `_decode_promotion_metadata` | `(row: Dict[str, Any]) -> None` | `@staticmethod` | — |
| `create_pipeline` | `*(async)* () -> Dict[str, Any]` | — | — |
| `get_pipeline` | `*(async)* (pipeline_id: str) -> Optional[Dict[str, Any]]` | — | — |
| `list_pipelines` | `*(async)* (status: Optional[str] = None, instrument: Optional[str] = None, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]` | — | — |
| `count_pipelines` | `*(async)* (status: Optional[str] = None, instrument: Optional[str] = None) -> int` | — | Phase 5.1: total count for paginated pipeline listings. |
| `update_pipeline` | `*(async)* (pipeline_id: str) -> Optional[Dict[str, Any]]` | — | — |
| `_decode_pipeline_metadata` | `(row: Dict[str, Any]) -> None` | `@staticmethod` | — |

## Relationships

- **imported_by**: [config_promoter](../modules/config_promoter.md)
- **imported_by**: [orchestrator](../modules/orchestrator.md)
- **imported_by**: [pipeline_controller](../modules/pipeline_controller.md)
- **imported_by**: [session_manager](../modules/session_manager.md)
- **imported_by**: [main](../modules/main.md)
- **imported_by**: [conftest](../modules/conftest.md)
- **imported_by**: [test_config_promoter_gate_bundle](../modules/test_config_promoter_gate_bundle.md)
- **used_by**: `store()` in [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md)
- **used_by**: `test_list_sessions_status_in_filters_at_sql_level()` in [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md)
- **used_by**: `test_results_store_records_schema_version()` in [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md)
- **used_by**: `test_results_store_idempotency_records_replay_and_conflict()` in [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md)
- **used_by**: `test_list_sessions_pagination()` in [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md)
- **used_by**: `_create_rl_session()` in [test_observability](../modules/test_observability.md)
- **imported_by**: [test_orchestrator_command_audit](../modules/test_orchestrator_command_audit.md)
- **used_by**: `_create_pipeline()` in [test_pipeline_promotion](../modules/test_pipeline_promotion.md)
- **imported_by**: [test_results_store_manifest_snapshots](../modules/test_results_store_manifest_snapshots.md)
- **used_by**: `_create_session()` in [test_runtime_recovery](../modules/test_runtime_recovery.md)
- **imported_by**: [test_service_preflight](../modules/test_service_preflight.md)
