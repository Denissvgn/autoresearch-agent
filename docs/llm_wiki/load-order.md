# Load order

Topological module load / startup order and import-time side effects.

## Load order

<!-- Dependency-first order: each module loads after the internal modules it imports. -->
1. [jsonl_driver](modules/jsonl_driver.md)
2. [examples_prompt-registry_main](modules/examples_prompt-registry_main.md)
3. [check_doc_references](modules/check_doc_references.md)
4. [check_domain_coupling](modules/check_domain_coupling.md)
5. [check_execution_ledger](modules/check_execution_ledger.md)
6. [check_legacy_vocab_branching](modules/check_legacy_vocab_branching.md)
7. [ci_qualification_gates](modules/ci_qualification_gates.md)
8. [run_compatibility_matrix](modules/run_compatibility_matrix.md)
9. [code-refactor_bootstrap](modules/code-refactor_bootstrap.md)
10. [code-refactor_eval_run](modules/code-refactor_eval_run.md)
11. [db-config-tuning_bootstrap](modules/db-config-tuning_bootstrap.md)
12. [db-config-tuning_eval_run](modules/db-config-tuning_eval_run.md)
13. [prompt-engineering_bootstrap](modules/prompt-engineering_bootstrap.md)
14. [dataset](modules/dataset.md)
15. [prompt-engineering_eval_run](modules/prompt-engineering_eval_run.md)
16. [agent_client](modules/agent_client.md)
17. [agent_cli](modules/agent_cli.md)
18. [cli](modules/cli.md)
19. [compat_legacy_alias](modules/compat_legacy_alias.md)
20. [legacy_phase_tables](modules/legacy_phase_tables.md)
21. [ml_enrichment](modules/ml_enrichment.md)
22. [config](modules/config.md)
23. [auth](modules/auth.md)
24. [audit](modules/audit.md)
25. [artifact_reference](modules/artifact_reference.md)
26. [blocker_classifier](modules/blocker_classifier.md)
27. [code_evaluator](modules/code_evaluator.md)
28. [comparison_context](modules/comparison_context.md)
29. [development_inference_validation](modules/development_inference_validation.md)
30. [development_signal_health](modules/development_signal_health.md)
31. [execution_contracts](modules/execution_contracts.md)
32. [execution_request](modules/execution_request.md)
33. [fs_safety](modules/fs_safety.md)
34. [gate_status](modules/gate_status.md)
35. [consistency_validator](modules/consistency_validator.md)
36. [development_gate_bundle](modules/development_gate_bundle.md)
37. [goal_semantics](modules/goal_semantics.md)
38. [harness_contract](modules/harness_contract.md)
39. [claude_code_harness](modules/claude_code_harness.md)
40. [codex_harness](modules/codex_harness.md)
41. [driver_host](modules/driver_host.md)
42. [harness_adapter](modules/harness_adapter.md)
43. [harnesses](modules/harnesses.md)
44. [harness_conformance](modules/harness_conformance.md)
45. [harness_qualification](modules/harness_qualification.md)
46. [http_headers](modules/http_headers.md)
47. [insights_feedback](modules/insights_feedback.md)
48. [instruction_assembly](modules/instruction_assembly.md)
49. [isolation](modules/isolation.md)
50. [iteration_snapshot](modules/iteration_snapshot.md)
51. [latency_benchmark](modules/latency_benchmark.md)
52. [core_legacy_alias](modules/core_legacy_alias.md)
53. [llm_provider](modules/llm_provider.md)
54. [multiobjective](modules/multiobjective.md)
55. [objective_comparator](modules/objective_comparator.md)
56. [iteration_context](modules/iteration_context.md)
57. [observability](modules/observability.md)
58. [output_digest](modules/output_digest.md)
59. [output_parser](modules/output_parser.md)
60. [experiment_parser](modules/experiment_parser.md)
61. [pagination](modules/pagination.md)
62. [process_limits](modules/process_limits.md)
63. [promotion_approval](modules/promotion_approval.md)
64. [promotion](modules/promotion.md)
65. [promotion_policy](modules/promotion_policy.md)
66. [promotion_target](modules/promotion_target.md)
67. [prompt_scorer](modules/prompt_scorer.md)
68. [research_phase_plan](modules/research_phase_plan.md)
69. [research_resume](modules/research_resume.md)
70. [research_state](modules/research_state.md)
71. [result_artifact](modules/result_artifact.md)
72. [result_authority](modules/result_authority.md)
73. [run_artifacts](modules/run_artifacts.md)
74. [run_restore](modules/run_restore.md)
75. [run_spec](modules/run_spec.md)
76. [scoped_credentials](modules/scoped_credentials.md)
77. [agent](modules/agent.md)
78. [service_preflight](modules/service_preflight.md)
79. [preflight](modules/preflight.md)
80. [significance](modules/significance.md)
81. [research_kernel](modules/research_kernel.md)
82. [builtin_harness](modules/builtin_harness.md)
83. [skill_host_services](modules/skill_host_services.md)
84. [skill_lifecycle](modules/skill_lifecycle.md)
85. [skill_manifest](modules/skill_manifest.md)
86. [plugin_runner](modules/plugin_runner.md)
87. [phase_resolver](modules/phase_resolver.md)
88. [skill_loader](modules/skill_loader.md)
89. [bootstrap_runner](modules/bootstrap_runner.md)
90. [skill_params](modules/skill_params.md)
91. [skill_paths](modules/skill_paths.md)
92. [research_manifest](modules/research_manifest.md)
93. [skill_registry](modules/skill_registry.md)
94. [src_api_skills](modules/src_api_skills.md)
95. [subjects](modules/subjects.md)
96. [domain_classifier](modules/domain_classifier.md)
97. [skill_generator](modules/skill_generator.md)
98. [skill_runtime](modules/skill_runtime.md)
99. [research](modules/research.md)
100. [state_store](modules/state_store.md)
101. [config_promoter](modules/config_promoter.md)
102. [postgres_state_store](modules/postgres_state_store.md)
103. [migrate_sqlite_to_postgres](modules/migrate_sqlite_to_postgres.md)
104. [results_store](modules/results_store.md)
105. [support_matrix](modules/support_matrix.md)
106. [tool_access](modules/tool_access.md)
107. [command_policy](modules/command_policy.md)
108. [command_runner](modules/command_runner.md)
109. [agent_tools](modules/agent_tools.md)
110. [trial_workspace](modules/trial_workspace.md)
111. [usage_ledger](modules/usage_ledger.md)
112. [events](modules/events.md)
113. [log_writer](modules/log_writer.md)
114. [results](modules/results.md)
115. [state_machine](modules/state_machine.md)
116. [orchestrator](modules/orchestrator.md)
117. [session_manager](modules/session_manager.md)
118. [src_main](modules/src_main.md)
119. [tests_conftest](modules/tests_conftest.md)
120. [conformance_bootstrap](modules/conformance_bootstrap.md)
121. [conformance_eval_run](modules/conformance_eval_run.md)
122. [pricing](modules/pricing.md)
123. [totals](modules/totals.md)
124. [test_behavior](modules/test_behavior.md)
125. [phases](modules/phases.md)
126. [phases_bad_schema](modules/phases_bad_schema.md)
127. [phases_egress](modules/phases_egress.md)
128. [phases_env_spy](modules/phases_env_spy.md)
129. [phases_tamper](modules/phases_tamper.md)
130. [phases_timeout](modules/phases_timeout.md)
131. [_engine](modules/_engine.md)
132. [capture](modules/capture.md)
133. [parity_conftest](modules/parity_conftest.md)
134. [test_parity](modules/test_parity.md)
135. [test_adaptive_noop_reason_fallback](modules/test_adaptive_noop_reason_fallback.md)
136. [test_agent_api](modules/test_agent_api.md)
137. [test_agent_cli](modules/test_agent_cli.md)
138. [test_anthropic_provider](modules/test_anthropic_provider.md)
139. [test_api_auth](modules/test_api_auth.md)
140. [test_async_tool_path](modules/test_async_tool_path.md)
141. [test_auto_phase_evidence](modules/test_auto_phase_evidence.md)
142. [test_auto_promote_terminate_waiver](modules/test_auto_promote_terminate_waiver.md)
143. [test_auto_promotion_readiness](modules/test_auto_promotion_readiness.md)
144. [test_baseline_capture_dedup_bypass](modules/test_baseline_capture_dedup_bypass.md)
145. [test_bootstrap_runner](modules/test_bootstrap_runner.md)
146. [test_builtin_harness](modules/test_builtin_harness.md)
147. [test_canonical_start_wiring](modules/test_canonical_start_wiring.md)
148. [test_ci_qualification_gates](modules/test_ci_qualification_gates.md)
149. [test_claude_code_harness](modules/test_claude_code_harness.md)
150. [test_cli](modules/test_cli.md)
151. [test_code_refactor_domain](modules/test_code_refactor_domain.md)
152. [test_codex_harness](modules/test_codex_harness.md)
153. [test_command_policy](modules/test_command_policy.md)
154. [test_compatibility_matrix](modules/test_compatibility_matrix.md)
155. [test_config_promoter_atomic](modules/test_config_promoter_atomic.md)
156. [test_config_promoter_gate_bundle](modules/test_config_promoter_gate_bundle.md)
157. [test_contract_examples](modules/test_contract_examples.md)
158. [test_cross_session_digest_hint](modules/test_cross_session_digest_hint.md)
159. [test_cross_worker_control](modules/test_cross_worker_control.md)
160. [test_delete_session_hpo_cascade](modules/test_delete_session_hpo_cascade.md)
161. [test_deployment_inputs](modules/test_deployment_inputs.md)
162. [test_distributed_state_store](modules/test_distributed_state_store.md)
163. [test_domain_classifier](modules/test_domain_classifier.md)
164. [test_domain_semantics_extension](modules/test_domain_semantics_extension.md)
165. [test_driver_host](modules/test_driver_host.md)
166. [test_duplicate_phase_advancement_guard](modules/test_duplicate_phase_advancement_guard.md)
167. [test_duplicate_rejection_budget](modules/test_duplicate_rejection_budget.md)
168. [test_durable_operation_qualification](modules/test_durable_operation_qualification.md)
169. [test_estimate_cost_api](modules/test_estimate_cost_api.md)
170. [test_event_broadcaster_concurrency](modules/test_event_broadcaster_concurrency.md)
171. [test_event_outbox](modules/test_event_outbox.md)
172. [test_evidence_artifact_validation](modules/test_evidence_artifact_validation.md)
173. [test_execution_concurrency](modules/test_execution_concurrency.md)
174. [test_execution_contracts](modules/test_execution_contracts.md)
175. [test_execution_isolation](modules/test_execution_isolation.md)
176. [test_execution_ledger_validator](modules/test_execution_ledger_validator.md)
177. [test_execution_request](modules/test_execution_request.md)
178. [test_experiment_parser_calibration](modules/test_experiment_parser_calibration.md)
179. [test_experiment_parser_inference_parity](modules/test_experiment_parser_inference_parity.md)
180. [test_experiment_parser_promotion_scope](modules/test_experiment_parser_promotion_scope.md)
181. [test_experiment_parser_seed_trials](modules/test_experiment_parser_seed_trials.md)
182. [test_experiment_parser_volatility_phase5](modules/test_experiment_parser_volatility_phase5.md)
183. [test_experiment_parser_volatility_phase8](modules/test_experiment_parser_volatility_phase8.md)
184. [test_exploration_markers](modules/test_exploration_markers.md)
185. [test_fencing_tokens](modules/test_fencing_tokens.md)
186. [test_fs_safety](modules/test_fs_safety.md)
187. [test_gap1_duplicate_guard](modules/test_gap1_duplicate_guard.md)
188. [test_gate_bundle_production_economics](modules/test_gate_bundle_production_economics.md)
189. [test_gate_status_contract](modules/test_gate_status_contract.md)
190. [test_generalization_falsifiability](modules/test_generalization_falsifiability.md)
191. [test_goal_phase_semantics](modules/test_goal_phase_semantics.md)
192. [test_hardening_phase1_to_5](modules/test_hardening_phase1_to_5.md)
193. [test_harness_contracts_g4](modules/test_harness_contracts_g4.md)
194. [test_harness_sdk](modules/test_harness_sdk.md)
195. [test_harnesses_api](modules/test_harnesses_api.md)
196. [test_headroom_hint](modules/test_headroom_hint.md)
197. [test_insights_feedback](modules/test_insights_feedback.md)
198. [test_issue10b_declined_outcome](modules/test_issue10b_declined_outcome.md)
199. [test_issue6_adaptive_not_attempted](modules/test_issue6_adaptive_not_attempted.md)
200. [test_issue8_consistency_blocked_outcome](modules/test_issue8_consistency_blocked_outcome.md)
201. [test_iteration_context](modules/test_iteration_context.md)
202. [test_iteration_cost_attribution](modules/test_iteration_cost_attribution.md)
203. [test_iteration_snapshot](modules/test_iteration_snapshot.md)
204. [test_iteration_snapshot_canonical_payload](modules/test_iteration_snapshot_canonical_payload.md)
205. [test_latency_benchmark](modules/test_latency_benchmark.md)
206. [test_leaderboard_api](modules/test_leaderboard_api.md)
207. [test_leaderboard_comparability](modules/test_leaderboard_comparability.md)
208. [test_llm_provider](modules/test_llm_provider.md)
209. [test_llm_provider_openai](modules/test_llm_provider_openai.md)
210. [test_log_writer](modules/test_log_writer.md)
211. [test_main_operational_endpoints](modules/test_main_operational_endpoints.md)
212. [test_manifest_runtime_production_path](modules/test_manifest_runtime_production_path.md)
213. [test_marker_file_staleness](modules/test_marker_file_staleness.md)
214. [test_metrics_forgery](modules/test_metrics_forgery.md)
215. [test_metrics_forgery_c3](modules/test_metrics_forgery_c3.md)
216. [test_migration_restore_qualification](modules/test_migration_restore_qualification.md)
217. [test_mlflow_run_id_contract](modules/test_mlflow_run_id_contract.md)
218. [test_mock_provider](modules/test_mock_provider.md)
219. [test_non_ml_session_e2e](modules/test_non_ml_session_e2e.md)
220. [test_domain_conformance](modules/test_domain_conformance.md)
221. [test_objective_comparator](modules/test_objective_comparator.md)
222. [test_observability](modules/test_observability.md)
223. [test_observation_identity](modules/test_observation_identity.md)
224. [test_openapi_contract](modules/test_openapi_contract.md)
225. [test_orchestrator_command_audit](modules/test_orchestrator_command_audit.md)
226. [test_orchestrator_config_snapshot_inheritance](modules/test_orchestrator_config_snapshot_inheritance.md)
227. [test_orchestrator_evidence_replay](modules/test_orchestrator_evidence_replay.md)
228. [test_orchestrator_global_stagnation](modules/test_orchestrator_global_stagnation.md)
229. [test_orchestrator_loop_guard](modules/test_orchestrator_loop_guard.md)
230. [test_orchestrator_terminal_reason](modules/test_orchestrator_terminal_reason.md)
231. [test_orchestrator_terminate_deferral](modules/test_orchestrator_terminate_deferral.md)
232. [test_orchestrator_timeout](modules/test_orchestrator_timeout.md)
233. [test_output_digest](modules/test_output_digest.md)
234. [test_output_parser](modules/test_output_parser.md)
235. [test_packaging](modules/test_packaging.md)
236. [test_pagination](modules/test_pagination.md)
237. [test_parallel_trials](modules/test_parallel_trials.md)
238. [test_parameter_bindings](modules/test_parameter_bindings.md)
239. [test_phase_evidence_dedup_inherit](modules/test_phase_evidence_dedup_inherit.md)
240. [test_phase_genuine_dwell](modules/test_phase_genuine_dwell.md)
241. [test_phase_state_broadcast](modules/test_phase_state_broadcast.md)
242. [test_pinned_evaluators](modules/test_pinned_evaluators.md)
243. [test_plugin_runner](modules/test_plugin_runner.md)
244. [test_postgres_sqlite_parity](modules/test_postgres_sqlite_parity.md)
245. [test_postgres_state_store](modules/test_postgres_state_store.md)
246. [test_preflight](modules/test_preflight.md)
247. [test_preflight_support_matrix](modules/test_preflight_support_matrix.md)
248. [test_process_limits](modules/test_process_limits.md)
249. [test_promotion_approval](modules/test_promotion_approval.md)
250. [test_promotion_diagnostics](modules/test_promotion_diagnostics.md)
251. [test_promotion_policy](modules/test_promotion_policy.md)
252. [test_promotion_target](modules/test_promotion_target.md)
253. [test_prompt_evaluation_domain](modules/test_prompt_evaluation_domain.md)
254. [test_prompt_evaluator](modules/test_prompt_evaluator.md)
255. [test_prompt_promotion_policy](modules/test_prompt_promotion_policy.md)
256. [test_provider_roles](modules/test_provider_roles.md)
257. [test_replay_fixture](modules/test_replay_fixture.md)
258. [test_research_api_compat](modules/test_research_api_compat.md)
259. [test_research_api_integration](modules/test_research_api_integration.md)
260. [test_research_config](modules/test_research_config.md)
261. [test_research_kernel](modules/test_research_kernel.md)
262. [test_research_manifest](modules/test_research_manifest.md)
263. [test_research_resume](modules/test_research_resume.md)
264. [test_result_artifact_ingestion](modules/test_result_artifact_ingestion.md)
265. [test_result_authority](modules/test_result_authority.md)
266. [test_result_semantics](modules/test_result_semantics.md)
267. [test_results_api](modules/test_results_api.md)
268. [test_results_store_manifest_snapshots](modules/test_results_store_manifest_snapshots.md)
269. [test_results_store_migrations](modules/test_results_store_migrations.md)
270. [test_rl_phase_tracing](modules/test_rl_phase_tracing.md)
271. [test_run_artifacts](modules/test_run_artifacts.md)
272. [test_run_restore](modules/test_run_restore.md)
273. [test_run_spec_persistence](modules/test_run_spec_persistence.md)
274. [test_run_workspace_isolation](modules/test_run_workspace_isolation.md)
275. [test_runtime_recovery](modules/test_runtime_recovery.md)
276. [test_service_preflight](modules/test_service_preflight.md)
277. [test_session_failure_modes](modules/test_session_failure_modes.md)
278. [test_session_status_routing](modules/test_session_status_routing.md)
279. [test_significance](modules/test_significance.md)
280. [test_skill_generator](modules/test_skill_generator.md)
281. [test_skill_lifecycle](modules/test_skill_lifecycle.md)
282. [test_skill_loader](modules/test_skill_loader.md)
283. [test_skill_params_validation](modules/test_skill_params_validation.md)
284. [test_skill_paths](modules/test_skill_paths.md)
285. [test_skill_prompt_engineering_e2e](modules/test_skill_prompt_engineering_e2e.md)
286. [test_skills_api](modules/test_skills_api.md)
287. [test_skills_generate_api](modules/test_skills_generate_api.md)
288. [test_stagnation_phase_genuineness](modules/test_stagnation_phase_genuineness.md)
289. [test_state_machine](modules/test_state_machine.md)
290. [test_state_store](modules/test_state_store.md)
291. [test_store_persistence_contracts](modules/test_store_persistence_contracts.md)
292. [test_store_transaction_serialization](modules/test_store_transaction_serialization.md)
293. [test_terminal_phase_contract](modules/test_terminal_phase_contract.md)
294. [test_tool_access](modules/test_tool_access.md)
295. [test_trial_workspace](modules/test_trial_workspace.md)
296. [test_trust_boundary_qualification](modules/test_trust_boundary_qualification.md)
297. [test_usage_ledger](modules/test_usage_ledger.md)
298. [test_webhook_promotion](modules/test_webhook_promotion.md)
299. [test_release_promotion_safety](modules/test_release_promotion_safety.md)
300. [test_work_reservations](modules/test_work_reservations.md)
301. [test_ws_event_enrichment](modules/test_ws_event_enrichment.md)
302. [postcss.config](modules/postcss.config.md)
303. [run-production-ops-tests](modules/run-production-ops-tests.md)
304. [client](modules/client.md)
305. [ClipboardCopy](modules/ClipboardCopy.md)
306. [ConfigDiff](modules/ConfigDiff.md)
307. [HarnessContextPanel](modules/HarnessContextPanel.md)
308. [HarnessPicker](modules/HarnessPicker.md)
309. [IterationsTable](modules/IterationsTable.md)
310. [MetricsChart](modules/MetricsChart.md)
311. [ResearchStatePanel](modules/ResearchStatePanel.md)
312. [SkillPicker](modules/SkillPicker.md)
313. [StatusBadge](modules/StatusBadge.md)
314. [HarnessUI.test](modules/HarnessUI.test.md)
315. [IterationsTable.test](modules/IterationsTable.test.md)
316. [MetricsChart.test](modules/MetricsChart.test.md)
317. [primitives](modules/primitives.md)
318. [useWebSocket](modules/useWebSocket.md)
319. [useResearch](modules/useResearch.md)
320. [AgentLog](modules/AgentLog.md)
321. [Topbar](modules/Topbar.md)
322. [Dashboard](modules/Dashboard.md)
323. [History](modules/History.md)
324. [Leaderboard](modules/Leaderboard.md)
325. [Promote](modules/Promote.md)
326. [ResearchDetail](modules/ResearchDetail.md)
327. [Settings](modules/Settings.md)
328. [ui_src_pages_Skills](modules/ui_src_pages_Skills.md)
329. [Leaderboard.test](modules/Leaderboard.test.md)
330. [index](modules/index.md)
331. [types](modules/types.md)
332. [registry](modules/registry.md)
333. [DynamicFormFields](modules/DynamicFormFields.md)
334. [DynamicFormFields.test](modules/DynamicFormFields.test.md)
335. [NewResearch](modules/NewResearch.md)
336. [App](modules/App.md)
337. [ui_src_main](modules/ui_src_main.md)
338. [NewResearch.test](modules/NewResearch.test.md)
339. [productionOps](modules/productionOps.md)
340. [ProductionOpsPanel](modules/ProductionOpsPanel.md)
341. [PromotionModal](modules/PromotionModal.md)
342. [PromotionModal.test](modules/PromotionModal.test.md)
343. [tailwind.config](modules/tailwind.config.md)
344. [vite.config](modules/vite.config.md)
345. [vitest.config](modules/vitest.config.md)
346. [vitest.setup](modules/vitest.setup.md)

