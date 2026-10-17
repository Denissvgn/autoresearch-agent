# get_research

**Entry point:** `get_research` (`http`)
**Source:** [research](../modules/research.md)
**Modules touched:** [compat_legacy_alias](../modules/compat_legacy_alias.md), [research](../modules/research.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_research
    participant p1 as _dual_shape_session
    participant p2 as model_type_to_skill_id
    participant p3 as dict (src/api/research.py:get_research)
    participant p4 as research_id.startswith
    participant p5 as _store.get_pipeline
    participant p6 as payload.setdefault
    participant p7 as pipe.get
    participant p8 as _store.get_session
    participant p9 as session.get (src/api/research.py:get_research)
    participant p10 as HTTPException
    participant p11 as dict (src/api/research.py:_dual_shape_session)
    participant p12 as session.get (src/api/research.py:_dual_shape_session)
    participant p13 as augmented.get
    participant p14 as augmented.setdefault
    participant p15 as _MODEL_TYPE_TO_SKILL_ID.get
    p0->>p1: _dual_shape_session
    p1->>p2: model_type_to_skill_id
    p0-->>p3: dict (src/api/research.py:get_research)(pipe)
    p0-->>p4: research_id.startswith('pipe_')
    p0-->>p5: _store.get_pipeline(research_id)
    p0-->>p6: payload.setdefault('model_type', 'pipeline')
    p0-->>p6: payload.setdefault('skill_name', 'pipeline')
    p0-->>p6: payload.setdefault('workspace_path', '')
    p0-->>p6: payload.setdefault('best_iteration', None)
    p0-->>p6: payload.setdefault('best_metric', None)
    p0-->>p6: payload.setdefault('resumed_from', None)
    p0-->>p7: pipe.get('current_phase')
    p0-->>p7: pipe.get(...)
    p0-->>p8: _store.get_session(session_id)
    p0-->>p9: session.get (src/api/research.py:get_research)('workspace_path', '')
    p0-->>p9: session.get (src/api/research.py:get_research)('id')
    p0-->>p8: _store.get_session(research_id)
    p0-->>p10: HTTPException(status_code=404, detail='Session not found')
    p1-->>p11: dict (src/api/research.py:_dual_shape_session)(session)
    p1-->>p12: session.get (src/api/research.py:_dual_shape_session)('model_type', '')
    p1-->>p12: session.get (src/api/research.py:_dual_shape_session)('instrument', '')
    p1-->>p12: session.get (src/api/research.py:_dual_shape_session)('timeframe', '')
    p1-->>p13: augmented.get('skill_id')
    p1-->>p13: augmented.get('subject_id')
    p1-->>p13: augmented.get('variant')
    p1-->>p14: augmented.setdefault('model_type', model_type)
    p1-->>p14: augmented.setdefault('instrument', instrument)
    p1-->>p14: augmented.setdefault('timeframe', timeframe)
    p1-->>p12: session.get (src/api/research.py:_dual_shape_session)('id')
    p2-->>p15: _MODEL_TYPE_TO_SKILL_ID.get(model_type, model_type)
```

> Call sequence diagram shows 30 of 31 interactions; 1 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 25 of 25 (0 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/api/research.py:get_research` | 1 | [src/api/research.py](../modules/research.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_research"]
    s2["2. research_id.startswith"]
    s3["3. _store.get_pipeline"]
    s4["4. dict (src/api/research.py:get_research)"]
    s5["5. payload.setdefault"]
    s6["6. payload.setdefault"]
    s7["7. payload.setdefault"]
    s8["8. payload.setdefault"]
    s9["9. payload.setdefault"]
    s10["10. payload.setdefault"]
    s11["11. pipe.get"]
    s12["12. pipe.get"]
    s1 -. "research_id.startswith('pipe_')" .-> s2
    s1 -. "_store.get_pipeline(research_id)" .-> s3
    s1 -. "dict (src/api/research.py:get_research)(pipe)" .-> s4
    s1 -. "payload.setdefault('model_type', 'pipeline')" .-> s5
    s1 -. "payload.setdefault('skill_name', 'pipeline')" .-> s6
    s1 -. "payload.setdefault('workspace_path', '')" .-> s7
    s1 -. "payload.setdefault('best_iteration', None)" .-> s8
    s1 -. "payload.setdefault('best_metric', None)" .-> s9
    s1 -. "payload.setdefault('resumed_from', None)" .-> s10
    s1 -. "pipe.get('current_phase')" .-> s11
    s1 -. "pipe.get(...)" .-> s12
    click s1 "../modules/research.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_research` | `research_id: str` | - | `payload[...]`, `payload[...]` | `_dual_shape_session(...)`, `_dual_shape_session(...)` |
| `research_id.startswith` | - | - | - | - |
| `_store.get_pipeline` | - | - | - | - |
| `dict (src/api/research.py:get_research)` | - | - | - | - |
| `payload.setdefault` | - | - | - | - |
| `payload.setdefault` | - | - | - | - |
| `payload.setdefault` | - | - | - | - |
| `payload.setdefault` | - | - | - | - |
| `payload.setdefault` | - | - | - | - |
| `payload.setdefault` | - | - | - | - |
| `pipe.get` | - | - | - | - |
| `pipe.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_research | research_id.startswith | 753 | `research_id.startswith('pipe_')` |
| get_research | _store.get_pipeline | 754 | `_store.get_pipeline(research_id)` |
| get_research | dict (src/api/research.py:get_research) | 756 | `dict(pipe)` |
| get_research | payload.setdefault | 757 | `payload.setdefault('model_type', 'pipeline')` |
| get_research | payload.setdefault | 758 | `payload.setdefault('skill_name', 'pipeline')` |
| get_research | payload.setdefault | 759 | `payload.setdefault('workspace_path', '')` |
| get_research | payload.setdefault | 760 | `payload.setdefault('best_iteration', None)` |
| get_research | payload.setdefault | 761 | `payload.setdefault('best_metric', None)` |
| get_research | payload.setdefault | 762 | `payload.setdefault('resumed_from', None)` |
| get_research | pipe.get | 764 | `pipe.get('current_phase')` |
| get_research | pipe.get | 766 | `pipe.get(...)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `get_research` | `research_id.startswith` | 753 |
| unresolved_call | `get_research` | `_store.get_pipeline` | 754 |
| unresolved_call | `get_research` | `payload.setdefault` | 757 |
| unresolved_call | `get_research` | `payload.setdefault` | 758 |
| unresolved_call | `get_research` | `payload.setdefault` | 759 |
| unresolved_call | `get_research` | `payload.setdefault` | 760 |
| unresolved_call | `get_research` | `payload.setdefault` | 761 |
| unresolved_call | `get_research` | `payload.setdefault` | 762 |
| unresolved_call | `get_research` | `pipe.get` | 764 |
| unresolved_call | `get_research` | `pipe.get` | 766 |
| step_limit | `get_research` | `first 12 steps` | 0 |

## Behavior

This flow starts at `get_research` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
