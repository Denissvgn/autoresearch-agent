# Usage

**Location:** `src/core/llm_provider.py:145`
**Kind:** Class
**Bases:** —
**Module:** [llm_provider](../modules/llm_provider.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Token accounting for one provider call (spike §3.6).

``cache_read_tokens`` / ``cache_write_tokens`` default to 0 and are unused
today (the orchestrator reads only input/output, ``orchestrator.py``
``run``); additive so P1-003 can capture cache-aware cost without breaking
parity.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `input_tokens` | `int` | *required* | — |
| `output_tokens` | `int` | *required* | — |
| `cache_read_tokens` | `int` | `0` | — |
| `cache_write_tokens` | `int` | `0` | — |
| `reasoning_tokens` | `int` | `0` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["Usage (src/core/llm_provider.py)"]
    n1["_from_openai_response (src/core/llm_provider.py)"]
    n2["_from_sdk_response (src/core/llm_provider.py)"]
    n3["AnthropicProvider.estimate_cost (src/core/llm_provider.py)"]
    n4["AnthropicProvider.price_quote (src/core/llm_provider.py)"]
    n5["LLMProvider.estimate_cost (src/core/llm_provider.py)"]
    n6["LLMProvider.price_quote (src/core/llm_provider.py)"]
    n7["MockProvider.estimate_cost (src/core/llm_provider.py)"]
    n8["MockProvider.messages_create (src/core/llm_provider.py)"]
    n9["MockProvider.price_quote (src/core/llm_provider.py)"]
    n10["OpenAIProvider.estimate_cost (src/core/llm_provider.py)"]
    n11["OpenAIProvider.price_quote (src/core/llm_provider.py)"]
    n12["AgentOrchestrator._record_usage (src/core/orchestrator.py)"]
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
    click n4 "../modules/llm_provider.md"
    click n5 "../modules/llm_provider.md"
    click n6 "../modules/llm_provider.md"
    click n7 "../modules/llm_provider.md"
    click n8 "../modules/llm_provider.md"
    click n9 "../modules/llm_provider.md"
    click n10 "../modules/llm_provider.md"
    click n11 "../modules/llm_provider.md"
    click n12 "../modules/orchestrator.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [llm_provider](../modules/llm_provider.md) | 0 | `cache_read_tokens`, `cache_write_tokens`, `input_tokens`, `output_tokens`, `reasoning_tokens` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_from_openai_response` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `_from_sdk_response` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `AnthropicProvider.estimate_cost` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `AnthropicProvider.price_quote` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `LLMProvider.estimate_cost` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `LLMProvider.price_quote` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `MockProvider.estimate_cost` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `MockProvider.messages_create` | call | [llm_provider](../modules/llm_provider.md) | 3 |
| `MockProvider.price_quote` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `OpenAIProvider.estimate_cost` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `OpenAIProvider.price_quote` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `AgentOrchestrator._record_usage` | type_reference | [orchestrator](../modules/orchestrator.md) | — |

> References: showing 12 of 35 logical references; 23 omitted by the 12-row generated summary limit.
