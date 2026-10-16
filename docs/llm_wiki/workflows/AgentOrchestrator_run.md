# AgentOrchestrator_run

**Entry point:** `orchestrator.AgentOrchestrator.run`
**Modules involved:** [agent_tools](../modules/agent_tools.md), [command_policy](../modules/command_policy.md), [command_runner](../modules/command_runner.md), [experiment_parser](../modules/experiment_parser.md), [llm_provider](../modules/llm_provider.md), [log_writer](../modules/log_writer.md), [orchestrator](../modules/orchestrator.md), [result_authority](../modules/result_authority.md), [skill_runtime](../modules/skill_runtime.md), [tool_access](../modules/tool_access.md), [trial_workspace](../modules/trial_workspace.md)

> Run the autonomous research loop for a single session.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `skill_runtime.materialize_skill_runtime`
2. `tool_access.build_tool_access_context`
3. `result_authority.protected_result_names`
4. `llm_provider.build_provider`
5. `llm_provider.RequiredCapabilities.from_llm_config`
6. `llm_provider.MockProvider`
7. `llm_provider.Message`
8. `log_writer.AgentLogWriter`
9. `log_writer.AgentLogWriter.append`
10. `log_writer.AgentLogWriter.append`
11. `log_writer.AgentLogWriter.append`
12. `log_writer.AgentLogWriter.append`
13. `trial_workspace.is_trial_eligible_command`
14. `log_writer.AgentLogWriter.append`
15. `command_runner.redact_sensitive_text`
16. `log_writer.AgentLogWriter.append`
17. `trial_workspace.build_trial_context`
18. `command_policy.evaluate_command_policy`
19. `agent_tools.compute_bash_timeout`
20. `command_runner.redact_sensitive_text`
21. `command_runner.redact_sensitive_text`
22. `agent_tools._nonce_env_for_command`
23. `command_runner.redact_sensitive_text`
24. `agent_tools._nonce_env_for_command`
25. `command_runner.redact_sensitive_text`
26. `log_writer.AgentLogWriter.append`
27. `log_writer.AgentLogWriter.append`
28. `experiment_parser.parse_iteration_marker`
29. `log_writer.AgentLogWriter.append`
30. `log_writer.AgentLogWriter.append`
31. `llm_provider.Message`
32. `llm_provider.Message`
33. `llm_provider.TextBlock`
34. `log_writer.AgentLogWriter.append`
35. `llm_provider.Message`
36. `llm_provider.Message`
37. `llm_provider.TextBlock`
38. `llm_provider.Message`
39. `llm_provider.TextBlock`
40. `llm_provider.TextBlock`
41. `llm_provider.TextBlock`
42. `llm_provider.TextBlock`
43. `llm_provider.Message`
44. `log_writer.AgentLogWriter.append`
45. `log_writer.AgentLogWriter.append`
46. `log_writer.AgentLogWriter.append`

## Touches

- [agent_tools](../modules/agent_tools.md)
- [command_policy](../modules/command_policy.md)
- [command_runner](../modules/command_runner.md)
- [experiment_parser](../modules/experiment_parser.md)
- [llm_provider](../modules/llm_provider.md)
- [log_writer](../modules/log_writer.md)
- [orchestrator](../modules/orchestrator.md)
- [result_authority](../modules/result_authority.md)
- [skill_runtime](../modules/skill_runtime.md)
- [tool_access](../modules/tool_access.md)
- [trial_workspace](../modules/trial_workspace.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator.run`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
