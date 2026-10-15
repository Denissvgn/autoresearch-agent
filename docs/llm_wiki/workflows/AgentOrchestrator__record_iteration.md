# AgentOrchestrator__record_iteration

**Entry point:** `orchestrator.AgentOrchestrator._record_iteration`
**Modules involved:** [artifact_reference](../modules/artifact_reference.md), [consistency_validator](../modules/consistency_validator.md), [gate_status](../modules/gate_status.md), [iteration_context](../modules/iteration_context.md), [iteration_snapshot](../modules/iteration_snapshot.md), [orchestrator](../modules/orchestrator.md), [research_phase_plan](../modules/research_phase_plan.md), [result_artifact](../modules/result_artifact.md)

> Record an iteration and broadcast the event.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `artifact_reference.normalize_artifact_references_in_mapping`
2. `gate_status.normalize_training_gate_aliases`
3. `iteration_snapshot.build_trial_identity`
4. `iteration_snapshot.canonical_config_hash`
5. `iteration_snapshot.trial_identity_hash`
6. `iteration_snapshot.canonical_config_hash`
7. `result_artifact.enrich_marker_from_result_artifact`
8. `iteration_snapshot.build_iteration_attempt_snapshot`
9. `iteration_snapshot.write_iteration_attempt_snapshot`
10. `iteration_context.derive_exploration_markers`
11. `consistency_validator.build_consistency_report`
12. `consistency_validator.consistency_report_json`
13. `research_phase_plan._is_rejected_duplicate`

## Touches

- [artifact_reference](../modules/artifact_reference.md)
- [consistency_validator](../modules/consistency_validator.md)
- [gate_status](../modules/gate_status.md)
- [iteration_context](../modules/iteration_context.md)
- [iteration_snapshot](../modules/iteration_snapshot.md)
- [orchestrator](../modules/orchestrator.md)
- [research_phase_plan](../modules/research_phase_plan.md)
- [result_artifact](../modules/result_artifact.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator._record_iteration`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
