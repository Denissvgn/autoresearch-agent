# Load order

Topological module load / startup order and import-time side effects.

## Load order

<!-- Dependency-first order: each module loads after the internal modules it imports. -->
1. [examples_prompt-registry_main](modules/examples_prompt-registry_main.md)
2. [check_doc_references](modules/check_doc_references.md)
3. [check_domain_coupling](modules/check_domain_coupling.md)
4. [check_execution_ledger](modules/check_execution_ledger.md)
5. [check_legacy_vocab_branching](modules/check_legacy_vocab_branching.md)
6. [code-refactor_bootstrap](modules/code-refactor_bootstrap.md)
7. [code-refactor_eval_run](modules/code-refactor_eval_run.md)
8. [db-config-tuning_bootstrap](modules/db-config-tuning_bootstrap.md)
9. [db-config-tuning_eval_run](modules/db-config-tuning_eval_run.md)
10. [prompt-engineering_bootstrap](modules/prompt-engineering_bootstrap.md)
11. [dataset](modules/dataset.md)
12. [prompt-engineering_eval_run](modules/prompt-engineering_eval_run.md)
13. [cli](modules/cli.md)
14. [compat_legacy_alias](modules/compat_legacy_alias.md)
15. [legacy_phase_tables](modules/legacy_phase_tables.md)
16. [ml_enrichment](modules/ml_enrichment.md)
17. [config](modules/config.md)
18. [auth](modules/auth.md)
19. [audit](modules/audit.md)
20. [artifact_reference](modules/artifact_reference.md)
21. [blocker_classifier](modules/blocker_classifier.md)
22. [development_inference_validation](modules/development_inference_validation.md)
23. [development_signal_health](modules/development_signal_health.md)
24. [execution_contracts](modules/execution_contracts.md)
25. [execution_request](modules/execution_request.md)
26. [fs_safety](modules/fs_safety.md)
27. [gate_status](modules/gate_status.md)
28. [consistency_validator](modules/consistency_validator.md)
29. [development_gate_bundle](modules/development_gate_bundle.md)
30. [http_headers](modules/http_headers.md)
31. [insights_feedback](modules/insights_feedback.md)
32. [iteration_context](modules/iteration_context.md)
33. [iteration_snapshot](modules/iteration_snapshot.md)
34. [core_legacy_alias](modules/core_legacy_alias.md)
35. [llm_provider](modules/llm_provider.md)
36. [observability](modules/observability.md)
37. [output_digest](modules/output_digest.md)
38. [output_parser](modules/output_parser.md)
39. [experiment_parser](modules/experiment_parser.md)
40. [pagination](modules/pagination.md)
41. [postgres_state_store](modules/postgres_state_store.md)
42. [migrate_sqlite_to_postgres](modules/migrate_sqlite_to_postgres.md)
43. [promotion_approval](modules/promotion_approval.md)
44. [promotion](modules/promotion.md)
45. [promotion_target](modules/promotion_target.md)
46. [research_phase_plan](modules/research_phase_plan.md)
47. [research_state](modules/research_state.md)
48. [result_artifact](modules/result_artifact.md)
49. [service_preflight](modules/service_preflight.md)
50. [preflight](modules/preflight.md)
51. [significance](modules/significance.md)
52. [skill_lifecycle](modules/skill_lifecycle.md)
53. [skill_manifest](modules/skill_manifest.md)
54. [skill_loader](modules/skill_loader.md)
55. [skill_paths](modules/skill_paths.md)
56. [research_manifest](modules/research_manifest.md)
57. [skill_registry](modules/skill_registry.md)
58. [src_api_skills](modules/src_api_skills.md)
59. [subjects](modules/subjects.md)
60. [domain_classifier](modules/domain_classifier.md)
61. [skill_generator](modules/skill_generator.md)
62. [skill_runtime](modules/skill_runtime.md)
63. [research](modules/research.md)
64. [state_store](modules/state_store.md)
65. [config_promoter](modules/config_promoter.md)
66. [results_store](modules/results_store.md)
67. [tool_access](modules/tool_access.md)
68. [command_policy](modules/command_policy.md)
69. [command_runner](modules/command_runner.md)
70. [agent_tools](modules/agent_tools.md)
71. [plugin_runner](modules/plugin_runner.md)
72. [bootstrap_runner](modules/bootstrap_runner.md)
73. [trial_workspace](modules/trial_workspace.md)
74. [events](modules/events.md)
75. [log_writer](modules/log_writer.md)
76. [results](modules/results.md)
77. [state_machine](modules/state_machine.md)
78. [orchestrator](modules/orchestrator.md)
79. [session_manager](modules/session_manager.md)
80. [src_main](modules/src_main.md)
81. [tests_conftest](modules/tests_conftest.md)
82. [_engine](modules/_engine.md)
83. [capture](modules/capture.md)
84. [parity_conftest](modules/parity_conftest.md)
85. [test_parity](modules/test_parity.md)
86. [test_adaptive_noop_reason_fallback](modules/test_adaptive_noop_reason_fallback.md)
87. [test_anthropic_provider](modules/test_anthropic_provider.md)
88. [test_api_auth](modules/test_api_auth.md)
89. [test_async_tool_path](modules/test_async_tool_path.md)
90. [test_auto_phase_evidence](modules/test_auto_phase_evidence.md)
91. [test_auto_promote_terminate_waiver](modules/test_auto_promote_terminate_waiver.md)
92. [test_auto_promotion_readiness](modules/test_auto_promotion_readiness.md)
93. [test_baseline_capture_dedup_bypass](modules/test_baseline_capture_dedup_bypass.md)
94. [test_bootstrap_runner](modules/test_bootstrap_runner.md)
95. [test_canonical_start_wiring](modules/test_canonical_start_wiring.md)
96. [test_cli](modules/test_cli.md)
97. [test_command_policy](modules/test_command_policy.md)
98. [test_config_promoter_atomic](modules/test_config_promoter_atomic.md)
99. [test_config_promoter_gate_bundle](modules/test_config_promoter_gate_bundle.md)
100. [test_contract_examples](modules/test_contract_examples.md)
101. [test_cross_session_digest_hint](modules/test_cross_session_digest_hint.md)
102. [test_cross_worker_control](modules/test_cross_worker_control.md)
103. [test_delete_session_hpo_cascade](modules/test_delete_session_hpo_cascade.md)
104. [test_deployment_inputs](modules/test_deployment_inputs.md)
105. [test_distributed_state_store](modules/test_distributed_state_store.md)
106. [test_domain_classifier](modules/test_domain_classifier.md)
107. [test_duplicate_phase_advancement_guard](modules/test_duplicate_phase_advancement_guard.md)
108. [test_duplicate_rejection_budget](modules/test_duplicate_rejection_budget.md)
109. [test_estimate_cost_api](modules/test_estimate_cost_api.md)
110. [test_event_broadcaster_concurrency](modules/test_event_broadcaster_concurrency.md)
111. [test_evidence_artifact_validation](modules/test_evidence_artifact_validation.md)
112. [test_execution_concurrency](modules/test_execution_concurrency.md)
113. [test_execution_contracts](modules/test_execution_contracts.md)
114. [test_execution_ledger_validator](modules/test_execution_ledger_validator.md)
115. [test_execution_request](modules/test_execution_request.md)
116. [test_experiment_parser_calibration](modules/test_experiment_parser_calibration.md)
117. [test_experiment_parser_inference_parity](modules/test_experiment_parser_inference_parity.md)
118. [test_experiment_parser_promotion_scope](modules/test_experiment_parser_promotion_scope.md)
119. [test_experiment_parser_seed_trials](modules/test_experiment_parser_seed_trials.md)
120. [test_experiment_parser_volatility_phase5](modules/test_experiment_parser_volatility_phase5.md)
121. [test_experiment_parser_volatility_phase8](modules/test_experiment_parser_volatility_phase8.md)
122. [test_exploration_markers](modules/test_exploration_markers.md)
123. [test_fencing_tokens](modules/test_fencing_tokens.md)
124. [test_fs_safety](modules/test_fs_safety.md)
125. [test_gap1_duplicate_guard](modules/test_gap1_duplicate_guard.md)
126. [test_gate_bundle_production_economics](modules/test_gate_bundle_production_economics.md)
127. [test_gate_status_contract](modules/test_gate_status_contract.md)
128. [test_generalization_falsifiability](modules/test_generalization_falsifiability.md)
129. [test_hardening_phase1_to_5](modules/test_hardening_phase1_to_5.md)
130. [test_headroom_hint](modules/test_headroom_hint.md)
131. [test_insights_feedback](modules/test_insights_feedback.md)
132. [test_issue10b_declined_outcome](modules/test_issue10b_declined_outcome.md)
133. [test_issue6_adaptive_not_attempted](modules/test_issue6_adaptive_not_attempted.md)
134. [test_issue8_consistency_blocked_outcome](modules/test_issue8_consistency_blocked_outcome.md)
135. [test_iteration_context](modules/test_iteration_context.md)
136. [test_iteration_cost_attribution](modules/test_iteration_cost_attribution.md)
137. [test_iteration_snapshot](modules/test_iteration_snapshot.md)
138. [test_iteration_snapshot_canonical_payload](modules/test_iteration_snapshot_canonical_payload.md)
139. [test_leaderboard_api](modules/test_leaderboard_api.md)
140. [test_llm_provider](modules/test_llm_provider.md)
141. [test_llm_provider_openai](modules/test_llm_provider_openai.md)
142. [test_log_writer](modules/test_log_writer.md)
143. [test_main_operational_endpoints](modules/test_main_operational_endpoints.md)
144. [test_manifest_runtime_production_path](modules/test_manifest_runtime_production_path.md)
145. [test_marker_file_staleness](modules/test_marker_file_staleness.md)
146. [test_metrics_forgery](modules/test_metrics_forgery.md)
147. [test_metrics_forgery_c3](modules/test_metrics_forgery_c3.md)
148. [test_mlflow_run_id_contract](modules/test_mlflow_run_id_contract.md)
149. [test_mock_provider](modules/test_mock_provider.md)
150. [test_non_ml_session_e2e](modules/test_non_ml_session_e2e.md)
151. [test_observability](modules/test_observability.md)
152. [test_openapi_contract](modules/test_openapi_contract.md)
153. [test_orchestrator_command_audit](modules/test_orchestrator_command_audit.md)
154. [test_orchestrator_config_snapshot_inheritance](modules/test_orchestrator_config_snapshot_inheritance.md)
155. [test_orchestrator_evidence_replay](modules/test_orchestrator_evidence_replay.md)
156. [test_orchestrator_global_stagnation](modules/test_orchestrator_global_stagnation.md)
157. [test_orchestrator_loop_guard](modules/test_orchestrator_loop_guard.md)
158. [test_orchestrator_terminal_reason](modules/test_orchestrator_terminal_reason.md)
159. [test_orchestrator_terminate_deferral](modules/test_orchestrator_terminate_deferral.md)
160. [test_orchestrator_timeout](modules/test_orchestrator_timeout.md)
161. [test_output_digest](modules/test_output_digest.md)
162. [test_output_parser](modules/test_output_parser.md)
163. [test_packaging](modules/test_packaging.md)
164. [test_pagination](modules/test_pagination.md)
165. [test_parallel_trials](modules/test_parallel_trials.md)
166. [test_phase_evidence_dedup_inherit](modules/test_phase_evidence_dedup_inherit.md)
167. [test_phase_genuine_dwell](modules/test_phase_genuine_dwell.md)
168. [test_phase_state_broadcast](modules/test_phase_state_broadcast.md)
169. [test_pinned_evaluators](modules/test_pinned_evaluators.md)
170. [test_plugin_runner](modules/test_plugin_runner.md)
171. [test_postgres_sqlite_parity](modules/test_postgres_sqlite_parity.md)
172. [test_postgres_state_store](modules/test_postgres_state_store.md)
173. [test_preflight](modules/test_preflight.md)
174. [test_promotion_approval](modules/test_promotion_approval.md)
175. [test_promotion_diagnostics](modules/test_promotion_diagnostics.md)
176. [test_promotion_target](modules/test_promotion_target.md)
177. [test_prompt_evaluator](modules/test_prompt_evaluator.md)
178. [test_prompt_promotion_policy](modules/test_prompt_promotion_policy.md)
179. [test_replay_fixture](modules/test_replay_fixture.md)
180. [test_research_api_compat](modules/test_research_api_compat.md)
181. [test_research_api_integration](modules/test_research_api_integration.md)
182. [test_research_config](modules/test_research_config.md)
183. [test_research_manifest](modules/test_research_manifest.md)
184. [test_result_artifact_ingestion](modules/test_result_artifact_ingestion.md)
185. [test_results_api](modules/test_results_api.md)
186. [test_results_store_manifest_snapshots](modules/test_results_store_manifest_snapshots.md)
187. [test_results_store_migrations](modules/test_results_store_migrations.md)
188. [test_rl_phase_tracing](modules/test_rl_phase_tracing.md)
189. [test_runtime_recovery](modules/test_runtime_recovery.md)
190. [test_service_preflight](modules/test_service_preflight.md)
191. [test_session_failure_modes](modules/test_session_failure_modes.md)
192. [test_session_status_routing](modules/test_session_status_routing.md)
193. [test_significance](modules/test_significance.md)
194. [test_skill_generator](modules/test_skill_generator.md)
195. [test_skill_lifecycle](modules/test_skill_lifecycle.md)
196. [test_skill_loader](modules/test_skill_loader.md)
197. [test_skill_paths](modules/test_skill_paths.md)
198. [test_skill_prompt_engineering_e2e](modules/test_skill_prompt_engineering_e2e.md)
199. [test_skills_api](modules/test_skills_api.md)
200. [test_skills_generate_api](modules/test_skills_generate_api.md)
201. [test_stagnation_phase_genuineness](modules/test_stagnation_phase_genuineness.md)
202. [test_state_machine](modules/test_state_machine.md)
203. [test_state_store](modules/test_state_store.md)
204. [test_terminal_phase_contract](modules/test_terminal_phase_contract.md)
205. [test_tool_access](modules/test_tool_access.md)
206. [test_trial_workspace](modules/test_trial_workspace.md)
207. [test_webhook_promotion](modules/test_webhook_promotion.md)
208. [test_release_promotion_safety](modules/test_release_promotion_safety.md)
209. [test_ws_event_enrichment](modules/test_ws_event_enrichment.md)
210. [postcss.config](modules/postcss.config.md)
211. [run-production-ops-tests](modules/run-production-ops-tests.md)
212. [client](modules/client.md)
213. [ClipboardCopy](modules/ClipboardCopy.md)
214. [ConfigDiff](modules/ConfigDiff.md)
215. [IterationsTable](modules/IterationsTable.md)
216. [MetricsChart](modules/MetricsChart.md)
217. [ResearchStatePanel](modules/ResearchStatePanel.md)
218. [SkillPicker](modules/SkillPicker.md)
219. [StatusBadge](modules/StatusBadge.md)
220. [IterationsTable.test](modules/IterationsTable.test.md)
221. [MetricsChart.test](modules/MetricsChart.test.md)
222. [primitives](modules/primitives.md)
223. [useWebSocket](modules/useWebSocket.md)
224. [useResearch](modules/useResearch.md)
225. [AgentLog](modules/AgentLog.md)
226. [Topbar](modules/Topbar.md)
227. [Dashboard](modules/Dashboard.md)
228. [History](modules/History.md)
229. [Leaderboard](modules/Leaderboard.md)
230. [Promote](modules/Promote.md)
231. [ResearchDetail](modules/ResearchDetail.md)
232. [Settings](modules/Settings.md)
233. [ui_src_pages_Skills](modules/ui_src_pages_Skills.md)
234. [index](modules/index.md)
235. [types](modules/types.md)
236. [registry](modules/registry.md)
237. [DynamicFormFields](modules/DynamicFormFields.md)
238. [DynamicFormFields.test](modules/DynamicFormFields.test.md)
239. [NewResearch](modules/NewResearch.md)
240. [App](modules/App.md)
241. [ui_src_main](modules/ui_src_main.md)
242. [NewResearch.test](modules/NewResearch.test.md)
243. [productionOps](modules/productionOps.md)
244. [ProductionOpsPanel](modules/ProductionOpsPanel.md)
245. [PromotionModal](modules/PromotionModal.md)
246. [PromotionModal.test](modules/PromotionModal.test.md)
247. [tailwind.config](modules/tailwind.config.md)
248. [vite.config](modules/vite.config.md)
249. [vitest.config](modules/vitest.config.md)
250. [vitest.setup](modules/vitest.setup.md)

