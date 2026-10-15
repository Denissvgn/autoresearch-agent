# is_trial_eligible_command

**Entry point:** `is_trial_eligible_command` (`api`)
**Source:** [trial_workspace](../modules/trial_workspace.md)
**Modules touched:** [trial_workspace](../modules/trial_workspace.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as is_trial_eligible_command
    participant p1 as str
    participant p2 as any
    p0-->>p1: str(...)
    p0-->>p2: any(...)
    p0-->>p1: str(script)
```

> Call sequence diagram shows 3 of 3 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. is_trial_eligible_command"]
    s2["2. str"]
    s3["3. any"]
    s4["4. str"]
    s1 -. "str(...)" .-> s2
    s1 -. "any(...)" .-> s3
    s1 -. "str(script)" .-> s4
    click s1 "../modules/trial_workspace.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `is_trial_eligible_command` | `command: object`, `allowed_scripts: Optional[Iterable[str] \| Mapping[str, str]]` | - | - | `False`, `any(...)`, `False` |
| `str` | - | - | - | - |
| `any` | - | - | - | - |
| `str` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| is_trial_eligible_command | str | 88 | `str(...)` |
| is_trial_eligible_command | any | 93 | `any(...)` |
| is_trial_eligible_command | str | 93 | `str(script)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `is_trial_eligible_command` | `any` | 93 |

## Behavior

This flow starts at `is_trial_eligible_command` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
