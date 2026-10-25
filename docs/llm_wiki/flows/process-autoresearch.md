# autoresearch

**Entry point:** `main` (`process`)
**Source:** [cli](../modules/cli.md)
**Modules touched:** [agent_cli](../modules/agent_cli.md), [cli](../modules/cli.md)

**Related modules:** [agent_cli](../modules/agent_cli.md), [config](../modules/config.md), [llm_provider](../modules/llm_provider.md), [objective_comparator](../modules/objective_comparator.md), and 6 more

**Complete related modules:**

- [agent_cli](../modules/agent_cli.md)
- [config](../modules/config.md)
- [llm_provider](../modules/llm_provider.md)
- [objective_comparator](../modules/objective_comparator.md)
- [plugin_runner](../modules/plugin_runner.md)
- [promotion_target](../modules/promotion_target.md)
- [results_store](../modules/results_store.md)
- [skill_generator](../modules/skill_generator.md)
- [skill_loader](../modules/skill_loader.md)
- [skill_manifest](../modules/skill_manifest.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as build_parser
    participant p2 as build_agent_parser
    participant p3 as _add_promote_flags
    participant p4 as asyncio.run
    participant p5 as build_parser().parse_args
    participant p6 as handler
    participant p7 as print
    participant p8 as argparse.ArgumentParser (src/cli.py:build_parser)
    participant p9 as parser.add_subparsers
    participant p10 as sub.add_parser (src/cli.py:build_parser)
    participant p11 as new_skill.add_argument
    participant p12 as promote.add_argument
    participant p13 as reconcile.add_argument
    participant p14 as argparse.ArgumentParser (src/agent_cli.py:build_agent_parser)
    participant p15 as p.add_argument
    participant p16 as common.add_argument
    p0->>p1: build_parser
    p1->>p2: build_agent_parser
    p1->>p3: _add_promote_flags
    p0-->>p4: asyncio.run(handler(...))
    p0-->>p5: build_parser().parse_args(argv)
    p0-->>p6: handler(args)
    p0-->>p7: print('interrupted.', file=sys.stderr)
    p1-->>p8: argparse.ArgumentParser (src/cli.py:build_parser)(…)
    p1-->>p9: parser.add_subparsers(dest='command', required=True)
    p1-->>p10: sub.add_parser (src/cli.py:build_parser)(…)
    p1-->>p11: new_skill.add_argument('--goal', required=True, help='Natural-language description of the research domain.')
    p1-->>p11: new_skill.add_argument('--id', default=None, help='Override the generated kebab-case skill id.')
    p1-->>p11: new_skill.add_argument(…)
    p1-->>p11: new_skill.add_argument(…)
    p1-->>p11: new_skill.add_argument('--dry-run', action='store_true', help='Generate into a throwaway dir nothing under skills/ is written.')
    p1-->>p11: new_skill.add_argument(…)
    p1-->>p10: sub.add_parser (src/cli.py:build_parser)(…)
    p1-->>p12: promote.add_argument('--id', required=True, help='The draft skill id.')
    p1-->>p10: sub.add_parser (src/cli.py:build_parser)(…)
    p1-->>p13: reconcile.add_argument('--db', default=None, help='SQLite DB path (default: settings.db_path).')
    p1-->>p13: reconcile.add_argument('--apply', action='store_true', help='Write corrections for reconcilable sessions (dry-run otherwise).')
    p2-->>p14: argparse.ArgumentParser (src/agent_cli.py:build_agent_parser)(add_help=False)
    p3-->>p15: p.add_argument('--promote', action='store_true', help=...)
    p2-->>p16: common.add_argument('--credential-env', default=DEFAULT_CREDENTIAL_ENV, help='environment variable holding the scoped credential')
    p3-->>p15: p.add_argument('--yes', action='store_true', help='Non-interactive: skip the confirmation prompt.')
    p2-->>p16: common.add_argument('--credential-file', default=None, help='file holding the scoped credential (never pass it on argv)')
    p3-->>p15: p.add_argument('--allow-critical', action='store_true', help='Promote even when the policy audit reported critical findings.')
    p2-->>p16: common.add_argument('--base-url', default=None, help='API base URL (default: $AUTORESEARCH_API_URL)')
    p3-->>p15: p.add_argument('--no-tag', action='store_true', help='Skip the best-effort skill/<id>/<version> git tag.')
    p2-->>p16: common.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT_S, help='bounded wait / request timeout in seconds')
