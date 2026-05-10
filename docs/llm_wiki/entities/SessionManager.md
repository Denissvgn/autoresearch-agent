# SessionManager

**Location:** `src/core/session_manager.py:43`
**Bases:** —
**Module:** [session_manager](../modules/session_manager.md)

## Description

Manages the lifecycle of research sessions as asyncio tasks.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(store: ResultsStore) -> None` | — | — |
| `active_count` | `() -> int` | `@property` | — |
| `is_running` | `(research_id: str) -> bool` | — | — |
| `_attach_done_callback` | `(task: asyncio.Task) -> None` | — | Log + broadcast any uncaught exception escaping a background task. |
| `recover_orphaned_sessions` | `*(async)* () -> Dict[str, int]` | — | Classify sessions left active by a previous service process. |
| `_classify_orphaned_session` | `*(async)* (session: Dict[str, Any]) -> Dict[str, Any]` | — | — |
| `start_session` | `*(async)* () -> Dict` | — | — |
| `_start_session_unlocked` | `*(async)* () -> Dict` | — | Start a new research session. Returns the created session dict. |
| `_run_and_cleanup` | `*(async)* (research_id: str, config: ResearchConfig) -> None` | — | Wrapper that ensures cleanup after the orchestrator finishes. |
| `_run_preflight` | `*(async)* (model_type: str) -> Dict[str, Any]` | — | Run dependency checks and raise before any LLM task is spawned. |
| `_archive_stale_workspace` | `*(async)* (workspace_path: str) -> None` | — | Move an existing model workspace to a timestamped archive directory. |
| `_build_manifest_payload` | `(config: ResearchConfig) -> tuple[str, str]` | — | — |
| `_build_hpo_plan` | `(config: ResearchConfig) -> Dict[str, Any]` | — | — |
| `_merge_manifest_overrides` | `(overrides: Optional[Dict[str, Any]], hpo_plan: Dict[str, Any]) -> Dict[str, Any]` | `@staticmethod` | — |
| `_record_hpo_plan` | `*(async)* (config: ResearchConfig, hpo_plan: Dict[str, Any]) -> None` | — | — |
| `_write_manifest` | `*(async)* (config: ResearchConfig, manifest_json: str) -> str` | — | — |
| `continue_session` | `*(async)* (parent_id: str) -> Dict` | — | — |
| `_continue_session_unlocked` | `*(async)* (parent_id: str) -> Dict` | — | ML-62: Continue a timed-out session as a new chained session. |
| `resume_interrupted_session` | `*(async)* (parent_id: str) -> Dict` | — | Explicit operator-controlled continuation for restart recovery. |
| `start_pipeline` | `*(async)* () -> Dict` | — | — |
| `_start_pipeline_unlocked` | `*(async)* () -> Dict` | — | Start a pipeline that trains direction → volatility → rl in sequence. |
| `_run_pipeline_and_cleanup` | `*(async)* (pipeline_id: str, config: PipelineConfig) -> None` | — | — |
| `start_phase_session` | `*(async)* () -> Dict` | — | — |
| `_start_phase_session_unlocked` | `*(async)* () -> Dict` | — | Start a sub-session for a pipeline phase. |
| `stop_pipeline` | `*(async)* (pipeline_id: str) -> bool` | — | Stop a running pipeline and its current phase session. |
| `continue_pipeline` | `*(async)* (pipeline_id: str) -> Dict` | — | — |
| `_continue_pipeline_unlocked` | `*(async)* (pipeline_id: str) -> Dict` | — | Resume a terminal pipeline from its last incomplete phase. |
| `stop_session` | `*(async)* (research_id: str) -> bool` | — | Request a graceful stop for a running session. |
| `_drain_or_cancel_task` | `*(async)* (task: asyncio.Task) -> None` | — | Wait briefly for graceful stop, then cancel and free the active slot. |
| `_workspace_path_from_kwargs` | `(kwargs: Dict[str, Any]) -> Optional[str]` | `@staticmethod` | — |
| `_cleanup_failed_start_workspace` | `*(async)* (workspace_path: str) -> None` | — | — |
| `pause_session` | `*(async)* (research_id: str) -> bool` | — | — |
| `resume_session` | `*(async)* (research_id: str) -> bool` | — | — |
| `shutdown` | `*(async)* () -> None` | — | Gracefully cancel all active sessions and pipelines. |

## Relationships

- **imported_by**: [main](../modules/main.md)
- **imported_by**: [test_runtime_recovery](../modules/test_runtime_recovery.md)