## Module-level side effects

| Module | Import-time calls |
|--------|-------------------|
| [examples_prompt-registry_main](modules/examples_prompt-registry_main.md) | `app = FastAPI` |
| [check_doc_references](modules/check_doc_references.md) | `DOC_PATH_RE = re.compile` |
| [check_domain_coupling](modules/check_domain_coupling.md) | `PATTERN = re.compile` |
| [check_execution_ledger](modules/check_execution_ledger.md) | `CARD_ID_RE = re.compile`, `CHECK_ID_RE = re.compile`, `STATES = frozenset`, `RESULT_STATES = frozenset` |
| [migrate_sqlite_to_postgres](modules/migrate_sqlite_to_postgres.md) | `sys.path.insert`, `logger = logging.getLogger` |
| [auth](modules/auth.md) | `logger = logging.getLogger`, `_bearer_scheme = HTTPBearer`, `_bearer_dependency = Depends` |
| [promotion](modules/promotion.md) | `router = APIRouter` |
| [research](modules/research.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [results](modules/results.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [src_api_skills](modules/src_api_skills.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [subjects](modules/subjects.md) | `logger = logging.getLogger`, `router = APIRouter` |
| [config](modules/config.md) | `logger = logging.getLogger`, `settings = get_settings` |
| [agent_tools](modules/agent_tools.md) | `logger = logging.getLogger` |
| [artifact_reference](modules/artifact_reference.md) | `SENTINEL_ARTIFACT_STRINGS = frozenset`, `ARTIFACT_REFERENCE_KEYS = frozenset` |
| [bootstrap_runner](modules/bootstrap_runner.md) | `logger = logging.getLogger` |
| [command_policy](modules/command_policy.md) | `_ALLOWED_SCRIPTS = set`, `_COPY_FILENAMES = set`, `_CAT_FILENAMES = set` |
| [command_runner](modules/command_runner.md) | `_SECRET_VALUE_RE = re.compile`, `_BEARER_RE = re.compile`, `_CHILD_ENV_ALLOWLIST = frozenset`, `_FORBIDDEN_CHILD_ENV = frozenset`, `_PATH_AFFECTING_PYTHON_ENV = frozenset` |
| [config_promoter](modules/config_promoter.md) | `logger = logging.getLogger` |
| [consistency_validator](modules/consistency_validator.md) | `logger = logging.getLogger`, `EVIDENCE_ARTIFACT_PHASES = frozenset`, `ACCEPTED_ADAPTIVE_NOOP_REASONS = frozenset`, `REJECTED_ADAPTIVE_NOOP_REASONS = frozenset` |
| [domain_classifier](modules/domain_classifier.md) | `logger = logging.getLogger` |
| [execution_contracts](modules/execution_contracts.md) | `SECRET_NAME_RE = re.compile`, `_SECRET_PARAM_KEY_RE = re.compile`, `DIGEST_RE = re.compile`, `KNOWN_CAPABILITIES = frozenset`, `MINIMUM_SUPPORTED_CAPABILITIES = frozenset`, `LINUX_ISOLATION_BOUNDARY = IsolationBoundary`, `_LEGACY_SESSION_SCHEMA_VERSIONS = frozenset`, `_REJECTED_FIELDS = tuple` |
| [execution_request](modules/execution_request.md) | `TEMPLATE_PLACEHOLDERS = frozenset`, `_PLACEHOLDER_RE = re.compile`, `SUPPORTED_EXECUTABLE_BINDINGS = frozenset`, `DISALLOWED_EXECUTABLES = frozenset`, `BUILTIN_BINDINGS = frozenset` |
| [experiment_parser](modules/experiment_parser.md) | `logger = logging.getLogger`, `_KV_PATTERN = re.compile` |
| [iteration_context](modules/iteration_context.md) | `logger = logging.getLogger` |
| [llm_provider](modules/llm_provider.md) | `logger = logging.getLogger`, `_TRANSIENT_STATUS_CODES = frozenset`, `_OPENAI_TRANSIENT_STATUS_CODES = frozenset` |
| [log_writer](modules/log_writer.md) | `logger = logging.getLogger` |
| [orchestrator](modules/orchestrator.md) | `logger = logging.getLogger`, `_PROMOTION_FAMILY = frozenset`, `_AGENT_ACTIONABLE_BLOCKERS = frozenset` |
| [output_parser](modules/output_parser.md) | `logger = logging.getLogger`, `_KV_PATTERN = re.compile`, `FAILURE_STATUSES = frozenset` |
| [plugin_runner](modules/plugin_runner.md) | `logger = logging.getLogger`, `_PLUGIN_ENV_ALLOWLIST = frozenset`, `_FORBIDDEN_PLUGIN_ENV = frozenset` |
| [postgres_state_store](modules/postgres_state_store.md) | `logger = logging.getLogger` |
| [promotion_approval](modules/promotion_approval.md) | `_DIGEST = re.compile` |
| [research_phase_plan](modules/research_phase_plan.md) | `NOOP_INHERITABLE_PHASES = frozenset`, `EVIDENCE_INHERITABLE_PHASES = frozenset`, `FAILED_ITERATION_STATUSES = frozenset`, `_PHASE_REQUIRES_IN_PHASE_TAG = frozenset` |
| [session_manager](modules/session_manager.md) | `logger = logging.getLogger` |
| [skill_generator](modules/skill_generator.md) | `logger = logging.getLogger` |
| [skill_lifecycle](modules/skill_lifecycle.md) | `_TERMINAL = frozenset` |
| [skill_loader](modules/skill_loader.md) | `logger = logging.getLogger`, `_SETTINGS_PATTERN = re.compile`, `_SKILL_PARAMS_PATTERN = re.compile` |
| [skill_paths](modules/skill_paths.md) | `PATH_TEMPLATE_PLACEHOLDERS = frozenset`, `PATH_TEMPLATE_IDENTITY_PLACEHOLDERS = frozenset`, `_FORBIDDEN_SEGMENT_VALUES = frozenset` |
| [skill_registry](modules/skill_registry.md) | `logger = logging.getLogger`, `default_registry = SkillRegistry` |
| [state_machine](modules/state_machine.md) | `logger = logging.getLogger`, `_TRANSITIONAL = frozenset`, `_TERMINAL = frozenset`, `_RECOVERY_TERMINAL = frozenset` |
| [state_store](modules/state_store.md) | `logger = logging.getLogger` |
| [trial_workspace](modules/trial_workspace.md) | `logger = logging.getLogger`, `_STAGE_IGNORE = frozenset` |
| [src_main](modules/src_main.md) | `logging.basicConfig`, `logger = logging.getLogger`, `app = FastAPI`, `ensure_app_request_headers`, `logger.warning`, `app.add_middleware`, `_API_V1_PREFIX = _normalise_api_prefix`, `_include_api_routers`, `_include_api_routers`, `_ui_dist = os.path.join`, `app.mount`, `_index_html = os.path.join` |
| [events](modules/events.md) | `logger = logging.getLogger`, `broadcaster = EventBroadcaster` |
| [tests_conftest](modules/tests_conftest.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.path.insert` |
| [_engine](modules/_engine.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.path.insert`, `_REDACT_KEY_RE = re.compile`, `_DROP_KEY_RE = re.compile` |
| [capture](modules/capture.md) | `sys.path.insert` |
| [test_parity](modules/test_parity.md) | `CASES = discover_cases` |
| [test_anthropic_provider](modules/test_anthropic_provider.md) | `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_api_auth](modules/test_api_auth.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_auto_promote_terminate_waiver](modules/test_auto_promote_terminate_waiver.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_auto_promotion_readiness](modules/test_auto_promotion_readiness.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_baseline_capture_dedup_bypass](modules/test_baseline_capture_dedup_bypass.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_canonical_start_wiring](modules/test_canonical_start_wiring.md) | `sys.modules['anthropic'] = types.SimpleNamespace`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_cli](modules/test_cli.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_command_policy](modules/test_command_policy.md) | `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_config_promoter_gate_bundle](modules/test_config_promoter_gate_bundle.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_cross_worker_control](modules/test_cross_worker_control.md) | `sys.modules['anthropic'] = types.SimpleNamespace`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_delete_session_hpo_cascade](modules/test_delete_session_hpo_cascade.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_distributed_state_store](modules/test_distributed_state_store.md) | `_SERVICE_ROOT = os.path.abspath` |
| [test_estimate_cost_api](modules/test_estimate_cost_api.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_execution_concurrency](modules/test_execution_concurrency.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_execution_ledger_validator](modules/test_execution_ledger_validator.md) | `_SPEC = importlib.util.spec_from_file_location`, `cel = importlib.util.module_from_spec`, `sys.modules['check_execution_ledger'] = cel`, `_SPEC.loader.exec_module` |
| [test_gap1_duplicate_guard](modules/test_gap1_duplicate_guard.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_gate_bundle_production_economics](modules/test_gate_bundle_production_economics.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_generalization_falsifiability](modules/test_generalization_falsifiability.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_headroom_hint](modules/test_headroom_hint.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_leaderboard_api](modules/test_leaderboard_api.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_llm_provider_openai](modules/test_llm_provider_openai.md) | `sys.modules['openai'] = types.SimpleNamespace` |
| [test_manifest_runtime_production_path](modules/test_manifest_runtime_production_path.md) | `sys.modules['anthropic'] = types.SimpleNamespace`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_marker_file_staleness](modules/test_marker_file_staleness.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub`, `_FRESH_MARKER = '\n'.join` |
| [test_metrics_forgery_c3](modules/test_metrics_forgery_c3.md) | `sys.modules['anthropic'] = types.SimpleNamespace`, `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_mlflow_run_id_contract](modules/test_mlflow_run_id_contract.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_mock_provider](modules/test_mock_provider.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_non_ml_session_e2e](modules/test_non_ml_session_e2e.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_orchestrator_command_audit](modules/test_orchestrator_command_audit.md) | `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_orchestrator_config_snapshot_inheritance](modules/test_orchestrator_config_snapshot_inheritance.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_orchestrator_evidence_replay](modules/test_orchestrator_evidence_replay.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_orchestrator_global_stagnation](modules/test_orchestrator_global_stagnation.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_orchestrator_loop_guard](modules/test_orchestrator_loop_guard.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_orchestrator_terminal_reason](modules/test_orchestrator_terminal_reason.md) | `_fake_anthropic = types.SimpleNamespace`, `sys.modules['anthropic'] = _fake_anthropic` |
| [test_orchestrator_terminate_deferral](modules/test_orchestrator_terminate_deferral.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_orchestrator_timeout](modules/test_orchestrator_timeout.md) | `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_pagination](modules/test_pagination.md) | `_SESSION_COMMON = dict`, `_PIPELINE_COMMON = dict` |
| [test_parallel_trials](modules/test_parallel_trials.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_EVAL_SCRIPT = '"""Synthetic slow eval: sleeps, writes sentinels + a marker KV file."""\nimport argparse\nimport pathlib\nimport time\n\nparser = argparse.ArgumentParser()\nparser.add_argument("--config", required=True)\nparser.add_argument("--sleep", type=float, default={sleep})\nargs = parser.parse_args()\n\ntime.sleep(args.sleep)\n\ncfg = pathlib.Path(args.config)\nstem = cfg.stem\n# Per-variant metric so the two trials are distinguishable in the DB.\nmetric = 0.50 if stem.endswith("a") else 0.75\npathlib.Path("sentinel_" + stem + ".txt").write_text("ran", encoding="utf-8")\n\nkv = (\n    "---\\n"\n    "status: completed\\n"\n    "primary_metric: " + str(metric) + "\\n"\n    "metric_name: demo_metric\\n"\n    "training_gates_passed: true\\n"\n    "---\\n"\n)\n# The marker file lands next to the config: inside the trial directory for\n# staged trials (relative config), in the session workspace otherwise —\n# exactly the resolution order output_parser.fallback + trial candidates\n# implement server-side.\n(cfg.parent / "{marker}").write_text(kv, encoding="utf-8")\nprint(kv)\n'.replace('{sleep}', str(_SLEEP_S)).replace` |
| [test_phase_evidence_dedup_inherit](modules/test_phase_evidence_dedup_inherit.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_promotion_approval](modules/test_promotion_approval.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_promotion_diagnostics](modules/test_promotion_diagnostics.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_prompt_promotion_policy](modules/test_prompt_promotion_policy.md) | `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_research_api_compat](modules/test_research_api_compat.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_research_api_integration](modules/test_research_api_integration.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_research_manifest](modules/test_research_manifest.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_result_artifact_ingestion](modules/test_result_artifact_ingestion.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_results_store_manifest_snapshots](modules/test_results_store_manifest_snapshots.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_results_store_migrations](modules/test_results_store_migrations.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_runtime_recovery](modules/test_runtime_recovery.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_service_preflight](modules/test_service_preflight.md) | `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_session_failure_modes](modules/test_session_failure_modes.md) | `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_session_status_routing](modules/test_session_status_routing.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.modules['anthropic'] = types.SimpleNamespace` |
| [test_significance](modules/test_significance.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_skill_loader](modules/test_skill_loader.md) | `STUB_SETTINGS = _StubSettings` |
| [test_skill_prompt_engineering_e2e](modules/test_skill_prompt_engineering_e2e.md) | `sys.modules['openai'] = types.SimpleNamespace`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_skills_api](modules/test_skills_api.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_skills_generate_api](modules/test_skills_generate_api.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_stagnation_phase_genuineness](modules/test_stagnation_phase_genuineness.md) | `os.environ.setdefault`, `os.environ.setdefault`, `_stub = types.SimpleNamespace`, `sys.modules['anthropic'] = _stub` |
| [test_state_machine](modules/test_state_machine.md) | `os.environ.setdefault`, `os.environ.setdefault`, `sys.path.insert` |
| [test_trial_workspace](modules/test_trial_workspace.md) | `os.environ.setdefault`, `os.environ.setdefault` |
| [test_webhook_promotion](modules/test_webhook_promotion.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [test_ws_event_enrichment](modules/test_ws_event_enrichment.md) | `os.environ.setdefault`, `os.environ.setdefault`, `os.environ.setdefault` |
| [run-production-ops-tests](modules/run-production-ops-tests.md) | `root = dirname`, `outDir = join`, `mkdirSync`, `writeFileSync`, `execFileSync`, `compiledPath = findCompiledModule`, `ok`, `compiledClientPath = findCompiledModule`, `ok`, `test`, `test`, `test`, `test`, `test` |
| [DynamicFormFields](modules/DynamicFormFields.md) | `KNOWN_TYPES = Set` |
| [DynamicFormFields.test](modules/DynamicFormFields.test.md) | `describe` |
| [IterationsTable.test](modules/IterationsTable.test.md) | `describe` |
| [MetricsChart.test](modules/MetricsChart.test.md) | `describe` |
| [PromotionModal.test](modules/PromotionModal.test.md) | `mock`, `describe` |
| [useWebSocket](modules/useWebSocket.md) | `WebSocketContext = createContext` |
| [ui_src_main](modules/ui_src_main.md) | `queryClient = QueryClient`, `render` |
| [NewResearch.test](modules/NewResearch.test.md) | `mock`, `describe` |

## Factory / wiring

<!-- Heuristic, name-based detection of app-factory / wiring functions. -->

| Function | Kind | Module |
|----------|------|--------|
| `register_prompt` | wiring | [examples_prompt-registry_main](modules/examples_prompt-registry_main.md) |
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
