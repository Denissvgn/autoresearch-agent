# session_manager Module

**Path:** `src/core/session_manager.py`

## Description

Session manager — tracks active asyncio tasks for research sessions.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `dataclasses` | `dataclass` |
| `datetime` | `datetime`, `timezone` |
| `json` | `json` |
| `logging` | `logging` |
| `pathlib` | `Path` |
| `shutil` | `shutil` |
| `src.config` | `settings` |
| `src.core.orchestrator` | `AgentOrchestrator`, `ResearchConfig` |
| `src.core.pipeline_controller` | `PipelineConfig`, `PipelineController` |
| `src.core.research_manifest` | `build_research_manifest`, `manifest_pretty_json` |
| `src.core.results_store` | `ResultsStore` |
| `src.core.service_preflight` | `require_preflight_ready`, `run_service_preflight` |
| `src.core.structured_hpo` | `build_structured_hpo_plan`, `hpo_plan_json` |
| `src.ws.events` | `broadcaster` |
| `typing` | `Any`, `Dict`, `Optional` |
| `uuid` | `uuid` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ActiveSession](../entities/ActiveSession.md) | 36 | — | — |
| [SessionManager](../entities/SessionManager.md) | 43 | — | Manages the lifecycle of research sessions as asyncio tasks. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_hard_timeout_grace_s` | `(soft_timeout_s: int) -> int` | — | Bound hard-timeout grace to 5% of the soft timeout, 3-10 minutes. |