```

> Call sequence diagram shows 30 of 59 interactions; 29 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 4 of 4 (0 omitted); unresolved 23 of 51 (28 omitted). These counts cover the captured static trace.

Omitted captured detail, grouped by actual caller occurrence and target module:

| Caller | Parent step | Target module | Kind | Omitted interactions |
| --- | --- | --- | --- | --- |
| `src/agent_cli.py:build_agent_parser` | 6 | - | unresolved | 27 |
| `src/cli.py:_add_promote_flags` | 46 | - | unresolved | 1 |
| `src/cli.py:build_parser` | 3 | [src/cli.py](../modules/cli.md) | internal | 1 |
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. build_parser().parse_args"]
    s3["3. build_parser"]
    s4["4. argparse.ArgumentParser (src/cli.py:build_parser)"]
    s5["5. parser.add_subparsers"]
    s6["6. build_agent_parser"]
    s7["7. argparse.ArgumentParser (src/agent_cli.py:build_agent_parser)"]
    s8["8. common.add_argument"]
    s9["9. common.add_argument"]
    s10["10. common.add_argument"]
    s11["11. common.add_argument"]
    s12["12. sub.add_parser (src/agent_cli.py:build_agent_parser)"]
    s1 -. "build_parser().parse_args(argv)" .-> s2
    s1 -->|"build_parser(data not statically known)"| s3
    s3 -. "argparse.ArgumentParser (src/cli.py:build_parser)(…)" .-> s4
    s3 -. "parser.add_subparsers(dest='command', required=True)" .-> s5
    s3 -->|"build_agent_parser(sub)"| s6
    s6 -. "argparse.ArgumentParser (src/agent_cli.py:build_agent_parser)(add_help=False)" .-> s7
    s6 -. "common.add_argument('--credential-env', default=DEFAULT_CREDENTIAL_ENV, help='environment variable holding the scoped credential')" .-> s8
    s6 -. "common.add_argument('--credential-file', default=None, help='file holding the scoped credential (never pass it on argv)')" .-> s9
    s6 -. "common.add_argument('--base-url', default=None, help='API base URL (default: $AUTORESEARCH_API_URL)')" .-> s10
    s6 -. "common.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT_S, help='bounded wait / request timeout in seconds')" .-> s11
    s6 -. "sub.add_parser (src/agent_cli.py:build_agent_parser)('agent', help='attached-agent research workflow (machine-readable)')" .-> s12
    b0["output print"]
    s1 -. "output print" .-> b0
    click s1 "../modules/cli.md"
    click s3 "../modules/cli.md"
    click s6 "../modules/agent_cli.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | `argv: Optional[list[str]]` | `_COMMANDS`, `sys` | - | `asyncio.run(...)`, `130` |
| `build_parser().parse_args` | - | - | - | - |
| `build_parser` | - | - | - | `parser` |
| `argparse.ArgumentParser (src/cli.py:build_parser)` | - | - | - | - |
| `parser.add_subparsers` | - | - | - | - |
| `build_agent_parser` | `sub: Any` | `DEFAULT_CREDENTIAL_ENV`, `DEFAULT_TIMEOUT_S` | - | - |
| `argparse.ArgumentParser (src/agent_cli.py:build_agent_parser)` | - | - | - | - |
| `common.add_argument` | - | - | - | - |
| `common.add_argument` | - | - | - | - |
| `common.add_argument` | - | - | - | - |
| `common.add_argument` | - | - | - | - |
| `sub.add_parser (src/agent_cli.py:build_agent_parser)` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | build_parser().parse_args | 535 | `build_parser().parse_args(argv)` |
| main | build_parser | 535 | `build_parser(data not statically known)` |
| build_parser | argparse.ArgumentParser (src/cli.py:build_parser) | 53 | `argparse.ArgumentParser(prog='autoresearch', description='autoresearch-agent operator CLI. Today: the Skill SDK (new-skill / promote-skill).')` |
| build_parser | parser.add_subparsers | 60 | `parser.add_subparsers(dest='command', required=True)` |
| build_parser | build_agent_parser | 64 | `build_agent_parser(sub)` |
| build_agent_parser | argparse.ArgumentParser (src/agent_cli.py:build_agent_parser) | 106 | `argparse.ArgumentParser(add_help=False)` |
| build_agent_parser | common.add_argument | 107 | `common.add_argument('--credential-env', default=DEFAULT_CREDENTIAL_ENV, help='environment variable holding the scoped credential')` |
| build_agent_parser | common.add_argument | 112 | `common.add_argument('--credential-file', default=None, help='file holding the scoped credential (never pass it on argv)')` |
| build_agent_parser | common.add_argument | 117 | `common.add_argument('--base-url', default=None, help='API base URL (default: $AUTORESEARCH_API_URL)')` |
| build_agent_parser | common.add_argument | 122 | `common.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT_S, help='bounded wait / request timeout in seconds')` |
| build_agent_parser | sub.add_parser (src/agent_cli.py:build_agent_parser) | 128 | `sub.add_parser('agent', help='attached-agent research workflow (machine-readable)')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| output | `print` | `main` | 540 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `main` | `build_parser().parse_args` | 535 |
| external_call | `build_parser` | `argparse.ArgumentParser` | 53 |
| unresolved_call | `build_parser` | `parser.add_subparsers` | 60 |
| external_call | `build_agent_parser` | `argparse.ArgumentParser` | 106 |
| unresolved_call | `build_agent_parser` | `common.add_argument` | 107 |
| unresolved_call | `build_agent_parser` | `common.add_argument` | 112 |
| unresolved_call | `build_agent_parser` | `common.add_argument` | 117 |
| unresolved_call | `build_agent_parser` | `common.add_argument` | 122 |
| unresolved_call | `build_agent_parser` | `sub.add_parser` | 128 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
