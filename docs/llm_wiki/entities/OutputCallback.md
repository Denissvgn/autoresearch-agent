# OutputCallback

**Location:** `src/core/command_runner.py:253`
**Kind:** Type alias
**Bases:** —
**Module:** [command_runner](../modules/command_runner.md)
**Target:** `Callable[[OutputStream, str], None]`

## Description

_Auto-generated from `OutputCallback` in `src/core/command_runner.py`._

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["OutputCallback (src/core/command_runner.py)"]
    n1["_execute_tool (src/core/agent_tools.py)"]
    n2["_tool_bash (src/core/agent_tools.py)"]
    n3["_collect_process_output (src/core/command_runner.py)"]
    n4["GovernedCommandRunner.run (src/core/command_runner.py)"]
    n5["AgentOrchestrator._make_command_output_callback (src/core/orchestrator.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/command_runner.md"
    click n1 "../modules/agent_tools.md"
    click n2 "../modules/agent_tools.md"
    click n3 "../modules/command_runner.md"
    click n4 "../modules/command_runner.md"
    click n5 "../modules/orchestrator.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [command_runner](../modules/command_runner.md) | 0 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_execute_tool` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_tool_bash` | type_reference | [agent_tools](../modules/agent_tools.md) | — |
| `_collect_process_output` | type_reference | [command_runner](../modules/command_runner.md) | — |
| `GovernedCommandRunner.run` | type_reference | [command_runner](../modules/command_runner.md) | — |
| `AgentOrchestrator._make_command_output_callback` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
