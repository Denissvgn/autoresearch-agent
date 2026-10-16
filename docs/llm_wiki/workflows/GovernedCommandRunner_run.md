# GovernedCommandRunner_run

**Entry point:** `command_runner.GovernedCommandRunner.run`
**Modules involved:** [command_policy](../modules/command_policy.md), [command_runner](../modules/command_runner.md), [config](../modules/config.md), [isolation](../modules/isolation.md), [process_limits](../modules/process_limits.md)

> Validate and execute one approved command without invoking a shell.

F06: the subprocess runs exactly what the resolved
:class:`~src.core.execution_request.ExecutionRequest` records —
``request.argv`` in ``request.cwd`` (the attempt output root) for
``request.timeout_s``. ``cwd`` sets the attempt output root when the
request is resolved here (trial-directory execution); when a
pre-resolved ``decision`` is supplied it already carries the root.
The policy still validates against the session workspace (a trial
dir lives inside it), so the override never widens what a command
may touch.

``isolation_policy`` wraps the spawn in the universal execution
boundary (:mod:`src.core.isolation`): filesystem/network policy is
then enforced at the OS and every child process inherits it. Without
it, the run is the retained trusted local-code path (pinned
executables) and is labeled ``trusted_local_code`` — never sandboxed.
Unenforceable policies or unavailable isolation refuse the execution.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `command_policy.evaluate_command_policy`
2. `isolation.wrap_command`
3. `config.get_settings`
4. `process_limits.ProcessResourceCaps`
5. `process_limits.rlimit_prefix`
6. `process_limits.TreeResourceGuard`
7. `process_limits.TreeResourceGuard.start`
8. `process_limits.signal_violation`
9. `process_limits.TreeResourceGuard.stop`

## Touches

- [command_policy](../modules/command_policy.md)
- [command_runner](../modules/command_runner.md)
- [config](../modules/config.md)
- [isolation](../modules/isolation.md)
- [process_limits](../modules/process_limits.md)

## Behavior

This workflow starts at `command_runner.GovernedCommandRunner.run`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
