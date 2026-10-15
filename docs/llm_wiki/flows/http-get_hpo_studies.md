# get_hpo_studies

**Entry point:** `get_hpo_studies` (`http`)
**Source:** [results](../modules/results.md)
**Modules touched:** [results](../modules/results.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_hpo_studies
    participant p1 as _resolve_result_context
    participant p2 as HTTPException (src/api/results.py:get_hpo_studies)
    participant p3 as _store.get_hpo_studies
    participant p4 as study.get
    participant p5 as isinstance (src/api/results.py:get_hpo_studies)
    participant p6 as json.loads (src/api/results.py:get_hpo_studies)
    participant p7 as research_id.startswith
    participant p8 as _store.get_pipeline
    participant p9 as HTTPException (src/api/results.py:_resolve_result_context)
    participant p10 as _decode_pipeline_payload
    participant p11 as pipeline.get
    participant p12 as _store.get_session
    participant p13 as dict (src/api/results.py:_resolve_result_context)
    participant p14 as sessions.append
    participant p15 as next
    participant p16 as s.get
    participant p17 as _decode_session_payload
    participant p18 as dict (src/api/results.py:_decode_pipeline_payload)
    participant p19 as dict (src/api/results.py:_decode_session_payload)
    participant p20 as decoded.get (src/api/results.py:_decode_pipeline_payload)
    participant p21 as decoded.get (src/api/results.py:_decode_session_payload)
    participant p22 as isinstance (src/api/results.py:_decode_pipeline_payload)
    participant p23 as isinstance (src/api/results.py:_decode_session_payload)
    participant p24 as json.loads (src/api/results.py:_decode_pipeline_payload)
    participant p25 as json.loads (src/api/results.py:_decode_session_payload)
    p0->>p1: _resolve_result_context
    p0-->>p2: HTTPException (src/api/results.py:get_hpo_studies)(status_code=404, detail='Phase session not found yet')
    p0-->>p3: _store.get_hpo_studies(session[...])
    p0-->>p4: study.get(source)
    p0-->>p5: isinstance (src/api/results.py:get_hpo_studies)(raw, str)
    p0-->>p6: json.loads (src/api/results.py:get_hpo_studies)(raw)
    p1-->>p7: research_id.startswith('pipe_')
    p1-->>p8: _store.get_pipeline(research_id)
    p1-->>p9: HTTPException (src/api/results.py:_resolve_result_context)(status_code=404, detail='Pipeline not found')
    p1->>p10: _decode_pipeline_payload
    p1-->>p11: pipeline.get(...)
    p1-->>p12: _store.get_session(session_id)
    p1-->>p13: dict (src/api/results.py:_resolve_result_context)(session)
    p1-->>p14: sessions.append(session)
    p1-->>p11: pipeline.get('current_phase')
    p1-->>p15: next(..., None)
    p1-->>p16: s.get('pipeline_phase')
    p1-->>p12: _store.get_session(research_id)
    p1-->>p9: HTTPException (src/api/results.py:_resolve_result_context)(status_code=404, detail='Session not found')
    p1->>p17: _decode_session_payload
    p10-->>p18: dict (src/api/results.py:_decode_pipeline_payload)(pipeline)
    p17-->>p19: dict (src/api/results.py:_decode_session_payload)(session)
    p10-->>p20: decoded.get (src/api/results.py:_decode_pipeline_payload)(source)
    p17-->>p21: decoded.get (src/api/results.py:_decode_session_payload)('promotion_blockers_json')
    p10-->>p22: isinstance (src/api/results.py:_decode_pipeline_payload)(raw, str)
    p17-->>p23: isinstance (src/api/results.py:_decode_session_payload)(raw, str)
    p10-->>p24: json.loads (src/api/results.py:_decode_pipeline_payload)(raw)
    p17-->>p25: json.loads (src/api/results.py:_decode_session_payload)(raw)
    p10-->>p22: isinstance (src/api/results.py:_decode_pipeline_payload)(parsed, fallback_type)
    p17-->>p23: isinstance (src/api/results.py:_decode_session_payload)(parsed, list)
```

> Call sequence diagram shows 30 of 30 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 15 of 15 (0 omitted); unresolved 12 of 12 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_hpo_studies"]
    s2["2. _resolve_result_context"]
    s3["3. research_id.startswith"]
    s4["4. _store.get_pipeline"]
    s5["5. HTTPException (src/api/results.py:_resolve_result_context)"]
    s6["6. _decode_pipeline_payload"]
    s7["7. dict (src/api/results.py:_decode_pipeline_payload)"]
    s8["8. decoded.get (src/api/results.py:_decode_pipeline_payload)"]
    s9["9. isinstance (src/api/results.py:_decode_pipeline_payload)"]
    s10["10. json.loads (src/api/results.py:_decode_pipeline_payload)"]
    s11["11. isinstance (src/api/results.py:_decode_pipeline_payload)"]
    s12["12. pipeline.get"]
    s1 -->|"_resolve_result_context(research_id)"| s2
    s2 -. "research_id.startswith('pipe_')" .-> s3
    s2 -. "_store.get_pipeline(research_id)" .-> s4
    s2 -. "HTTPException (src/api/results.py:_resolve_result_context)(status_code=404, detail='Pipeline not found')" .-> s5
    s2 -->|"_decode_pipeline_payload(pipeline)"| s6
    s6 -. "dict (src/api/results.py:_decode_pipeline_payload)(pipeline)" .-> s7
    s6 -. "decoded.get (src/api/results.py:_decode_pipeline_payload)(source)" .-> s8
    s6 -. "isinstance (src/api/results.py:_decode_pipeline_payload)(raw, str)" .-> s9
    s6 -. "json.loads (src/api/results.py:_decode_pipeline_payload)(raw)" .-> s10
    s6 -. "isinstance (src/api/results.py:_decode_pipeline_payload)(parsed, fallback_type)" .-> s11
    s2 -. "pipeline.get(...)" .-> s12
    b0["mutation sessions.append"]
    s2 -. "mutation sessions.append" .-> b0
    click s1 "../modules/results.md"
    click s2 "../modules/results.md"
    click s6 "../modules/results.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_hpo_studies` | `research_id: str` | `json` | `study[...]`, `study[...]`, `study[...]` | `{...}` |
| `_resolve_result_context` | `research_id: str` | `_PIPELINE_PHASES` | `session[...]` | `(...)`, `(...)`, `(...)` |
| `research_id.startswith` | - | - | - | - |
| `_store.get_pipeline` | - | - | - | - |
| `HTTPException (src/api/results.py:_resolve_result_context)` | - | - | - | - |
| `_decode_pipeline_payload` | `pipeline: Dict[str, Any]` | `json` | `decoded[...]` | `decoded` |
| `dict (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `decoded.get (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `isinstance (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `json.loads (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `isinstance (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `pipeline.get` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_hpo_studies | _resolve_result_context | 556 | `_resolve_result_context(research_id)` |
| _resolve_result_context | research_id.startswith | 342 | `research_id.startswith('pipe_')` |
| _resolve_result_context | _store.get_pipeline | 343 | `_store.get_pipeline(research_id)` |
| _resolve_result_context | HTTPException (src/api/results.py:_resolve_result_context) | 345 | `HTTPException(status_code=404, detail='Pipeline not found')` |
| _resolve_result_context | _decode_pipeline_payload | 346 | `_decode_pipeline_payload(pipeline)` |
| _decode_pipeline_payload | dict (src/api/results.py:_decode_pipeline_payload) | 56 | `dict(pipeline)` |
| _decode_pipeline_payload | decoded.get (src/api/results.py:_decode_pipeline_payload) | 63 | `decoded.get(source)` |
| _decode_pipeline_payload | isinstance (src/api/results.py:_decode_pipeline_payload) | 67 | `isinstance(raw, str)` |
| _decode_pipeline_payload | json.loads (src/api/results.py:_decode_pipeline_payload) | 67 | `json.loads(raw)` |
| _decode_pipeline_payload | isinstance (src/api/results.py:_decode_pipeline_payload) | 70 | `isinstance(parsed, fallback_type)` |
| _resolve_result_context | pipeline.get | 350 | `pipeline.get(...)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `sessions.append` | `_resolve_result_context` | 358 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `_resolve_result_context` | `research_id.startswith` | 342 |
| unresolved_call | `_resolve_result_context` | `_store.get_pipeline` | 343 |
| external_call | `_resolve_result_context` | `HTTPException` | 345 |
| unresolved_call | `_decode_pipeline_payload` | `decoded.get` | 63 |
| external_call | `_decode_pipeline_payload` | `isinstance` | 67 |
| external_call | `_decode_pipeline_payload` | `json.loads` | 67 |
| external_call | `_decode_pipeline_payload` | `isinstance` | 70 |
| unresolved_call | `_resolve_result_context` | `pipeline.get` | 350 |
| step_limit | `get_hpo_studies` | `first 12 steps` | 0 |

## Behavior

This flow starts at `get_hpo_studies` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
