# ensure_capabilities_allowed

**Entry point:** `ensure_capabilities_allowed` (`api`)
**Source:** [execution_contracts](../modules/execution_contracts.md)
**Modules touched:** [execution_contracts](../modules/execution_contracts.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as ensure_capabilities_allowed
    participant p1 as ContractError
    participant p2 as sorted
    participant p3 as set
    participant p4 as UnsupportedCapabilityError
    p0->>p1: ContractError
    p0-->>p2: sorted(unknown)
    p0-->>p3: set(descriptor.capabilities)
    p0->>p4: UnsupportedCapabilityError
    p0-->>p2: sorted(excess)
```

> Call sequence diagram shows 5 of 5 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. ensure_capabilities_allowed"]
    s2["2. ContractError"]
    s3["3. sorted"]
    s4["4. set"]
    s5["5. UnsupportedCapabilityError"]
    s6["6. sorted"]
    s1 -->|"ContractError(...)"| s2
    s1 -. "sorted(unknown)" .-> s3
    s1 -. "set(descriptor.capabilities)" .-> s4
    s1 -->|"UnsupportedCapabilityError(...)"| s5
    s1 -. "sorted(excess)" .-> s6
    click s1 "../modules/execution_contracts.md"
    click s2 "../modules/execution_contracts.md"
    click s5 "../modules/execution_contracts.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `ensure_capabilities_allowed` | `descriptor: CapabilityDescriptor`, `allowed: frozenset[str]` | `KNOWN_CAPABILITIES` | - | - |
| `ContractError` | - | - | - | - |
| `sorted` | - | - | - | - |
| `set` | - | - | - | - |
| `UnsupportedCapabilityError` | - | - | - | - |
| `sorted` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| ensure_capabilities_allowed | ContractError | 507 | `ContractError(...)` |
| ensure_capabilities_allowed | sorted | 507 | `sorted(unknown)` |
| ensure_capabilities_allowed | set | 508 | `set(descriptor.capabilities)` |
| ensure_capabilities_allowed | UnsupportedCapabilityError | 510 | `UnsupportedCapabilityError(...)` |
| ensure_capabilities_allowed | sorted | 512 | `sorted(excess)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `ensure_capabilities_allowed` | `sorted` | 507 |
| external_call | `ensure_capabilities_allowed` | `sorted` | 512 |

## Behavior

This flow starts at `ensure_capabilities_allowed` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
