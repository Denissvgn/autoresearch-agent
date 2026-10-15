# log_writer Module

**Path:** `src/core/log_writer.py`

## Description

Persistent agent log writer — captures the full Claude conversation to JSONL.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `datetime` | `datetime`, `timezone` |
| `json` | `json` |
| `logging` | `logging` |
| `os` | `os` |
| `pathlib` | `Path` |
| `src.ws.events` | `broadcaster` |
| `typing` | `Any`, `Dict`, `List`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/results.py"]
    n1["src/core/log_writer.py"]
    n2["src/core/orchestrator.py"]
    n3["src/ws/events.py"]
    n4["tests/test_log_writer.py"]
    n0 --> n1
    n1 --> n3
    n2 --> n1
    n2 --> n3
    n4 --> n1
    click n0 "../modules/results.md"
    click n1 "../modules/log_writer.md"
    click n2 "../modules/orchestrator.md"
    click n3 "../modules/events.md"
    click n4 "../modules/test_log_writer.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [results](../modules/results.md) |
| Inbound | [orchestrator](../modules/orchestrator.md) |
| Inbound | [test_log_writer](../modules/test_log_writer.md) |
| Outbound | [events](../modules/events.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [AgentLogWriter](../entities/AgentLogWriter.md) | 31 | — | Append-only JSONL log writer with WebSocket broadcasting. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_format_entry` | `(entry: Dict[str, Any]) -> str` | — | Format a single log entry as a human-readable line. |
