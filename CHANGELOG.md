# Changelog

## Unreleased

### Added
- **Universal Research Harness & External Driver Adapters:**
  - Extracted the domain-neutral `ResearchKernel` (`src/core/research_kernel.py`) and versioned `HarnessAdapter` SDK (`src/core/harness_sdk.py`) with explicit capability descriptors (`pause`, `resume`, `steering`, `native_resume`).
  - Added `BuiltinHarnessAdapter` (`src/core/builtin_harness.py`), `CodexHarnessAdapter` (`src/core/codex_harness.py`, consuming `codex exec --json`), `ClaudeCodeHarnessAdapter` (`src/core/claude_code_harness.py`, consuming Claude Code programmatic JSONL streams), and `SubprocessDriverHost` (`src/core/driver_host.py`) for custom JSONL drivers.
  - Added the `/api/v1/harnesses` catalog and run-capability inspection endpoints (`src/api/harnesses.py`) and updated the UI (`NewResearch`, `ResearchDetail`) to surface adapter selection, capability-gated controls, and explicit refusal reasons.
- **Scoped Attached-Agent API & CLI:**
  - Added `/api/v1/agent/*` (`src/api/agent.py`) and `autoresearch agent` CLI subcommands (`src/agent_cli.py`) allowing external agents to attach with short-lived, run-scoped, revocable credentials (`read`, `submit`, `evaluate`, `lifecycle`) without receiving operator or production-approval authority.
- **Enforced Linux Process Isolation & Resource Quotas:**
  - Added OS-level execution isolation (`src/core/isolation_backend.py`) with read-only root/evaluator mounts, isolated candidate workdirs, default-deny network egress (`unshare`), process-tree cancellation, cumulative CPU and RSS caps, `RLIMIT_FSIZE` write quotas, and bounded output streaming (`src/core/plugin_runner.py`, `src/core/command_runner.py`).
  - Added descriptor-relative, symlink-safe filesystem confinement (`src/core/safe_fs.py`) and unified `ExecutionRequest` resolution (`src/core/execution_request.py`) across live and demo runs.
- **Evaluator-Authenticated Result Receipts & Domain Semantics:**
  - Added server-verified result receipts (`src/core/result_authority.py`) binding evaluator output directly to attempt, candidate, evaluator, and dataset digests.
  - Added unified objective comparison (`src/core/objective_comparison.py`) supporting minimization (`lower_is_better`), maximization (`higher_is_better`), epsilon ties, replication/significance policies (`src/core/replication_policy.py`), and Pareto multiobjective frontiers (`src/core/multiobjective.py`).
  - Added standard JSON Schema Draft 2020-12 parameter validation and declarative parameter-to-work bindings (`src/core/skill_params.py`).
  - Added comparable-context leaderboard grouping (`GET /api/v1/skills/{id}/leaderboard`) so sessions rank only within matching objective, unit, dataset, scorer, and fidelity contexts.
  - Added measured latency-minimization benchmark support (`src/core/latency_benchmark.py` and `skills/latency-benchmark/`).
- **Durable Run Specifications, Leases, & Event Replay:**
  - Added immutable persisted `RunSpec` (`src/core/run_spec.py`), atomic work-admission leases, budget reservations (`src/core/usage_accounting.py`), and cursor-addressable WebSocket event outbox replay with resync fallback.

### Changed
- Tightened Pydantic contract models across API requests and versioned contracts to reject undeclared fields (`extra="forbid"`) and normalized JSON-destined serialization (`model_dump(mode="json")`).
- Updated `LICENSE` copyright attribution to `Autoresearch Agent maintainers` and added PEP 621 `keywords` and `classifiers` to `pyproject.toml`.

## 0.1.0 (2026-09-19)

### Added
- **Manifest-Driven Skill Architecture (`research_skill.v1`):**
  - Domain-neutral `ManifestSkillRuntime` (`src/core/skill_runtime.py`), `SkillRegistry` (`src/core/skill_registry.py`), and `SkillLoader` (`src/core/skill_loader.py`) driving prompts, phases, default-deny command policies, output parsers, preflight checks, metric schemas, and promotion targets from `skills/<id>/SKILL.yaml`.
  - Bundled three `research_skill.v1` packages in release archives and Docker images: `prompt-engineering` (`openai` provider, controlled scorer, `registry_api` promotion), `code-refactor` (offline AST/lint/test evaluator, `file_path` promotion), and `db-config-tuning` (deterministic offline throughput/latency simulator, `file_path` promotion).
  - Added the Skill SDK CLI (`autoresearch new-skill`, `autoresearch promote-skill`), `PluginRunner` / `BootstrapRunner`, lexical `DomainClassifier`, and `SkillGenerator` for drafting and promoting new skills.
  - Added zero-credential demo mode (`AUTORESEARCH_DEMO=true`) backed by `MockProvider`, refused automatically when `ENVIRONMENT=production`.
- **Promotion Pipeline & Cryptographic Production Approvals:**
  - Candidate-bound `hmac-sha256-v2` (`production-approval.v2`) cryptographic approval verification (`src/core/promotion_approval.py`) binding `research_id`, canonical `scope`, `approver`, `iteration`, `config_snapshot_sha256`, and `target_identity`.
  - Added `FilePathPromotionTarget` (atomic write with sidecar metadata and rollback snapshots) and `WebhookPromotionTarget` (idempotent HTTP delivery with retries and durable `target_descriptor` rollback), plus an example receiver in `examples/prompt-registry/`.
- **State Storage & Multi-Worker Support:**
  - Default single-instance `SQLiteStateStore` (`src/core/state_store.py`) with automatic numbered schema migrations (`schema_version`) and online backup support.
  - Optional `PostgresStateStore` (`src/core/postgres_state_store.py`) enabled via `AUTORESEARCH_DATABASE_URL` (`postgresql://...`) with transaction-scoped advisory locks (`pg_advisory_xact_lock`), fencing epochs (`lock_epoch`), cross-worker `stop`/`pause`/`resume` propagation, and an idempotent SQLite-to-Postgres migration script (`scripts/migrate_sqlite_to_postgres.py`).
- **Observability, Security, & Operations:**
  - Prometheus `/metrics` exposition with dedicated bearer-token authentication (`AUTORESEARCH_PROMETHEUS_TOKEN`), `/health`, `/health/ready`, and `/monitoring/health` readiness probes.
  - Operator bearer-token authentication (`AUTORESEARCH_API_TOKEN`) and optional RFC 7666 OAuth2 token introspection (`AUTORESEARCH_IDENTITY_INTROSPECTION_URL`).
  - Default-deny subprocess environment sanitization stripping control-plane secrets from governed child processes.
