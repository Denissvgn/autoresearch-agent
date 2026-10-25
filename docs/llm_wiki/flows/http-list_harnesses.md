# list_harnesses

**Entry point:** `list_harnesses` (`http`)
**Source:** [harnesses](../modules/harnesses.md)
**Modules touched:** [harnesses](../modules/harnesses.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as list_harnesses
    participant p1 as HTTPException
    participant p2 as _descriptor
    participant p3 as _registry.resolve
    participant p4 as _registry.names
    participant p5 as dict
    participant p6 as adapter.identity
    participant p7 as sorted
    participant p8 as adapter.capabilities
    participant p9 as getattr
    participant p10 as callable
    participant p11 as preflight_fn
    participant p12 as set
    participant p13 as identity.get
    p0-->>p1: HTTPException(status_code=503, detail='harness registry is not initialized')
    p0->>p2: _descriptor
    p0-->>p3: _registry.resolve(name)
    p0-->>p4: _registry.names
    p2-->>p5: dict(adapter.identity(...))
    p2-->>p6: adapter.identity
    p2-->>p7: sorted(adapter.capabilities(...))
    p2-->>p8: adapter.capabilities
    p2-->>p9: getattr(adapter, 'preflight', None)
    p2-->>p10: callable(preflight_fn)
    p2-->>p11: preflight_fn
    p2-->>p7: sorted(...)
    p2-->>p12: set(capabilities)
    p2-->>p13: identity.get('name')
    p2-->>p13: identity.get('version')
    p2-->>p13: identity.get('contract_version')
    p2-->>p13: identity.get('interface')
    p2-->>p13: identity.get('schema_pin')
    p2-->>p13: identity.get('attach_modes')
    p2-->>p13: identity.get('resume_mode')
    p2-->>p13: identity.get('permissions')
```

> Call sequence diagram shows 21 of 21 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 7 of 7 (0 omitted); unresolved 13 of 13 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. list_harnesses"]
    s2["2. HTTPException"]
    s3["3. _descriptor"]
    s4["4. dict"]
    s5["5. adapter.identity"]
    s6["6. sorted"]
    s7["7. adapter.capabilities"]
    s8["8. getattr"]
    s9["9. callable"]
    s10["10. preflight_fn"]
    s11["11. sorted"]
    s12["12. set"]
    s1 -. "HTTPException(status_code=503, detail='harness registry is not initialized')" .-> s2
    s1 -->|"_descriptor(_registry.resolve(...))"| s3
    s3 -. "dict(adapter.identity(...))" .-> s4
    s3 -. "adapter.identity(data not statically known)" .-> s5
    s3 -. "sorted(adapter.capabilities(...))" .-> s6
    s3 -. "adapter.capabilities(data not statically known)" .-> s7
    s3 -. "getattr(adapter, 'preflight', None)" .-> s8
    s3 -. "callable(preflight_fn)" .-> s9
    s3 -. "preflight_fn(data not statically known)" .-> s10
    s3 -. "sorted(...)" .-> s11
    s3 -. "set(capabilities)" .-> s12
    click s1 "../modules/harnesses.md"
    click s3 "../modules/harnesses.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `list_harnesses` | - | `_registry` | - | `{...}` |
| `HTTPException` | - | - | - | - |
| `_descriptor` | `adapter: Any` | `OPTIONAL_CAPABILITIES` | - | `{...}` |
| `dict` | - | - | - | - |
| `adapter.identity` | - | - | - | - |
| `sorted` | - | - | - | - |
| `adapter.capabilities` | - | - | - | - |
| `getattr` | - | - | - | - |
| `callable` | - | - | - | - |
| `preflight_fn` | - | - | - | - |
| `sorted` | - | - | - | - |
| `set` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| list_harnesses | HTTPException | 106 | `HTTPException(status_code=503, detail='harness registry is not initialized')` |
| list_harnesses | _descriptor | 108 | `_descriptor(_registry.resolve(...))` |
| _descriptor | dict | 62 | `dict(adapter.identity(...))` |
| _descriptor | adapter.identity | 62 | `adapter.identity(data not statically known)` |
| _descriptor | sorted | 63 | `sorted(adapter.capabilities(...))` |
| _descriptor | adapter.capabilities | 63 | `adapter.capabilities(data not statically known)` |
| _descriptor | getattr | 64 | `getattr(adapter, 'preflight', None)` |
| _descriptor | callable | 65 | `callable(preflight_fn)` |
| _descriptor | preflight_fn | 66 | `preflight_fn(data not statically known)` |
| _descriptor | sorted | 85 | `sorted(...)` |
| _descriptor | set | 85 | `set(capabilities)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `list_harnesses` | `HTTPException` | 106 |
| unresolved_call | `_descriptor` | `adapter.identity` | 62 |
| external_call | `_descriptor` | `sorted` | 63 |
| unresolved_call | `_descriptor` | `adapter.capabilities` | 63 |
| external_call | `_descriptor` | `getattr` | 64 |
| external_call | `_descriptor` | `callable` | 65 |
| unresolved_call | `_descriptor` | `preflight_fn` | 66 |
| external_call | `_descriptor` | `sorted` | 85 |
| step_limit | `list_harnesses` | `first 12 steps` | 0 |

## Behavior

This flow starts at `list_harnesses` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
