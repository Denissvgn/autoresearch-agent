# reject_raw_secret_parameters

**Entry point:** `reject_raw_secret_parameters` (`api`)
**Source:** [execution_contracts](../modules/execution_contracts.md)
**Modules touched:** [execution_contracts](../modules/execution_contracts.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as reject_raw_secret_parameters
    participant p1 as parameters.items
    participant p2 as _SECRET_PARAM_KEY_RE.search
    participant p3 as is_secret_reference
    participant p4 as ContractError
    participant p5 as isinstance
    participant p6 as value.startswith
    p0-->>p1: parameters.items
    p0-->>p2: _SECRET_PARAM_KEY_RE.search(key)
    p0->>p3: is_secret_reference
    p0->>p4: ContractError
    p3-->>p5: isinstance(value, str)
    p3-->>p6: value.startswith(SECRET_WIRE_PREFIX)
```

> Call sequence diagram shows 6 of 6 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 1 of 1 (0 omitted); unresolved 3 of 3 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. reject_raw_secret_parameters"]
    s2["2. parameters.items"]
    s3["3. _SECRET_PARAM_KEY_RE.search"]
    s4["4. is_secret_reference"]
    s5["5. isinstance"]
    s6["6. value.startswith"]
    s7["7. ContractError"]
    s1 -. "parameters.items(data not statically known)" .-> s2
    s1 -. "_SECRET_PARAM_KEY_RE.search(key)" .-> s3
    s1 -->|"is_secret_reference(value)"| s4
    s4 -. "isinstance(value, str)" .-> s5
    s4 -. "value.startswith(SECRET_WIRE_PREFIX)" .-> s6
    s1 -->|"ContractError(...)"| s7
    click s1 "../modules/execution_contracts.md"
    click s4 "../modules/execution_contracts.md"
    click s7 "../modules/execution_contracts.md"
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `reject_raw_secret_parameters` | `parameters: Mapping[str, Any]`, `where: str` | `SECRET_WIRE_PREFIX` | - | - |
| `parameters.items` | - | - | - | - |
| `_SECRET_PARAM_KEY_RE.search` | - | - | - | - |
| `is_secret_reference` | `value: Any` | `SECRET_WIRE_PREFIX` | - | `...` |
| `isinstance` | - | - | - | - |
| `value.startswith` | - | - | - | - |
| `ContractError` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| reject_raw_secret_parameters | parameters.items | 189 | `parameters.items(data not statically known)` |
| reject_raw_secret_parameters | _SECRET_PARAM_KEY_RE.search | 190 | `_SECRET_PARAM_KEY_RE.search(key)` |
| reject_raw_secret_parameters | is_secret_reference | 190 | `is_secret_reference(value)` |
| is_secret_reference | isinstance | 184 | `isinstance(value, str)` |
| is_secret_reference | value.startswith | 184 | `value.startswith(SECRET_WIRE_PREFIX)` |
| reject_raw_secret_parameters | ContractError | 191 | `ContractError(...)` |

### Boundary effects

*No boundary effects detected.*

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `reject_raw_secret_parameters` | `parameters.items` | 189 |
| unresolved_call | `reject_raw_secret_parameters` | `_SECRET_PARAM_KEY_RE.search` | 190 |
| external_call | `is_secret_reference` | `isinstance` | 184 |
| unresolved_call | `is_secret_reference` | `value.startswith` | 184 |

## Behavior

This flow starts at `reject_raw_secret_parameters` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
