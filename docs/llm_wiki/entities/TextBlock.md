# TextBlock

**Location:** `src/core/llm_provider.py:182`
**Kind:** Class
**Bases:** —
**Module:** [llm_provider](../modules/llm_provider.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

A text content block emitted by the model.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `text` | `str` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["TextBlock (src/core/llm_provider.py)"]
    n1["_from_openai_response (src/core/llm_provider.py)"]
    n2["_from_sdk_response (src/core/llm_provider.py)"]
    n3["MockProvider.messages_create (src/core/llm_provider.py)"]
    n4["AgentOrchestrator._append_iteration_context_digest (src/core/orchestrator.py)"]
    n5["AgentOrchestrator.run (src/core/orchestrator.py)"]
    n6["test_to_sdk_messages_mixed_blocks (tests/test_anthropic_provider.py)"]
    n7["_OnePerTurnScriptedProvider.messages_create (tests/test_domain_conformance.py)"]
    n8["test_value_types_are_frozen_and_construct_correctly (tests/test_llm_provider.py)"]
    n9["TestFromOpenAIResponse.test_text_only_end_turn (tests/test_llm_provider_openai.py)"]
    n10["TestToOpenAIMessages.test_assistant_with_tool_use (tests/test_llm_provider_openai.py)"]
    n11["tests/test_mock_provider.py"]
    n12["_fake_text_response (tests/test_orchestrator_loop_guard.py)"]
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
    click n0 "../modules/llm_provider.md"
    click n1 "../modules/llm_provider.md"
    click n2 "../modules/llm_provider.md"
    click n3 "../modules/llm_provider.md"
    click n4 "../modules/orchestrator.md"
    click n5 "../modules/orchestrator.md"
    click n6 "../modules/test_anthropic_provider.md"
    click n7 "../modules/test_domain_conformance.md"
    click n8 "../modules/test_llm_provider.md"
    click n9 "../modules/test_llm_provider_openai.md"
    click n10 "../modules/test_llm_provider_openai.md"
    click n11 "../modules/test_mock_provider.md"
    click n12 "../modules/test_orchestrator_loop_guard.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [llm_provider](../modules/llm_provider.md) | 0 | `text` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_from_openai_response` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `_from_sdk_response` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `MockProvider.messages_create` | call | [llm_provider](../modules/llm_provider.md) | 2 |
| `AgentOrchestrator._append_iteration_context_digest` | call | [orchestrator](../modules/orchestrator.md) | 1 |
| `AgentOrchestrator.run` | call | [orchestrator](../modules/orchestrator.md) | 7 |
| `test_to_sdk_messages_mixed_blocks` | call | [test_anthropic_provider](../modules/test_anthropic_provider.md) | 2 |
| `_OnePerTurnScriptedProvider.messages_create` | call | [test_domain_conformance](../modules/test_domain_conformance.md) | 1 |
| `test_value_types_are_frozen_and_construct_correctly` | type_reference | [test_llm_provider](../modules/test_llm_provider.md) | — |
| `TestFromOpenAIResponse.test_text_only_end_turn` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |
| `TestToOpenAIMessages.test_assistant_with_tool_use` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |
| `test_mock_provider` | import | [test_mock_provider](../modules/test_mock_provider.md) | — |
| `_fake_text_response` | call | [test_orchestrator_loop_guard](../modules/test_orchestrator_loop_guard.md) | 1 |

> References: showing 12 of 15 logical references; 3 omitted by the 12-row generated summary limit.
