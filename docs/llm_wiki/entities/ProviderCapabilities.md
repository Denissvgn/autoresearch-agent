# ProviderCapabilities

**Location:** `src/core/llm_provider.py:261`
**Kind:** Class
**Bases:** —
**Module:** [llm_provider](../modules/llm_provider.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Static capability advertisement (→ P4-009 capabilities / P4-010 router).

In v1 all targeted providers set ``native_tool_use=True`` and
``system_prompt=True``; the flags are forward-looking (e.g. a local model
without native tool use would need a prompt-based tool-use shim).
``max_output_tokens`` is the adapter's per-request output ceiling;
``None`` means the adapter imposes no ceiling of its own.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `native_tool_use` | `bool` | *required* | — |
| `streaming` | `bool` | *required* | — |
| `system_prompt` | `bool` | *required* | — |
| `max_context_tokens` | `int` | *required* | — |
| `max_output_tokens` | `Optional[int]` | `None` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ProviderCapabilities (src/core/llm_provider.py)"]
    n1["AnthropicProvider.capabilities (src/core/llm_provider.py)"]
    n2["clamp_output_tokens (src/core/llm_provider.py)"]
    n3["LLMProvider.capabilities (src/core/llm_provider.py)"]
    n4["MockProvider.capabilities (src/core/llm_provider.py)"]
    n5["OpenAIProvider.capabilities (src/core/llm_provider.py)"]
    n6["RequiredCapabilities.check (src/core/llm_provider.py)"]
    n7["_OnePerTurnScriptedProvider.capabilities (tests/test_domain_conformance.py)"]
    n8["test_value_types_are_frozen_and_construct_correctly (tests/test_llm_provider.py)"]
    n9["TestCapabilityMatching.test_insufficient_context_raises (tests/test_llm_provider_openai.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    click n0 "../modules/llm_provider.md"
    click n1 "../modules/llm_provider.md"
    click n2 "../modules/llm_provider.md"
    click n3 "../modules/llm_provider.md"
    click n4 "../modules/llm_provider.md"
    click n5 "../modules/llm_provider.md"
    click n6 "../modules/llm_provider.md"
    click n7 "../modules/test_domain_conformance.md"
    click n8 "../modules/test_llm_provider.md"
    click n9 "../modules/test_llm_provider_openai.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [llm_provider](../modules/llm_provider.md) | 0 | `max_context_tokens`, `max_output_tokens`, `native_tool_use`, `streaming`, `system_prompt` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `AnthropicProvider.capabilities` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `AnthropicProvider.capabilities` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `clamp_output_tokens` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `LLMProvider.capabilities` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `MockProvider.capabilities` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `MockProvider.capabilities` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `OpenAIProvider.capabilities` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `OpenAIProvider.capabilities` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `RequiredCapabilities.check` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `_OnePerTurnScriptedProvider.capabilities` | call | [test_domain_conformance](../modules/test_domain_conformance.md) | 1 |
| `test_value_types_are_frozen_and_construct_correctly` | type_reference | [test_llm_provider](../modules/test_llm_provider.md) | — |
| `TestCapabilityMatching.test_insufficient_context_raises` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |

> References: showing 12 of 19 logical references; 7 omitted by the 12-row generated summary limit.
