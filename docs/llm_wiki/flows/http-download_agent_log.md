# download_agent_log

**Entry point:** `download_agent_log` (`http`)
**Source:** [results](../modules/results.md)
**Modules touched:** [log_writer](../modules/log_writer.md), [results](../modules/results.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as download_agent_log
    participant p1 as _resolve_result_context
    participant p2 as _collect_log_entries
    participant p3 as _decode_pipeline_payload
    participant p4 as AgentLogWriter.read_lines
    participant p5 as _decode_session_payload
    participant p6 as HTTPException (src/api/results.py:download_agent_log)
    participant p7 as research_id.startswith (src/api/results.py:download_agent_log)
    participant p8 as session.get (src/api/results.py:download_agent_log)
    participant p9 as Response
    participant p10 as ''.join
    participant p11 as json.dumps
    participant p12 as research_id.startswith (src/api/results.py:_resolve_result_context)
    participant p13 as session.get (src/api/results.py:_collect_log_entries)
    participant p14 as _store.get_pipeline
    participant p15 as Path
    participant p16 as HTTPException (src/api/results.py:_resolve_result_context)
    participant p17 as log_path.exists (src/api/results.py:_collect_log_entries)
    participant p18 as pipeline.get
    participant p19 as _store.get_session
    participant p20 as dict (src/api/results.py:_resolve_result_context)
    participant p21 as sessions.append
    participant p22 as dict (src/api/results.py:_collect_log_entries)
    participant p23 as entry.get
    p0->>p1: _resolve_result_context
    p0->>p2: _collect_log_entries
    p1->>p3: _decode_pipeline_payload
    p2->>p4: AgentLogWriter.read_lines
    p1->>p5: _decode_session_payload
    p0-->>p6: HTTPException (src/api/results.py:download_agent_log)(status_code=404, detail='Agent log not found')
    p0-->>p7: research_id.startswith (src/api/results.py:download_agent_log)('pipe_')
    p0-->>p6: HTTPException (src/api/results.py:download_agent_log)(status_code=404, detail='Session not found')
    p0-->>p6: HTTPException (src/api/results.py:download_agent_log)(status_code=404, detail='Agent log not found')
    p0-->>p8: session.get (src/api/results.py:download_agent_log)('instrument', 'unknown')
    p0-->>p8: session.get (src/api/results.py:download_agent_log)('model_type', 'model')
    p0-->>p9: Response(content=..., media_type='application/x-ndjson', headers={...})
    p0-->>p10: ''.join(...)
    p0-->>p11: json.dumps(entry, default=str)
    p1-->>p12: research_id.startswith (src/api/results.py:_resolve_result_context)('pipe_')
    p2-->>p13: session.get (src/api/results.py:_collect_log_entries)('workspace_path', '')
    p1-->>p14: _store.get_pipeline(research_id)
    p2-->>p15: Path(workspace)
    p1-->>p16: HTTPException (src/api/results.py:_resolve_result_context)(status_code=404, detail='Pipeline not found')
    p2-->>p17: log_path.exists (src/api/results.py:_collect_log_entries)
    p2-->>p13: session.get (src/api/results.py:_collect_log_entries)('pipeline_phase')
    p1-->>p18: pipeline.get(...)
    p2-->>p13: session.get (src/api/results.py:_collect_log_entries)('model_type')
    p1-->>p19: _store.get_session(session_id)
    p2-->>p13: session.get (src/api/results.py:_collect_log_entries)('id')
    p1-->>p20: dict (src/api/results.py:_resolve_result_context)(session)
    p1-->>p21: sessions.append(session)
    p2-->>p22: dict (src/api/results.py:_collect_log_entries)(raw_entry)
    p1-->>p18: pipeline.get('current_phase')
    p2-->>p23: entry.get('meta')
```

> Call sequence diagram shows 30 of 57 interactions; 27 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 9 of 25 (16 omitted); unresolved 16 of 27 (11 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/api/results.py:_decode_pipeline_payload` | 6 | - | external | 4 |
| `src/api/results.py:_decode_pipeline_payload` | 6 | - | unresolved | 1 |
| `src/api/results.py:_resolve_result_context` | 2 | - | external | 2 |
| `src/api/results.py:_resolve_result_context` | 2 | - | unresolved | 2 |
| `src/api/results.py:_decode_session_payload` | 21 | - | external | 4 |
| `src/api/results.py:_decode_session_payload` | 21 | - | unresolved | 1 |
| `src/core/log_writer.py:AgentLogWriter.read_lines` | 37 | - | unresolved | 4 |
| `src/core/log_writer.py:AgentLogWriter.read_lines` | 37 | - | external | 4 |
> Omission summary shows 8 of 10 groups; 2 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. download_agent_log"]
    s2["2. _resolve_result_context"]
    s3["3. research_id.startswith (src/api/results.py:_resolve_result_context)"]
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
    s2 -. "research_id.startswith (src/api/results.py:_resolve_result_context)('pipe_')" .-> s3
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
| `download_agent_log` | `research_id: str` | - | - | `Response(...)` |
| `_resolve_result_context` | `research_id: str` | `_PIPELINE_PHASES` | `session[...]` | `(...)`, `(...)`, `(...)` |
| `research_id.startswith (src/api/results.py:_resolve_result_context)` | - | - | - | - |
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
| download_agent_log | _resolve_result_context | 694 | `_resolve_result_context(research_id)` |
| _resolve_result_context | research_id.startswith (src/api/results.py:_resolve_result_context) | 342 | `research_id.startswith('pipe_')` |
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
| step_limit | `download_agent_log` | `first 12 steps` | 0 |

## Behavior

This flow starts at `download_agent_log` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
