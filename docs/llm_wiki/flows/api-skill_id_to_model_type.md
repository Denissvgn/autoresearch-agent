# skill_id_to_model_type

**Entry point:** `skill_id_to_model_type` (`api`)
**Source:** [compat_legacy_alias](../modules/compat_legacy_alias.md)
**Modules touched:** [compat_legacy_alias](../modules/compat_legacy_alias.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as skill_id_to_model_type
    participant p1 as _SKILL_ID_TO_MODEL_TYPE.get
    p0-->>p1: _SKILL_ID_TO_MODEL_TYPE.get(skill_id, skill_id)
```

> Call sequence diagram shows 1 of 1 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 0 of 0 (0 omitted); unresolved 1 of 1 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. skill_id_to_model_type"]
    s2["2. _SKILL_ID_TO_MODEL_TYPE.get"]
    s1 -. "_SKILL_ID_TO_MODEL_TYPE.get(skill_id, skill_id)" .-> s2
    click s1 "../modules/compat_legacy_alias.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `skill_id_to_model_type` | `skill_id: str` | - | - | `''`, `_SKILL_ID_TO_MODEL_TYPE.get(...)` |
| `_SKILL_ID_TO_MODEL_TYPE.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| skill_id_to_model_type | _SKILL_ID_TO_MODEL_TYPE.get | 56 | `_SKILL_ID_TO_MODEL_TYPE.get(skill_id, skill_id)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `skill_id_to_model_type` | `_SKILL_ID_TO_MODEL_TYPE.get` | 56 |

## Behavior

This flow starts at `skill_id_to_model_type` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
