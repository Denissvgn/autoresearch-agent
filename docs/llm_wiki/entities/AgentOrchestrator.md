# AgentOrchestrator

**Location:** `src/core/orchestrator.py:414`
**Bases:** —
**Module:** [orchestrator](../modules/orchestrator.md)

## Description

Runs a Claude agent session for autonomous ML experiment tuning.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(store: ResultsStore) -> None` | — | — |
| `request_stop` | `(research_id: str) -> None` | — | — |
| `request_pause` | `(research_id: str) -> None` | — | — |
| `request_resume` | `(research_id: str) -> None` | — | — |
| `_call_claude_with_retry` | `*(async)* () -> anthropic.types.Message` | — | Call messages.create() with retry + backoff on transient errors. |
| `_compact_messages` | `(messages: List[Dict[str, Any]], keep_recent: int = 40) -> List[Dict[str, Any]]` | `@staticmethod` | Bound retained conversation history to avoid unbounded memory growth. |
| `_latest_iteration_context_digest` | `(messages: List[Dict[str, Any]]) -> Optional[str]` | `@staticmethod` | — |
| `_should_stop` | `(research_id: str) -> bool` | — | — |
| `_wait_while_paused` | `*(async)* (research_id: str) -> None` | — | — |
| `_load_skill_async` | `*(async)* (model_type: str) -> str` | — | — |
| `_load_claude_md_async` | `*(async)* () -> str` | — | — |
| `_read_marker_file_async` | `*(async)* (config: ResearchConfig) -> Optional[str]` | — | — |
| `_load_skill` | `(model_type: str) -> str` | — | — |
| `_load_claude_md` | `() -> str` | — | — |
| `_read_marker_file` | `(config: ResearchConfig) -> Optional[str]` | — | Read and consume last_metrics.txt marker file if it exists. |
| `_load_research_resume` | `(config: ResearchConfig) -> str` | — | Load the research resume for this instrument if it exists. |
| `_read_research_resume_file` | `(resume_path: str) -> str` | `@staticmethod` | — |
| `_generate_research_resume_file` | `() -> None` | `@staticmethod` | — |
| `_build_prompt` | `(config: ResearchConfig) -> str` | — | — |
| `_build_resume_prompt` | `*(async)* (config: ResearchConfig) -> str` | — | ML-62: Build a prompt for resuming a timed-out session. |
| `_build_prompt_rl_hpo` | `(config: ResearchConfig, workspace: str, setup_extra_args: str, fixed_settings_notice: str, quick_flag: str, focus: str, instrument_underscore: str) -> str` | — | Build prompt for 3-phase HPO workflow (ML-59). |
| `_update_research_resume` | `*(async)* (instrument: str, timeframe: str) -> None` | — | Rebuild the research resume for an instrument after session ends. |
| `_extract_session_insights` | `*(async)* (research_id: str) -> None` | — | ML-60: Use Claude to extract compact insights from a completed session. |
| `_record_command_policy_rejection` | `*(async)* () -> None` | — | — |
| `_structured_hpo_enforced` | `(config: ResearchConfig) -> bool` | `@staticmethod` | — |
| `_active_hpo_study_id` | `*(async)* (research_id: str) -> Optional[str]` | — | — |
| `_ensure_structured_plan_materialized` | `*(async)* () -> None` | — | — |
| `_guard_structured_hpo_tool` | `*(async)* () -> tuple[Optional[Dict[str, Any]], Optional[ToolExecutionResult]]` | — | — |
| `_is_structured_hpo_config_write` | `(raw_path: str) -> bool` | `@staticmethod` | — |
| `_record_structured_hpo_manual_review` | `*(async)* () -> None` | — | — |
| `_attach_planned_trial_metadata` | `(marker: Dict[str, Any], planned_trial: Optional[Dict[str, Any]]) -> None` | `@staticmethod` | — |
| `_finish_planned_trial` | `*(async)* () -> None` | — | — |
| `_guard_duplicate_training_attempt` | `*(async)* () -> tuple[Optional[ToolExecutionResult], Optional[Dict[str, Any]]]` | — | Reject an already-attempted config/seed/mode/split identity. |
| `_build_iteration_context_digest` | `*(async)* () -> Optional[str]` | — | Build advisory context from persisted attempts for the next turn. |
| `_append_iteration_context_digest` | `*(async)* () -> None` | — | — |
| `run` | `*(async)* (config: ResearchConfig) -> None` | — | Run the autonomous research loop for a single session. |
| `_try_auto_promote` | `*(async)* (research_id: str, config: ResearchConfig, agent_log: AgentLogWriter) -> None` | — | Auto-promote the best iteration if it passed all gates. |
| `_infer_decision` | `*(async)* (research_id: str, primary_metric: Optional[float], all_gates_passed: bool) -> str` | — | Determine keep/improve/discard by comparing against session best. |
| `_record_iteration` | `*(async)* (research_id: str, iteration: int, marker: Dict[str, Any], cumulative_cost: float) -> None` | — | Record an iteration and broadcast the event. |
| `_attach_consistency_report` | `*(async)* (research_id: str, iteration: int, marker: Dict[str, Any]) -> None` | — | Attach/update consistency report before overwriting an iteration. |
| `_refresh_phase_state` | `*(async)* (research_id: str) -> None` | — | — |
| `_infer_failed_attempt_status` | `(tool_result: str) -> Optional[str]` | `@staticmethod` | — |
| `_effective_tool_timeout` | `(input_data: Dict[str, Any]) -> int` | `@staticmethod` | — |
| `_runtime_command_status` | `(tool_meta: Dict[str, Any]) -> str` | `@staticmethod` | — |
| `_attach_runtime_command_metadata` | `(marker: Dict[str, Any], tool_meta: Dict[str, Any]) -> None` | `@staticmethod` | — |

## Relationships

- **imported_by**: [session_manager](../modules/session_manager.md)
- **imported_by**: [test_orchestrator_command_audit](../modules/test_orchestrator_command_audit.md)
- **imported_by**: [test_prompt_promotion_policy](../modules/test_prompt_promotion_policy.md)
- **imported_by**: [test_runtime_recovery](../modules/test_runtime_recovery.md)
