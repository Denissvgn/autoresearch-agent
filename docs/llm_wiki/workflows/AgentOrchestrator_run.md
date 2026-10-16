# AgentOrchestrator_run

**Entry point:** `orchestrator.AgentOrchestrator.run`
**Modules involved:** [agent_tools](../modules/agent_tools.md), [command_policy](../modules/command_policy.md), [command_runner](../modules/command_runner.md), [experiment_parser](../modules/experiment_parser.md), [llm_provider](../modules/llm_provider.md), [log_writer](../modules/log_writer.md), [orchestrator](../modules/orchestrator.md), [skill_runtime](../modules/skill_runtime.md), [tool_access](../modules/tool_access.md), [trial_workspace](../modules/trial_workspace.md)

> Run the autonomous research loop for a single session.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `skill_runtime.materialize_skill_runtime`
2. `tool_access.build_tool_access_context`
3. `llm_provider.build_provider`
4. `llm_provider.RequiredCapabilities.from_llm_config`
5. `llm_provider.MockProvider`
6. `llm_provider.Message`
7. `log_writer.AgentLogWriter`
8. `log_writer.AgentLogWriter.append`
9. `log_writer.AgentLogWriter.append`
10. `log_writer.AgentLogWriter.append`
11. `log_writer.AgentLogWriter.append`
12. `trial_workspace.is_trial_eligible_command`
13. `log_writer.AgentLogWriter.append`
14. `command_runner.redact_sensitive_text`
15. `log_writer.AgentLogWriter.append`
16. `trial_workspace.build_trial_context`
17. `command_policy.evaluate_command_policy`
18. `agent_tools.compute_bash_timeout`
19. `command_runner.redact_sensitive_text`
20. `command_runner.redact_sensitive_text`
21. `agent_tools._nonce_env_for_command`
22. `command_runner.redact_sensitive_text`
23. `agent_tools._nonce_env_for_command`
24. `command_runner.redact_sensitive_text`
25. `log_writer.AgentLogWriter.append`
26. `experiment_parser.parse_iteration_marker`
27. `log_writer.AgentLogWriter.append`
28. `log_writer.AgentLogWriter.append`
29. `llm_provider.Message`
30. `llm_provider.Message`
31. `llm_provider.TextBlock`
32. `log_writer.AgentLogWriter.append`
33. `llm_provider.Message`
34. `llm_provider.Message`
35. `llm_provider.TextBlock`
36. `llm_provider.Message`
37. `llm_provider.TextBlock`
38. `llm_provider.TextBlock`
39. `llm_provider.TextBlock`
40. `llm_provider.TextBlock`
41. `llm_provider.Message`
42. `log_writer.AgentLogWriter.append`
43. `log_writer.AgentLogWriter.append`
44. `log_writer.AgentLogWriter.append`

## Touches

- [agent_tools](../modules/agent_tools.md)
- [command_policy](../modules/command_policy.md)
- [command_runner](../modules/command_runner.md)
- [experiment_parser](../modules/experiment_parser.md)
- [llm_provider](../modules/llm_provider.md)
- [log_writer](../modules/log_writer.md)
- [orchestrator](../modules/orchestrator.md)
- [skill_runtime](../modules/skill_runtime.md)
- [tool_access](../modules/tool_access.md)
- [trial_workspace](../modules/trial_workspace.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator.run`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
