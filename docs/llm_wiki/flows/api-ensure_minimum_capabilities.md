# ensure_minimum_capabilities

**Entry point:** `ensure_minimum_capabilities` (`api`)
**Source:** [execution_contracts](../modules/execution_contracts.md)
**Modules touched:** [execution_contracts](../modules/execution_contracts.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as ensure_minimum_capabilities
    participant p1 as set
    participant p2 as descriptor.unsupported.get
    participant p3 as sorted
    participant p4 as UnsupportedCapabilityError
    p0-->>p1: set(descriptor.capabilities)
    p0-->>p2: descriptor.unsupported.get(name, 'not provided')
    p0-->>p3: sorted(missing)
    p0->>p4: UnsupportedCapabilityError
    p0-->>p3: sorted(missing)
```

> Call sequence diagram shows 5 of 5 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. ensure_minimum_capabilities"]
    s2["2. set"]
    s3["3. descriptor.unsupported.get"]
    s4["4. sorted"]
    s5["5. UnsupportedCapabilityError"]
    s6["6. sorted"]
    s1 -. "set(descriptor.capabilities)" .-> s2
    s1 -. "descriptor.unsupported.get(name, 'not provided')" .-> s3
    s1 -. "sorted(missing)" .-> s4
    s1 -->|"UnsupportedCapabilityError(...)"| s5
    s1 -. "sorted(missing)" .-> s6
    click s1 "../modules/execution_contracts.md"
    click s5 "../modules/execution_contracts.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `ensure_minimum_capabilities` | `descriptor: CapabilityDescriptor`, `required: frozenset[str]` | - | - | - |
| `set` | - | - | - | - |
| `descriptor.unsupported.get` | - | - | - | - |
| `sorted` | - | - | - | - |
| `UnsupportedCapabilityError` | - | - | - | - |
| `sorted` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| ensure_minimum_capabilities | set | 484 | `set(descriptor.capabilities)` |
| ensure_minimum_capabilities | descriptor.unsupported.get | 487 | `descriptor.unsupported.get(name, 'not provided')` |
| ensure_minimum_capabilities | sorted | 487 | `sorted(missing)` |
| ensure_minimum_capabilities | UnsupportedCapabilityError | 489 | `UnsupportedCapabilityError(...)` |
| ensure_minimum_capabilities | sorted | 491 | `sorted(missing)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `ensure_minimum_capabilities` | `descriptor.unsupported.get` | 487 |
| external_call | `ensure_minimum_capabilities` | `sorted` | 487 |
| external_call | `ensure_minimum_capabilities` | `sorted` | 491 |

## Behavior

This flow starts at `ensure_minimum_capabilities` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
