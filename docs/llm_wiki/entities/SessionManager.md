# SessionManager

**Location:** `src/core/session_manager.py:86`
**Kind:** Class
**Bases:** —
**Module:** [session_manager](../modules/session_manager.md)

## Description

Manages the lifecycle of research sessions as asyncio tasks.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(store: StateStore, *, state_machine: Optional[SessionStateMachine] = None) -> None` | — | — |
| `active_count` | `() -> int` | `@property` | — |
| `is_running` | `(research_id: str) -> bool` | — | — |
| `_attach_done_callback` | `(task: asyncio.Task, *, research_id: Optional[str] = None, pipeline_id: Optional[str] = None) -> None` | — | Log + persist + broadcast any uncaught exception escaping a |
| `_finalize_crashed_session` | *(async)* `(research_id: str, exc: BaseException) -> None` | — | Persist a terminal ``failed`` state for a crashed background task. |
| `recover_orphaned_sessions` | *(async)* `() -> Dict[str, int]` | — | Classify sessions left active by a previous service process. |
| `_classify_orphaned_session` | *(async)* `(session: Dict[str, Any]) -> Dict[str, Any]` | — | — |
| `start_session` | *(async)* `(**kwargs: Any) -> Dict` | — | — |
| `_start_session_unlocked` | *(async)* `(*, instrument: str, timeframe: str, model_type: str, tag: Optional[str] = None, quick_mode: Optional[bool] = None, max_iterations: Optional[int] = None, max_budget_usd: Optional[float] = None, timeout_minutes: Optional[int] = None, focus_hint: Optional[str] = None, manifest: Optional[Dict[str, Any]] = None, skill_id: Optional[str] = None, skill_params: Optional[Dict[str, Any]] = None, subject_id: Optional[str] = None, variant: Optional[str] = None) -> Dict` | — | Start a new research session. Returns the created session dict. |
| `_run_and_cleanup` | *(async)* `(research_id: str, config: ResearchConfig) -> None` | — | Wrapper that ensures cleanup after the orchestrator finishes. |
| `_validate_session_skill` | `(config: ResearchConfig) -> None` | `@staticmethod` | Validate the session's skill runtime before anything is persisted. |
| `_run_skill_bootstrap` | *(async)* `(config: ResearchConfig) -> None` | — | Render the session workspace with the skill's ``bootstrap.py`` |
| `_run_preflight` | *(async)* `(config: ResearchConfig) -> Dict[str, Any]` | — | Run the skill's declared dependency checks and raise before any |
| `_skill_preflight_targets` | `(skill_id: str) -> list[ServicePreflightTarget]` | `@staticmethod` | Map the skill manifest's ``preflight`` section to check targets. |
| `_archive_stale_workspace` | *(async)* `(workspace_path: str) -> None` | — | Move an existing model workspace to a timestamped archive directory. |
| `_build_manifest_payload` | `(config: ResearchConfig, *, overrides: Optional[Dict[str, Any]] = None) -> tuple[str, str, str]` | — | — |
| `_write_manifest` | *(async)* `(config: ResearchConfig, manifest_json: str) -> str` | — | — |
| `continue_session` | *(async)* `(parent_id: str, **kwargs: Any) -> Dict` | — | — |
| `_continue_session_unlocked` | *(async)* `(parent_id: str, *, max_iterations: Optional[int] = None, max_budget_usd: Optional[float] = None, timeout_minutes: Optional[int] = None, focus_hint: Optional[str] = None) -> Dict` | — | ML-62: Continue a timed-out session as a new chained session. |
| `resume_interrupted_session` | *(async)* `(parent_id: str, *, reason: str, allow_interrupted: bool = False, max_iterations: Optional[int] = None, max_budget_usd: Optional[float] = None, timeout_minutes: Optional[int] = None, focus_hint: Optional[str] = None) -> Dict` | — | Explicit operator-controlled continuation for restart recovery. |
| `stop_session` | *(async)* `(research_id: str) -> bool` | — | Request a graceful stop for a running session. |
| `_drain_or_cancel_task` | *(async)* `(task: asyncio.Task, *, label: str, active_dict: Dict[str, Any], active_key: str, grace_s: float = 5.0) -> None` | — | Wait briefly for graceful stop, then cancel and free the active slot. |
| `_workspace_path_from_kwargs` | `(kwargs: Dict[str, Any]) -> Optional[str]` | `@staticmethod` | — |
| `_cleanup_failed_start_workspace` | *(async)* `(workspace_path: str) -> None` | — | — |
| `pause_session` | *(async)* `(research_id: str) -> bool` | — | — |
| `resume_session` | *(async)* `(research_id: str) -> bool` | — | — |
| `shutdown` | *(async)* `() -> None` | — | Gracefully cancel all active sessions and pipelines. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SessionManager (src/core/session_manager.py)"]
    n1["lifespan (src/main.py)"]
    n2["_start_and_capture (tests/test_canonical_start_wiring.py)"]
    n3["_manager_with_fake_orchestrator (tests/test_cross_worker_control.py)"]
    n4["tests/test_distributed_state_store.py"]
    n5["test_workspace_manifest_omits_nonce (tests/test_metrics_forgery_c3.py)"]
    n6["tests/test_research_manifest.py"]
    n7["test_orphaned_running_session_becomes_resumable (tests/test_runtime_recovery.py)"]
    n8["test_runtime_resume_requires_operator_and_creates_chained_session (tests/test_runtime_recovery.py)"]
    n9["test_session_start_persists_preflight_in_manifest (tests/test_service_preflight.py)"]
    n10["test_session_start_preflight_failure_skips_llm_call (tests/test_service_preflight.py)"]
    n11["_make_manager (tests/test_session_failure_modes.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    n11 --> n0
    click n0 "../modules/session_manager.md"
    click n1 "../modules/src_main.md"
    click n2 "../modules/test_canonical_start_wiring.md"
    click n3 "../modules/test_cross_worker_control.md"
    click n4 "../modules/test_distributed_state_store.md"
    click n5 "../modules/test_metrics_forgery_c3.md"
    click n6 "../modules/test_research_manifest.md"
    click n7 "../modules/test_runtime_recovery.md"
    click n8 "../modules/test_runtime_recovery.md"
    click n9 "../modules/test_service_preflight.md"
    click n10 "../modules/test_service_preflight.md"
    click n11 "../modules/test_session_failure_modes.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [session_manager](../modules/session_manager.md) | 27 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `lifespan` | call | [src_main](../modules/src_main.md) | 1 |
| `_start_and_capture` | call | [test_canonical_start_wiring](../modules/test_canonical_start_wiring.md) | 1 |
| `_manager_with_fake_orchestrator` | call | [test_cross_worker_control](../modules/test_cross_worker_control.md) | 1 |
| `_manager_with_fake_orchestrator` | type_reference | [test_cross_worker_control](../modules/test_cross_worker_control.md) | — |
| `test_distributed_state_store` | import | [test_distributed_state_store](../modules/test_distributed_state_store.md) | — |
| `test_workspace_manifest_omits_nonce` | call | [test_metrics_forgery_c3](../modules/test_metrics_forgery_c3.md) | 1 |
| `test_research_manifest` | import | [test_research_manifest](../modules/test_research_manifest.md) | — |
| `test_orphaned_running_session_becomes_resumable` | call | [test_runtime_recovery](../modules/test_runtime_recovery.md) | 1 |
| `test_runtime_resume_requires_operator_and_creates_chained_session` | call | [test_runtime_recovery](../modules/test_runtime_recovery.md) | 1 |
| `test_session_start_persists_preflight_in_manifest` | call | [test_service_preflight](../modules/test_service_preflight.md) | 1 |
| `test_session_start_preflight_failure_skips_llm_call` | call | [test_service_preflight](../modules/test_service_preflight.md) | 1 |
| `_make_manager` | call | [test_session_failure_modes](../modules/test_session_failure_modes.md) | 1 |

> References: showing 12 of 21 logical references; 9 omitted by the 12-row generated summary limit.
