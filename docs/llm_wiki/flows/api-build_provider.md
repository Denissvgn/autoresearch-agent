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
    participant p1 as _demo_requested
    participant p2 as MockProvider
    participant p3 as str(…).lower
    participant p4 as str
    participant p5 as getattr
    participant p6 as ValueError
    participant p7 as required_capabilities.check
    participant p8 as MockProvider.capabilities
    participant p9 as AnthropicProvider
    participant p10 as secret_value
    participant p11 as OpenAIProvider
    participant p12 as provider.capabilities
    participant p13 as ProviderCapabilities
    participant p14 as isinstance
    participant p15 as value.get_secret_value
    p0-->>p1: _demo_requested
    p0->>p2: MockProvider
    p0-->>p3: str(…).lower
    p0-->>p4: str(getattr(...))
    p0-->>p5: getattr(settings_obj, 'environment', 'development')
    p0-->>p6: ValueError('mock provider is refused in production')
    p0-->>p7: required_capabilities.check(mock.capabilities(...), 'mock')
    p0->>p8: MockProvider.capabilities
    p0->>p9: AnthropicProvider
    p0->>p10: secret_value
    p0-->>p5: getattr(settings_obj, 'openai_api_key', None)
    p0->>p11: OpenAIProvider
    p0->>p10: secret_value
    p0-->>p6: ValueError(...)
    p0-->>p7: required_capabilities.check(provider.capabilities(...), provider_id)
    p0-->>p12: provider.capabilities
    p8->>p13: ProviderCapabilities
    p10-->>p14: isinstance(value, SecretStr)
    p10-->>p15: value.get_secret_value
```

> Call sequence diagram shows 19 of 19 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 6 of 6 (0 omitted); unresolved 6 of 6 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. build_provider"]
    s2["2. _demo_requested"]
    s3["3. MockProvider"]
    s4["4. str(…).lower"]
    s5["5. str"]
    s6["6. getattr"]
    s7["7. ValueError"]
    s8["8. required_capabilities.check"]
    s9["9. MockProvider.capabilities"]
    s10["10. ProviderCapabilities"]
    s11["11. AnthropicProvider"]
    s12["12. secret_value"]
    s1 -. "_demo_requested(data not statically known)" .-> s2
    s1 -->|"MockProvider(data not statically known)"| s3
    s1 -. "str(…).lower(data not statically known)" .-> s4
    s1 -. "str(getattr(...))" .-> s5
    s1 -. "getattr(settings_obj, 'environment', 'development')" .-> s6
    s1 -. "ValueError('mock provider is refused in production')" .-> s7
    s1 -. "required_capabilities.check(mock.capabilities(...), 'mock')" .-> s8
    s1 -->|"MockProvider.capabilities(data not statically known)"| s9
    s9 -->|"ProviderCapabilities(native_tool_use=True, streaming=False, system_prompt=True, max_context_tokens=32000)"| s10
    s1 -->|"AnthropicProvider(base_url=..., api_key=..., timeout_s=settings_obj.anthropic_api_timeout_s)"| s11
    s1 -->|"secret_value(settings_obj.anthropic_auth_token)"| s12
    click s1 "../modules/llm_provider.md"
    click s3 "../modules/llm_provider.md"
    click s9 "../modules/llm_provider.md"
    click s10 "../modules/llm_provider.md"
    click s11 "../modules/llm_provider.md"
    click s12 "../modules/config.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `build_provider` | `provider_id: str`, `settings_obj: Any`, `required_capabilities: Optional[RequiredCapabilities]` | - | - | `mock`, `provider` |
| `_demo_requested` | - | - | - | - |
| `MockProvider` | - | - | - | - |
| `str(…).lower` | - | - | - | - |
| `str` | - | - | - | - |
| `getattr` | - | - | - | - |
| `ValueError` | - | - | - | - |
| `required_capabilities.check` | - | - | - | - |
| `MockProvider.capabilities` | - | - | - | `ProviderCapabilities(...)` |
| `ProviderCapabilities` | - | - | - | - |
| `AnthropicProvider` | - | - | - | - |
| `secret_value` | `value: SecretStr \| str \| None` | `SecretStr` | - | `value.get_secret_value(...)`, `value` |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| build_provider | _demo_requested | 1149 | `_demo_requested(data not statically known)` |
| build_provider | MockProvider | 1150 | `MockProvider(data not statically known)` |
| build_provider | str(…).lower | 1151 | `str(getattr(settings_obj, 'environment', 'development')).lower(data not statically known)` |
| build_provider | str | 1151 | `str(getattr(...))` |
| build_provider | getattr | 1151 | `getattr(settings_obj, 'environment', 'development')` |
| build_provider | ValueError | 1155 | `ValueError('mock provider is refused in production')` |
| build_provider | required_capabilities.check | 1157 | `required_capabilities.check(mock.capabilities(...), 'mock')` |
| build_provider | MockProvider.capabilities | 1157 | `mock.capabilities(data not statically known)` |
| MockProvider.capabilities | ProviderCapabilities | 1044 | `ProviderCapabilities(native_tool_use=True, streaming=False, system_prompt=True, max_context_tokens=32000)` |
| build_provider | AnthropicProvider | 1160 | `AnthropicProvider(base_url=..., api_key=..., timeout_s=settings_obj.anthropic_api_timeout_s)` |
| build_provider | secret_value | 1162 | `secret_value(settings_obj.anthropic_auth_token)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `build_provider` | `_demo_requested` | 1149 |
| unresolved_call | `build_provider` | `str(getattr(settings_obj, 'environment', 'development')).lower` | 1151 |
| external_call | `build_provider` | `getattr` | 1151 |
| external_call | `build_provider` | `ValueError` | 1155 |
| unresolved_call | `build_provider` | `required_capabilities.check` | 1157 |
| step_limit | `build_provider` | `first 12 steps` | 0 |

## Behavior

This flow starts at `build_provider` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
