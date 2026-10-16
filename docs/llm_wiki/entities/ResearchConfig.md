# ResearchConfig

**Location:** `src/core/orchestrator.py:189`
**Kind:** Class
**Bases:** —
**Module:** [orchestrator](../modules/orchestrator.md)

**Decorators:** `@dataclass`

## Description

_Auto-generated from `ResearchConfig` in `src/core/orchestrator.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `id` | `str` | *required* | — |
| `instrument` | `str` | *required* | — |
| `timeframe` | `str` | *required* | — |
| `model_type` | `str` | *required* | — |
| `tag` | `str` | `''` | — |
| `quick_mode` | `bool` | `False` | — |
| `max_iterations` | `int` | `30` | — |
| `max_budget_usd` | `float` | `10.0` | — |
| `timeout_s` | `int` | `0` | — |
| `focus_hint` | `Optional[str]` | `None` | — |
| `workspace_path` | `str` | `''` | — |
| `resumed_from` | `Optional[str]` | `None` | — |
| `pipeline_id` | `Optional[str]` | `None` | — |
| `skill_id` | `str` | `''` | — |
| `skill_version` | `str` | `''` | — |
| `subject_id` | `str` | `''` | — |
| `variant` | `str` | `''` | — |
| `skill_params` | `dict` | `None` | — |
| `session_nonce` | `str` | `''` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__post_init__` | `() -> None` | — | — |
| `domain` | `() -> str` | `@property` | The research domain (legacy ``model_type`` value: direction/volatility/rl). |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ResearchConfig (src/core/orchestrator.py)"]
    n1["AgentOrchestrator._append_iteration_context_digest (src/core/orchestrator.py)"]
    n2["AgentOrchestrator._build_baseline_link (src/core/orchestrator.py)"]
    n3["AgentOrchestrator._build_evidence_replay_link (src/core/orchestrator.py)"]
    n4["AgentOrchestrator._build_iteration_context_digest (src/core/orchestrator.py)"]
    n5["AgentOrchestrator._build_phase_continuation_kick (src/core/orchestrator.py)"]
    n6["AgentOrchestrator._build_phase_contract_block (src/core/orchestrator.py)"]
    n7["AgentOrchestrator._build_phase_evidence_link (src/core/orchestrator.py)"]
    n8["AgentOrchestrator._derive_terminal_reason (src/core/orchestrator.py)"]
    n9["AgentOrchestrator._drain_oldest_pending_trial (src/core/orchestrator.py)"]
    n10["AgentOrchestrator._emit_auto_promotion_skipped (src/core/orchestrator.py)"]
    n11["AgentOrchestrator._finalize_tool_result (src/core/orchestrator.py)"]
    n12["AgentOrchestrator._guard_duplicate_training_attempt (src/core/orchestrator.py)"]
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
    n12 --> n0
    click n0 "../modules/orchestrator.md"
    click n1 "../modules/orchestrator.md"
    click n2 "../modules/orchestrator.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/orchestrator.md"
    click n5 "../modules/orchestrator.md"
    click n6 "../modules/orchestrator.md"
    click n7 "../modules/orchestrator.md"
    click n8 "../modules/orchestrator.md"
    click n9 "../modules/orchestrator.md"
    click n10 "../modules/orchestrator.md"
    click n11 "../modules/orchestrator.md"
    click n12 "../modules/orchestrator.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [orchestrator](../modules/orchestrator.md) | 2 | `focus_hint`, `id`, `instrument`, `max_budget_usd`, `max_iterations`, `model_type`, `pipeline_id`, `quick_mode`, `resumed_from`, `session_nonce`, `skill_id`, `skill_params` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `AgentOrchestrator._append_iteration_context_digest` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._build_baseline_link` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._build_evidence_replay_link` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._build_iteration_context_digest` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._build_phase_continuation_kick` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._build_phase_contract_block` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._build_phase_evidence_link` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._derive_terminal_reason` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._drain_oldest_pending_trial` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._emit_auto_promotion_skipped` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._finalize_tool_result` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._guard_duplicate_training_attempt` | type_reference | [orchestrator](../modules/orchestrator.md) | — |

> References: showing 12 of 105 logical references; 93 omitted by the 12-row generated summary limit.
