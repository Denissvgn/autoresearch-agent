# compile_scope_graph

**Entry point:** `compile_scope_graph` (`api`)
**Source:** [promotion_policy](../modules/promotion_policy.md)
**Modules touched:** [promotion_policy](../modules/promotion_policy.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as compile_scope_graph
    participant p1 as str
    participant p2 as getattr
    participant p3 as ScopePolicyError
    participant p4 as tuple
    participant p5 as sorted
    participant p6 as ScopeNode
    participant p7 as bool
    participant p8 as graph.values
    participant p9 as visit
    p0-->>p1: str(...)
    p0-->>p2: getattr(scope, 'id', '')
    p0->>p3: ScopePolicyError
    p0->>p3: ScopePolicyError
    p0-->>p4: tuple(...)
    p0-->>p1: str(p)
    p0-->>p2: getattr(scope, 'prior_scopes', None)
    p0-->>p4: tuple(...)
    p0-->>p1: str(e)
    p0-->>p2: getattr(scope, 'evidence', None)
    p0->>p3: ScopePolicyError
    p0-->>p5: sorted(SCOPE_EVIDENCE_VALIDATORS)
    p0->>p6: ScopeNode
    p0-->>p7: bool(getattr(...))
    p0-->>p2: getattr(scope, 'approval_required', False)
    p0-->>p8: graph.values
    p0->>p3: ScopePolicyError
    p0-->>p9: visit(scope_id, (...))
```

> Call sequence diagram shows 18 of 18 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 11 of 11 (0 omitted); unresolved 2 of 2 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. compile_scope_graph"]
    s2["2. str"]
    s3["3. getattr"]
    s4["4. ScopePolicyError"]
    s5["5. ScopePolicyError"]
    s6["6. tuple"]
    s7["7. str"]
    s8["8. getattr"]
    s9["9. tuple"]
    s10["10. str"]
    s11["11. getattr"]
    s12["12. ScopePolicyError"]
    s1 -. "str(...)" .-> s2
    s1 -. "getattr(scope, 'id', '')" .-> s3
    s1 -->|"ScopePolicyError('promotion scope requires a non-empty id')"| s4
    s1 -->|"ScopePolicyError(...)"| s5
    s1 -. "tuple(...)" .-> s6
    s1 -. "str(p)" .-> s7
    s1 -. "getattr(scope, 'prior_scopes', None)" .-> s8
    s1 -. "tuple(...)" .-> s9
    s1 -. "str(e)" .-> s10
    s1 -. "getattr(scope, 'evidence', None)" .-> s11
    s1 -->|"ScopePolicyError(...)"| s12
    click s1 "../modules/promotion_policy.md"
    click s4 "../modules/promotion_policy.md"
    click s5 "../modules/promotion_policy.md"
    click s12 "../modules/promotion_policy.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `compile_scope_graph` | `scopes: Iterable[Any]` | `SCOPE_EVIDENCE_VALIDATORS`, `SCOPE_EVIDENCE_VALIDATORS` | `graph[...]` | `graph` |
| `str` | - | - | - | - |
| `getattr` | - | - | - | - |
| `ScopePolicyError` | - | - | - | - |
| `ScopePolicyError` | - | - | - | - |
| `tuple` | - | - | - | - |
| `str` | - | - | - | - |
| `getattr` | - | - | - | - |
| `tuple` | - | - | - | - |
| `str` | - | - | - | - |
| `getattr` | - | - | - | - |
| `ScopePolicyError` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| compile_scope_graph | str | 61 | `str(...)` |
| compile_scope_graph | getattr | 61 | `getattr(scope, 'id', '')` |
| compile_scope_graph | ScopePolicyError | 63 | `ScopePolicyError('promotion scope requires a non-empty id')` |
| compile_scope_graph | ScopePolicyError | 65 | `ScopePolicyError(...)` |
| compile_scope_graph | tuple | 66 | `tuple(...)` |
| compile_scope_graph | str | 66 | `str(p)` |
| compile_scope_graph | getattr | 66 | `getattr(scope, 'prior_scopes', None)` |
| compile_scope_graph | tuple | 67 | `tuple(...)` |
| compile_scope_graph | str | 67 | `str(e)` |
| compile_scope_graph | getattr | 67 | `getattr(scope, 'evidence', None)` |
| compile_scope_graph | ScopePolicyError | 70 | `ScopePolicyError(...)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `compile_scope_graph` | `getattr` | 61 |
| external_call | `compile_scope_graph` | `getattr` | 66 |
| external_call | `compile_scope_graph` | `getattr` | 67 |
| step_limit | `compile_scope_graph` | `first 12 steps` | 0 |

## Behavior

This flow starts at `compile_scope_graph` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
