# AgentOrchestrator_run

**Entry point:** `orchestrator.AgentOrchestrator.run`
**Modules involved:** [agent_tools](../modules/agent_tools.md), [command_policy](../modules/command_policy.md), [command_runner](../modules/command_runner.md), [llm_provider](../modules/llm_provider.md), [log_writer](../modules/log_writer.md), [orchestrator](../modules/orchestrator.md), [result_authority](../modules/result_authority.md), [skill_runtime](../modules/skill_runtime.md), [tool_access](../modules/tool_access.md), [trial_workspace](../modules/trial_workspace.md)

> Run the autonomous research loop for a single session.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `skill_runtime.materialize_skill_runtime`
2. `tool_access.build_tool_access_context`
3. `result_authority.protected_result_names`
4. `llm_provider.resolve_model_roles`
5. `llm_provider.resolve_effective_provider`
6. `llm_provider.build_provider`
7. `llm_provider.RequiredCapabilities.from_llm_config`
8. `llm_provider.MockProvider`
9. `llm_provider.Message`
10. `log_writer.AgentLogWriter`
11. `log_writer.AgentLogWriter.append`
12. `log_writer.AgentLogWriter.append`
13. `log_writer.AgentLogWriter.append`
14. `log_writer.AgentLogWriter.append`
15. `trial_workspace.is_trial_eligible_command`
16. `log_writer.AgentLogWriter.append`
17. `command_runner.redact_sensitive_text`
18. `log_writer.AgentLogWriter.append`
19. `trial_workspace.build_trial_context`
20. `command_policy.evaluate_command_policy`
21. `agent_tools.compute_bash_timeout`
22. `command_runner.redact_sensitive_text`
23. `command_runner.redact_sensitive_text`
24. `agent_tools._nonce_env_for_command`
25. `command_runner.redact_sensitive_text`
26. `agent_tools._nonce_env_for_command`
27. `command_runner.redact_sensitive_text`
28. `log_writer.AgentLogWriter.append`
29. `log_writer.AgentLogWriter.append`
30. `log_writer.AgentLogWriter.append`
31. `log_writer.AgentLogWriter.append`
32. `llm_provider.Message`
33. `llm_provider.Message`
34. `llm_provider.TextBlock`
35. `log_writer.AgentLogWriter.append`
36. `llm_provider.Message`
37. `llm_provider.Message`
38. `llm_provider.TextBlock`
39. `llm_provider.Message`
40. `llm_provider.TextBlock`
41. `llm_provider.TextBlock`
42. `llm_provider.TextBlock`
43. `llm_provider.TextBlock`
44. `llm_provider.TextBlock`
45. `llm_provider.Message`
46. `log_writer.AgentLogWriter.append`
47. `log_writer.AgentLogWriter.append`
48. `log_writer.AgentLogWriter.append`

## Touches

- [agent_tools](../modules/agent_tools.md)
- [command_policy](../modules/command_policy.md)
- [command_runner](../modules/command_runner.md)
- [llm_provider](../modules/llm_provider.md)
- [log_writer](../modules/log_writer.md)
- [orchestrator](../modules/orchestrator.md)
- [result_authority](../modules/result_authority.md)
- [skill_runtime](../modules/skill_runtime.md)
- [tool_access](../modules/tool_access.md)
- [trial_workspace](../modules/trial_workspace.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator.run`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
