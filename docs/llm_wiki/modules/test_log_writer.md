# test_log_writer Module

**Path:** `tests/test_log_writer.py`

## Description

_Auto-generated from `tests/test_log_writer.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core.log_writer` | `AgentLogWriter` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/log_writer.py"]
    n1["tests/test_log_writer.py"]
    n1 --> n0
    click n0 "../modules/log_writer.md"
    click n1 "../modules/test_log_writer.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [log_writer](../modules/log_writer.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `test_agent_log_writer_persists_stable_line_numbers` | *(async)* `(tmp_path: Path)` | `@pytest.mark.asyncio` | — |
