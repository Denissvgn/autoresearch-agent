# autoresearch

**Entry point:** `main` (`process`)
**Source:** [cli](../modules/cli.md)
**Modules touched:** [cli](../modules/cli.md)

**Related modules:** [config](../modules/config.md), [llm_provider](../modules/llm_provider.md), [plugin_runner](../modules/plugin_runner.md), [promotion_target](../modules/promotion_target.md), and 3 more

**Complete related modules:**

- [config](../modules/config.md)
- [llm_provider](../modules/llm_provider.md)
- [plugin_runner](../modules/plugin_runner.md)
- [promotion_target](../modules/promotion_target.md)
- [skill_generator](../modules/skill_generator.md)
- [skill_loader](../modules/skill_loader.md)
- [skill_manifest](../modules/skill_manifest.md)

## Call sequence

> Static overview in presentation order, not runtime execution order. Arrows retain captured callers; representative internal continuations and boundary examples precede repeated helper detail.

<!-- Auto-generated from static call edges. Dashed arrows are external or unresolved calls. Reviewed runtime conditions and side effects belong in Behavior. -->
```mermaid
sequenceDiagram
    participant p0 as main
    participant p1 as build_parser().parse_args
    participant p2 as build_parser
    participant p3 as asyncio.run
    participant p4 as handler
    participant p5 as print
    participant p6 as argparse.ArgumentParser
    participant p7 as parser.add_subparsers
    participant p8 as sub.add_parser
    participant p9 as new_skill.add_argument
    participant p10 as _add_promote_flags
    participant p11 as promote.add_argument
    participant p12 as p.add_argument
    p0-->>p1: build_parser().parse_args(argv)
    p0->>p2: build_parser
    p0-->>p3: asyncio.run(handler(...))
    p0-->>p4: handler(args)
    p0-->>p5: print('interrupted.', file=sys.stderr)
    p2-->>p6: argparse.ArgumentParser(prog='autoresearch', description='autoresearch-agent operator CLI. Today: the Skill SDK (new-skill / promote-skill).')
    p2-->>p7: parser.add_subparsers(dest='command', required=True)
    p2-->>p8: sub.add_parser(…)
    p2-->>p9: new_skill.add_argument('--goal', required=True, help='Natural-language description of the research domain.')
    p2-->>p9: new_skill.add_argument('--id', default=None, help='Override the generated kebab-case skill id.')
    p2-->>p9: new_skill.add_argument('--provider', default='anthropic', choices=[...], help='LLM provider for generation (default: anthropic).')
    p2-->>p9: new_skill.add_argument('--model', default=None, help='Model id (default: settings.anthropic_model required for openai).')
    p2-->>p9: new_skill.add_argument('--dry-run', action='store_true', help='Generate into a throwaway dir nothing under skills/ is written.')
    p2-->>p9: new_skill.add_argument(…)
    p2->>p10: _add_promote_flags
    p2-->>p8: sub.add_parser(…)
    p2-->>p11: promote.add_argument('--id', required=True, help='The draft skill id.')
    p2->>p10: _add_promote_flags
    p10-->>p12: p.add_argument('--promote', action='store_true', help=...)
    p10-->>p12: p.add_argument('--yes', action='store_true', help='Non-interactive: skip the confirmation prompt.')
    p10-->>p12: p.add_argument('--allow-critical', action='store_true', help='Promote even when the policy audit reported critical findings.')
    p10-->>p12: p.add_argument('--no-tag', action='store_true', help='Skip the best-effort skill/<id>/<version> git tag.')
    p10-->>p12: p.add_argument('--skills-root', default=None, type=Path, help='Override the skills root (default: the packaged skills/ dir).')
```

> Call sequence diagram shows 23 of 23 interactions; 0 omitted to keep the visualization within the 30-interaction and generated-diagram limits, with uncertain identities omitted rather than inferred.

> Captured boundary calls: external 3 of 3 (0 omitted); unresolved 17 of 17 (0 omitted). These counts cover the captured static trace.
> Detailed flow queries retain their own coverage and limits; omitted paths may execute at runtime.

## Data flow

