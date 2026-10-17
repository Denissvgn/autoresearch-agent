# list_research

**Entry point:** `list_research` (`http`)
**Source:** [research](../modules/research.md)
**Modules touched:** [compat_legacy_alias](../modules/compat_legacy_alias.md), [pagination](../modules/pagination.md), [research](../modules/research.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as list_research
    participant p1 as _dual_shape_session
    participant p2 as build_cursor_page
    participant p3 as decode_cursor
    participant p4 as compute_next_cursor
    participant p5 as model_type_to_skill_id
    participant p6 as encode_cursor
    participant p7 as isinstance (src/api/research.py:list_research)
    participant p8 as logger.warning
    participant p9 as _store.list_sessions
    participant p10 as _store.count_sessions
    participant p11 as len (src/core/pagination.py:decode_cursor)
    participant p12 as dict
    participant p13 as list
    participant p14 as base64.urlsafe_b64decode(…).decode
    participant p15 as session.get
    participant p16 as base64.urlsafe_b64decode
    participant p17 as json.loads
    participant p18 as isinstance (src/core/pagination.py:decode_cursor)
    participant p19 as augmented.get
    participant p20 as int
    participant p21 as payload.get
    p0->>p1: _dual_shape_session
    p0->>p2: build_cursor_page
    p0->>p3: decode_cursor
    p0->>p4: compute_next_cursor
    p1->>p5: model_type_to_skill_id
    p4->>p6: encode_cursor
    p0-->>p7: isinstance (src/api/research.py:list_research)(limit, int)
    p0-->>p8: logger.warning('malformed /research cursor token serving page 1')
    p0-->>p7: isinstance (src/api/research.py:list_research)(offset, int)
    p0-->>p9: _store.list_sessions(status=status, model_type=model_type, instrument=instrument, limit=limit, cursor=decoded)
    p0-->>p8: logger.warning('offset pagination is deprecated for /research use cursor (ARC-011 P0-016)')
    p0-->>p9: _store.list_sessions(status=status, model_type=model_type, instrument=instrument, limit=limit, offset=offset)
    p0-->>p10: _store.count_sessions(status=status, model_type=model_type, instrument=instrument)
    p3-->>p11: len (src/core/pagination.py:decode_cursor)(token)
    p1-->>p12: dict(session)
    p2-->>p13: list(items)
    p3-->>p14: base64.urlsafe_b64decode(…).decode('utf-8')
    p1-->>p15: session.get('model_type', '')
    p3-->>p16: base64.urlsafe_b64decode(...)
    p1-->>p15: session.get('instrument', '')
    p3-->>p17: json.loads(decoded)
    p1-->>p15: session.get('timeframe', '')
    p3-->>p18: isinstance (src/core/pagination.py:decode_cursor)(payload, dict)
    p1-->>p19: augmented.get('skill_id')
    p3-->>p20: int(payload.get(...))
    p3-->>p21: payload.get('v', 0)
    p1-->>p19: augmented.get('subject_id')
    p3-->>p21: payload.get('k')
    p1-->>p19: augmented.get('variant')
    p3-->>p21: payload.get('r')
```

> Call sequence diagram shows 30 of 45 interactions; 15 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 9 of 13 (4 omitted); unresolved 15 of 24 (9 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/pagination.py:decode_cursor` | 4 | - | external | 1 |
| `src/compat/legacy_alias.py:model_type_to_skill_id` | 23 | - | unresolved | 1 |
| `src/api/research.py:_dual_shape_session` | 17 | - | unresolved | 4 |
| `src/core/pagination.py:build_cursor_page` | 31 | [src/core/pagination.py](../modules/pagination.md) | internal | 1 |
| `src/core/pagination.py:compute_next_cursor` | 33 | - | external | 1 |
| `src/core/pagination.py:compute_next_cursor` | 33 | - | unresolved | 1 |
| `src/core/pagination.py:encode_cursor` | 36 | - | unresolved | 3 |
| `src/core/pagination.py:encode_cursor` | 36 | - | external | 2 |
> Omission summary shows 8 of 9 groups; 1 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. list_research"]
    s2["2. isinstance (src/api/research.py:list_research)"]
    s3["3. isinstance (src/api/research.py:list_research)"]
    s4["4. decode_cursor"]
    s5["5. len (src/core/pagination.py:decode_cursor)"]
    s6["6. base64.urlsafe_b64decode(…).decode"]
    s7["7. base64.urlsafe_b64decode"]
    s8["8. json.loads"]
    s9["9. isinstance (src/core/pagination.py:decode_cursor)"]
    s10["10. int"]
    s11["11. payload.get"]
    s12["12. payload.get"]
    s1 -. "isinstance (src/api/research.py:list_research)(limit, int)" .-> s2
    s1 -. "isinstance (src/api/research.py:list_research)(offset, int)" .-> s3
    s1 -->|"decode_cursor(cursor)"| s4
    s4 -. "len (src/core/pagination.py:decode_cursor)(token)" .-> s5
    s4 -. "base64.urlsafe_b64decode(…).decode('utf-8')" .-> s6
    s4 -. "base64.urlsafe_b64decode(...)" .-> s7
    s4 -. "json.loads(decoded)" .-> s8
    s4 -. "isinstance (src/core/pagination.py:decode_cursor)(payload, dict)" .-> s9
    s4 -. "int(payload.get(...))" .-> s10
    s4 -. "payload.get('v', 0)" .-> s11
    s4 -. "payload.get('k')" .-> s12
    click s1 "../modules/research.md"
    click s4 "../modules/pagination.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `list_research` | `status: Optional[str]`, `model_type: Optional[str]`, `instrument: Optional[str]`, `limit: int`, `offset: int`, `cursor: Optional[str]` | `DEFAULT_PAGE_SIZE`, `_started_at_id_cursor`, `_started_at_id_cursor` | - | `build_cursor_page(...)`, `{...}` |
| `isinstance (src/api/research.py:list_research)` | - | - | - | - |
| `isinstance (src/api/research.py:list_research)` | - | - | - | - |
| `decode_cursor` | `token: Optional[str]` | `_CURSOR_VERSION`, `json` | - | `None`, `None`, `None`, `None`, `None`, `(...)`, `None` |
| `len (src/core/pagination.py:decode_cursor)` | - | - | - | - |
| `base64.urlsafe_b64decode(…).decode` | - | - | - | - |
| `base64.urlsafe_b64decode` | - | - | - | - |
| `json.loads` | - | - | - | - |
| `isinstance (src/core/pagination.py:decode_cursor)` | - | - | - | - |
| `int` | - | - | - | - |
| `payload.get` | - | - | - | - |
| `payload.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| list_research | isinstance (src/api/research.py:list_research) | 684 | `isinstance(limit, int)` |
| list_research | isinstance (src/api/research.py:list_research) | 686 | `isinstance(offset, int)` |
| list_research | decode_cursor | 688 | `decode_cursor(cursor)` |
| decode_cursor | len (src/core/pagination.py:decode_cursor) | 66 | `len(token)` |
| decode_cursor | base64.urlsafe_b64decode(…).decode | 67 | `base64.urlsafe_b64decode(token + padding).decode('utf-8')` |
| decode_cursor | base64.urlsafe_b64decode | 67 | `base64.urlsafe_b64decode(...)` |
| decode_cursor | json.loads | 68 | `json.loads(decoded)` |
| decode_cursor | isinstance (src/core/pagination.py:decode_cursor) | 69 | `isinstance(payload, dict)` |
| decode_cursor | int | 71 | `int(payload.get(...))` |
| decode_cursor | payload.get | 71 | `payload.get('v', 0)` |
| decode_cursor | payload.get | 73 | `payload.get('k')` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `list_research` | `isinstance` | 684 |
| external_call | `list_research` | `isinstance` | 686 |
| unresolved_call | `decode_cursor` | `base64.urlsafe_b64decode(token + padding).decode` | 67 |
| external_call | `decode_cursor` | `base64.urlsafe_b64decode` | 67 |
| external_call | `decode_cursor` | `json.loads` | 68 |
| external_call | `decode_cursor` | `isinstance` | 69 |
| unresolved_call | `decode_cursor` | `payload.get` | 71 |
| unresolved_call | `decode_cursor` | `payload.get` | 73 |
| step_limit | `list_research` | `first 12 steps` | 0 |

## Behavior

This flow starts at `list_research` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
