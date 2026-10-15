# PostgresStateStore_add_iteration

**Entry point:** `postgres_state_store.PostgresStateStore.add_iteration`
**Modules involved:** [artifact_reference](../modules/artifact_reference.md), [observability](../modules/observability.md), [postgres_state_store](../modules/postgres_state_store.md), [state_store](../modules/state_store.md)

> Record an iteration. ``metrics_json``/``all_gates_passed`` are
normalized exactly as in SQLiteStateStore (see
:func:`_normalized_iteration_metrics_json`-equivalent logic lives in
the shared module — re-imported here for parity).

``lock_epoch`` (P6-004): when provided, the follow-on ``best_*`` update
is conditional on the epoch; a stale worker's iteration row is still
inserted (it's an immutable record of what the command produced) but
the session's ``best_iteration``/``best_metric`` do not advance.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `state_store._normalized_iteration_metrics_json`
2. `artifact_reference.normalize_optional_artifact_ref`
3. `state_store._json_object`
4. `state_store._json_object`
5. `observability.log_research_event`
6. `state_store._attempt_outcome`

## Touches

- [artifact_reference](../modules/artifact_reference.md)
- [observability](../modules/observability.md)
- [postgres_state_store](../modules/postgres_state_store.md)
- [state_store](../modules/state_store.md)

## Behavior

This workflow starts at `postgres_state_store.PostgresStateStore.add_iteration`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
