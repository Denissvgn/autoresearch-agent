# snapshot_parent_workspace

**Entry point:** `snapshot_parent_workspace` (`api`)
**Source:** [run_artifacts](../modules/run_artifacts.md)
**Modules touched:** [run_artifacts](../modules/run_artifacts.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as snapshot_parent_workspace
    participant p1 as store.import_tree
    p0-->>p1: store.import_tree(workspace, includes=includes)
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. snapshot_parent_workspace"]
    s2["2. store.import_tree"]
    s1 -. "store.import_tree(workspace, includes=includes)" .-> s2
    click s1 "../modules/run_artifacts.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `snapshot_parent_workspace` | `workspace: Path \| str`, `store: ArtifactStore`, `includes: Iterable[str]` | - | - | `store.import_tree(...)` |
| `store.import_tree` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| snapshot_parent_workspace | store.import_tree | 437 | `store.import_tree(workspace, includes=includes)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `snapshot_parent_workspace` | `store.import_tree` | 437 |

## Behavior

This flow starts at `snapshot_parent_workspace` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
