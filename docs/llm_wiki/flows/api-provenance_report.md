# provenance_report

**Entry point:** `provenance_report` (`api`)
**Source:** [run_spec](../modules/run_spec.md)
**Modules touched:** [run_spec](../modules/run_spec.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as provenance_report
    participant p1 as set
    participant p2 as sorted
    participant p3 as raw_manifest.get
    participant p4 as isinstance (src/core/run_spec.py:provenance_report)
    participant p5 as verify_run_spec
    participant p6 as spec.get
    participant p7 as isinstance (src/core/run_spec.py:verify_run_spec)
    participant p8 as hashlib.sha256(…).hexdigest
    participant p9 as hashlib.sha256
    participant p10 as canonical_spec_json(…).encode
    participant p11 as canonical_spec_json
    participant p12 as dict
    participant p13 as payload.pop
    participant p14 as json.dumps
    p0-->>p1: set(ResearchSessionManifest.model_fields)
    p0-->>p2: sorted(...)
    p0-->>p3: raw_manifest.get(name)
    p0-->>p3: raw_manifest.get('run_spec')
    p0-->>p4: isinstance (src/core/run_spec.py:provenance_report)(run_spec, Mapping)
    p0->>p5: verify_run_spec
    p0-->>p3: raw_manifest.get('schema_version')
    p5-->>p6: spec.get('spec_sha256')
    p5-->>p7: isinstance (src/core/run_spec.py:verify_run_spec)(recorded, str)
    p5-->>p8: hashlib.sha256(…).hexdigest
    p5-->>p9: hashlib.sha256(...)
    p5-->>p10: canonical_spec_json(…).encode('utf-8')
    p5->>p11: canonical_spec_json
    p11-->>p12: dict(spec)
    p11-->>p13: payload.pop('spec_sha256', None)
    p11-->>p14: json.dumps(payload, sort_keys=True, separators=(...))
```

> Call sequence diagram shows 16 of 16 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 7 of 7 (0 omitted); unresolved 7 of 7 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. provenance_report"]
    s2["2. set"]
    s3["3. sorted"]
    s4["4. raw_manifest.get"]
    s5["5. raw_manifest.get"]
    s6["6. isinstance (src/core/run_spec.py:provenance_report)"]
    s7["7. verify_run_spec"]
    s8["8. spec.get"]
    s9["9. isinstance (src/core/run_spec.py:verify_run_spec)"]
    s10["10. hashlib.sha256(…).hexdigest"]
    s11["11. hashlib.sha256"]
    s12["12. canonical_spec_json(…).encode"]
    s1 -. "set(ResearchSessionManifest.model_fields)" .-> s2
    s1 -. "sorted(...)" .-> s3
    s1 -. "raw_manifest.get(name)" .-> s4
    s1 -. "raw_manifest.get('run_spec')" .-> s5
    s1 -. "isinstance (src/core/run_spec.py:provenance_report)(run_spec, Mapping)" .-> s6
    s1 -->|"verify_run_spec(run_spec)"| s7
    s7 -. "spec.get('spec_sha256')" .-> s8
    s7 -. "isinstance (src/core/run_spec.py:verify_run_spec)(recorded, str)" .-> s9
    s7 -. "hashlib.sha256(…).hexdigest(data not statically known)" .-> s10
    s7 -. "hashlib.sha256(...)" .-> s11
    s7 -. "canonical_spec_json(…).encode('utf-8')" .-> s12
    click s1 "../modules/run_spec.md"
    click s7 "../modules/run_spec.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `provenance_report` | `raw_manifest: Mapping[str, Any]` | `PROVENANCE_SECTIONS`, `Mapping` | - | `{...}` |
| `set` | - | - | - | - |
| `sorted` | - | - | - | - |
| `raw_manifest.get` | - | - | - | - |
| `raw_manifest.get` | - | - | - | - |
| `isinstance (src/core/run_spec.py:provenance_report)` | - | - | - | - |
| `verify_run_spec` | `spec: Mapping[str, Any]` | - | - | `False`, `...` |
| `spec.get` | - | - | - | - |
| `isinstance (src/core/run_spec.py:verify_run_spec)` | - | - | - | - |
| `hashlib.sha256(…).hexdigest` | - | - | - | - |
| `hashlib.sha256` | - | - | - | - |
| `canonical_spec_json(…).encode` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| provenance_report | set | 235 | `set(ResearchSessionManifest.model_fields)` |
| provenance_report | sorted | 236 | `sorted(...)` |
| provenance_report | raw_manifest.get | 239 | `raw_manifest.get(name)` |
| provenance_report | raw_manifest.get | 241 | `raw_manifest.get('run_spec')` |
| provenance_report | isinstance (src/core/run_spec.py:provenance_report) | 243 | `isinstance(run_spec, Mapping)` |
| provenance_report | verify_run_spec | 244 | `verify_run_spec(run_spec)` |
| verify_run_spec | spec.get | 216 | `spec.get('spec_sha256')` |
| verify_run_spec | isinstance (src/core/run_spec.py:verify_run_spec) | 217 | `isinstance(recorded, str)` |
| verify_run_spec | hashlib.sha256(…).hexdigest | 219 | `hashlib.sha256(canonical_spec_json(spec).encode('utf-8')).hexdigest(data not statically known)` |
| verify_run_spec | hashlib.sha256 | 219 | `hashlib.sha256(...)` |
| verify_run_spec | canonical_spec_json(…).encode | 220 | `canonical_spec_json(spec).encode('utf-8')` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `provenance_report` | `sorted` | 236 |
| unresolved_call | `provenance_report` | `raw_manifest.get` | 239 |
| unresolved_call | `provenance_report` | `raw_manifest.get` | 241 |
| external_call | `provenance_report` | `isinstance` | 243 |
| unresolved_call | `verify_run_spec` | `spec.get` | 216 |
| external_call | `verify_run_spec` | `isinstance` | 217 |
| unresolved_call | `verify_run_spec` | `hashlib.sha256(canonical_spec_json(spec).encode('utf-8')).hexdigest` | 219 |
| external_call | `verify_run_spec` | `hashlib.sha256` | 219 |
| unresolved_call | `verify_run_spec` | `canonical_spec_json(spec).encode` | 220 |
| step_limit | `provenance_report` | `first 12 steps` | 0 |

## Behavior

This flow starts at `provenance_report` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
