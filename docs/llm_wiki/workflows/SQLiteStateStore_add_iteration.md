# SQLiteStateStore_add_iteration

**Entry point:** `state_store.SQLiteStateStore.add_iteration`
**Modules involved:** [artifact_reference](../modules/artifact_reference.md), [objective_comparator](../modules/objective_comparator.md), [observability](../modules/observability.md), [state_store](../modules/state_store.md)

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `artifact_reference.normalize_optional_artifact_ref`
2. `objective_comparator.ObjectiveComparator`
3. `observability.log_research_event`

## Touches

- [artifact_reference](../modules/artifact_reference.md)
- [objective_comparator](../modules/objective_comparator.md)
- [observability](../modules/observability.md)
- [state_store](../modules/state_store.md)

## Behavior

This workflow starts at `state_store.SQLiteStateStore.add_iteration`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
