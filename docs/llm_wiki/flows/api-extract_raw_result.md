# extract_raw_result

**Entry point:** `extract_raw_result` (`api`)
**Source:** [output_parser](../modules/output_parser.md)
**Modules touched:** [artifact_reference](../modules/artifact_reference.md), [gate_status](../modules/gate_status.md), [output_parser](../modules/output_parser.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as extract_raw_result
    participant p1 as _coerce_kv_value
    participant p2 as normalize_optional_artifact_ref
    participant p3 as coerce_bool
    participant p4 as len
    participant p5 as text.splitlines
    participant p6 as line.strip
    participant p7 as stripped.startswith
    participant p8 as stripped[…].strip
    participant p9 as json.loads (src/core/output_parser.py:extract_raw_result)
    participant p10 as logger.warning
    participant p11 as isinstance (src/core/output_parser.py:extract_raw_result)
    participant p12 as dict
    participant p13 as _KV_PATTERN.match
    participant p14 as match.group
    participant p15 as match.group(…).strip
    participant p16 as part.strip
    participant p17 as value.split
    participant p18 as key.endswith
    participant p19 as json.loads (src/core/output_parser.py:_coerce_kv_value)
    participant p20 as float
    participant p21 as str(…).strip
    p0->>p1: _coerce_kv_value
    p1->>p2: normalize_optional_artifact_ref
    p1->>p3: coerce_bool
    p0-->>p4: len(spec.marker_prefix)
    p0-->>p5: text.splitlines
    p0-->>p6: line.strip
    p0-->>p7: stripped.startswith(spec.marker_prefix)
    p0-->>p8: stripped[…].strip
    p0-->>p9: json.loads (src/core/output_parser.py:extract_raw_result)(payload)
    p0-->>p10: logger.warning('Failed to parse result marker JSON: s', payload)
    p0-->>p11: isinstance (src/core/output_parser.py:extract_raw_result)(parsed, dict)
    p0-->>p12: dict(parsed)
    p0-->>p10: logger.warning('Result marker JSON was not an object: s', payload)
    p0-->>p5: text.splitlines
    p0-->>p6: line.strip
    p0-->>p13: _KV_PATTERN.match(line)
    p0-->>p14: match.group(1)
    p0-->>p14: match.group(1)
    p0-->>p15: match.group(…).strip
    p0-->>p14: match.group(2)
    p0-->>p9: json.loads (src/core/output_parser.py:extract_raw_result)(text)
    p0-->>p11: isinstance (src/core/output_parser.py:extract_raw_result)(parsed, dict)
    p0-->>p12: dict(parsed)
    p1-->>p16: part.strip
    p1-->>p17: value.split(' ')
    p1-->>p16: part.strip
    p1-->>p18: key.endswith('_json')
    p1-->>p19: json.loads (src/core/output_parser.py:_coerce_kv_value)(value)
    p1-->>p20: float(value)
    p2-->>p21: str(…).strip
```

> Call sequence diagram shows 30 of 38 interactions; 8 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 9 of 14 (5 omitted); unresolved 18 of 21 (3 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/artifact_reference.py:normalize_optional_artifact_ref` | 20 | - | external | 1 |
| `src/core/artifact_reference.py:normalize_optional_artifact_ref` | 20 | - | unresolved | 1 |
| `src/core/gate_status.py:coerce_bool` | 24 | - | external | 4 |
| `src/core/gate_status.py:coerce_bool` | 24 | - | unresolved | 2 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. extract_raw_result"]
    s2["2. text.splitlines"]
    s3["3. line.strip"]
    s4["4. stripped.startswith"]
    s5["5. stripped[…].strip"]
    s6["6. len"]
    s7["7. json.loads (src/core/output_parser.py:extract_raw_result)"]
    s8["8. logger.warning"]
    s9["9. isinstance (src/core/output_parser.py:extract_raw_result)"]
    s10["10. dict"]
    s11["11. logger.warning"]
    s12["12. text.splitlines"]
    s1 -. "text.splitlines(data not statically known)" .-> s2
    s1 -. "line.strip(data not statically known)" .-> s3
    s1 -. "stripped.startswith(spec.marker_prefix)" .-> s4
    s1 -. "stripped[…].strip(data not statically known)" .-> s5
    s1 -. "len(spec.marker_prefix)" .-> s6
    s1 -. "json.loads (src/core/output_parser.py:extract_raw_result)(payload)" .-> s7
    s1 -. "logger.warning('Failed to parse result marker JSON: %s', payload)" .-> s8
    s1 -. "isinstance (src/core/output_parser.py:extract_raw_result)(parsed, dict)" .-> s9
    s1 -. "dict(parsed)" .-> s10
    s1 -. "logger.warning('Result marker JSON was not an object: %s', payload)" .-> s11
    s1 -. "text.splitlines(data not statically known)" .-> s12
    click s1 "../modules/output_parser.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `extract_raw_result` | `text: str`, `spec: ResultSpec`, `allow_bare_json: bool` | `json`, `json` | - | `dict(...)`, `...`, `None`, `None`, `...` |
| `text.splitlines` | - | - | - | - |
| `line.strip` | - | - | - | - |
| `stripped.startswith` | - | - | - | - |
| `stripped[…].strip` | - | - | - | - |
| `len` | - | - | - | - |
| `json.loads (src/core/output_parser.py:extract_raw_result)` | - | - | - | - |
| `logger.warning` | - | - | - | - |
| `isinstance (src/core/output_parser.py:extract_raw_result)` | - | - | - | - |
| `dict` | - | - | - | - |
| `logger.warning` | - | - | - | - |
| `text.splitlines` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| extract_raw_result | text.splitlines | 242 | `text.splitlines(data not statically known)` |
| extract_raw_result | line.strip | 243 | `line.strip(data not statically known)` |
| extract_raw_result | stripped.startswith | 244 | `stripped.startswith(spec.marker_prefix)` |
| extract_raw_result | stripped[…].strip | 246 | `stripped[len(spec.marker_prefix):].strip(data not statically known)` |
| extract_raw_result | len | 246 | `len(spec.marker_prefix)` |
| extract_raw_result | json.loads (src/core/output_parser.py:extract_raw_result) | 248 | `json.loads(payload)` |
| extract_raw_result | logger.warning | 250 | `logger.warning('Failed to parse result marker JSON: %s', payload)` |
| extract_raw_result | isinstance (src/core/output_parser.py:extract_raw_result) | 252 | `isinstance(parsed, dict)` |
| extract_raw_result | dict | 253 | `dict(parsed)` |
| extract_raw_result | logger.warning | 254 | `logger.warning('Result marker JSON was not an object: %s', payload)` |
| extract_raw_result | text.splitlines | 260 | `text.splitlines(data not statically known)` |

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
| unresolved_call | `extract_raw_result` | `text.splitlines` | 260 |
| step_limit | `extract_raw_result` | `first 12 steps` | 0 |

## Behavior

This flow starts at `extract_raw_result` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
