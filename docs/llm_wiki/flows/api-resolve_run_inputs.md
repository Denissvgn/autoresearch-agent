# resolve_run_inputs

**Entry point:** `resolve_run_inputs` (`api`)
**Source:** [execution_contracts](../modules/execution_contracts.md)
**Modules touched:** [execution_contracts](../modules/execution_contracts.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as resolve_run_inputs
    participant p1 as reject_raw_secret_parameters
    participant p2 as _chain_pick
    participant p3 as SkillDefaults
    participant p4 as HarnessPreferences
    participant p5 as ContractError
    participant p6 as ResolutionRecord
    participant p7 as ResolvedRunInputs
    participant p8 as BudgetDimensions
    participant p9 as is_secret_reference
    participant p10 as dict
    participant p11 as records.append
    participant p12 as getattr
    participant p13 as set
    participant p14 as sorted
    participant p15 as parameters.items
    participant p16 as _SECRET_PARAM_KEY_RE.search
    participant p17 as isinstance
    participant p18 as value.startswith
    p0->>p1: reject_raw_secret_parameters
    p0->>p2: _chain_pick
    p0->>p3: SkillDefaults
    p0->>p4: HarnessPreferences
    p0->>p5: ContractError
    p0->>p6: ResolutionRecord
    p0->>p7: ResolvedRunInputs
    p0->>p8: BudgetDimensions
    p1->>p9: is_secret_reference
    p0-->>p10: dict(...)
    p0-->>p11: records.append(ResolutionRecord(...))
    p0-->>p10: dict(...)
    p0-->>p12: getattr(operator, field)
    p0-->>p13: set(skill.parameters)
    p0-->>p13: set(explicit)
    p0-->>p13: set(_RESOLVABLE_BUDGET_FIELDS)
    p0-->>p14: sorted(parameter_keys)
    p0-->>p11: records.append(ResolutionRecord(...))
    p0-->>p14: sorted(...)
    p0-->>p13: set(skill.model_roles)
    p0-->>p13: set(prefs.model_roles)
    p0-->>p11: records.append(ResolutionRecord(...))
    p1-->>p15: parameters.items
    p1-->>p16: _SECRET_PARAM_KEY_RE.search(key)
    p9-->>p17: isinstance(value, str)
    p9-->>p18: value.startswith(SECRET_WIRE_PREFIX)
    p0->>p1: reject_raw_secret_parameters
    p0->>p2: _chain_pick
    p0->>p6: ResolutionRecord
    p0->>p2: _chain_pick
```

> Call sequence diagram shows 30 of 33 interactions; 3 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 11 of 11 (0 omitted); unresolved 6 of 6 (0 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/core/execution_contracts.py:reject_raw_secret_parameters` | 6 | [src/core/execution_contracts.py](../modules/execution_contracts.md) | internal | 1 |
| `src/core/execution_contracts.py:_chain_pick` | 14 | [src/core/execution_contracts.py](../modules/execution_contracts.md) | internal | 1 |
| `src/core/execution_contracts.py:resolve_run_inputs` | 1 | [src/core/execution_contracts.py](../modules/execution_contracts.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. resolve_run_inputs"]
    s2["2. dict"]
    s3["3. SkillDefaults"]
    s4["4. HarnessPreferences"]
    s5["5. dict"]
    s6["6. reject_raw_secret_parameters"]
    s7["7. parameters.items"]
    s8["8. _SECRET_PARAM_KEY_RE.search"]
    s9["9. is_secret_reference"]
    s10["10. isinstance"]
    s11["11. value.startswith"]
    s12["12. ContractError"]
    s1 -. "dict(...)" .-> s2
    s1 -->|"SkillDefaults(data not statically known)"| s3
    s1 -->|"HarnessPreferences(data not statically known)"| s4
    s1 -. "dict(...)" .-> s5
    s1 -->|"reject_raw_secret_parameters(explicit, 'explicit inputs')"| s6
    s6 -. "parameters.items(data not statically known)" .-> s7
    s6 -. "_SECRET_PARAM_KEY_RE.search(key)" .-> s8
    s6 -->|"is_secret_reference(value)"| s9
    s9 -. "isinstance(value, str)" .-> s10
    s9 -. "value.startswith(SECRET_WIRE_PREFIX)" .-> s11
    s6 -->|"ContractError(...)"| s12
    b0["mutation records.append"]
    s1 -. "mutation records.append" .-> b0
    b1["mutation records.append"]
    s1 -. "mutation records.append" .-> b1
    b2["mutation records.append"]
    s1 -. "mutation records.append" .-> b2
    click s1 "../modules/execution_contracts.md"
    click s3 "../modules/execution_contracts.md"
    click s4 "../modules/execution_contracts.md"
    click s6 "../modules/execution_contracts.md"
    click s9 "../modules/execution_contracts.md"
    click s12 "../modules/execution_contracts.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
    class b1 boundary
    class b2 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `resolve_run_inputs` | `operator: OperatorConstraints`, `explicit: Optional[Mapping[str, Any]]`, `skill_defaults: Optional[SkillDefaults]`, `harness_preferences: Optional[HarnessPreferences]`, `system_defaults: Optional[Mapping[str, Any]]` | `SYSTEM_DEFAULTS`, `_RESOLVABLE_BUDGET_FIELDS`, `_RESOLVABLE_BUDGET_FIELDS` | `budget_values[...]`, `parameters[...]`, `model_roles[...]` | `ResolvedRunInputs(...)` |
| `dict` | - | - | - | - |
| `SkillDefaults` | - | - | - | - |
| `HarnessPreferences` | - | - | - | - |
| `dict` | - | - | - | - |
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
| resolve_run_inputs | dict | 1073 | `dict(...)` |
| resolve_run_inputs | SkillDefaults | 1074 | `SkillDefaults(data not statically known)` |
| resolve_run_inputs | HarnessPreferences | 1075 | `HarnessPreferences(data not statically known)` |
| resolve_run_inputs | dict | 1076 | `dict(...)` |
| resolve_run_inputs | reject_raw_secret_parameters | 1078 | `reject_raw_secret_parameters(explicit, 'explicit inputs')` |
| reject_raw_secret_parameters | parameters.items | 187 | `parameters.items(data not statically known)` |
| reject_raw_secret_parameters | _SECRET_PARAM_KEY_RE.search | 188 | `_SECRET_PARAM_KEY_RE.search(key)` |
| reject_raw_secret_parameters | is_secret_reference | 188 | `is_secret_reference(value)` |
| is_secret_reference | isinstance | 182 | `isinstance(value, str)` |
| is_secret_reference | value.startswith | 182 | `value.startswith(SECRET_WIRE_PREFIX)` |
| reject_raw_secret_parameters | ContractError | 189 | `ContractError(...)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `records.append` | `resolve_run_inputs` | 1103 |
| mutation | `records.append` | `resolve_run_inputs` | 1126 |
| mutation | `records.append` | `resolve_run_inputs` | 1142 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `reject_raw_secret_parameters` | `parameters.items` | 187 |
| unresolved_call | `reject_raw_secret_parameters` | `_SECRET_PARAM_KEY_RE.search` | 188 |
| external_call | `is_secret_reference` | `isinstance` | 182 |
| unresolved_call | `is_secret_reference` | `value.startswith` | 182 |
| step_limit | `resolve_run_inputs` | `first 12 steps` | 0 |

## Behavior

This flow starts at `resolve_run_inputs` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
