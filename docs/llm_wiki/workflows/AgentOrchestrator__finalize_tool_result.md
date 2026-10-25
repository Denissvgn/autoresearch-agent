# AgentOrchestrator__finalize_tool_result

**Entry point:** `orchestrator.AgentOrchestrator._finalize_tool_result`
**Modules involved:** [fs_safety](../modules/fs_safety.md), [iteration_snapshot](../modules/iteration_snapshot.md), [llm_provider](../modules/llm_provider.md), [orchestrator](../modules/orchestrator.md), [output_digest](../modules/output_digest.md)

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `fs_safety.safe_write_text`
2. `output_digest.digest_command_output`
3. `llm_provider.ToolResultBlock`
4. `iteration_snapshot.canonical_config_hash`
5. `llm_provider.ToolResultBlock`
6. `iteration_snapshot.canonical_config_hash`

## Touches

- [fs_safety](../modules/fs_safety.md)
- [iteration_snapshot](../modules/iteration_snapshot.md)
- [llm_provider](../modules/llm_provider.md)
- [orchestrator](../modules/orchestrator.md)
- [output_digest](../modules/output_digest.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator._finalize_tool_result`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
