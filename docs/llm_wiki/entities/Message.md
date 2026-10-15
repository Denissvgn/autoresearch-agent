# Message

**Location:** `src/core/llm_provider.py:202`
**Kind:** Class
**Bases:** —
**Module:** [llm_provider](../modules/llm_provider.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

One conversation turn (spike §4, completion #2 for content shape).

``content`` is ``str`` for plain user prompts (the orchestrator builds the
initial user message as a string, ``orchestrator.py`` ``run``) and
``list[RequestBlock]`` for assistant turns and tool-result turns. Typing it
as the union keeps P1-002 a pass-through wrapper (parity-preserving).

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `role` | `str` | *required* | — |
| `content` | `str \| list[RequestBlock]` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["Message (src/core/llm_provider.py)"]
    n1["_to_openai_messages (src/core/llm_provider.py)"]
    n2["_to_sdk_messages (src/core/llm_provider.py)"]
    n3["AnthropicProvider.messages_create (src/core/llm_provider.py)"]
    n4["LLMProvider.messages_create (src/core/llm_provider.py)"]
    n5["MockProvider._last_tool_marker (src/core/llm_provider.py)"]
    n6["MockProvider.messages_create (src/core/llm_provider.py)"]
    n7["OpenAIProvider.messages_create (src/core/llm_provider.py)"]
    n8["AgentOrchestrator._call_llm_with_retry (src/core/orchestrator.py)"]
    n9["AgentOrchestrator._compact_messages (src/core/orchestrator.py)"]
    n10["AgentOrchestrator._latest_iteration_context_digest (src/core/orchestrator.py)"]
    n11["AgentOrchestrator.run (src/core/orchestrator.py)"]
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
    click n0 "../modules/llm_provider.md"
    click n1 "../modules/llm_provider.md"
    click n2 "../modules/llm_provider.md"
    click n3 "../modules/llm_provider.md"
    click n4 "../modules/llm_provider.md"
    click n5 "../modules/llm_provider.md"
    click n6 "../modules/llm_provider.md"
    click n7 "../modules/llm_provider.md"
    click n8 "../modules/orchestrator.md"
    click n9 "../modules/orchestrator.md"
    click n10 "../modules/orchestrator.md"
    click n11 "../modules/orchestrator.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [llm_provider](../modules/llm_provider.md) | 0 | `content`, `role` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_to_openai_messages` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `_to_sdk_messages` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `AnthropicProvider.messages_create` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `LLMProvider.messages_create` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `MockProvider._last_tool_marker` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `MockProvider.messages_create` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `OpenAIProvider.messages_create` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `AgentOrchestrator._call_llm_with_retry` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._compact_messages` | call | [orchestrator](../modules/orchestrator.md) | 1 |
| `AgentOrchestrator._compact_messages` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator._latest_iteration_context_digest` | type_reference | [orchestrator](../modules/orchestrator.md) | — |
| `AgentOrchestrator.run` | call | [orchestrator](../modules/orchestrator.md) | 7 |

> References: showing 12 of 30 logical references; 18 omitted by the 12-row generated summary limit.
