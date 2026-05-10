# AgentLogWriter

**Location:** `src/core/log_writer.py:30`
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
| `__init__` | `(log_path: Path, research_id: str) -> None` | — | — |
| `append` | `*(async)* (entry_type: str, content: str, turn: int = ..., meta: Optional[Dict[str, Any]] = None) -> None` | — | Append one log entry to file and broadcast via WebSocket. |
| `_write_line` | `(line: str) -> None` | — | — |
| `read_all` | `(log_path: Path) -> str` | `@staticmethod` | Read the full log and return human-readable formatted text. |
| `read_lines` | `(log_path: Path, after_line: int = 0) -> List[Dict[str, Any]]` | `@staticmethod` | Return parsed entries after the given line number (0-based). |

## Relationships

- **imported_by**: [results](../modules/results.md)
- **imported_by**: [orchestrator](../modules/orchestrator.md)