<!-- Auto-generated static analysis. Treat values and boundaries as best-effort hints, not runtime proof. -->
```mermaid
flowchart LR
    s1["1. main"]
    s2["2. build_parser().parse_args"]
    s3["3. build_parser"]
    s4["4. argparse.ArgumentParser"]
    s5["5. parser.add_subparsers"]
    s6["6. sub.add_parser"]
    s7["7. new_skill.add_argument"]
    s8["8. new_skill.add_argument"]
    s9["9. new_skill.add_argument"]
    s10["10. new_skill.add_argument"]
    s11["11. new_skill.add_argument"]
    s12["12. new_skill.add_argument"]
    s1 -. "build_parser().parse_args(argv)" .-> s2
    s1 -->|"build_parser(data not statically known)"| s3
    s3 -. "argparse.ArgumentParser(prog='autoresearch', description='autoresearch-agent operator CLI. Today: the Skill SDK (new-skill / promote-skill).')" .-> s4
    s3 -. "parser.add_subparsers(dest='command', required=True)" .-> s5
    s3 -. "sub.add_parser(…)" .-> s6
    s3 -. "new_skill.add_argument('--goal', required=True, help='Natural-language description of the research domain.')" .-> s7
    s3 -. "new_skill.add_argument('--id', default=None, help='Override the generated kebab-case skill id.')" .-> s8
    s3 -. "new_skill.add_argument('--provider', default='anthropic', choices=[...], help='LLM provider for generation (default: anthropic).')" .-> s9
    s3 -. "new_skill.add_argument('--model', default=None, help='Model id (default: settings.anthropic_model; required for openai).')" .-> s10
    s3 -. "new_skill.add_argument('--dry-run', action='store_true', help='Generate into a throwaway dir; nothing under skills/ is written.')" .-> s11
    s3 -. "new_skill.add_argument(…)" .-> s12
    b0["output print"]
    s1 -. "output print" .-> b0
    click s1 "../modules/cli.md"
    click s3 "../modules/cli.md"
    classDef boundary stroke:#b45309,stroke-dasharray: 4 2
    class b0 boundary
```

### Step data

| Step | Inputs | Reads | Writes | Returns |
|---|---|---|---|---|
| `main` | `argv: Optional[list[str]]` | `_COMMANDS`, `sys` | - | `asyncio.run(...)`, `130` |
| `build_parser().parse_args` | - | - | - | - |
| `build_parser` | - | - | - | `parser` |
| `argparse.ArgumentParser` | - | - | - | - |
| `parser.add_subparsers` | - | - | - | - |
| `sub.add_parser` | - | - | - | - |
| `new_skill.add_argument` | - | - | - | - |
| `new_skill.add_argument` | - | - | - | - |
| `new_skill.add_argument` | - | - | - | - |
| `new_skill.add_argument` | - | - | - | - |
| `new_skill.add_argument` | - | - | - | - |
| `new_skill.add_argument` | - | - | - | - |

### Call data

| From | To | Line | Call |
|---|---|---:|---|
| main | build_parser().parse_args | 436 | `build_parser().parse_args(argv)` |
| main | build_parser | 436 | `build_parser(data not statically known)` |
| build_parser | argparse.ArgumentParser | 53 | `argparse.ArgumentParser(prog='autoresearch', description='autoresearch-agent operator CLI. Today: the Skill SDK (new-skill / promote-skill).')` |
| build_parser | parser.add_subparsers | 60 | `parser.add_subparsers(dest='command', required=True)` |
| build_parser | sub.add_parser | 62 | `sub.add_parser('new-skill', help='Draft a new skill package from a natural-language goal (LLM).', description='Generate a research_skill.v1 draft (manifest + bootstrap + eval + primer) into skills/_drafts/<id>/ from a goal description. The draft is validated, linted, and policy-audited before it is written; it is NOT selectable for production until promoted.')` |
| build_parser | new_skill.add_argument | 72 | `new_skill.add_argument('--goal', required=True, help='Natural-language description of the research domain.')` |
| build_parser | new_skill.add_argument | 76 | `new_skill.add_argument('--id', default=None, help='Override the generated kebab-case skill id.')` |
| build_parser | new_skill.add_argument | 80 | `new_skill.add_argument('--provider', default='anthropic', choices=[...], help='LLM provider for generation (default: anthropic).')` |
| build_parser | new_skill.add_argument | 84 | `new_skill.add_argument('--model', default=None, help='Model id (default: settings.anthropic_model; required for openai).')` |
| build_parser | new_skill.add_argument | 88 | `new_skill.add_argument('--dry-run', action='store_true', help='Generate into a throwaway dir; nothing under skills/ is written.')` |
| build_parser | new_skill.add_argument | 92 | `new_skill.add_argument('--dry-bootstrap', action='store_true', help='Execute the generated bootstrap.py under strict plugin caps in a temp workspace and print the rendered file tree (preview only).')` |

### Boundary effects

| Kind | Target | Step | Line |
|---|---|---|---:|
| output | `print` | `main` | 441 |

### Static analysis gaps

| Kind | Step | Target | Line |
|---|---|---|---:|
| unresolved_call | `main` | `build_parser().parse_args` | 436 |
| external_call | `build_parser` | `argparse.ArgumentParser` | 53 |
| unresolved_call | `build_parser` | `parser.add_subparsers` | 60 |
| unresolved_call | `build_parser` | `sub.add_parser` | 62 |
| unresolved_call | `build_parser` | `new_skill.add_argument` | 72 |
| unresolved_call | `build_parser` | `new_skill.add_argument` | 76 |
| unresolved_call | `build_parser` | `new_skill.add_argument` | 80 |
| unresolved_call | `build_parser` | `new_skill.add_argument` | 84 |
| unresolved_call | `build_parser` | `new_skill.add_argument` | 88 |
| unresolved_call | `build_parser` | `new_skill.add_argument` | 92 |
| step_limit | `main` | `first 12 steps` | 0 |

## Behavior

This flow starts at `main` and is classified as `process`. The generated call and data-flow sections are bounded static projections; runtime conditions and side effects require source-level confirmation.
