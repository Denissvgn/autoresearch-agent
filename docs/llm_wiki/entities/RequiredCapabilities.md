# RequiredCapabilities

**Location:** `src/core/llm_provider.py:1072`
**Kind:** Class
**Bases:** —
**Module:** [llm_provider](../modules/llm_provider.md)

## Description

Subset of :class:`ProviderCapabilities` a skill demands (P4-009).

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(*, native_tool_use: Optional[bool] = None, system_prompt: Optional[bool] = None, max_context_tokens: Optional[int] = None) -> None` | — | — |
| `from_llm_config` | `(llm_cfg: Any) -> 'RequiredCapabilities'` | `@classmethod` | Build from a skill manifest's ``LLMConfig`` (P4-009). |
| `check` | `(caps: ProviderCapabilities, provider_id: str) -> None` | — | Raise :class:`ProviderCapabilityMismatch` if ``caps`` is insufficient. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["RequiredCapabilities (src/core/llm_provider.py)"]
    n1["build_provider (src/core/llm_provider.py)"]
    n2["RequiredCapabilities.from_llm_config (src/core/llm_provider.py)"]
    n3["src/core/orchestrator.py"]
    n4["TestCapabilityMatching.test_insufficient_context_raises (tests/test_llm_provider_openai.py)"]
    n5["TestCapabilityMatching.test_missing_native_tool_use_raises (tests/test_llm_provider_openai.py)"]
    n6["TestCapabilityMatching.test_missing_system_prompt_raises (tests/test_llm_provider_openai.py)"]
    n7["TestCapabilityMatching.test_satisfied_requirements_accepted (tests/test_llm_provider_openai.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    click n0 "../modules/llm_provider.md"
    click n1 "../modules/llm_provider.md"
    click n2 "../modules/llm_provider.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/test_llm_provider_openai.md"
    click n5 "../modules/test_llm_provider_openai.md"
    click n6 "../modules/test_llm_provider_openai.md"
    click n7 "../modules/test_llm_provider_openai.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [llm_provider](../modules/llm_provider.md) | 3 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `build_provider` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `RequiredCapabilities.from_llm_config` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `RequiredCapabilities.from_llm_config` | type_reference | [llm_provider](../modules/llm_provider.md) | — |
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `TestCapabilityMatching.test_insufficient_context_raises` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |
| `TestCapabilityMatching.test_missing_native_tool_use_raises` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |
| `TestCapabilityMatching.test_missing_system_prompt_raises` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |
| `TestCapabilityMatching.test_satisfied_requirements_accepted` | call | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | 1 |
