# promotion_target_from_manifest

**Entry point:** `promotion_target_from_manifest` (`api`)
**Source:** [promotion_target](../modules/promotion_target.md)
**Modules touched:** [promotion_target](../modules/promotion_target.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as promotion_target_from_manifest
    participant p1 as getattr
    participant p2 as ValueError
    participant p3 as FilePathPromotionTarget
    participant p4 as WebhookPromotionTarget
    p0-->>p1: getattr(getattr(...), 'primary', None)
    p0-->>p1: getattr(skill_manifest, 'promotion_target', None)
    p0-->>p2: ValueError(...)
    p0-->>p1: getattr(skill_manifest, 'id', '?')
    p0-->>p1: getattr(primary, 'kind', None)
    p0-->>p1: getattr(primary, 'path_template', None)
    p0->>p3: FilePathPromotionTarget
    p0->>p4: WebhookPromotionTarget
    p0-->>p1: getattr(primary, 'timeout_s', 10.0)
    p0-->>p1: getattr(primary, 'retries', 2)
    p0-->>p1: getattr(primary, 'endpoint', None)
    p0-->>p2: ValueError(...)
    p0-->>p1: getattr(skill_manifest, 'id', '?')
    p0->>p4: WebhookPromotionTarget
    p0-->>p1: getattr(primary, 'auth_secret', None)
    p0-->>p2: ValueError(...)
    p0-->>p1: getattr(skill_manifest, 'id', '?')
```

> Call sequence diagram shows 17 of 17 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 14 of 14 (0 omitted); unresolved 0 of 0 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. promotion_target_from_manifest"]
    s2["2. getattr"]
    s3["3. getattr"]
    s4["4. ValueError"]
    s5["5. getattr"]
    s6["6. getattr"]
    s7["7. getattr"]
    s8["8. FilePathPromotionTarget"]
    s9["9. WebhookPromotionTarget"]
    s10["10. getattr"]
    s11["11. getattr"]
    s12["12. getattr"]
    s1 -. "getattr(getattr(...), 'primary', None)" .-> s2
    s1 -. "getattr(skill_manifest, 'promotion_target', None)" .-> s3
    s1 -. "ValueError(...)" .-> s4
    s1 -. "getattr(skill_manifest, 'id', '?')" .-> s5
    s1 -. "getattr(primary, 'kind', None)" .-> s6
    s1 -. "getattr(primary, 'path_template', None)" .-> s7
    s1 -->|"FilePathPromotionTarget(path_template=...)"| s8
    s1 -->|"WebhookPromotionTarget(endpoint=primary.endpoint, auth_env_var=..., timeout_s=getattr(...), retries=getattr(...))"| s9
    s1 -. "getattr(primary, 'timeout_s', 10.0)" .-> s10
    s1 -. "getattr(primary, 'retries', 2)" .-> s11
    s1 -. "getattr(primary, 'endpoint', None)" .-> s12
    click s1 "../modules/promotion_target.md"
    click s8 "../modules/promotion_target.md"
    click s9 "../modules/promotion_target.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `promotion_target_from_manifest` | `skill_manifest: Any` | - | - | `FilePathPromotionTarget(...)`, `WebhookPromotionTarget(...)`, `WebhookPromotionTarget(...)` |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `ValueError` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `FilePathPromotionTarget` | - | - | - | - |
| `WebhookPromotionTarget` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |
| `getattr` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| promotion_target_from_manifest | getattr | 464 | `getattr(getattr(...), 'primary', None)` |
| promotion_target_from_manifest | getattr | 465 | `getattr(skill_manifest, 'promotion_target', None)` |
| promotion_target_from_manifest | ValueError | 468 | `ValueError(...)` |
| promotion_target_from_manifest | getattr | 469 | `getattr(skill_manifest, 'id', '?')` |
| promotion_target_from_manifest | getattr | 472 | `getattr(primary, 'kind', None)` |
| promotion_target_from_manifest | getattr | 476 | `getattr(primary, 'path_template', None)` |
| promotion_target_from_manifest | FilePathPromotionTarget | 477 | `FilePathPromotionTarget(path_template=...)` |
| promotion_target_from_manifest | WebhookPromotionTarget | 481 | `WebhookPromotionTarget(endpoint=primary.endpoint, auth_env_var=..., timeout_s=getattr(...), retries=getattr(...))` |
| promotion_target_from_manifest | getattr | 484 | `getattr(primary, 'timeout_s', 10.0)` |
| promotion_target_from_manifest | getattr | 485 | `getattr(primary, 'retries', 2)` |
| promotion_target_from_manifest | getattr | 488 | `getattr(primary, 'endpoint', None)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `promotion_target_from_manifest` | `getattr` | 464 |
| external_call | `promotion_target_from_manifest` | `getattr` | 465 |
| external_call | `promotion_target_from_manifest` | `ValueError` | 468 |
| external_call | `promotion_target_from_manifest` | `getattr` | 469 |
| external_call | `promotion_target_from_manifest` | `getattr` | 472 |
| external_call | `promotion_target_from_manifest` | `getattr` | 476 |
| external_call | `promotion_target_from_manifest` | `getattr` | 484 |
| external_call | `promotion_target_from_manifest` | `getattr` | 485 |
| external_call | `promotion_target_from_manifest` | `getattr` | 488 |
| step_limit | `promotion_target_from_manifest` | `first 12 steps` | 0 |

## Behavior

This flow starts at `promotion_target_from_manifest` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
