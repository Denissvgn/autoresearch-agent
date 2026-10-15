# load_skill_manifest

**Entry point:** `load_skill_manifest` (`api`)
**Source:** [skill_loader](../modules/skill_loader.md)
**Modules touched:** [skill_loader](../modules/skill_loader.md), [skill_manifest](../modules/skill_manifest.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as load_skill_manifest
    participant p1 as _interpolate
    participant p2 as _wrap_validation_error
    participant p3 as ManifestValidationError
    participant p4 as ManifestVersionError
    participant p5 as _interpolate_string
    participant p6 as isinstance (src/core/skill_loader.py:load_skill_manifest)
    participant p7 as Path(…).read_text
    participant p8 as dict
    participant p9 as Path
    participant p10 as yaml.safe_load
    participant p11 as type
    participant p12 as candidate.exists
    participant p13 as candidate.read_text
    participant p14 as data.get
    participant p15 as ResearchSkillManifest.model_validate
    participant p16 as isinstance (src/core/skill_loader.py:_interpolate)
    participant p17 as exc.errors
    participant p18 as '.'.join
    participant p19 as str
    participant p20 as lines.append
    participant p21 as node.items
    p0->>p1: _interpolate
    p0->>p2: _wrap_validation_error
    p0->>p3: ManifestValidationError
    p0->>p4: ManifestVersionError
    p1->>p5: _interpolate_string
    p0-->>p6: isinstance (src/core/skill_loader.py:load_skill_manifest)(source, Mapping)
    p0-->>p7: Path(…).read_text(encoding='utf-8')
    p0-->>p8: dict(source)
    p0-->>p6: isinstance (src/core/skill_loader.py:load_skill_manifest)(source, Path)
    p0-->>p9: Path(source)
    p0-->>p10: yaml.safe_load(text)
    p0-->>p6: isinstance (src/core/skill_loader.py:load_skill_manifest)(parsed, dict)
    p0-->>p11: type(parsed)
    p0-->>p6: isinstance (src/core/skill_loader.py:load_skill_manifest)(source, str)
    p0-->>p9: Path(source)
    p0-->>p12: candidate.exists
    p0-->>p13: candidate.read_text(encoding='utf-8')
    p0-->>p10: yaml.safe_load(text)
    p0-->>p6: isinstance (src/core/skill_loader.py:load_skill_manifest)(parsed, dict)
    p0-->>p11: type(parsed)
    p0-->>p11: type(source)
    p0-->>p14: data.get('schema_version')
    p0-->>p15: ResearchSkillManifest.model_validate(data)
    p1-->>p16: isinstance (src/core/skill_loader.py:_interpolate)(node, str)
    p2-->>p17: exc.errors
    p2-->>p18: '.'.join(...)
    p1-->>p16: isinstance (src/core/skill_loader.py:_interpolate)(node, dict)
    p2-->>p19: str(part)
    p2-->>p20: lines.append(...)
    p1-->>p21: node.items
```

> Call sequence diagram shows 30 of 40 interactions; 10 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 16 of 18 (2 omitted); unresolved 9 of 12 (3 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/skill_loader.py:load_skill_manifest` | 1 | [src/core/skill_manifest.py](../modules/skill_manifest.md) | internal | 2 |
| `src/core/skill_loader.py:_interpolate_string` | 25 | - | unresolved | 2 |
| `src/core/skill_loader.py:_interpolate` | 23 | [src/core/skill_loader.py](../modules/skill_loader.md) | internal | 2 |
| `src/core/skill_loader.py:_interpolate` | 23 | - | external | 2 |
| `src/core/skill_loader.py:_wrap_validation_error` | 35 | - | unresolved | 1 |
| `src/core/skill_loader.py:_wrap_validation_error` | 35 | [src/core/skill_manifest.py](../modules/skill_manifest.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. load_skill_manifest"]
    s2["2. isinstance (src/core/skill_loader.py:load_skill_manifest)"]
    s3["3. dict"]
    s4["4. isinstance (src/core/skill_loader.py:load_skill_manifest)"]
    s5["5. Path(…).read_text"]
    s6["6. Path"]
    s7["7. yaml.safe_load"]
    s8["8. isinstance (src/core/skill_loader.py:load_skill_manifest)"]
    s9["9. ManifestValidationError"]
    s10["10. type"]
    s11["11. isinstance (src/core/skill_loader.py:load_skill_manifest)"]
    s12["12. Path"]
    s1 -. "isinstance (src/core/skill_loader.py:load_skill_manifest)(source, Mapping)" .-> s2
    s1 -. "dict(source)" .-> s3
    s1 -. "isinstance (src/core/skill_loader.py:load_skill_manifest)(source, Path)" .-> s4
    s1 -. "Path(…).read_text(encoding='utf-8')" .-> s5
    s1 -. "Path(source)" .-> s6
    s1 -. "yaml.safe_load(text)" .-> s7
    s1 -. "isinstance (src/core/skill_loader.py:load_skill_manifest)(parsed, dict)" .-> s8
    s1 -->|"ManifestValidationError(...)"| s9
    s1 -. "type(parsed)" .-> s10
    s1 -. "isinstance (src/core/skill_loader.py:load_skill_manifest)(source, str)" .-> s11
    s1 -. "Path(source)" .-> s12
    b0["filesystem_read candidate.read_text"]
    s1 -. "filesystem_read candidate.read_text" .-> b0
    click s1 "../modules/skill_loader.md"
    click s9 "../modules/skill_manifest.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `load_skill_manifest` | `source: Union[str, Path, Mapping[str, Any]]`, `settings_obj: Any`, `skill_params: Optional[Mapping[str, Any]]` | `Mapping`, `Path`, `SCHEMA_VERSION`, `SCHEMA_VERSION`, `SCHEMA_VERSION`, `ValidationError` | - | `ResearchSkillManifest.model_validate(...)` |
| `isinstance (src/core/skill_loader.py:load_skill_manifest)` | - | - | - | - |
| `dict` | - | - | - | - |
| `isinstance (src/core/skill_loader.py:load_skill_manifest)` | - | - | - | - |
| `Path(…).read_text` | - | - | - | - |
| `Path` | - | - | - | - |
| `yaml.safe_load` | - | - | - | - |
| `isinstance (src/core/skill_loader.py:load_skill_manifest)` | - | - | - | - |
| `ManifestValidationError` | - | - | - | - |
| `type` | - | - | - | - |
| `isinstance (src/core/skill_loader.py:load_skill_manifest)` | - | - | - | - |
| `Path` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| load_skill_manifest | isinstance (src/core/skill_loader.py:load_skill_manifest) | 383 | `isinstance(source, Mapping)` |
| load_skill_manifest | dict | 384 | `dict(source)` |
| load_skill_manifest | isinstance (src/core/skill_loader.py:load_skill_manifest) | 385 | `isinstance(source, Path)` |
| load_skill_manifest | Path(…).read_text | 386 | `Path(source).read_text(encoding='utf-8')` |
| load_skill_manifest | Path | 386 | `Path(source)` |
| load_skill_manifest | yaml.safe_load | 387 | `yaml.safe_load(text)` |
| load_skill_manifest | isinstance (src/core/skill_loader.py:load_skill_manifest) | 388 | `isinstance(parsed, dict)` |
| load_skill_manifest | ManifestValidationError | 389 | `ManifestValidationError(...)` |
| load_skill_manifest | type | 390 | `type(parsed)` |
| load_skill_manifest | isinstance (src/core/skill_loader.py:load_skill_manifest) | 393 | `isinstance(source, str)` |
| load_skill_manifest | Path | 396 | `Path(source)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| filesystem_read | `candidate.read_text` | `load_skill_manifest` | 398 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `load_skill_manifest` | `isinstance` | 383 |
| external_call | `load_skill_manifest` | `isinstance` | 385 |
| unresolved_call | `load_skill_manifest` | `Path(source).read_text` | 386 |
| external_call | `load_skill_manifest` | `yaml.safe_load` | 387 |
| external_call | `load_skill_manifest` | `isinstance` | 388 |
| external_call | `load_skill_manifest` | `type` | 390 |
| external_call | `load_skill_manifest` | `isinstance` | 393 |
| step_limit | `load_skill_manifest` | `first 12 steps` | 0 |

## Behavior

This flow starts at `load_skill_manifest` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
