# ProviderCapabilityMismatch

**Location:** `src/core/llm_provider.py:1215`
**Kind:** Class
**Bases:** `ValueError`
**Module:** [llm_provider](../modules/llm_provider.md)

## Description

Raised (ARC-011 P4-009) when a skill manifest's required capabilities
are not satisfied by the selected provider's ``capabilities()``.

Fail-closed: a session whose skill demands (e.g.) native tool use but is
routed to a provider that lacks it must be rejected at session start,
before any LLM call — mirroring the codebase's existing fail-closed posture
(production-approval HMAC, command policy default-deny).

## Attributes

*No annotated attributes found.*

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ProviderCapabilityMismatch (src/core/llm_provider.py)"]
    n1["ValueError"]
    n2["RequiredCapabilities.check (src/core/llm_provider.py)"]
    n3["src/core/orchestrator.py"]
    n4["tests/test_llm_provider_openai.py"]
    n5["tests/test_provider_roles.py"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    click n0 "../modules/llm_provider.md"
    click n2 "../modules/llm_provider.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/test_llm_provider_openai.md"
    click n5 "../modules/test_provider_roles.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [llm_provider](../modules/llm_provider.md) | 0 | — |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `ValueError` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `RequiredCapabilities.check` | call | [llm_provider](../modules/llm_provider.md) | 1 |
| `orchestrator` | import | [orchestrator](../modules/orchestrator.md) | — |
| `test_llm_provider_openai` | import | [test_llm_provider_openai](../modules/test_llm_provider_openai.md) | — |
| `test_provider_roles` | import | [test_provider_roles](../modules/test_provider_roles.md) | — |
