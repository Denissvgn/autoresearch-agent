# candidate_summary

**Entry point:** `research_state._candidate_summary`
**Modules involved:** [artifact_reference](../modules/artifact_reference.md), [consistency_validator](../modules/consistency_validator.md), [gate_status](../modules/gate_status.md), [research_state](../modules/research_state.md)

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `consistency_validator.parse_consistency_report`
2. `gate_status.training_gates_passed_from`
3. `artifact_reference.first_valid_artifact_ref`
4. `artifact_reference.first_valid_artifact_ref`

## Touches

- [artifact_reference](../modules/artifact_reference.md)
- [consistency_validator](../modules/consistency_validator.md)
- [gate_status](../modules/gate_status.md)
- [research_state](../modules/research_state.md)

## Behavior

This workflow starts at `research_state._candidate_summary`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
