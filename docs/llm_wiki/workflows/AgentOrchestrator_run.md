# AgentOrchestrator_run

**Entry point:** `orchestrator.AgentOrchestrator.run`
**Modules involved:** [agent_tools](../modules/agent_tools.md), [command_runner](../modules/command_runner.md), [experiment_parser](../modules/experiment_parser.md), [llm_provider](../modules/llm_provider.md), [log_writer](../modules/log_writer.md), [orchestrator](../modules/orchestrator.md), [skill_runtime](../modules/skill_runtime.md), [trial_workspace](../modules/trial_workspace.md)

> Run the autonomous research loop for a single session.

## Sequence

<!-- Auto-generated static call-chain projection. Reviewed runtime ordering, branching, and side effects belong in Behavior. -->
1. `skill_runtime.materialize_skill_runtime`
2. `llm_provider.build_provider`
3. `llm_provider.RequiredCapabilities.from_llm_config`
4. `llm_provider.MockProvider`
5. `llm_provider.Message`
6. `log_writer.AgentLogWriter`
7. `log_writer.AgentLogWriter.append`
8. `log_writer.AgentLogWriter.append`
9. `log_writer.AgentLogWriter.append`
10. `log_writer.AgentLogWriter.append`
11. `trial_workspace.is_trial_eligible_command`
12. `log_writer.AgentLogWriter.append`
13. `command_runner.redact_sensitive_text`
14. `log_writer.AgentLogWriter.append`
15. `trial_workspace.build_trial_context`
16. `agent_tools._config_snapshot_path_from_command`
17. `command_runner.redact_sensitive_text`
18. `command_runner.redact_sensitive_text`
19. `agent_tools._nonce_env_for_command`
20. `command_runner.redact_sensitive_text`
21. `agent_tools._nonce_env_for_command`
22. `command_runner.redact_sensitive_text`
23. `log_writer.AgentLogWriter.append`
24. `experiment_parser.parse_iteration_marker`
25. `log_writer.AgentLogWriter.append`
26. `log_writer.AgentLogWriter.append`
27. `llm_provider.Message`
28. `llm_provider.Message`
29. `llm_provider.TextBlock`
30. `log_writer.AgentLogWriter.append`
31. `llm_provider.Message`
32. `llm_provider.Message`
33. `llm_provider.TextBlock`
34. `llm_provider.Message`
35. `llm_provider.TextBlock`
36. `llm_provider.TextBlock`
37. `llm_provider.TextBlock`
38. `llm_provider.TextBlock`
39. `llm_provider.Message`
40. `log_writer.AgentLogWriter.append`
41. `log_writer.AgentLogWriter.append`
42. `log_writer.AgentLogWriter.append`

## Touches

- [agent_tools](../modules/agent_tools.md)
- [command_runner](../modules/command_runner.md)
- [experiment_parser](../modules/experiment_parser.md)
- [llm_provider](../modules/llm_provider.md)
- [log_writer](../modules/log_writer.md)
- [orchestrator](../modules/orchestrator.md)
- [skill_runtime](../modules/skill_runtime.md)
- [trial_workspace](../modules/trial_workspace.md)

## Behavior

This workflow starts at `orchestrator.AgentOrchestrator.run`. The generated sequence is a bounded static projection; runtime ordering, branching, and side effects require source-level confirmation.
