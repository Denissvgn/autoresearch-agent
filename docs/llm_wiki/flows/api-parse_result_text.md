# parse_result_text

**Entry point:** `parse_result_text` (`api`)
**Source:** [output_parser](../modules/output_parser.md)
**Modules touched:** [artifact_reference](../modules/artifact_reference.md), [gate_status](../modules/gate_status.md), [output_parser](../modules/output_parser.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as parse_result_text
    participant p1 as extract_raw_result
    participant p2 as normalize_result
    participant p3 as normalize_training_gate_aliases
    participant p4 as _coerce_kv_value
    participant p5 as coerce_bool
    participant p6 as NormalizedResult
    participant p7 as normalize_optional_artifact_ref
    participant p8 as dict (src/core/output_parser.py:normalize_result)
    participant p9 as text.splitlines
    participant p10 as line.strip
    participant p11 as stripped.startswith
    participant p12 as payload.get (src/core/output_parser.py:normalize_result)
    participant p13 as stripped[…].strip
    participant p14 as isinstance (src/core/output_parser.py:normalize_result)
    participant p15 as len
    participant p16 as raw_status.strip
    participant p17 as json.loads (src/core/output_parser.py:extract_raw_result)
    participant p18 as logger.warning (src/core/output_parser.py:extract_raw_result)
    participant p19 as violations.append
    participant p20 as isinstance (src/core/output_parser.py:extract_raw_result)
    participant p21 as dict (src/core/output_parser.py:extract_raw_result)
    participant p22 as str (src/core/output_parser.py:normalize_result)
    p0->>p1: extract_raw_result
    p0->>p2: normalize_result
    p2->>p3: normalize_training_gate_aliases
    p1->>p4: _coerce_kv_value
    p2->>p5: coerce_bool
    p2->>p6: NormalizedResult
    p4->>p7: normalize_optional_artifact_ref
    p2-->>p8: dict (src/core/output_parser.py:normalize_result)(raw)
    p1-->>p9: text.splitlines
    p1-->>p10: line.strip
    p1-->>p11: stripped.startswith(spec.marker_prefix)
    p2-->>p12: payload.get (src/core/output_parser.py:normalize_result)('status')
    p1-->>p13: stripped[…].strip
    p2-->>p14: isinstance (src/core/output_parser.py:normalize_result)(raw_status, str)
    p1-->>p15: len(spec.marker_prefix)
    p2-->>p16: raw_status.strip
    p1-->>p17: json.loads (src/core/output_parser.py:extract_raw_result)(payload)
    p2-->>p16: raw_status.strip
    p1-->>p18: logger.warning (src/core/output_parser.py:extract_raw_result)('Failed to parse result marker JSON: s', payload)
    p2-->>p19: violations.append('missing status')
    p1-->>p20: isinstance (src/core/output_parser.py:extract_raw_result)(parsed, dict)
    p2-->>p12: payload.get (src/core/output_parser.py:normalize_result)('schema_version')
    p1-->>p21: dict (src/core/output_parser.py:extract_raw_result)(parsed)
    p2-->>p22: str (src/core/output_parser.py:normalize_result)(declared_version)
    p1-->>p18: logger.warning (src/core/output_parser.py:extract_raw_result)('Result marker JSON was not an object: s', payload)
    p2-->>p19: violations.append(...)
    p1-->>p9: text.splitlines
    p2-->>p12: payload.get (src/core/output_parser.py:normalize_result)(name)
    p1-->>p10: line.strip
    p2-->>p14: isinstance (src/core/output_parser.py:normalize_result)(value, str)
```

> Call sequence diagram shows 30 of 126 interactions; 96 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 8 of 50 (42 omitted); unresolved 15 of 64 (49 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/output_parser.py:extract_raw_result` | 2 | - | unresolved | 5 |
| `src/core/output_parser.py:_coerce_kv_value` | 17 | - | unresolved | 4 |
| `src/core/artifact_reference.py:normalize_optional_artifact_ref` | 21 | - | unresolved | 2 |
| `src/core/artifact_reference.py:normalize_optional_artifact_ref` | 21 | - | external | 1 |
| `src/core/output_parser.py:_coerce_kv_value` | 17 | [src/core/gate_status.py](../modules/gate_status.md) | internal | 1 |
| `src/core/gate_status.py:coerce_bool` | 25 | - | external | 4 |
| `src/core/gate_status.py:coerce_bool` | 25 | - | unresolved | 2 |
| `src/core/output_parser.py:_coerce_kv_value` | 17 | - | external | 2 |
> Omission summary shows 8 of 13 groups; 5 further groups are not expanded here. Counts above include all omitted interactions.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. parse_result_text"]
    s2["2. extract_raw_result"]
    s3["3. text.splitlines"]
    s4["4. line.strip"]
    s5["5. stripped.startswith"]
    s6["6. stripped[…].strip"]
    s7["7. len"]
    s8["8. json.loads (src/core/output_parser.py:extract_raw_result)"]
    s9["9. logger.warning (src/core/output_parser.py:extract_raw_result)"]
    s10["10. isinstance (src/core/output_parser.py:extract_raw_result)"]
    s11["11. dict (src/core/output_parser.py:extract_raw_result)"]
    s12["12. logger.warning (src/core/output_parser.py:extract_raw_result)"]
    s1 -->|"extract_raw_result(text, spec, allow_bare_json=allow_bare_json)"| s2
    s2 -. "text.splitlines(data not statically known)" .-> s3
    s2 -. "line.strip(data not statically known)" .-> s4
    s2 -. "stripped.startswith(spec.marker_prefix)" .-> s5
    s2 -. "stripped[…].strip(data not statically known)" .-> s6
    s2 -. "len(spec.marker_prefix)" .-> s7
    s2 -. "json.loads (src/core/output_parser.py:extract_raw_result)(payload)" .-> s8
    s2 -. "logger.warning (src/core/output_parser.py:extract_raw_result)('Failed to parse result marker JSON: %s', payload)" .-> s9
    s2 -. "isinstance (src/core/output_parser.py:extract_raw_result)(parsed, dict)" .-> s10
    s2 -. "dict (src/core/output_parser.py:extract_raw_result)(parsed)" .-> s11
    s2 -. "logger.warning (src/core/output_parser.py:extract_raw_result)('Result marker JSON was not an object: %s', payload)" .-> s12
    click s1 "../modules/output_parser.md"
    click s2 "../modules/output_parser.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `parse_result_text` | `text: str`, `spec: ResultSpec`, `allow_bare_json: bool` | - | - | `None`, `normalize_result(...)` |
| `extract_raw_result` | `text: str`, `spec: ResultSpec`, `allow_bare_json: bool` | `json`, `json` | - | `dict(...)`, `...`, `None`, `None`, `...` |
| `text.splitlines` | - | - | - | - |
| `line.strip` | - | - | - | - |
| `stripped.startswith` | - | - | - | - |
| `stripped[…].strip` | - | - | - | - |
| `len` | - | - | - | - |
| `json.loads (src/core/output_parser.py:extract_raw_result)` | - | - | - | - |
| `logger.warning (src/core/output_parser.py:extract_raw_result)` | - | - | - | - |
| `isinstance (src/core/output_parser.py:extract_raw_result)` | - | - | - | - |
| `dict (src/core/output_parser.py:extract_raw_result)` | - | - | - | - |
| `logger.warning (src/core/output_parser.py:extract_raw_result)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| parse_result_text | extract_raw_result | 458 | `extract_raw_result(text, spec, allow_bare_json=allow_bare_json)` |
| extract_raw_result | text.splitlines | 242 | `text.splitlines(data not statically known)` |
| extract_raw_result | line.strip | 243 | `line.strip(data not statically known)` |
| extract_raw_result | stripped.startswith | 244 | `stripped.startswith(spec.marker_prefix)` |
| extract_raw_result | stripped[…].strip | 246 | `stripped[len(spec.marker_prefix):].strip(data not statically known)` |
| extract_raw_result | len | 246 | `len(spec.marker_prefix)` |
| extract_raw_result | json.loads (src/core/output_parser.py:extract_raw_result) | 248 | `json.loads(payload)` |
| extract_raw_result | logger.warning (src/core/output_parser.py:extract_raw_result) | 250 | `logger.warning('Failed to parse result marker JSON: %s', payload)` |
| extract_raw_result | isinstance (src/core/output_parser.py:extract_raw_result) | 252 | `isinstance(parsed, dict)` |
| extract_raw_result | dict (src/core/output_parser.py:extract_raw_result) | 253 | `dict(parsed)` |
| extract_raw_result | logger.warning (src/core/output_parser.py:extract_raw_result) | 254 | `logger.warning('Result marker JSON was not an object: %s', payload)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `extract_raw_result` | `text.splitlines` | 242 |
| unresolved_call | `extract_raw_result` | `line.strip` | 243 |
| unresolved_call | `extract_raw_result` | `stripped.startswith` | 244 |
| unresolved_call | `extract_raw_result` | `stripped[len(spec.marker_prefix):].strip` | 246 |
| external_call | `extract_raw_result` | `json.loads` | 248 |
| unresolved_call | `extract_raw_result` | `logger.warning` | 250 |
| external_call | `extract_raw_result` | `isinstance` | 252 |
| unresolved_call | `extract_raw_result` | `logger.warning` | 254 |
| step_limit | `parse_result_text` | `first 12 steps` | 0 |

## Behavior

This flow starts at `parse_result_text` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
