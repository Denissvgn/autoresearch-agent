# build_default_registry

**Entry point:** `harnesses.build_default_registry`
**Modules involved:** [builtin_harness](../modules/builtin_harness.md), [claude_code_harness](../modules/claude_code_harness.md), [codex_harness](../modules/codex_harness.md), [harness_adapter](../modules/harness_adapter.md), [harnesses](../modules/harnesses.md)

> The harnesses this service hosts — registering needs no name branch.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `harness_adapter.HarnessRegistry`
2. `harness_adapter.HarnessRegistry.register`
3. `builtin_harness.BuiltinHarnessAdapter`
4. `harness_adapter.HarnessRegistry.register`
5. `codex_harness.CodexHarnessAdapter`
6. `harness_adapter.HarnessRegistry.register`
7. `claude_code_harness.ClaudeCodeHarnessAdapter`

## Touches

- [builtin_harness](../modules/builtin_harness.md)
- [claude_code_harness](../modules/claude_code_harness.md)
- [codex_harness](../modules/codex_harness.md)
- [harness_adapter](../modules/harness_adapter.md)
- [harnesses](../modules/harnesses.md)

## Behavior

This workflow starts at `harnesses.build_default_registry`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
