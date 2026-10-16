# Dependencies

Internal module dependency graph and external package reconciliation.

## Module graph

<!-- Collapsed to top-level packages; the full module list is in the Fan-in / Fan-out table below. -->
```mermaid
flowchart TD
    n0["examples"]
    n1["scripts"]
    n2["skills"]
    n3["src"]
    n4["tests"]
    n5["ui"]
    n1 --> n3
    n4 --> n3
```

## Cycles

*No import cycles detected.*

> These groups reach each other only from inside functions or under `TYPE_CHECKING`, so nothing is imported while they load and their order is well defined. They are listed because they are cyclic on paper, not because they need fixing.

- [orchestrator](modules/orchestrator.md) ⇄ [skill_runtime](modules/skill_runtime.md)
- [preflight](modules/preflight.md) ⇄ [service_preflight](modules/service_preflight.md)

## Fan-in / Fan-out

| Module | Fan-in | Fan-out |
|--------|--------|---------|
| [results_store](modules/results_store.md) | 44 | 1 |
| [config](modules/config.md) | 39 | 0 |
| [orchestrator](modules/orchestrator.md) | 39 | 22 |
| [skill_registry](modules/skill_registry.md) | 24 | 2 |
| [client](modules/client.md) | 23 | 0 |
| [llm_provider](modules/llm_provider.md) | 18 | 1 |
| [research_phase_plan](modules/research_phase_plan.md) | 18 | 3 |
| [skill_manifest](modules/skill_manifest.md) | 15 | 0 |
| [config_promoter](modules/config_promoter.md) | 14 | 14 |
| [skill_runtime](modules/skill_runtime.md) | 14 | 8 |
| [experiment_parser](modules/experiment_parser.md) | 13 | 1 |
| [skill_loader](modules/skill_loader.md) | 13 | 2 |
| [state_store](modules/state_store.md) | 13 | 4 |
| [consistency_validator](modules/consistency_validator.md) | 12 | 2 |
| [tool_access](modules/tool_access.md) | 12 | 0 |
| [events](modules/events.md) | 12 | 1 |
| [artifact_reference](modules/artifact_reference.md) | 11 | 0 |
| [useResearch](modules/useResearch.md) | 11 | 2 |
| [command_runner](modules/command_runner.md) | 10 | 4 |
| [gate_status](modules/gate_status.md) | 10 | 0 |
| [iteration_snapshot](modules/iteration_snapshot.md) | 10 | 2 |
| [promotion_target](modules/promotion_target.md) | 10 | 1 |
| [session_manager](modules/session_manager.md) | 10 | 10 |
| [primitives](modules/primitives.md) | 10 | 0 |
| [promotion](modules/promotion.md) | 9 | 7 |
| [research](modules/research.md) | 9 | 10 |
| [fs_safety](modules/fs_safety.md) | 9 | 0 |
| [auth](modules/auth.md) | 8 | 1 |
| [results](modules/results.md) | 8 | 9 |
| [core_legacy_alias](modules/core_legacy_alias.md) | 8 | 1 |
| [state_machine](modules/state_machine.md) | 8 | 2 |
| [agent_tools](modules/agent_tools.md) | 7 | 6 |
| [command_policy](modules/command_policy.md) | 7 | 4 |
| [plugin_runner](modules/plugin_runner.md) | 7 | 3 |
| [postgres_state_store](modules/postgres_state_store.md) | 7 | 5 |
| [src_api_skills](modules/src_api_skills.md) | 6 | 8 |
| [observability](modules/observability.md) | 6 | 0 |
| [result_artifact](modules/result_artifact.md) | 6 | 2 |
| [service_preflight](modules/service_preflight.md) | 6 | 2 |
| [iteration_context](modules/iteration_context.md) | 5 | 2 |
| [output_parser](modules/output_parser.md) | 5 | 2 |
| [pagination](modules/pagination.md) | 5 | 0 |
| [useWebSocket](modules/useWebSocket.md) | 5 | 1 |
| [development_gate_bundle](modules/development_gate_bundle.md) | 4 | 2 |
| [execution_contracts](modules/execution_contracts.md) | 4 | 1 |
| [execution_request](modules/execution_request.md) | 4 | 0 |
| [promotion_approval](modules/promotion_approval.md) | 4 | 0 |
| [skill_paths](modules/skill_paths.md) | 4 | 0 |
| [trial_workspace](modules/trial_workspace.md) | 4 | 1 |
| [audit](modules/audit.md) | 3 | 1 |
| [subjects](modules/subjects.md) | 3 | 4 |
| [blocker_classifier](modules/blocker_classifier.md) | 3 | 0 |
| [isolation](modules/isolation.md) | 3 | 0 |
| [log_writer](modules/log_writer.md) | 3 | 1 |
| [preflight](modules/preflight.md) | 3 | 1 |
| [process_limits](modules/process_limits.md) | 3 | 0 |
| [skill_generator](modules/skill_generator.md) | 3 | 3 |
| [src_main](modules/src_main.md) | 3 | 16 |
| [compat_legacy_alias](modules/compat_legacy_alias.md) | 2 | 0 |
| [bootstrap_runner](modules/bootstrap_runner.md) | 2 | 4 |
| [http_headers](modules/http_headers.md) | 2 | 0 |
| [output_digest](modules/output_digest.md) | 2 | 0 |
| [research_manifest](modules/research_manifest.md) | 2 | 5 |
| [research_state](modules/research_state.md) | 2 | 6 |
| [result_authority](modules/result_authority.md) | 2 | 1 |
| [significance](modules/significance.md) | 2 | 0 |
| [skill_lifecycle](modules/skill_lifecycle.md) | 2 | 0 |
| [DynamicFormFields](modules/DynamicFormFields.md) | 2 | 3 |
| [IterationsTable](modules/IterationsTable.md) | 2 | 1 |
| [MetricsChart](modules/MetricsChart.md) | 2 | 1 |
| [Topbar](modules/Topbar.md) | 2 | 3 |
| [NewResearch](modules/NewResearch.md) | 2 | 4 |
| [registry](modules/registry.md) | 2 | 2 |
| [productionOps](modules/productionOps.md) | 2 | 0 |
| [cli](modules/cli.md) | 1 | 7 |
| [legacy_phase_tables](modules/legacy_phase_tables.md) | 1 | 0 |
| [ml_enrichment](modules/ml_enrichment.md) | 1 | 0 |
| [development_inference_validation](modules/development_inference_validation.md) | 1 | 0 |
| [development_signal_health](modules/development_signal_health.md) | 1 | 0 |
| [domain_classifier](modules/domain_classifier.md) | 1 | 2 |
| [insights_feedback](modules/insights_feedback.md) | 1 | 0 |
| [test_canonical_start_wiring](modules/test_canonical_start_wiring.md) | 1 | 5 |
| [test_webhook_promotion](modules/test_webhook_promotion.md) | 1 | 8 |
| [App](modules/App.md) | 1 | 13 |
| [AgentLog](modules/AgentLog.md) | 1 | 3 |
| [ClipboardCopy](modules/ClipboardCopy.md) | 1 | 0 |
| [ConfigDiff](modules/ConfigDiff.md) | 1 | 0 |
| [PromotionModal](modules/PromotionModal.md) | 1 | 4 |
| [SkillPicker](modules/SkillPicker.md) | 1 | 1 |
| [Dashboard](modules/Dashboard.md) | 1 | 3 |
| [History](modules/History.md) | 1 | 2 |
| [Leaderboard](modules/Leaderboard.md) | 1 | 3 |
| [Promote](modules/Promote.md) | 1 | 3 |
| [ResearchDetail](modules/ResearchDetail.md) | 1 | 7 |
| [Settings](modules/Settings.md) | 1 | 3 |
| [ui_src_pages_Skills](modules/ui_src_pages_Skills.md) | 1 | 2 |
| [types](modules/types.md) | 1 | 1 |
| [examples_prompt-registry_main](modules/examples_prompt-registry_main.md) | 0 | 0 |
| [check_doc_references](modules/check_doc_references.md) | 0 | 0 |
| [check_domain_coupling](modules/check_domain_coupling.md) | 0 | 0 |
| [check_execution_ledger](modules/check_execution_ledger.md) | 0 | 0 |
| [check_legacy_vocab_branching](modules/check_legacy_vocab_branching.md) | 0 | 0 |
| [migrate_sqlite_to_postgres](modules/migrate_sqlite_to_postgres.md) | 0 | 1 |
| [code-refactor_bootstrap](modules/code-refactor_bootstrap.md) | 0 | 0 |
| [code-refactor_eval_run](modules/code-refactor_eval_run.md) | 0 | 0 |
| [db-config-tuning_bootstrap](modules/db-config-tuning_bootstrap.md) | 0 | 0 |
| [db-config-tuning_eval_run](modules/db-config-tuning_eval_run.md) | 0 | 0 |
| [prompt-engineering_bootstrap](modules/prompt-engineering_bootstrap.md) | 0 | 0 |
| [dataset](modules/dataset.md) | 0 | 0 |
| [prompt-engineering_eval_run](modules/prompt-engineering_eval_run.md) | 0 | 0 |
| [tests_conftest](modules/tests_conftest.md) | 0 | 1 |
| [_engine](modules/_engine.md) | 0 | 7 |
| [capture](modules/capture.md) | 0 | 0 |
| [parity_conftest](modules/parity_conftest.md) | 0 | 0 |
| [test_parity](modules/test_parity.md) | 0 | 0 |
| [test_adaptive_noop_reason_fallback](modules/test_adaptive_noop_reason_fallback.md) | 0 | 0 |
| [test_anthropic_provider](modules/test_anthropic_provider.md) | 0 | 1 |
| [test_api_auth](modules/test_api_auth.md) | 0 | 5 |
| [test_async_tool_path](modules/test_async_tool_path.md) | 0 | 4 |
| [test_auto_phase_evidence](modules/test_auto_phase_evidence.md) | 0 | 2 |
| [test_auto_promote_terminate_waiver](modules/test_auto_promote_terminate_waiver.md) | 0 | 3 |
| [test_auto_promotion_readiness](modules/test_auto_promotion_readiness.md) | 0 | 3 |
| [test_baseline_capture_dedup_bypass](modules/test_baseline_capture_dedup_bypass.md) | 0 | 3 |
| [test_bootstrap_runner](modules/test_bootstrap_runner.md) | 0 | 3 |
| [test_cli](modules/test_cli.md) | 0 | 2 |
| [test_command_policy](modules/test_command_policy.md) | 0 | 4 |
| [test_config_promoter_atomic](modules/test_config_promoter_atomic.md) | 0 | 1 |
| [test_config_promoter_gate_bundle](modules/test_config_promoter_gate_bundle.md) | 0 | 3 |
| [test_contract_examples](modules/test_contract_examples.md) | 0 | 1 |
| [test_cross_session_digest_hint](modules/test_cross_session_digest_hint.md) | 0 | 2 |
| [test_cross_worker_control](modules/test_cross_worker_control.md) | 0 | 4 |
| [test_delete_session_hpo_cascade](modules/test_delete_session_hpo_cascade.md) | 0 | 1 |
| [test_deployment_inputs](modules/test_deployment_inputs.md) | 0 | 2 |
| [test_distributed_state_store](modules/test_distributed_state_store.md) | 0 | 4 |
| [test_domain_classifier](modules/test_domain_classifier.md) | 0 | 3 |
| [test_duplicate_phase_advancement_guard](modules/test_duplicate_phase_advancement_guard.md) | 0 | 1 |
| [test_duplicate_rejection_budget](modules/test_duplicate_rejection_budget.md) | 0 | 1 |
| [test_estimate_cost_api](modules/test_estimate_cost_api.md) | 0 | 3 |
| [test_event_broadcaster_concurrency](modules/test_event_broadcaster_concurrency.md) | 0 | 1 |
| [test_evidence_artifact_validation](modules/test_evidence_artifact_validation.md) | 0 | 2 |
| [test_execution_concurrency](modules/test_execution_concurrency.md) | 0 | 3 |
| [test_execution_contracts](modules/test_execution_contracts.md) | 0 | 1 |
| [test_execution_isolation](modules/test_execution_isolation.md) | 0 | 4 |
| [test_execution_ledger_validator](modules/test_execution_ledger_validator.md) | 0 | 0 |
| [test_execution_request](modules/test_execution_request.md) | 0 | 8 |
| [test_experiment_parser_calibration](modules/test_experiment_parser_calibration.md) | 0 | 1 |
| [test_experiment_parser_inference_parity](modules/test_experiment_parser_inference_parity.md) | 0 | 1 |
| [test_experiment_parser_promotion_scope](modules/test_experiment_parser_promotion_scope.md) | 0 | 1 |
| [test_experiment_parser_seed_trials](modules/test_experiment_parser_seed_trials.md) | 0 | 1 |
| [test_experiment_parser_volatility_phase5](modules/test_experiment_parser_volatility_phase5.md) | 0 | 1 |
| [test_experiment_parser_volatility_phase8](modules/test_experiment_parser_volatility_phase8.md) | 0 | 1 |
| [test_exploration_markers](modules/test_exploration_markers.md) | 0 | 1 |
| [test_fencing_tokens](modules/test_fencing_tokens.md) | 0 | 4 |
| [test_fs_safety](modules/test_fs_safety.md) | 0 | 5 |
| [test_gap1_duplicate_guard](modules/test_gap1_duplicate_guard.md) | 0 | 1 |
| [test_gate_bundle_production_economics](modules/test_gate_bundle_production_economics.md) | 0 | 1 |
| [test_gate_status_contract](modules/test_gate_status_contract.md) | 0 | 3 |
| [test_generalization_falsifiability](modules/test_generalization_falsifiability.md) | 0 | 6 |
| [test_hardening_phase1_to_5](modules/test_hardening_phase1_to_5.md) | 0 | 5 |
| [test_headroom_hint](modules/test_headroom_hint.md) | 0 | 1 |
| [test_insights_feedback](modules/test_insights_feedback.md) | 0 | 1 |
| [test_issue10b_declined_outcome](modules/test_issue10b_declined_outcome.md) | 0 | 1 |
| [test_issue6_adaptive_not_attempted](modules/test_issue6_adaptive_not_attempted.md) | 0 | 2 |
| [test_issue8_consistency_blocked_outcome](modules/test_issue8_consistency_blocked_outcome.md) | 0 | 1 |
| [test_iteration_context](modules/test_iteration_context.md) | 0 | 1 |
| [test_iteration_cost_attribution](modules/test_iteration_cost_attribution.md) | 0 | 2 |
| [test_iteration_snapshot](modules/test_iteration_snapshot.md) | 0 | 1 |
| [test_iteration_snapshot_canonical_payload](modules/test_iteration_snapshot_canonical_payload.md) | 0 | 1 |
| [test_leaderboard_api](modules/test_leaderboard_api.md) | 0 | 2 |
| [test_llm_provider](modules/test_llm_provider.md) | 0 | 1 |
| [test_llm_provider_openai](modules/test_llm_provider_openai.md) | 0 | 1 |
| [test_log_writer](modules/test_log_writer.md) | 0 | 1 |
| [test_main_operational_endpoints](modules/test_main_operational_endpoints.md) | 0 | 3 |
| [test_manifest_runtime_production_path](modules/test_manifest_runtime_production_path.md) | 0 | 8 |
| [test_marker_file_staleness](modules/test_marker_file_staleness.md) | 0 | 2 |
| [test_metrics_forgery](modules/test_metrics_forgery.md) | 0 | 1 |
| [test_metrics_forgery_c3](modules/test_metrics_forgery_c3.md) | 0 | 6 |
| [test_mlflow_run_id_contract](modules/test_mlflow_run_id_contract.md) | 0 | 7 |
| [test_mock_provider](modules/test_mock_provider.md) | 0 | 1 |
| [test_non_ml_session_e2e](modules/test_non_ml_session_e2e.md) | 0 | 7 |
| [test_observability](modules/test_observability.md) | 0 | 2 |
| [test_openapi_contract](modules/test_openapi_contract.md) | 0 | 1 |
| [test_orchestrator_command_audit](modules/test_orchestrator_command_audit.md) | 0 | 2 |
| [test_orchestrator_config_snapshot_inheritance](modules/test_orchestrator_config_snapshot_inheritance.md) | 0 | 2 |
| [test_orchestrator_evidence_replay](modules/test_orchestrator_evidence_replay.md) | 0 | 5 |
| [test_orchestrator_global_stagnation](modules/test_orchestrator_global_stagnation.md) | 0 | 2 |
| [test_orchestrator_loop_guard](modules/test_orchestrator_loop_guard.md) | 0 | 3 |
| [test_orchestrator_terminal_reason](modules/test_orchestrator_terminal_reason.md) | 0 | 2 |
| [test_orchestrator_terminate_deferral](modules/test_orchestrator_terminate_deferral.md) | 0 | 2 |
| [test_orchestrator_timeout](modules/test_orchestrator_timeout.md) | 0 | 6 |
| [test_output_digest](modules/test_output_digest.md) | 0 | 1 |
| [test_output_parser](modules/test_output_parser.md) | 0 | 1 |
| [test_packaging](modules/test_packaging.md) | 0 | 1 |
| [test_pagination](modules/test_pagination.md) | 0 | 5 |
| [test_parallel_trials](modules/test_parallel_trials.md) | 0 | 6 |
| [test_phase_evidence_dedup_inherit](modules/test_phase_evidence_dedup_inherit.md) | 0 | 4 |
| [test_phase_genuine_dwell](modules/test_phase_genuine_dwell.md) | 0 | 1 |
| [test_phase_state_broadcast](modules/test_phase_state_broadcast.md) | 0 | 2 |
| [test_pinned_evaluators](modules/test_pinned_evaluators.md) | 0 | 8 |
| [test_plugin_runner](modules/test_plugin_runner.md) | 0 | 2 |
| [test_postgres_sqlite_parity](modules/test_postgres_sqlite_parity.md) | 0 | 2 |
| [test_postgres_state_store](modules/test_postgres_state_store.md) | 0 | 1 |
| [test_preflight](modules/test_preflight.md) | 0 | 2 |
| [test_process_limits](modules/test_process_limits.md) | 0 | 4 |
| [test_promotion_approval](modules/test_promotion_approval.md) | 0 | 3 |
| [test_promotion_diagnostics](modules/test_promotion_diagnostics.md) | 0 | 1 |
| [test_promotion_target](modules/test_promotion_target.md) | 0 | 2 |
| [test_prompt_evaluator](modules/test_prompt_evaluator.md) | 0 | 5 |
| [test_prompt_promotion_policy](modules/test_prompt_promotion_policy.md) | 0 | 3 |
| [test_release_promotion_safety](modules/test_release_promotion_safety.md) | 0 | 8 |
| [test_replay_fixture](modules/test_replay_fixture.md) | 0 | 1 |
| [test_research_api_compat](modules/test_research_api_compat.md) | 0 | 2 |
| [test_research_api_integration](modules/test_research_api_integration.md) | 0 | 3 |
| [test_research_config](modules/test_research_config.md) | 0 | 2 |
| [test_research_manifest](modules/test_research_manifest.md) | 0 | 3 |
| [test_result_artifact_ingestion](modules/test_result_artifact_ingestion.md) | 0 | 6 |
| [test_result_authority](modules/test_result_authority.md) | 0 | 9 |
| [test_results_api](modules/test_results_api.md) | 0 | 1 |
| [test_results_store_manifest_snapshots](modules/test_results_store_manifest_snapshots.md) | 0 | 5 |
| [test_results_store_migrations](modules/test_results_store_migrations.md) | 0 | 3 |
| [test_rl_phase_tracing](modules/test_rl_phase_tracing.md) | 0 | 2 |
| [test_runtime_recovery](modules/test_runtime_recovery.md) | 0 | 3 |
| [test_service_preflight](modules/test_service_preflight.md) | 0 | 4 |
| [test_session_failure_modes](modules/test_session_failure_modes.md) | 0 | 9 |
| [test_session_status_routing](modules/test_session_status_routing.md) | 0 | 3 |
| [test_significance](modules/test_significance.md) | 0 | 3 |
| [test_skill_generator](modules/test_skill_generator.md) | 0 | 2 |
| [test_skill_lifecycle](modules/test_skill_lifecycle.md) | 0 | 2 |
| [test_skill_loader](modules/test_skill_loader.md) | 0 | 3 |
| [test_skill_paths](modules/test_skill_paths.md) | 0 | 1 |
| [test_skill_prompt_engineering_e2e](modules/test_skill_prompt_engineering_e2e.md) | 0 | 7 |
| [test_skills_api](modules/test_skills_api.md) | 0 | 3 |
| [test_skills_generate_api](modules/test_skills_generate_api.md) | 0 | 4 |
| [test_stagnation_phase_genuineness](modules/test_stagnation_phase_genuineness.md) | 0 | 2 |
| [test_state_machine](modules/test_state_machine.md) | 0 | 3 |
| [test_state_store](modules/test_state_store.md) | 0 | 2 |
| [test_terminal_phase_contract](modules/test_terminal_phase_contract.md) | 0 | 1 |
| [test_tool_access](modules/test_tool_access.md) | 0 | 5 |
| [test_trial_workspace](modules/test_trial_workspace.md) | 0 | 4 |
| [test_ws_event_enrichment](modules/test_ws_event_enrichment.md) | 0 | 1 |
| [postcss.config](modules/postcss.config.md) | 0 | 0 |
| [run-production-ops-tests](modules/run-production-ops-tests.md) | 0 | 0 |
| [ProductionOpsPanel](modules/ProductionOpsPanel.md) | 0 | 3 |
| [ResearchStatePanel](modules/ResearchStatePanel.md) | 0 | 1 |
| [StatusBadge](modules/StatusBadge.md) | 0 | 0 |
| [DynamicFormFields.test](modules/DynamicFormFields.test.md) | 0 | 3 |
| [IterationsTable.test](modules/IterationsTable.test.md) | 0 | 2 |
| [MetricsChart.test](modules/MetricsChart.test.md) | 0 | 2 |
| [PromotionModal.test](modules/PromotionModal.test.md) | 0 | 2 |
| [ui_src_main](modules/ui_src_main.md) | 0 | 1 |
| [NewResearch.test](modules/NewResearch.test.md) | 0 | 1 |
| [index](modules/index.md) | 0 | 0 |
| [tailwind.config](modules/tailwind.config.md) | 0 | 0 |
| [vite.config](modules/vite.config.md) | 0 | 0 |
| [vitest.config](modules/vitest.config.md) | 0 | 0 |
| [vitest.setup](modules/vitest.setup.md) | 0 | 0 |

## External dependencies

### python

- **Used:** `aiosqlite`, `anthropic`, `asyncpg`, `dataset`, `engine`, `eval`, `fastapi`, `httpx`, `numpy`, `openai`, `prometheus-client`, `psutil`, `pydantic`, `pydantic-settings`, `pytest`, `pyyaml`, `starlette`, `uvicorn`
- ⚠️ **Undeclared:** `aiosqlite`, `anthropic`, `dataset`, `engine`, `eval`, `fastapi`, `psutil`, `pytest`, `starlette`, `uvicorn`
- **Unused (declared, not imported):** `requests`

### typescript

- **Used:** `@tanstack/react-query`, `@testing-library/jest-dom`, `@testing-library/react`, `@testing-library/user-event`, `@vitejs/plugin-react`, `react`, `react-dom`, `react-router-dom`, `recharts`, `vite`, `vitest`

## Notes

This page reflects statically observed imports and declared dependencies. Dynamic or conditional imports and runtime-loaded integrations may not appear in the generated sections.
