# SessionManager__run_skill_bootstrap

**Entry point:** `session_manager.SessionManager._run_skill_bootstrap`
**Modules involved:** [bootstrap_runner](../modules/bootstrap_runner.md), [session_manager](../modules/session_manager.md), [skill_loader](../modules/skill_loader.md), [skill_runtime](../modules/skill_runtime.md)

> Render the session workspace with the skill's ``bootstrap.py``
(ARC-012 P7-011).

The ARC-011 §5.4 lifecycle step the BootstrapRunner was built for
(P5-005): the skill owns its workspace layout (prompt.yaml, eval
sets, target files), so a fresh session has something for its
evaluator to score. Skills without a ``bootstrap.py`` skip this step;
a bootstrap that runs but fails refuses the start (``SkillConfigError``
— nothing persisted, nothing spawned). Continuations do not
re-bootstrap: the inherited workspace IS the continuation state.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `skill_loader.load_layout`
2. `skill_runtime.SkillConfigError`
3. `bootstrap_runner.BootstrapRunner.run`
4. `bootstrap_runner.BootstrapRunner`
5. `skill_runtime.SkillConfigError`

## Touches

- [bootstrap_runner](../modules/bootstrap_runner.md)
- [session_manager](../modules/session_manager.md)
- [skill_loader](../modules/skill_loader.md)
- [skill_runtime](../modules/skill_runtime.md)

## Behavior

This workflow starts at `session_manager.SessionManager._run_skill_bootstrap`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
