# evaluate_command_policy

**Entry point:** `command_policy.evaluate_command_policy`
**Modules involved:** [command_policy](../modules/command_policy.md), [execution_request](../modules/execution_request.md), [result_authority](../modules/result_authority.md), [tool_access](../modules/tool_access.md)

> Resolve one command into an ExecutionRequest, then authorize it.

F06: resolution happens exactly once through
:func:`src.core.execution_request.resolve_execution_request` — the same
typed request feeds this authorization, the pre-run snapshot, the
governed subprocess, and result lookup, so policy and process always
observe the same candidate bytes and paths. ``workdir`` is the attempt
output root (a trial directory for parallel trials, the session
workspace otherwise); relative path-typed arguments resolve against it
and declared outputs land there.

``policy_extension`` is the per-skill ``CommandPolicyExtension``
(``skill.command_policy_extension()``). It is strictly **additive** —
entries union with the base allow-lists and can never remove or bypass
a base restriction. ``access`` is the shared file-operation
authorization context; when omitted, one is derived server-side from
the session workspace and the skill's declarations.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `result_authority.protected_result_names`
2. `tool_access.build_tool_access_context`
3. `execution_request.resolve_execution_request`

## Touches

- [command_policy](../modules/command_policy.md)
- [execution_request](../modules/execution_request.md)
- [result_authority](../modules/result_authority.md)
- [tool_access](../modules/tool_access.md)

## Behavior

This workflow starts at `command_policy.evaluate_command_policy`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
