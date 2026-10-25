# SessionManager__continue_session_unlocked

**Entry point:** `session_manager.SessionManager._continue_session_unlocked`
**Modules involved:** [orchestrator](../modules/orchestrator.md), [run_artifacts](../modules/run_artifacts.md), [run_restore](../modules/run_restore.md), [session_manager](../modules/session_manager.md)

> ML-62: Continue a timed-out session as a new chained session.

Creates a new session that inherits instrument/timeframe/model_type
and all fixed settings from the parent. Crucially, it does NOT
archive the workspace — the new session picks up where the parent
left off with the same train.yaml, best_train.yaml, and results.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `run_artifacts.ArtifactStore`
2. `run_artifacts.default_artifact_root`
3. `run_restore.raise_unless_ready`
4. `run_restore.assess_recovery`
5. `orchestrator.ResearchConfig`

## Touches

- [orchestrator](../modules/orchestrator.md)
- [run_artifacts](../modules/run_artifacts.md)
- [run_restore](../modules/run_restore.md)
- [session_manager](../modules/session_manager.md)

## Behavior

This workflow starts at `session_manager.SessionManager._continue_session_unlocked`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
