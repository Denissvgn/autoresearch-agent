# get_harness

**Entry point:** `get_harness` (`http`)
**Source:** [harnesses](../modules/harnesses.md)
**Modules touched:** [harnesses](../modules/harnesses.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_harness
    participant p1 as HTTPException
    participant p2 as _registry.resolve
    participant p3 as _descriptor
    participant p4 as dict
    participant p5 as adapter.identity
    participant p6 as sorted
    participant p7 as adapter.capabilities
    participant p8 as getattr
    participant p9 as callable
    participant p10 as preflight_fn
    participant p11 as set
    participant p12 as identity.get
    p0-->>p1: HTTPException(status_code=503, detail='harness registry is not initialized')
    p0-->>p2: _registry.resolve(name)
    p0-->>p1: HTTPException(status_code=404, detail=...)
    p0->>p3: _descriptor
    p3-->>p4: dict(adapter.identity(...))
    p3-->>p5: adapter.identity
    p3-->>p6: sorted(adapter.capabilities(...))
    p3-->>p7: adapter.capabilities
    p3-->>p8: getattr(adapter, 'preflight', None)
    p3-->>p9: callable(preflight_fn)
    p3-->>p10: preflight_fn
    p3-->>p6: sorted(...)
    p3-->>p11: set(capabilities)
    p3-->>p12: identity.get('name')
    p3-->>p12: identity.get('version')
    p3-->>p12: identity.get('contract_version')
    p3-->>p12: identity.get('interface')
    p3-->>p12: identity.get('schema_pin')
    p3-->>p12: identity.get('attach_modes')
    p3-->>p12: identity.get('resume_mode')
    p3-->>p12: identity.get('permissions')
```

> Call sequence diagram shows 21 of 21 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 8 of 8 (0 omitted); unresolved 12 of 12 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_harness"]
    s2["2. HTTPException"]
    s3["3. _registry.resolve"]
    s4["4. HTTPException"]
    s5["5. _descriptor"]
    s6["6. dict"]
    s7["7. adapter.identity"]
    s8["8. sorted"]
    s9["9. adapter.capabilities"]
    s10["10. getattr"]
    s11["11. callable"]
    s12["12. preflight_fn"]
    s1 -. "HTTPException(status_code=503, detail='harness registry is not initialized')" .-> s2
    s1 -. "_registry.resolve(name)" .-> s3
    s1 -. "HTTPException(status_code=404, detail=...)" .-> s4
    s1 -->|"_descriptor(adapter)"| s5
    s5 -. "dict(adapter.identity(...))" .-> s6
    s5 -. "adapter.identity(data not statically known)" .-> s7
    s5 -. "sorted(adapter.capabilities(...))" .-> s8
    s5 -. "adapter.capabilities(data not statically known)" .-> s9
    s5 -. "getattr(adapter, 'preflight', None)" .-> s10
    s5 -. "callable(preflight_fn)" .-> s11
    s5 -. "preflight_fn(data not statically known)" .-> s12
    click s1 "../modules/harnesses.md"
    click s5 "../modules/harnesses.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_harness` | `name: str` | `_registry` | - | `_descriptor(...)` |
| `HTTPException` | - | - | - | - |
| `_registry.resolve` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `_descriptor` | `adapter: Any` | `OPTIONAL_CAPABILITIES` | - | `{...}` |
| `dict` | - | - | - | - |
| `adapter.identity` | - | - | - | - |
| `sorted` | - | - | - | - |
| `adapter.capabilities` | - | - | - | - |
| `getattr` | - | - | - | - |
| `callable` | - | - | - | - |
| `preflight_fn` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_harness | HTTPException | 115 | `HTTPException(status_code=503, detail='harness registry is not initialized')` |
| get_harness | _registry.resolve | 117 | `_registry.resolve(name)` |
| get_harness | HTTPException | 119 | `HTTPException(status_code=404, detail=...)` |
| get_harness | _descriptor | 122 | `_descriptor(adapter)` |
| _descriptor | dict | 62 | `dict(adapter.identity(...))` |
| _descriptor | adapter.identity | 62 | `adapter.identity(data not statically known)` |
| _descriptor | sorted | 63 | `sorted(adapter.capabilities(...))` |
| _descriptor | adapter.capabilities | 63 | `adapter.capabilities(data not statically known)` |
| _descriptor | getattr | 64 | `getattr(adapter, 'preflight', None)` |
| _descriptor | callable | 65 | `callable(preflight_fn)` |
| _descriptor | preflight_fn | 66 | `preflight_fn(data not statically known)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `get_harness` | `HTTPException` | 115 |
| unresolved_call | `get_harness` | `_registry.resolve` | 117 |
| external_call | `get_harness` | `HTTPException` | 119 |
| unresolved_call | `_descriptor` | `adapter.identity` | 62 |
| external_call | `_descriptor` | `sorted` | 63 |
| unresolved_call | `_descriptor` | `adapter.capabilities` | 63 |
| external_call | `_descriptor` | `getattr` | 64 |
| external_call | `_descriptor` | `callable` | 65 |
| unresolved_call | `_descriptor` | `preflight_fn` | 66 |
| step_limit | `get_harness` | `first 12 steps` | 0 |

## Behavior

This flow starts at `get_harness` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
