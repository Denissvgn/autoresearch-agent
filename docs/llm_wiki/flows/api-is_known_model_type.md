# is_known_model_type

**Entry point:** `is_known_model_type` (`api`)
**Source:** [compat_legacy_alias](../modules/compat_legacy_alias.md)
**Modules touched:** [compat_legacy_alias](../modules/compat_legacy_alias.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
*No outbound calls were detected by static analysis.*

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. is_known_model_type"]
    click s1 "../modules/compat_legacy_alias.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `is_known_model_type` | `model_type: str` | `_MODEL_TYPE_TO_SKILL_ID` | - | `...` |

### Call data

*No call data transfers detected.*

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

*No static analysis gaps detected.*

## Behavior

This flow starts at `is_known_model_type` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
