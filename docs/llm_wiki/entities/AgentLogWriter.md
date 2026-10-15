# AgentLogWriter

**Location:** `src/core/log_writer.py:31`
**Kind:** Class
**Bases:** —
**Module:** [log_writer](../modules/log_writer.md)

## Description

Append-only JSONL log writer with WebSocket broadcasting.

Each line is a JSON object:
    {"ts": str, "turn": int, "type": str, "content": str, "meta": dict}

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(log_path: Path, research_id: str, *, pipeline_id: Optional[str] = None, phase: Optional[str] = None) -> None` | — | — |
| `append` | *(async)* `(entry_type: str, content: str, turn: int = -1, meta: Optional[Dict[str, Any]] = None) -> None` | — | Append one log entry to file and broadcast via WebSocket. |
| `_write_line` | `(line: str) -> None` | — | — |
| `_existing_line_count` | `(log_path: Path) -> int` | `@staticmethod` | — |
| `read_all` | `(log_path: Path) -> str` | `@staticmethod` | Read the full log and return human-readable formatted text. |
| `read_lines` | `(log_path: Path, after_line: int = 0) -> List[Dict[str, Any]]` | `@staticmethod` | Return parsed entries after the given line number (0-based). |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["AgentLogWriter (src/core/log_writer.py)"]
    n1["src/api/results.py"]
    n2["AgentOrchestrator._call_llm_with_retry (src/core/orchestrator.py)"]
    n3["AgentOrchestrator._drain_oldest_pending_trial (src/core/orchestrator.py)"]
    n4["AgentOrchestrator._emit_auto_promotion_skipped (src/core/orchestrator.py)"]
    n5["AgentOrchestrator._finalize_tool_result (src/core/orchestrator.py)"]
    n6["AgentOrchestrator._make_command_output_callback (src/core/orchestrator.py)"]
    n7["AgentOrchestrator._try_auto_promote (src/core/orchestrator.py)"]
    n8["AgentOrchestrator._verify_kv_metrics (src/core/orchestrator.py)"]
    n9["AgentOrchestrator.run (src/core/orchestrator.py)"]
    n10["test_agent_log_writer_persists_stable_line_numbers (tests/test_log_writer.py)"]
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
    click n0 "../modules/log_writer.md"
    click n1 "../modules/results.md"
    click n2 "../modules/orchestrator.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/orchestrator.md"
    click n5 "../modules/orchestrator.md"
    click n6 "../modules/orchestrator.md"
    click n7 "../modules/orchestrator.md"
    click n8 "../modules/orchestrator.md"
    click n9 "../modules/orchestrator.md"
    click n10 "../modules/test_log_writer.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [log_writer](../modules/log_writer.md) | 6 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `results` | import | [results](../modules/results.md) | — |
| `AgentOrchestrator._call_llm_with_retry` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._drain_oldest_pending_trial` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._emit_auto_promotion_skipped` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._finalize_tool_result` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._make_command_output_callback` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._try_auto_promote` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._verify_kv_metrics` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator.run` | call | [orchestrator](../modules/orchestrator.md) | 1 |
| `test_agent_log_writer_persists_stable_line_numbers` | call | [test_log_writer](../modules/test_log_writer.md) | 2 |
