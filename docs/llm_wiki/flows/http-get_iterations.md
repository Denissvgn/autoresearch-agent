# get_iterations

**Entry point:** `get_iterations` (`http`)
**Source:** [results](../modules/results.md)
**Modules touched:** [artifact_reference](../modules/artifact_reference.md), [compat_legacy_alias](../modules/compat_legacy_alias.md), [consistency_validator](../modules/consistency_validator.md), and 4 more

**Complete modules touched:**

- [artifact_reference](../modules/artifact_reference.md)
- [compat_legacy_alias](../modules/compat_legacy_alias.md)
- [consistency_validator](../modules/consistency_validator.md)
- [gate_status](../modules/gate_status.md)
- [ml_enrichment](../modules/ml_enrichment.md)
- [pagination](../modules/pagination.md)
- [results](../modules/results.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as get_iterations
    participant p1 as _resolve_result_context
    participant p2 as _enrich_iterations
    participant p3 as build_cursor_page
    participant p4 as decode_cursor
    participant p5 as _enrich_iteration
    participant p6 as compute_next_cursor
    participant p7 as training_gates_passed_from
    participant p8 as first_valid_artifact_ref
    participant p9 as build_consistency_report
    participant p10 as _rl_economic_replay_summary
    participant p11 as _feature_readiness_metrics
    participant p12 as _rl_economic_replay_payload
    participant p13 as _adaptive_schema_flags_blocker
    participant p14 as _rl_channel_provenance
    participant p15 as _rl_feature_bundle_hash
    participant p16 as _rl_nested_validation_present
    participant p17 as _rl_multi_seed_present
    participant p18 as _rl_required_metrics_present
    participant p19 as _rl_unsafe_feature_provenance
    participant p20 as _rl_replay_assumptions_present
    participant p21 as _rl_replay_worse_than_baseline
    participant p22 as check_adaptive_feature_sweep
    participant p23 as check_evidence_artifact
    participant p24 as _adaptive_feature_evidence
    participant p25 as _rl_metric_value
    participant p26 as _feature_schema_flags
    participant p27 as _decode_pipeline_payload
    participant p28 as _decode_session_payload
    participant p29 as isinstance (src/api/results.py:get_iterations)
    participant p30 as _store.get_iterations
    p0->>p1: _resolve_result_context
    p0->>p2: _enrich_iterations
    p0->>p3: build_cursor_page
    p0->>p4: decode_cursor
    p2->>p5: _enrich_iteration
    p3->>p6: compute_next_cursor
    p5->>p7: training_gates_passed_from
    p5->>p8: first_valid_artifact_ref
    p5->>p9: build_consistency_report
    p5->>p10: _rl_economic_replay_summary
    p5->>p11: _feature_readiness_metrics
    p9->>p12: _rl_economic_replay_payload
    p9->>p13: _adaptive_schema_flags_blocker
    p9->>p14: _rl_channel_provenance
    p9->>p15: _rl_feature_bundle_hash
    p9->>p16: _rl_nested_validation_present
    p9->>p17: _rl_multi_seed_present
    p9->>p18: _rl_required_metrics_present
    p9->>p19: _rl_unsafe_feature_provenance
    p9->>p20: _rl_replay_assumptions_present
    p9->>p21: _rl_replay_worse_than_baseline
    p9->>p22: check_adaptive_feature_sweep
    p9->>p23: check_evidence_artifact
    p13->>p24: _adaptive_feature_evidence
    p18->>p25: _rl_metric_value
    p13->>p26: _feature_schema_flags
    p1->>p27: _decode_pipeline_payload
    p1->>p28: _decode_session_payload
    p0-->>p29: isinstance (src/api/results.py:get_iterations)(limit, int)
    p0-->>p30: _store.get_iterations(session[...])
```

> Call sequence diagram shows 30 of 606 interactions; 576 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 124 (123 omitted); unresolved 1 of 359 (358 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/api/results.py:_resolve_result_context` | 3 | - | unresolved | 8 |
| `src/api/results.py:_resolve_result_context` | 3 | - | external | 4 |
| `src/api/results.py:_decode_pipeline_payload` | 7 | - | external | 4 |
| `src/api/results.py:_decode_pipeline_payload` | 7 | - | unresolved | 1 |
| `src/api/results.py:_decode_session_payload` | 22 | - | external | 4 |
| `src/api/results.py:_decode_session_payload` | 22 | - | unresolved | 1 |
| `src/api/results.py:_enrich_iteration` | 30 | - | external | 15 |
| `src/api/results.py:_enrich_iteration` | 30 | - | unresolved | 55 |
> Omission summary shows 8 of 105 groups; 97 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

> Trace truncated at the depth limit; deeper calls are omitted.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. get_iterations"]
    s2["2. isinstance (src/api/results.py:get_iterations)"]
    s3["3. _resolve_result_context"]
    s4["4. research_id.startswith"]
    s5["5. _store.get_pipeline"]
    s6["6. HTTPException"]
    s7["7. _decode_pipeline_payload"]
    s8["8. dict (src/api/results.py:_decode_pipeline_payload)"]
    s9["9. decoded.get (src/api/results.py:_decode_pipeline_payload)"]
    s10["10. isinstance (src/api/results.py:_decode_pipeline_payload)"]
    s11["11. json.loads (src/api/results.py:_decode_pipeline_payload)"]
    s12["12. isinstance (src/api/results.py:_decode_pipeline_payload)"]
    s1 -. "isinstance (src/api/results.py:get_iterations)(limit, int)" .-> s2
    s1 -->|"_resolve_result_context(research_id)"| s3
    s3 -. "research_id.startswith('pipe_')" .-> s4
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
| `get_iterations` | `research_id: str`, `limit: Optional[int]`, `cursor: Optional[str]` | `_iteration_cursor_extractor` | `page[...]` | `[...]`, `{...}`, `_enrich_iterations(...)`, `page` |
| `isinstance (src/api/results.py:get_iterations)` | - | - | - | - |
| `_resolve_result_context` | `research_id: str` | `_PIPELINE_PHASES` | `session[...]` | `(...)`, `(...)`, `(...)` |
| `research_id.startswith` | - | - | - | - |
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
| get_iterations | isinstance (src/api/results.py:get_iterations) | 458 | `isinstance(limit, int)` |
| get_iterations | _resolve_result_context | 460 | `_resolve_result_context(research_id)` |
| _resolve_result_context | research_id.startswith | 342 | `research_id.startswith('pipe_')` |
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
| external_call | `get_iterations` | `isinstance` | 458 |
| unresolved_call | `_resolve_result_context` | `research_id.startswith` | 342 |
| unresolved_call | `_resolve_result_context` | `_store.get_pipeline` | 343 |
| external_call | `_resolve_result_context` | `HTTPException` | 345 |
| unresolved_call | `_decode_pipeline_payload` | `decoded.get` | 63 |
| external_call | `_decode_pipeline_payload` | `isinstance` | 67 |
| external_call | `_decode_pipeline_payload` | `json.loads` | 67 |
| external_call | `_decode_pipeline_payload` | `isinstance` | 70 |
| step_limit | `get_iterations` | `first 12 steps` | 0 |
| truncated_flow | `get_iterations` | `depth limit` | 0 |

## Behavior

This flow starts at `get_iterations` and is classified as `http`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
