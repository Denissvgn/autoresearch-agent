# build_provider

**Entry point:** `build_provider` (`api`)
**Source:** [llm_provider](../modules/llm_provider.md)
**Modules touched:** [config](../modules/config.md), [llm_provider](../modules/llm_provider.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as build_provider
    participant p1 as MockProvider.capabilities
    participant p2 as MockProvider
    participant p3 as _str_setting
    participant p4 as secret_value
    participant p5 as AnthropicProvider
    participant p6 as OpenAIProvider
    participant p7 as ProviderCapabilities
    participant p8 as str
    participant p9 as (…).strip().lower
    participant p10 as (…).strip
    participant p11 as _demo_requested
    participant p12 as str(…).lower
    participant p13 as getattr (src/core/llm_provider.py:build_provider)
    participant p14 as ValueError
    participant p15 as required_capabilities.check
    participant p16 as float
    participant p17 as provider.capabilities
    participant p18 as getattr (src/core/llm_provider.py:_str_setting)
    participant p19 as isinstance (src/config.py:secret_value)
    participant p20 as isinstance (src/core/llm_provider.py:_str_setting)
    participant p21 as value.get_secret_value
    p0->>p1: MockProvider.capabilities
    p0->>p2: MockProvider
    p0->>p3: _str_setting
    p0->>p4: secret_value
    p0->>p5: AnthropicProvider
    p0->>p6: OpenAIProvider
    p1->>p7: ProviderCapabilities
    p0-->>p8: str(getattr(...))
    p0-->>p9: (…).strip().lower
    p0-->>p10: (…).strip
    p0-->>p11: _demo_requested
    p0-->>p12: str(…).lower
    p0-->>p13: getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'environment', 'development')
    p0-->>p14: ValueError('mock provider is refused in production')
    p0-->>p15: required_capabilities.check(mock.capabilities(...), 'mock')
    p0-->>p13: getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'llm_api_key', None)
    p0-->>p13: getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'anthropic_auth_token', None)
    p0-->>p16: float(getattr(...))
    p0-->>p13: getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'anthropic_api_timeout_s', 600)
    p0-->>p13: getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'openai_api_key', None)
    p0-->>p16: float(getattr(...))
    p0-->>p13: getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'openai_api_timeout_s', 600)
    p0-->>p13: getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'openrouter_api_key', None)
    p0-->>p14: ValueError(...)
    p0-->>p15: required_capabilities.check(provider.capabilities(...), norm_id)
    p0-->>p17: provider.capabilities
    p3-->>p18: getattr (src/core/llm_provider.py:_str_setting)(settings_obj, attr, None)
    p4-->>p19: isinstance (src/config.py:secret_value)(value, SecretStr)
    p3-->>p20: isinstance (src/core/llm_provider.py:_str_setting)(val, str)
    p4-->>p21: value.get_secret_value
```

> Call sequence diagram shows 30 of 43 interactions; 13 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 15 of 15 (0 omitted); unresolved 8 of 9 (1 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/llm_provider.py:_str_setting` | 13 | - | unresolved | 1 |
| `src/core/llm_provider.py:build_provider` | 1 | [src/core/llm_provider.py](../modules/llm_provider.md) | internal | 9 |
| `src/core/llm_provider.py:build_provider` | 1 | [src/config.py](../modules/config.md) | internal | 3 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. build_provider"]
    s2["2. (…).strip().lower"]
    s3["3. (…).strip"]
    s4["4. _demo_requested"]
    s5["5. MockProvider"]
    s6["6. str(…).lower"]
    s7["7. str"]
    s8["8. getattr (src/core/llm_provider.py:build_provider)"]
    s9["9. ValueError"]
    s10["10. required_capabilities.check"]
    s11["11. MockProvider.capabilities"]
    s12["12. ProviderCapabilities"]
    s1 -. "(…).strip().lower(data not statically known)" .-> s2
    s1 -. "(…).strip(data not statically known)" .-> s3
    s1 -. "_demo_requested(data not statically known)" .-> s4
    s1 -->|"MockProvider(data not statically known)"| s5
    s1 -. "str(…).lower(data not statically known)" .-> s6
    s1 -. "str(getattr(...))" .-> s7
    s1 -. "getattr (src/core/llm_provider.py:build_provider)(settings_obj, 'environment', 'development')" .-> s8
    s1 -. "ValueError('mock provider is refused in production')" .-> s9
    s1 -. "required_capabilities.check(mock.capabilities(...), 'mock')" .-> s10
    s1 -->|"MockProvider.capabilities(data not statically known)"| s11
    s11 -->|"ProviderCapabilities(native_tool_use=True, streaming=False, system_prompt=True, max_context_tokens=32000)"| s12
    click s1 "../modules/llm_provider.md"
    click s5 "../modules/llm_provider.md"
    click s11 "../modules/llm_provider.md"
    click s12 "../modules/llm_provider.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `build_provider` | `provider_id: str`, `settings_obj: Any`, `required_capabilities: Optional[RequiredCapabilities]` | `OPENAI_COMPAT_PROVIDERS`, `SUPPORTED_LLM_PROVIDERS` | - | `mock`, `provider` |
| `(…).strip().lower` | - | - | - | - |
| `(…).strip` | - | - | - | - |
| `_demo_requested` | - | - | - | - |
| `MockProvider` | - | - | - | - |
| `str(…).lower` | - | - | - | - |
| `str` | - | - | - | - |
| `getattr (src/core/llm_provider.py:build_provider)` | - | - | - | - |
| `ValueError` | - | - | - | - |
| `required_capabilities.check` | - | - | - | - |
| `MockProvider.capabilities` | - | - | - | `ProviderCapabilities(...)` |
| `ProviderCapabilities` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| build_provider | (…).strip().lower | 1475 | `(provider_id or '').strip().lower(data not statically known)` |
| build_provider | (…).strip | 1475 | `(provider_id or '').strip(data not statically known)` |
| build_provider | _demo_requested | 1481 | `_demo_requested(data not statically known)` |
| build_provider | MockProvider | 1482 | `MockProvider(data not statically known)` |
| build_provider | str(…).lower | 1483 | `str(getattr(settings_obj, 'environment', 'development')).lower(data not statically known)` |
| build_provider | str | 1483 | `str(getattr(...))` |
| build_provider | getattr (src/core/llm_provider.py:build_provider) | 1483 | `getattr(settings_obj, 'environment', 'development')` |
| build_provider | ValueError | 1487 | `ValueError('mock provider is refused in production')` |
| build_provider | required_capabilities.check | 1489 | `required_capabilities.check(mock.capabilities(...), 'mock')` |
| build_provider | MockProvider.capabilities | 1489 | `mock.capabilities(data not statically known)` |
| MockProvider.capabilities | ProviderCapabilities | 1201 | `ProviderCapabilities(native_tool_use=True, streaming=False, system_prompt=True, max_context_tokens=32000)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `build_provider` | `(provider_id or '').strip().lower` | 1475 |
| unresolved_call | `build_provider` | `(provider_id or '').strip` | 1475 |
| unresolved_call | `build_provider` | `_demo_requested` | 1481 |
| unresolved_call | `build_provider` | `str(getattr(settings_obj, 'environment', 'development')).lower` | 1483 |
| external_call | `build_provider` | `getattr` | 1483 |
| external_call | `build_provider` | `ValueError` | 1487 |
| unresolved_call | `build_provider` | `required_capabilities.check` | 1489 |
| step_limit | `build_provider` | `first 12 steps` | 0 |

## Behavior

This flow starts at `build_provider` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
