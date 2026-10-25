# clear_revocations

**Entry point:** `clear_revocations` (`api`)
**Source:** [scoped_credentials](../modules/scoped_credentials.md)
**Modules touched:** [scoped_credentials](../modules/scoped_credentials.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as clear_revocations
    participant p1 as _REVOKED.clear
    p0-->>p1: _REVOKED.clear
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. clear_revocations"]
    s2["2. _REVOKED.clear"]
    s1 -. "_REVOKED.clear(data not statically known)" .-> s2
    b0["mutation _REVOKED.clear"]
    s1 -. "mutation _REVOKED.clear" .-> b0
    click s1 "../modules/scoped_credentials.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `clear_revocations` | - | - | - | - |
| `_REVOKED.clear` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| clear_revocations | _REVOKED.clear | 174 | `_REVOKED.clear(data not statically known)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `_REVOKED.clear` | `clear_revocations` | 174 |

### Static analysis gaps

*No static analysis gaps detected.*

## Behavior

This flow starts at `clear_revocations` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
