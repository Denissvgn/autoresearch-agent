# AgentOrchestrator__finalize_tool_result

**Entry point:** `orchestrator.AgentOrchestrator._finalize_tool_result`
**Modules involved:** [experiment_parser](../modules/experiment_parser.md), [iteration_snapshot](../modules/iteration_snapshot.md), [llm_provider](../modules/llm_provider.md), [orchestrator](../modules/orchestrator.md), [output_digest](../modules/output_digest.md)

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `output_digest.digest_command_output`
2. `llm_provider.ToolResultBlock`
3. `experiment_parser.parse_prepare_output`
4. `iteration_snapshot.canonical_config_hash`
5. `llm_provider.ToolResultBlock`
6. `experiment_parser.parse_prepare_output`
7. `iteration_snapshot.canonical_config_hash`

## Touches

- [experiment_parser](../modules/experiment_parser.md)
- [iteration_snapshot](../modules/iteration_snapshot.md)
- [llm_provider](../modules/llm_provider.md)
- [orchestrator](../modules/orchestrator.md)
- [output_digest](../modules/output_digest.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator._finalize_tool_result`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
