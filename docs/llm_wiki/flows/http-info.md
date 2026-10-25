# info

**Entry point:** `info` (`http`)
**Source:** [src_main](../modules/src_main.md)
**Modules touched:** [src_main](../modules/src_main.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as info
    participant p1 as str(…).rstrip
    participant p2 as str
    p0-->>p1: str(…).rstrip('/')
    p0-->>p2: str(request.base_url)
```

> Call sequence diagram shows 2 of 2 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. info"]
    s2["2. str(…).rstrip"]
    s3["3. str"]
    s1 -. "str(…).rstrip('/')" .-> s2
    s1 -. "str(request.base_url)" .-> s3
    click s1 "../modules/src_main.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `info` | `request: Request` | `settings`, `app`, `_API_V1_PREFIX`, `_API_V1_PREFIX` | - | `{...}` |
| `str(…).rstrip` | - | - | - | - |
| `str` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| info | str(…).rstrip | 224 | `str(request.base_url).rstrip('/')` |
| info | str | 224 | `str(request.base_url)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `info` | `str(request.base_url).rstrip` | 224 |

## Behavior

This flow starts at `info` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
