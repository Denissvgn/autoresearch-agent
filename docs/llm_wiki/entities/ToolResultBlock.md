# ToolResultBlock

**Location:** `src/core/llm_provider.py:182`
**Kind:** Class
**Bases:** —
**Module:** [llm_provider](../modules/llm_provider.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

A tool result fed back to the model by the loop (request-side block).

Matches the orchestrator's existing tool-result shape
(``{"type": "tool_result", "tool_use_id", "content": <str>}``).

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `tool_use_id` | `str` | *required* | — |
| `content` | `str` | *required* | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ToolResultBlock (src/core/llm_provider.py)"]
    n1["AgentOrchestrator._finalize_tool_result (src/core/orchestrator.py)"]
    n2["test_to_sdk_messages_mixed_blocks (tests/test_anthropic_provider.py)"]
    n3["test_value_types_are_frozen_and_construct_correctly (tests/test_llm_provider.py)"]
    n4["TestToOpenAIMessages.test_tool_result_becomes_tool_message (tests/test_llm_provider_openai.py)"]
    n5["test_mock_provider_honors_custom_marker_prefix (tests/test_mock_provider.py)"]
    n6["test_mock_provider_relay_only_from_newest_tool_result (tests/test_mock_provider.py)"]
    n7["test_mock_provider_relays_governed_eval_marker (tests/test_mock_provider.py)"]
    n8["test_iteration_context_digest_appended_after_recorded_attempt (tests/test_prompt_promotion_policy.py)"]
    n9["test_iteration_context_digest_disabled (tests/test_prompt_promotion_policy.py)"]
    n10["test_iteration_context_digest_not_appended_without_recorded_attempt (tests/test_prompt_promotion_policy.py)"]
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
    click n0 "../modules/llm_provider.md"
    click n1 "../modules/orchestrator.md"
    click n2 "../modules/test_anthropic_provider.md"
    click n3 "../modules/test_llm_provider.md"
    click n4 "../modules/test_llm_provider_openai.md"
    click n5 "../modules/test_mock_provider.md"
    click n6 "../modules/test_mock_provider.md"
    click n7 "../modules/test_mock_provider.md"
    click n8 "../modules/test_prompt_promotion_policy.md"
    click n9 "../modules/test_prompt_promotion_policy.md"
    click n10 "../modules/test_prompt_promotion_policy.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [llm_provider](../modules/llm_provider.md) | 0 | `content`, `tool_use_id` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `AgentOrchestrator._finalize_tool_result` | call | [orchestrator](../modules/orchestrator.md) | 2 |
| `test_to_sdk_messages_mixed_blocks` | call | [test_anthropic_provider](../modules/test_anthropic_provider.md) | 1 |
| `test_value_types_are_frozen_and_construct_correctly` | type_reference | [test_llm_provider](../modules/test_llm_provider.md) | — |
| `TestToOpenAIMessages.test_tool_result_becomes_tool_message` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |
| `test_mock_provider_honors_custom_marker_prefix` | call | [test_mock_provider](../modules/test_mock_provider.md) | 1 |
| `test_mock_provider_relay_only_from_newest_tool_result` | call | [test_mock_provider](../modules/test_mock_provider.md) | 2 |
| `test_mock_provider_relays_governed_eval_marker` | call | [test_mock_provider](../modules/test_mock_provider.md) | 1 |
| `test_iteration_context_digest_appended_after_recorded_attempt` | call | [test_prompt_promotion_policy](../modules/test_prompt_promotion_policy.md) | 1 |
| `test_iteration_context_digest_disabled` | call | [test_prompt_promotion_policy](../modules/test_prompt_promotion_policy.md) | 1 |
| `test_iteration_context_digest_not_appended_without_recorded_attempt` | call | [test_prompt_promotion_policy](../modules/test_prompt_promotion_policy.md) | 1 |
