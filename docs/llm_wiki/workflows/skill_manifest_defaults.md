# skill_manifest_defaults

**Entry point:** `research_manifest._skill_manifest_defaults`
**Modules involved:** [research_manifest](../modules/research_manifest.md), [run_spec](../modules/run_spec.md), [service_preflight](../modules/service_preflight.md), [skill_paths](../modules/skill_paths.md)

> Skill-driven sections (ARC-012 P7-003): everything is sourced from the
skill's SKILL.yaml — no invented ML artifacts. A manifest must never
claim artefacts the skill does not produce.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `skill_paths.session_workspace_path`
2. `run_spec.build_run_spec`
3. `service_preflight.build_not_run_preflight`

## Touches

- [research_manifest](../modules/research_manifest.md)
- [run_spec](../modules/run_spec.md)
- [service_preflight](../modules/service_preflight.md)
- [skill_paths](../modules/skill_paths.md)

## Behavior

This workflow starts at `research_manifest._skill_manifest_defaults`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
