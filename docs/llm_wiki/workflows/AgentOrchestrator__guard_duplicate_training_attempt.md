# AgentOrchestrator__guard_duplicate_training_attempt

**Entry point:** `orchestrator.AgentOrchestrator._guard_duplicate_training_attempt`
**Modules involved:** [agent_tools](../modules/agent_tools.md), [consistency_validator](../modules/consistency_validator.md), [iteration_snapshot](../modules/iteration_snapshot.md), [orchestrator](../modules/orchestrator.md)

> Reject an already-attempted config/seed/mode/split identity.

Exception: when the session is in ``baseline_capture`` phase and the
duplicate is a cross-session attempt (a prior session's baseline of
the same canonical config), inherit the prior baseline rather than
rejecting. The agent's contracted next_action for this phase is to
run the immutable promoted-config baseline, which is by definition
identical across sessions.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `iteration_snapshot.build_trial_identity`
2. `iteration_snapshot.trial_identity_hash`
3. `consistency_validator.check_adaptive_feature_sweep`
4. `agent_tools.ToolExecutionResult`
5. `agent_tools._normalize_command_for_plan`

## Touches

- [agent_tools](../modules/agent_tools.md)
- [consistency_validator](../modules/consistency_validator.md)
- [iteration_snapshot](../modules/iteration_snapshot.md)
- [orchestrator](../modules/orchestrator.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator._guard_duplicate_training_attempt`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
