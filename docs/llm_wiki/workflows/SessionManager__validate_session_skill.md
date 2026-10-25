# SessionManager__validate_session_skill

**Entry point:** `session_manager.SessionManager._validate_session_skill`
**Modules involved:** [llm_provider](../modules/llm_provider.md), [session_manager](../modules/session_manager.md), [skill_runtime](../modules/skill_runtime.md), [support_matrix](../modules/support_matrix.md)

> Validate the session's skill runtime before anything is persisted.

ARC-012 P7-010 (blocker B2 / S1): the orchestrator materializes the
skill runtime on its first tick — outside its own exception handler —
so an unresolvable skill used to 201 at the API and then crash the
background task, leaving a zombie ``running`` row. Materializing here
(registry lookup + manifest load — cheap, side-effect-free) makes the
same ``SkillConfigError`` fire during ``start_session`` instead: no
row, no workspace, no spawned task for a session that cannot run.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `skill_runtime.materialize_skill_runtime`
2. `support_matrix.validate_manifest_support`
3. `skill_runtime.SkillConfigError`
4. `llm_provider.resolve_model_roles`
5. `llm_provider.build_provider`
6. `llm_provider.resolve_effective_provider`
7. `llm_provider.RequiredCapabilities.from_llm_config`

## Touches

- [llm_provider](../modules/llm_provider.md)
- [session_manager](../modules/session_manager.md)
- [skill_runtime](../modules/skill_runtime.md)
- [support_matrix](../modules/support_matrix.md)

## Behavior

This workflow starts at `session_manager.SessionManager._validate_session_skill`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
