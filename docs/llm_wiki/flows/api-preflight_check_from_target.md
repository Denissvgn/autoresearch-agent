# preflight_check_from_target

**Entry point:** `preflight_check_from_target` (`api`)
**Source:** [preflight](../modules/preflight.md)
**Modules touched:** [preflight](../modules/preflight.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as preflight_check_from_target
    participant p1 as TCPConnectCheck
    participant p2 as HTTPHealthCheck
    p0->>p1: TCPConnectCheck
    p0->>p2: HTTPHealthCheck
```

> Call sequence diagram shows 2 of 2 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. preflight_check_from_target"]
    s2["2. TCPConnectCheck"]
    s3["3. HTTPHealthCheck"]
    s1 -->|"TCPConnectCheck(target, timeout_s=timeout_s)"| s2
    s1 -->|"HTTPHealthCheck(target)"| s3
    click s1 "../modules/preflight.md"
    click s2 "../modules/preflight.md"
    click s3 "../modules/preflight.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `preflight_check_from_target` | `target: ServicePreflightTarget`, `timeout_s: float` | - | - | `TCPConnectCheck(...)`, `HTTPHealthCheck(...)` |
| `TCPConnectCheck` | - | - | - | - |
| `HTTPHealthCheck` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| preflight_check_from_target | TCPConnectCheck | 147 | `TCPConnectCheck(target, timeout_s=timeout_s)` |
| preflight_check_from_target | HTTPHealthCheck | 148 | `HTTPHealthCheck(target)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

*No static analysis gaps detected.*

## Behavior

This flow starts at `preflight_check_from_target` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
