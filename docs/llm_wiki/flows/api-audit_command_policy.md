# audit_command_policy

**Entry point:** `audit_command_policy` (`api`)
**Source:** [skill_generator](../modules/skill_generator.md)
**Modules touched:** [skill_generator](../modules/skill_generator.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as audit_command_policy
    participant p1 as _yaml.safe_load
    participant p2 as CommandPolicyFinding
    participant p3 as isinstance
    participant p4 as data.get
    participant p5 as policy.get
    participant p6 as str
    participant p7 as re.search
    participant p8 as findings.append
    p0-->>p1: _yaml.safe_load(manifest_yaml)
    p0->>p2: CommandPolicyFinding
    p0-->>p3: isinstance(data, dict)
    p0-->>p4: data.get('command_policy')
    p0-->>p3: isinstance(policy, dict)
    p0-->>p5: policy.get(field_name)
    p0-->>p3: isinstance(entries, list)
    p0-->>p6: str(entry)
    p0-->>p7: re.search(pattern, entry_str)
    p0-->>p8: findings.append(CommandPolicyFinding(...))
    p0->>p2: CommandPolicyFinding
```

> Call sequence diagram shows 11 of 11 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 6 of 6 (0 omitted); unresolved 3 of 3 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. audit_command_policy"]
    s2["2. _yaml.safe_load"]
    s3["3. CommandPolicyFinding"]
    s4["4. isinstance"]
    s5["5. data.get"]
    s6["6. isinstance"]
    s7["7. policy.get"]
    s8["8. isinstance"]
    s9["9. str"]
    s10["10. re.search"]
    s11["11. findings.append"]
    s12["12. CommandPolicyFinding"]
    s1 -. "_yaml.safe_load(manifest_yaml)" .-> s2
    s1 -->|"CommandPolicyFinding('critical', 'yaml', 'manifest is not valid YAML', '#60;root#62;')"| s3
    s1 -. "isinstance(data, dict)" .-> s4
    s1 -. "data.get('command_policy')" .-> s5
    s1 -. "isinstance(policy, dict)" .-> s6
    s1 -. "policy.get(field_name)" .-> s7
    s1 -. "isinstance(entries, list)" .-> s8
    s1 -. "str(entry)" .-> s9
    s1 -. "re.search(pattern, entry_str)" .-> s10
    s1 -. "findings.append(CommandPolicyFinding(...))" .-> s11
    s1 -->|"CommandPolicyFinding(severity=severity, pattern=pattern, reason=reason, location=...)"| s12
    b0["mutation findings.append"]
    s1 -. "mutation findings.append" .-> b0
    click s1 "../modules/skill_generator.md"
    click s3 "../modules/skill_generator.md"
    click s12 "../modules/skill_generator.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `audit_command_policy` | `manifest_yaml: str` | `_OVERPERMISSIVE_PATTERNS` | - | `[...]`, `findings`, `findings`, `findings` |
| `_yaml.safe_load` | - | - | - | - |
| `CommandPolicyFinding` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `data.get` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `policy.get` | - | - | - | - |
| `isinstance` | - | - | - | - |
| `str` | - | - | - | - |
| `re.search` | - | - | - | - |
| `findings.append` | - | - | - | - |
| `CommandPolicyFinding` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| audit_command_policy | _yaml.safe_load | 117 | `_yaml.safe_load(manifest_yaml)` |
| audit_command_policy | CommandPolicyFinding | 119 | `CommandPolicyFinding('critical', 'yaml', 'manifest is not valid YAML', '<root>')` |
| audit_command_policy | isinstance | 120 | `isinstance(data, dict)` |
| audit_command_policy | data.get | 122 | `data.get('command_policy')` |
| audit_command_policy | isinstance | 123 | `isinstance(policy, dict)` |
| audit_command_policy | policy.get | 129 | `policy.get(field_name)` |
| audit_command_policy | isinstance | 130 | `isinstance(entries, list)` |
| audit_command_policy | str | 133 | `str(entry)` |
| audit_command_policy | re.search | 135 | `re.search(pattern, entry_str)` |
| audit_command_policy | findings.append | 136 | `findings.append(CommandPolicyFinding(...))` |
| audit_command_policy | CommandPolicyFinding | 137 | `CommandPolicyFinding(severity=severity, pattern=pattern, reason=reason, location=...)` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| mutation | `findings.append` | `audit_command_policy` | 136 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| external_call | `audit_command_policy` | `_yaml.safe_load` | 117 |
| external_call | `audit_command_policy` | `isinstance` | 120 |
| unresolved_call | `audit_command_policy` | `data.get` | 122 |
| external_call | `audit_command_policy` | `isinstance` | 123 |
| unresolved_call | `audit_command_policy` | `policy.get` | 129 |
| external_call | `audit_command_policy` | `isinstance` | 130 |
| external_call | `audit_command_policy` | `re.search` | 135 |

## Behavior

This flow starts at `audit_command_policy` and is classified as `api`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
