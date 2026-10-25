# AgentOrchestrator___init__

**Entry point:** `orchestrator.AgentOrchestrator.__init__`
**Modules involved:** [command_runner](../modules/command_runner.md), [llm_provider](../modules/llm_provider.md), [orchestrator](../modules/orchestrator.md), [output_parser](../modules/output_parser.md), [state_machine](../modules/state_machine.md)

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `state_machine.SessionStateMachine`
2. `command_runner.CommandProcessRegistry`
3. `llm_provider.build_provider`
4. `llm_provider.resolve_effective_provider`
5. `output_parser.DelimitedKVParser`
6. `output_parser.JSONMarkerParser`

## Touches

- [command_runner](../modules/command_runner.md)
- [llm_provider](../modules/llm_provider.md)
- [orchestrator](../modules/orchestrator.md)
- [output_parser](../modules/output_parser.md)
- [state_machine](../modules/state_machine.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator.__init__`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
