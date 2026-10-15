# get_agent_log

**Entry point:** `get_agent_log` (`http`)
**Source:** [results](../modules/results.md)
**Modules touched:** [log_writer](../modules/log_writer.md), [results](../modules/results.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_agent_log
    participant p1 as _resolve_result_context
    participant p2 as _collect_log_entries
    participant p3 as _build_log_text
    participant p4 as _format_entry
    participant p5 as _decode_pipeline_payload
    participant p6 as AgentLogWriter.read_lines
    participant p7 as _decode_session_payload
    participant p8 as isinstance (src/api/results.py:get_agent_log)
    participant p9 as research_id.startswith (src/api/results.py:get_agent_log)
    participant p10 as len (src/api/results.py:get_agent_log)
    participant p11 as research_id.startswith (src/api/results.py:_resolve_result_context)
    participant p12 as session.get
    participant p13 as '\n'.join
    participant p14 as _store.get_pipeline
    participant p15 as Path
    participant p16 as HTTPException
    participant p17 as log_path.exists (src/api/results.py:_collect_log_entries)
    participant p18 as pipeline.get
    participant p19 as _store.get_session
    participant p20 as dict (src/api/results.py:_resolve_result_context)
    participant p21 as sessions.append
    participant p22 as dict (src/api/results.py:_collect_log_entries)
    participant p23 as entry.get (src/api/results.py:_collect_log_entries)
    participant p24 as next
    participant p25 as isinstance (src/api/results.py:_collect_log_entries)
    participant p26 as s.get
    p0->>p1: _resolve_result_context
    p0->>p2: _collect_log_entries
    p0->>p3: _build_log_text
    p3->>p4: _format_entry
    p1->>p5: _decode_pipeline_payload
    p2->>p6: AgentLogWriter.read_lines
    p1->>p7: _decode_session_payload
    p0-->>p8: isinstance (src/api/results.py:get_agent_log)(after, int)
    p0-->>p9: research_id.startswith (src/api/results.py:get_agent_log)('pipe_')
    p0-->>p10: len (src/api/results.py:get_agent_log)(_collect_log_entries(...))
    p1-->>p11: research_id.startswith (src/api/results.py:_resolve_result_context)('pipe_')
    p2-->>p12: session.get('workspace_path', '')
    p3-->>p13: '\n'.join(...)
    p1-->>p14: _store.get_pipeline(research_id)
    p2-->>p15: Path(workspace)
    p1-->>p16: HTTPException(status_code=404, detail='Pipeline not found')
    p2-->>p17: log_path.exists (src/api/results.py:_collect_log_entries)
    p2-->>p12: session.get('pipeline_phase')
    p1-->>p18: pipeline.get(...)
    p2-->>p12: session.get('model_type')
    p1-->>p19: _store.get_session(session_id)
    p2-->>p12: session.get('id')
    p1-->>p20: dict (src/api/results.py:_resolve_result_context)(session)
    p1-->>p21: sessions.append(session)
    p2-->>p22: dict (src/api/results.py:_collect_log_entries)(raw_entry)
    p1-->>p18: pipeline.get('current_phase')
    p2-->>p23: entry.get (src/api/results.py:_collect_log_entries)('meta')
    p1-->>p24: next(..., None)
    p2-->>p25: isinstance (src/api/results.py:_collect_log_entries)(meta, dict)
    p1-->>p26: s.get('pipeline_phase')
```

> Call sequence diagram shows 30 of 70 interactions; 40 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 8 of 27 (19 omitted); unresolved 15 of 35 (20 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/api/results.py:_decode_pipeline_payload` | 7 | - | external | 4 |
| `src/api/results.py:_decode_pipeline_payload` | 7 | - | unresolved | 1 |
| `src/api/results.py:_resolve_result_context` | 3 | - | unresolved | 1 |
| `src/api/results.py:_resolve_result_context` | 3 | - | external | 1 |
| `src/api/results.py:_decode_session_payload` | 22 | - | external | 4 |
| `src/api/results.py:_decode_session_payload` | 22 | - | unresolved | 1 |
| `src/core/log_writer.py:AgentLogWriter.read_lines` | 36 | - | unresolved | 4 |
| `src/core/log_writer.py:AgentLogWriter.read_lines` | 36 | - | external | 4 |
> Omission summary shows 8 of 13 groups; 5 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_agent_log"]
    s2["2. isinstance (src/api/results.py:get_agent_log)"]
    s3["3. _resolve_result_context"]
    s4["4. research_id.startswith (src/api/results.py:_resolve_result_context)"]
    s5["5. _store.get_pipeline"]
    s6["6. HTTPException"]
    s7["7. _decode_pipeline_payload"]
    s8["8. dict (src/api/results.py:_decode_pipeline_payload)"]
    s9["9. decoded.get (src/api/results.py:_decode_pipeline_payload)"]
    s10["10. isinstance (src/api/results.py:_decode_pipeline_payload)"]
    s11["11. json.loads (src/api/results.py:_decode_pipeline_payload)"]
    s12["12. isinstance (src/api/results.py:_decode_pipeline_payload)"]
    s1 -. "isinstance (src/api/results.py:get_agent_log)(after, int)" .-> s2
    s1 -->|"_resolve_result_context(research_id)"| s3
    s3 -. "research_id.startswith (src/api/results.py:_resolve_result_context)('pipe_')" .-> s4
    s3 -. "_store.get_pipeline(research_id)" .-> s5
    s3 -. "HTTPException(status_code=404, detail='Pipeline not found')" .-> s6
    s3 -->|"_decode_pipeline_payload(pipeline)"| s7
    s7 -. "dict (src/api/results.py:_decode_pipeline_payload)(pipeline)" .-> s8
    s7 -. "decoded.get (src/api/results.py:_decode_pipeline_payload)(source)" .-> s9
    s7 -. "isinstance (src/api/results.py:_decode_pipeline_payload)(raw, str)" .-> s10
    s7 -. "json.loads (src/api/results.py:_decode_pipeline_payload)(raw)" .-> s11
    s7 -. "isinstance (src/api/results.py:_decode_pipeline_payload)(parsed, fallback_type)" .-> s12
    b0["mutation sessions.append"]
    s3 -. "mutation sessions.append" .-> b0
    click s1 "../modules/results.md"
    click s3 "../modules/results.md"
    click s7 "../modules/results.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `get_agent_log` | `research_id: str`, `after: Optional[int]`, `format: Optional[str]` | - | - | `{...}`, `{...}`, `{...}`, `{...}` |
| `isinstance (src/api/results.py:get_agent_log)` | - | - | - | - |
| `_resolve_result_context` | `research_id: str` | `_PIPELINE_PHASES` | `session[...]` | `(...)`, `(...)`, `(...)` |
| `research_id.startswith (src/api/results.py:_resolve_result_context)` | - | - | - | - |
| `_store.get_pipeline` | - | - | - | - |
| `HTTPException` | - | - | - | - |
| `_decode_pipeline_payload` | `pipeline: Dict[str, Any]` | `json` | `decoded[...]` | `decoded` |
| `dict (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `decoded.get (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `isinstance (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `json.loads (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |
| `isinstance (src/api/results.py:_decode_pipeline_payload)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| get_agent_log | isinstance (src/api/results.py:get_agent_log) | 526 | `isinstance(after, int)` |
| get_agent_log | _resolve_result_context | 527 | `_resolve_result_context(research_id)` |
| _resolve_result_context | research_id.startswith (src/api/results.py:_resolve_result_context) | 342 | `research_id.startswith('pipe_')` |
| _resolve_result_context | _store.get_pipeline | 343 | `_store.get_pipeline(research_id)` |
| _resolve_result_context | HTTPException | 345 | `HTTPException(status_code=404, detail='Pipeline not found')` |
| _resolve_result_context | _decode_pipeline_payload | 346 | `_decode_pipeline_payload(pipeline)` |
| _decode_pipeline_payload | dict (src/api/results.py:_decode_pipeline_payload) | 56 | `dict(pipeline)` |
| _decode_pipeline_payload | decoded.get (src/api/results.py:_decode_pipeline_payload) | 63 | `decoded.get(source)` |
| _decode_pipeline_payload | isinstance (src/api/results.py:_decode_pipeline_payload) | 67 | `isinstance(raw, str)` |
| _decode_pipeline_payload | json.loads (src/api/results.py:_decode_pipeline_payload) | 67 | `json.loads(raw)` |
| _decode_pipeline_payload | isinstance (src/api/results.py:_decode_pipeline_payload) | 70 | `isinstance(parsed, fallback_type)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `sessions.append` | `_resolve_result_context` | 358 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `get_agent_log` | `isinstance` | 526 |
| unresolved_call | `_resolve_result_context` | `research_id.startswith` | 342 |
| unresolved_call | `_resolve_result_context` | `_store.get_pipeline` | 343 |
| external_call | `_resolve_result_context` | `HTTPException` | 345 |
| unresolved_call | `_decode_pipeline_payload` | `decoded.get` | 63 |
| external_call | `_decode_pipeline_payload` | `isinstance` | 67 |
| external_call | `_decode_pipeline_payload` | `json.loads` | 67 |
| external_call | `_decode_pipeline_payload` | `isinstance` | 70 |
| step_limit | `get_agent_log` | `first 12 steps` | 0 |

## Behavior

This flow starts at `get_agent_log` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
