# get_skill_leaderboard

**Entry point:** `get_skill_leaderboard` (`http`)
**Source:** [src_api_skills](../modules/src_api_skills.md)
**Modules touched:** [compat_legacy_alias](../modules/compat_legacy_alias.md), [src_api_skills](../modules/src_api_skills.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_skill_leaderboard
    participant p1 as _get_or_404
    participant p2 as skill_id_to_model_type
    participant p3 as set
    participant p4 as manifest.metric_schema.model_dump
    participant p5 as metric_dump.get
    participant p6 as primary.get
    participant p7 as sorted
    participant p8 as _store.list_sessions
    participant p9 as str
    participant p10 as session.get
    participant p11 as seen_ids.add
    participant p12 as rows.append
    participant p13 as rows.sort
    participant p14 as r.get
    p0->>p1: _get_or_404
    p0->>p2: skill_id_to_model_type
    p0-->>p3: set
    p0-->>p4: manifest.metric_schema.model_dump(exclude_none=True, mode='json')
    p0-->>p5: metric_dump.get('primary', {...})
    p0-->>p6: primary.get('direction', 'higher_is_better')
    p0-->>p7: sorted(model_type_aliases)
    p0-->>p8: _store.list_sessions(model_type=alias, limit=500)
    p0-->>p9: str(...)
    p0-->>p10: session.get('id')
    p0-->>p10: session.get('best_metric')
    p0-->>p11: seen_ids.add(rid)
    p0-->>p12: rows.append({...})
    p0-->>p10: session.get('subject_id')
    p0-->>p10: session.get('instrument')
    p0-->>p10: session.get('variant')
    p0-->>p10: session.get('timeframe')
    p0-->>p10: session.get('tag')
    p0-->>p10: session.get('status')
    p0-->>p10: session.get('best_metric')
    p0-->>p10: session.get('metric_name')
    p0-->>p10: session.get('best_iteration')
    p0-->>p10: session.get('effective_iteration_count')
    p0-->>p10: session.get('best_iteration')
    p0-->>p10: session.get('total_api_cost_usd')
    p0-->>p10: session.get('started_at')
    p0-->>p10: session.get('completed_at')
    p0-->>p13: rows.sort(key=..., reverse=...)
    p0-->>p14: r.get('best_metric')
    p0-->>p14: r.get('best_metric')
```

> Call sequence diagram shows 30 of 37 interactions; 7 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 5 (2 omitted); unresolved 25 of 30 (5 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/api/skills.py:_get_or_404` | 2 | - | unresolved | 1 |
| `src/api/skills.py:_get_or_404` | 2 | - | external | 1 |
| `src/compat/legacy_alias.py:skill_id_to_model_type` | 9 | - | unresolved | 1 |
| `src/api/skills.py:get_skill_leaderboard` | 1 | - | external | 1 |
| `src/api/skills.py:get_skill_leaderboard` | 1 | - | unresolved | 3 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_skill_leaderboard"]
    s2["2. _get_or_404"]
    s3["3. _registry.get"]
    s4["4. HTTPException"]
    s5["5. manifest.metric_schema.model_dump"]
    s6["6. metric_dump.get"]
    s7["7. primary.get"]
    s8["8. set"]
    s9["9. skill_id_to_model_type"]
    s10["10. _SKILL_ID_TO_MODEL_TYPE.get"]
    s11["11. sorted"]
    s12["12. _store.list_sessions"]
    s1 -->|"_get_or_404(skill_id)"| s2
    s2 -. "_registry.get(skill_id)" .-> s3
    s2 -. "HTTPException(status_code=404, detail={...})" .-> s4
    s1 -. "manifest.metric_schema.model_dump(exclude_none=True, mode='json')" .-> s5
    s1 -. "metric_dump.get('primary', {...})" .-> s6
    s1 -. "primary.get('direction', 'higher_is_better')" .-> s7
    s1 -. "set(data not statically known)" .-> s8
    s1 -->|"skill_id_to_model_type(skill_id)"| s9
    s9 -. "_SKILL_ID_TO_MODEL_TYPE.get(skill_id, skill_id)" .-> s10
    s1 -. "sorted(model_type_aliases)" .-> s11
    s1 -. "_store.list_sessions(model_type=alias, limit=500)" .-> s12
    b0["mutation seen_ids.add"]
    s1 -. "mutation seen_ids.add" .-> b0
    b1["mutation rows.append"]
    s1 -. "mutation rows.append" .-> b1
    b2["mutation rows.sort"]
    s1 -. "mutation rows.sort" .-> b2
    click s1 "../modules/src_api_skills.md"
    click s2 "../modules/src_api_skills.md"
    click s9 "../modules/compat_legacy_alias.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_skill_leaderboard` | `skill_id: str`, `limit: int` | `_store` | - | `{...}` |
| `_get_or_404` | `skill_id: str` | `SkillNotRegisteredError` | - | `_registry.get(...)` |
| `_registry.get` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `manifest.metric_schema.model_dump` | - | - | - | - |
| `metric_dump.get` | - | - | - | - |
| `primary.get` | - | - | - | - |
| `set` | - | - | - | - |
| `skill_id_to_model_type` | `skill_id: str` | - | - | `''`, `_SKILL_ID_TO_MODEL_TYPE.get(...)` |
| `_SKILL_ID_TO_MODEL_TYPE.get` | - | - | - | - |
| `sorted` | - | - | - | - |
| `_store.list_sessions` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_skill_leaderboard | _get_or_404 | 256 | `_get_or_404(skill_id)` |
| _get_or_404 | _registry.get | 181 | `_registry.get(skill_id)` |
| _get_or_404 | HTTPException | 183 | `HTTPException(status_code=404, detail={...})` |
| get_skill_leaderboard | manifest.metric_schema.model_dump | 257 | `manifest.metric_schema.model_dump(exclude_none=True, mode='json')` |
| get_skill_leaderboard | metric_dump.get | 258 | `metric_dump.get('primary', {...})` |
| get_skill_leaderboard | primary.get | 259 | `primary.get('direction', 'higher_is_better')` |
| get_skill_leaderboard | set | 262 | `set(data not statically known)` |
| get_skill_leaderboard | skill_id_to_model_type | 266 | `skill_id_to_model_type(skill_id)` |
| skill_id_to_model_type | _SKILL_ID_TO_MODEL_TYPE.get | 56 | `_SKILL_ID_TO_MODEL_TYPE.get(skill_id, skill_id)` |
| get_skill_leaderboard | sorted | 267 | `sorted(model_type_aliases)` |
| get_skill_leaderboard | _store.list_sessions | 270 | `_store.list_sessions(model_type=alias, limit=500)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `seen_ids.add` | `get_skill_leaderboard` | 276 |
| mutation | `rows.append` | `get_skill_leaderboard` | 277 |
| mutation | `rows.sort` | `get_skill_leaderboard` | 297 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_get_or_404` | `_registry.get` | 181 |
| external_call | `_get_or_404` | `HTTPException` | 183 |
| unresolved_call | `get_skill_leaderboard` | `manifest.metric_schema.model_dump` | 257 |
| unresolved_call | `get_skill_leaderboard` | `metric_dump.get` | 258 |
| unresolved_call | `get_skill_leaderboard` | `primary.get` | 259 |
| unresolved_call | `skill_id_to_model_type` | `_SKILL_ID_TO_MODEL_TYPE.get` | 56 |
| external_call | `get_skill_leaderboard` | `sorted` | 267 |
| unresolved_call | `get_skill_leaderboard` | `_store.list_sessions` | 270 |
| step_limit | `get_skill_leaderboard` | `first 12 steps` | 0 |

## Behavior

This flow starts at `get_skill_leaderboard` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