## Module-level side effects

| Module | Import-time calls |
|--------|-------------------|
| [examples_prompt-registry_main](modules/examples_prompt-registry_main.md) | `app = FastAPI` |
| [check_doc_references](modules/check_doc_references.md) | `DOC_PATH_RE = re.compile` |
| [check_domain_coupling](modules/check_domain_coupling.md) | `PATTERN = re.compile` |
| [check_execution_ledger](modules/check_execution_ledger.md) | `CARD_ID_RE = re.compile`, `CHECK_ID_RE = re.compile`, `STATES = frozenset`, `RESULT_STATES = frozenset` |
| [migrate_sqlite_to_postgres](modules/migrate_sqlite_to_postgres.md) | `sys.path.insert`, `logger = logging.getLogger` |
| [run_compatibility_matrix](modules/run_compatibility_matrix.md) | `sys.path.insert`, `sys.path.insert` |
| [agent](modules/agent.md) | `_router_auth = HTTPBearer`, `router = APIRouter` |
| [auth](modules/auth.md) | `logger = logging.getLogger`, `_bearer_scheme = HTTPBearer`, `_bearer_dependency = Depends` |
| [harnesses](modules/harnesses.md) | `router = APIRouter` |
| [promotion](modules/promotion.md) | `router = APIRouter` |
| [research](modules/research.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [results](modules/results.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [src_api_skills](modules/src_api_skills.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [subjects](modules/subjects.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [config](modules/config.md) | `logger = logging.getLogger`, `settings = get_settings` |
| [agent_tools](modules/agent_tools.md) | `logger = logging.getLogger` |
| [artifact_reference](modules/artifact_reference.md) | `SENTINEL_ARTIFACT_STRINGS = frozenset`, `ARTIFACT_REFERENCE_KEYS = frozenset` |
| [bootstrap_runner](modules/bootstrap_runner.md) | `logger = logging.getLogger` |
| [claude_code_harness](modules/claude_code_harness.md) | `CLAUDE_EVENT_TYPES = frozenset`, `CLAUDE_CONTENT_TYPES = frozenset`, `UNSUPPORTED_OPTIONAL_FEATURES = frozenset` |
| [codex_harness](modules/codex_harness.md) | `CODEX_EVENT_TYPES = frozenset`, `CODEX_ITEM_TYPES = frozenset`, `UNSUPPORTED_OPTIONAL_FEATURES = frozenset` |
| [command_policy](modules/command_policy.md) | `_ALLOWED_SCRIPTS = set`, `_COPY_FILENAMES = set`, `_CAT_FILENAMES = set` |
| [command_runner](modules/command_runner.md) | `_SECRET_VALUE_RE = re.compile`, `_BEARER_RE = re.compile`, `_CHILD_ENV_ALLOWLIST = frozenset`, `_FORBIDDEN_CHILD_ENV = frozenset`, `_PATH_AFFECTING_PYTHON_ENV = frozenset` |
| [config_promoter](modules/config_promoter.md) | `logger = logging.getLogger` |
| [consistency_validator](modules/consistency_validator.md) | `logger = logging.getLogger`, `EVIDENCE_ARTIFACT_PHASES = frozenset`, `ACCEPTED_ADAPTIVE_NOOP_REASONS = frozenset`, `REJECTED_ADAPTIVE_NOOP_REASONS = frozenset` |
| [domain_classifier](modules/domain_classifier.md) | `logger = logging.getLogger` |
| [driver_host](modules/driver_host.md) | `DRIVER_ENV_ALLOWLIST = frozenset` |
| [execution_contracts](modules/execution_contracts.md) | `SECRET_NAME_RE = re.compile`, `_SECRET_PARAM_KEY_RE = re.compile`, `DIGEST_RE = re.compile`, `KNOWN_CAPABILITIES = frozenset`, `MINIMUM_SUPPORTED_CAPABILITIES = frozenset`, `LINUX_ISOLATION_BOUNDARY = IsolationBoundary`, `_LEGACY_SESSION_SCHEMA_VERSIONS = frozenset`, `_REJECTED_FIELDS = tuple` |
| [execution_request](modules/execution_request.md) | `TEMPLATE_PLACEHOLDERS = frozenset`, `_PLACEHOLDER_RE = re.compile`, `SUPPORTED_EXECUTABLE_BINDINGS = frozenset`, `DISALLOWED_EXECUTABLES = frozenset`, `BUILTIN_BINDINGS = frozenset` |
| [experiment_parser](modules/experiment_parser.md) | `logger = logging.getLogger`, `_KV_PATTERN = re.compile` |
| [harness_contract](modules/harness_contract.md) | `OPTIONAL_CAPABILITIES = frozenset`, `ATTACH_MODES = frozenset` |
| [iteration_context](modules/iteration_context.md) | `logger = logging.getLogger` |
| [llm_provider](modules/llm_provider.md) | `logger = logging.getLogger`, `_TRANSIENT_STATUS_CODES = frozenset`, `_OPENAI_TRANSIENT_STATUS_CODES = frozenset`, `LOCAL_OPENAI_COMPAT_PROVIDERS = frozenset`, `OPENAI_COMPAT_PROVIDERS = frozenset` |
| [log_writer](modules/log_writer.md) | `logger = logging.getLogger` |
| [orchestrator](modules/orchestrator.md) | `logger = logging.getLogger`, `_PROMOTION_FAMILY = frozenset`, `_AGENT_ACTIONABLE_BLOCKERS = frozenset` |
| [output_parser](modules/output_parser.md) | `logger = logging.getLogger`, `_KV_PATTERN = re.compile`, `SUCCESS_STATUSES = frozenset`, `FIELD_TYPE_VOCABULARY = frozenset`, `_UNIT_FIELD_TYPES = frozenset`, `FAILURE_STATUSES = frozenset` |
| [plugin_runner](modules/plugin_runner.md) | `logger = logging.getLogger`, `_PLUGIN_ENV_ALLOWLIST = frozenset`, `_FORBIDDEN_PLUGIN_ENV = frozenset` |
| [postgres_state_store](modules/postgres_state_store.md) | `logger = logging.getLogger` |
| [promotion_approval](modules/promotion_approval.md) | `_DIGEST = re.compile` |
| [research_phase_plan](modules/research_phase_plan.md) | `NOOP_INHERITABLE_PHASES = frozenset`, `EVIDENCE_INHERITABLE_PHASES = frozenset`, `FAILED_ITERATION_STATUSES = frozenset`, `_PHASE_REQUIRES_IN_PHASE_TAG = frozenset` |
| [run_artifacts](modules/run_artifacts.md) | `DEFAULT_LIMITS = ArtifactLimits` |
| [scoped_credentials](modules/scoped_credentials.md) | `SCOPED_PERMISSIONS = frozenset`, `NON_GRANTABLE_PERMISSIONS = frozenset`, `_REVOKED = set` |
| [session_manager](modules/session_manager.md) | `logger = logging.getLogger`, `_TERMINAL_STATUSES = frozenset` |
| [skill_generator](modules/skill_generator.md) | `logger = logging.getLogger` |
| [skill_lifecycle](modules/skill_lifecycle.md) | `_TERMINAL = frozenset` |
| [skill_loader](modules/skill_loader.md) | `logger = logging.getLogger`, `_SETTINGS_PATTERN = re.compile`, `_SKILL_PARAMS_PATTERN = re.compile` |
| [skill_params](modules/skill_params.md) | `SUPPORTED_KEYWORDS = frozenset` |
| [skill_paths](modules/skill_paths.md) | `PATH_TEMPLATE_PLACEHOLDERS = frozenset`, `PATH_TEMPLATE_IDENTITY_PLACEHOLDERS = frozenset`, `_FORBIDDEN_SEGMENT_VALUES = frozenset` |
| [skill_registry](modules/skill_registry.md) | `logger = logging.getLogger`, `default_registry = SkillRegistry` |
| [state_machine](modules/state_machine.md) | `logger = logging.getLogger`, `_TRANSITIONAL = frozenset`, `_TERMINAL = frozenset`, `_RECOVERY_TERMINAL = frozenset` |
| [state_store](modules/state_store.md) | `logger = logging.getLogger` |
| [trial_workspace](modules/trial_workspace.md) | `logger = logging.getLogger`, `_STAGE_IGNORE = frozenset` |
| [src_main](modules/src_main.md) | `logging.basicConfig`, `logger = logging.getLogger`, `app = FastAPI`, `ensure_app_request_headers`, `logger.warning`, `app.add_middleware`, `_API_V1_PREFIX = _normalise_api_prefix`, `_include_api_routers`, `_include_api_routers`, `_ui_dist = os.path.join`, `app.mount`, `_index_html = os.path.join` |
| [events](modules/events.md) | `logger = logging.getLogger`, `broadcaster = EventBroadcaster` |
| [tests_conftest](modules/tests_conftest.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.path.insert` |
| [phases_bad_schema](modules/phases_bad_schema.md) | `json.load`, `print` |
| [phases_egress](modules/phases_egress.md) | `json.load`, `urllib.request.urlopen`, `print`, `print` |
| [phases_env_spy](modules/phases_env_spy.md) | `json.load`, `secret = os.environ.get`, `print` |
| [phases_tamper](modules/phases_tamper.md) | `sys.stdin.read`, `print` |
| [phases_timeout](modules/phases_timeout.md) | `json.load`, `time.sleep`, `print`, `sys.exit` |
| [_engine](modules/_engine.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.path.insert`, `_REDACT_KEY_RE = re.compile`, `_DROP_KEY_RE = re.compile` |
| [capture](modules/capture.md) | `sys.path.insert` |
| [test_parity](modules/test_parity.md) | `CASES = discover_cases` |
| [test_anthropic_provider](modules/test_anthropic_provider.md) | `sys.modules['anthropic'] = cast` |
| [test_api_auth](modules/test_api_auth.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_auto_promote_terminate_waiver](modules/test_auto_promote_terminate_waiver.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_auto_promotion_readiness](modules/test_auto_promotion_readiness.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_baseline_capture_dedup_bypass](modules/test_baseline_capture_dedup_bypass.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_canonical_start_wiring](modules/test_canonical_start_wiring.md) | `sys.modules['anthropic'] = cast`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_ci_qualification_gates](modules/test_ci_qualification_gates.md) | `_SPEC = importlib.util.spec_from_file_location`, `cqg = importlib.util.module_from_spec`, `sys.modules['ci_qualification_gates'] = cast`, `_SPEC.loader.exec_module` |
| [test_cli](modules/test_cli.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_code_refactor_domain](modules/test_code_refactor_domain.md) | `REQUIREMENTS = EvalRequirements` |
| [test_command_policy](modules/test_command_policy.md) | `sys.modules['anthropic'] = cast` |
| [test_compatibility_matrix](modules/test_compatibility_matrix.md) | `_SPEC = importlib.util.spec_from_file_location`, `rcm = importlib.util.module_from_spec`, `sys.modules['run_compatibility_matrix'] = cast`, `_SPEC.loader.exec_module` |
| [test_config_promoter_gate_bundle](modules/test_config_promoter_gate_bundle.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_cross_worker_control](modules/test_cross_worker_control.md) | `sys.modules['anthropic'] = cast`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_delete_session_hpo_cascade](modules/test_delete_session_hpo_cascade.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_distributed_state_store](modules/test_distributed_state_store.md) | `_SERVICE_ROOT = os.path.abspath` |
| [test_durable_operation_qualification](modules/test_durable_operation_qualification.md) | `_WORKER = textwrap.dedent`, `_SCENARIO_WORKER = textwrap.dedent` |
| [test_estimate_cost_api](modules/test_estimate_cost_api.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_execution_concurrency](modules/test_execution_concurrency.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_execution_isolation](modules/test_execution_isolation.md) | `_HOST_READY = bool`, `requires_backend = pytest.mark.skipif` |
| [test_execution_ledger_validator](modules/test_execution_ledger_validator.md) | `_SPEC = importlib.util.spec_from_file_location`, `cel = importlib.util.module_from_spec`, `sys.modules['check_execution_ledger'] = cast`, `_SPEC.loader.exec_module` |
| [test_gap1_duplicate_guard](modules/test_gap1_duplicate_guard.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_gate_bundle_production_economics](modules/test_gate_bundle_production_economics.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_generalization_falsifiability](modules/test_generalization_falsifiability.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_goal_phase_semantics](modules/test_goal_phase_semantics.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_headroom_hint](modules/test_headroom_hint.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_latency_benchmark](modules/test_latency_benchmark.md) | `PROTOCOL = MeasurementProtocol`, `WORKLOAD = build_workload` |
| [test_leaderboard_api](modules/test_leaderboard_api.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_leaderboard_comparability](modules/test_leaderboard_comparability.md) | `CTX_A = build_comparison_context`, `CTX_B = build_comparison_context` |
| [test_llm_provider_openai](modules/test_llm_provider_openai.md) | `sys.modules['openai'] = cast` |
| [test_manifest_runtime_production_path](modules/test_manifest_runtime_production_path.md) | `sys.modules['anthropic'] = cast`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_marker_file_staleness](modules/test_marker_file_staleness.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast`, `_FRESH_MARKER = '\n'.join` |
| [test_metrics_forgery_c3](modules/test_metrics_forgery_c3.md) | `sys.modules['anthropic'] = cast`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_mlflow_run_id_contract](modules/test_mlflow_run_id_contract.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_mock_provider](modules/test_mock_provider.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_non_ml_session_e2e](modules/test_non_ml_session_e2e.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_objective_comparator](modules/test_objective_comparator.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_observation_identity](modules/test_observation_identity.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_orchestrator_command_audit](modules/test_orchestrator_command_audit.md) | `sys.modules['anthropic'] = cast` |
| [test_orchestrator_config_snapshot_inheritance](modules/test_orchestrator_config_snapshot_inheritance.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_orchestrator_evidence_replay](modules/test_orchestrator_evidence_replay.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_orchestrator_global_stagnation](modules/test_orchestrator_global_stagnation.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_orchestrator_loop_guard](modules/test_orchestrator_loop_guard.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_orchestrator_terminal_reason](modules/test_orchestrator_terminal_reason.md) | `_fake_anthropic = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_orchestrator_terminate_deferral](modules/test_orchestrator_terminate_deferral.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_orchestrator_timeout](modules/test_orchestrator_timeout.md) | `sys.modules['anthropic'] = cast` |
| [test_pagination](modules/test_pagination.md) | `_SESSION_COMMON = dict`, `_PIPELINE_COMMON = dict` |
| [test_parallel_trials](modules/test_parallel_trials.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_EVAL_SCRIPT = '"""Synthetic slow eval: sleeps, writes sentinels + a marker KV file."""\nimport argparse\nimport pathlib\nimport time\n\nparser = argparse.ArgumentParser()\nparser.add_argument("--config", required=True)\nparser.add_argument("--sleep", type=float, default={sleep})\nargs = parser.parse_args()\n\ntime.sleep(args.sleep)\n\ncfg = pathlib.Path(args.config)\nstem = cfg.stem\n# Per-variant metric so the two trials are distinguishable in the DB.\nmetric = 0.50 if stem.endswith("a") else 0.75\npathlib.Path("sentinel_" + stem + ".txt").write_text("ran", encoding="utf-8")\n\nkv = (\n    "---\\n"\n    "status: completed\\n"\n    "primary_metric: " + str(metric) + "\\n"\n    "metric_name: demo_metric\\n"\n    "training_gates_passed: true\\n"\n    "---\\n"\n)\n# The marker file lands next to the config: inside the trial directory for\n# staged trials (relative config), in the session workspace otherwise —\n# exactly the resolution order output_parser.fallback + trial candidates\n# implement server-side.\n(cfg.parent / "{marker}").write_text(kv, encoding="utf-8")\nprint(kv)\n'.replace('{sleep}', str(_SLEEP_S)).replace` |
| [test_phase_evidence_dedup_inherit](modules/test_phase_evidence_dedup_inherit.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_promotion_approval](modules/test_promotion_approval.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_promotion_diagnostics](modules/test_promotion_diagnostics.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_prompt_promotion_policy](modules/test_prompt_promotion_policy.md) | `sys.modules['anthropic'] = cast` |
| [test_research_api_compat](modules/test_research_api_compat.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_research_api_integration](modules/test_research_api_integration.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_research_kernel](modules/test_research_kernel.md) | `DENIED_MODULES = frozenset` |
| [test_research_manifest](modules/test_research_manifest.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_result_artifact_ingestion](modules/test_result_artifact_ingestion.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_results_store_manifest_snapshots](modules/test_results_store_manifest_snapshots.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_results_store_migrations](modules/test_results_store_migrations.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_runtime_recovery](modules/test_runtime_recovery.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.modules['anthropic'] = cast` |
| [test_service_preflight](modules/test_service_preflight.md) | `sys.modules['anthropic'] = cast` |
| [test_session_failure_modes](modules/test_session_failure_modes.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_session_status_routing](modules/test_session_status_routing.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.modules['anthropic'] = cast` |
| [test_significance](modules/test_significance.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_skill_loader](modules/test_skill_loader.md) | `STUB_SETTINGS = _StubSettings` |
| [test_skill_params_validation](modules/test_skill_params_validation.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_skill_prompt_engineering_e2e](modules/test_skill_prompt_engineering_e2e.md) | `sys.modules['openai'] = cast`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_skills_api](modules/test_skills_api.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_skills_generate_api](modules/test_skills_generate_api.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_stagnation_phase_genuineness](modules/test_stagnation_phase_genuineness.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = cast` |
| [test_state_machine](modules/test_state_machine.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.path.insert` |
| [test_trial_workspace](modules/test_trial_workspace.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_usage_ledger](modules/test_usage_ledger.md) | `_BUDGET_WORKER = textwrap.dedent` |
| [test_webhook_promotion](modules/test_webhook_promotion.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_work_reservations](modules/test_work_reservations.md) | `ITERATION_KW = dict`, `_WORKER_SCRIPT = textwrap.dedent` |
| [test_ws_event_enrichment](modules/test_ws_event_enrichment.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [run-production-ops-tests](modules/run-production-ops-tests.md) | `root = dirname`, `outDir = join`, `mkdirSync`, `writeFileSync`, `execFileSync`, `compiledPath = findCompiledModule`, `ok`, `compiledClientPath = findCompiledModule`, `ok`, `test`, `test`, `test`, `test`, `test` |
| [DynamicFormFields](modules/DynamicFormFields.md) | `KNOWN_TYPES = Set` |
| [DynamicFormFields.test](modules/DynamicFormFields.test.md) | `describe` |
| [HarnessUI.test](modules/HarnessUI.test.md) | `describe`, `describe`, `describe` |
| [IterationsTable.test](modules/IterationsTable.test.md) | `describe` |
| [MetricsChart.test](modules/MetricsChart.test.md) | `describe` |
| [PromotionModal.test](modules/PromotionModal.test.md) | `mock`, `describe` |
| [useWebSocket](modules/useWebSocket.md) | `WebSocketContext = createContext` |
| [ui_src_main](modules/ui_src_main.md) | `queryClient = QueryClient`, `render` |
| [Leaderboard.test](modules/Leaderboard.test.md) | `mock`, `describe` |
| [NewResearch.test](modules/NewResearch.test.md) | `mock`, `describe` |

## Factory / wiring

<!-- Heuristic, name-based detection of app-factory / wiring functions. -->

| Function | Kind | Module |
|----------|------|--------|
| `register_prompt` | wiring | [examples_prompt-registry_main](modules/examples_prompt-registry_main.md) |
| `create_or_attach_run` | factory | [agent](modules/agent.md) |
| `configure_api_auth` | wiring | [test_api_auth](modules/test_api_auth.md) |
| `create_test_app` | factory | [test_api_auth](modules/test_api_auth.md) |
| `configure_auth` | wiring | [test_estimate_cost_api](modules/test_estimate_cost_api.md) |
| `configure` | wiring | [test_generalization_falsifiability](modules/test_generalization_falsifiability.md) |
| `create_test_app` | factory | [test_generalization_falsifiability](modules/test_generalization_falsifiability.md) |
| `configure_auth` | wiring | [test_leaderboard_api](modules/test_leaderboard_api.md) |
| `create_test_app` | factory | [test_leaderboard_api](modules/test_leaderboard_api.md) |
| `configure_module` | wiring | [test_promotion_approval](modules/test_promotion_approval.md) |
| `create_test_app` | factory | [test_promotion_approval](modules/test_promotion_approval.md) |
| `configure` | wiring | [test_research_api_compat](modules/test_research_api_compat.md) |
| `create_test_app` | factory | [test_research_api_compat](modules/test_research_api_compat.md) |
| `configure_auth` | wiring | [test_skills_api](modules/test_skills_api.md) |
| `create_test_app` | factory | [test_skills_api](modules/test_skills_api.md) |
| `create_test_app` | factory | [test_skills_generate_api](modules/test_skills_generate_api.md) |

## Notes

This page presents a static dependency projection. Lazy imports, conditional initialization, and runtime side effects can change the effective order.
