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
| `os` | `os` |
| `pathlib` | `Path` |
| `secrets` | `secrets` |
| `shutil` | `shutil` |
| `socket` | `socket` |
| `src.config` | `settings` |
| `src.core` | `fs_safety` |
| `src.core.bootstrap_runner` | `BootstrapRunner` |
| `src.core.command_runner` | `CommandProcessRegistry` |
| `src.core.comparison_context` | `build_comparison_context` |
| `src.core.llm_provider` | `RequiredCapabilities`, `build_provider`, `resolve_effective_provider`, `resolve_model_roles` |
| `src.core.orchestrator` | `AgentOrchestrator`, `ResearchConfig` |
| `src.core.preflight` | `LocalFileCheck` |
| `src.core.research_manifest` | `build_research_manifest`, `load_persisted_manifest`, `manifest_pretty_json` |
| `src.core.run_artifacts` | `ArtifactStore`, `default_artifact_root`, `snapshot_parent_workspace`, `ArtifactStore`, `default_artifact_root` |
| `src.core.run_restore` | `assess_recovery`, `raise_unless_ready` |
| `src.core.run_spec` | `package_digests`, `skill_package_dir`, `package_digests`, `skill_package_dir` |
| `src.core.service_preflight` | `ServicePreflightTarget`, `require_preflight_ready`, `run_service_preflight` |
| `src.core.skill_loader` | `load_layout` |
| `src.core.skill_paths` | `session_workspace_path` |
| `src.core.skill_registry` | `default_registry`, `DEFAULT_SKILLS_ROOT`, `default_registry`, `default_registry`, `default_registry`, `default_registry`, `default_registry` |
| `src.core.skill_runtime` | `SkillConfigError`, `materialize_skill_runtime`, `SkillConfigError`, `SkillConfigError` |
| `src.core.state_machine` | `IllegalTransitionError`, `SessionEvent`, `SessionState`, `SessionStateMachine` |
| `src.core.state_store` | `BudgetExceeded`, `CapacityExceeded`, `StateStore` |
| `src.core.support_matrix` | `validate_manifest_support` |
| `src.ws.events` | `broadcaster` |
| `typing` | `Any`, `Dict`, `List`, `Mapping`, `Optional`, `Tuple` |
| `uuid` | `uuid` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src"]
    n1["src/core/session_manager.py"]
    n2["tests"]
    n0 --> n1
    n1 --> n0
    n2 --> n1
    click n1 "../modules/session_manager.md"
```

> Module-level dependencies exceed the generated-diagram limits, so the diagram and table below group them by top-level package. Counts report the number of module neighbors in each package.

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | `src` (1) |
| Inbound | `tests` (17) |
| Outbound | `src` (21) |

> All 39 module neighbor(s) are summarized by package because the module-level view exceeds the 12-node limit.

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [ActiveSession](../entities/ActiveSession.md) | 97 | — | — |
| [SessionManager](../entities/SessionManager.md) | 104 | — | Manages the lifecycle of research sessions as asyncio tasks. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_derive_workspace_path` | `(*, skill_id: str, instrument: str, timeframe: str, model_type: str, research_id: str = '') -> str` | — | Session workspace path (ARC-012 P7-005 / D1). |
| `_hard_timeout_grace_s` | `(soft_timeout_s: int) -> int` | — | Bound hard-timeout grace to 5% of the soft timeout, 3-10 minutes. |
