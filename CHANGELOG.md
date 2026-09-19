# Changelog

## Unreleased

- Nothing yet.

## 0.1.0 (2026-09-19)

- **Non-ML sessions are real.** Every bundled skill can
  start, run to iterations, and promote through the public API and UI —
  proven by an API-level end-to-end suite (`tests/test_non_ml_session_e2e.py`)
  and a scripted Docker smoke (`scripts/smoke_docker.sh`), both release
  gates. **Two breaking changes** ride with this work (0.x semver; callers
  must adapt):
  - *Breaking:* production promotion approval is the candidate-bound
    `hmac-sha256-v2` scheme — see the pre-release hardening entry below and
    RUNBOOK → Promotion Scopes. Legacy `{research_id}:{scope}:{approver}`
    signatures are rejected.
  - *Breaking:* the start API fails fast instead of 201-then-crash. An
    unknown `skill_id` (or a legacy `model_type`-only request whose
    translated id — `direction` → `ml-direction` — is not installed) is a
    4xx `skill_not_found` naming the available skills; sessions must name an
    installed skill. `ml-direction`/`ml-volatility`/`ml-rl` are **not
    installed** in this release — historical rows still read correctly, and
    reinstalling an ML skill re-enables legacy callers with zero code
    changes.
  - *Executable skills in this release:* the three bundled skills start,
    run, and promote through the public API and UI. `code-refactor` and
    `db-config-tuning` are fully offline (deterministic evaluators, no
    external services). `prompt-engineering` runs its offline fallback
    scorer in demo mode; live scoring requires an operator-provided
    `skill_params.scorer_url` (or the demo fallback) — without one it fails
    closed rather than fabricating a metric. All three are
    development-scope promotable; production scope requires the signed
    approval above.
  - **Manifest v3** (`research_session_manifest.v3`): `skill_id` is
    authoritative and required; `model_type` is a derived, write-dead legacy
    alias with a closed vocabulary (`^(direction|volatility|rl)?$`, empty =
    no alias). v1/v2 manifests load and normalize unchanged. Non-ML
    manifests are sourced entirely from the skill's SKILL.yaml — no
    fabricated ML provenance — and section requirements are profile-based.
  - **Non-ML promotion is wired.** One target-resolution site
    (`promotion_target_from_manifest`) serves the API, the orchestrator
    auto-promote path, and preview/confirm: `file_path` skills promote to
    their declared `path_template` (validated at skill load, confined under
    the host-configs root; the generic layout is only the default template),
    and `registry_api`/`webhook` skills deliver to their declared endpoint
    with an idempotency key + retries (fail-closed) and a durable
    `target_descriptor` for restart-safe rollback. Preview/confirm responses
    carry the skill-appropriate `target_kind`. Promotion consistency checks
    are skill-proportional: ML serving-era evidence (artifact refs,
    inference parity, smoke validation, serving rollback targets) no longer
    hard-blocks sessions that run an installed skill — the skill's declared
    metric gates and the target's own rollback semantics govern instead.
  - **Failure semantics.** A background task that crashes now persists a
    terminal `failed` state (`error_message` +
    `terminal_reason=background_task_crashed:<type>`) within one event-loop
    turn — never a zombie `running` row — without ever overwriting a status
    the orchestrator already set. Skills whose bootstrap cannot render the
    workspace refuse the start.
  - **Demo mode runs the real flow.** `AUTORESEARCH_DEMO=true` sessions now
    execute the skill's declared `prompt.demo_experiment_command` (offline
    evaluator, `{session_workspace}` placeholders, validated at load) under
    the governed command policy, and the scripted provider relays the
    governed eval's `ITERATION_RESULT` marker verbatim — the whole loop
    (bootstrap → governed eval → nonce-verified iterations → results →
    promotion preview) works with no LLM keys. The session start path runs
    each skill's `bootstrap.py`; skills declare
    `command_policy.config_flag` (`--prompt`/`--target`) so per-iteration
    config snapshots and policy confinement work for non-ML artifacts.

- **Pre-release hardening (7 release blockers).** Addresses findings from a
  release-readiness review; the promotion-approval change is **BREAKING** for
  existing production approvers (see RUNBOOK → Promotion Scopes).
  1. **Production approval alias bypass — closed.** `promote/confirm` and
     `promote/preview` normalize `scope` through the promoter's canonical
     resolver before the gate, so `prod`/`live`/whitespace/padded values now
     require the signed approval instead of skipping the HMAC check.
  2. **Approval bound to the approved candidate (v2).** New pure module
     `src/core/promotion_approval.py`: `canonical_approval_message` (stable
     JSON, `hmac-sha256-v2`, schema `production-approval.v2`) covers
     `research_id`, canonical `scope`, `approved`, `approver`, `method`,
     `reason` **plus** `iteration` + `config_snapshot_sha256` +
     `target_identity`. `ConfigPromoter.confirm` re-binds the supplied
     candidate to its own fresh preview and fails closed on mismatch, so a
     signature for candidate A can no longer authorize candidate B. Legacy
     `"{research_id}:{scope}:{approver}"` signatures are rejected. Preview
     exposes `target_identity`; confirm persists `target_descriptor`
     (endpoint/path, auth env-var *name* only) for durable rollback.
  3. **Webhook rollback now restores the remote system.** `rollback()` rebuilds
     the destination from the recorded `target_descriptor` instead of using the
     singleton file target, and `WebhookPromotionTarget.restore()` delivers
     with an operation-scoped idempotency key (so restoring A after B is not
     deduplicated as the original A). Delivery failure leaves the local
     provenance copy untouched and raises instead of reporting success.
     `write()` delivers before advancing the local copy.
  4. **Prompt evaluator fails closed on real scoring.** Hash-derived fallback
     scores are now explicit demo-only (`--demo true`); live runs with no
     scorer, or any remote/scorer failure, emit `eval_error` with a null metric
     and `training_gates_passed=false` (exit 1). The selected `eval_set` is
     honored (validated for size/format/symlinks/traversal), the chosen scorer
     URL is wired through the manifest command, and the governed child env is
     threaded from server settings rather than ambient credentials.
  5. **Bundled skills ship in release artifacts.** `pyproject.toml` declares an
     explicit allowlist of the three bundled skills for sdist+wheel (so
     `skills/_drafts` and unbundled dirs never ship); `Dockerfile` copies
     `skills/` to `/app/skills/`. CI builds archives, asserts their contents,
     and smoke-tests an installed wheel from outside the checkout.
  6. **Compose env overrides match the docs.** `AUTORESEARCH_DATABASE_URL` uses
     `${VAR-default}` (unset-only) so an explicit empty value selects SQLite,
     and the published port defaults to loopback
     (`${AUTORESEARCH_BIND_HOST:-127.0.0.1}`). Postgres keeps no host port.
  7. **Output capture is memory-bounded.** Child stdout/stderr stream to
     quota-limited per-session logs with fixed head/tail buffers (including
     newline-free data), `grep` drains pipes incrementally with a real
     deadline, and `read_file` no longer materializes whole large files.
  Also: `Settings` no longer requires Anthropic credentials in demo mode;
  provider base URLs default sensibly; mypy/ruff cleanups in
  `skill_registry`/`domain_classifier`/`output_parser`/`preflight`; the
  promotion parity fixture redacts the derived `target_identity`.

- **Useful-area push — real skills, demo mode, leaderboard, webhook
  promotion, and the first orchestrator split.**
  - **Real scorer chain (prompt-engineering).** The eval scorer is no
    longer a sha256 stub: `--scorer-url`/`SCORER_URL` remote scorer →
    OpenAI judge (`OPENAI_API_KEY`, judge capped at 50 examples) → the
    deterministic offline fallback (flagged `scorer: fallback`). The
    `ITERATION_RESULT:` + `server_nonce` anti-forgery contract is unchanged;
    the winning scorer link is recorded in the metrics (`scorer` field).
  - **Two offline real skills.** `skills/code-refactor/` (syntax + lint
    + JSONL test-ledger scorer) and `skills/db-config-tuning/` (deterministic
    offline TPS/latency bench model) join `prompt-engineering` as installed
    `research_skill.v1` packages — both validate through the loader, pass the
    domain-coupling guard, and run their eval CLIs with zero network.
  - **Demo mode.** `AUTORESEARCH_DEMO=true` routes every LLM call to the
    zero-credential `MockProvider` (scripted edit-run-keep loop, $0 cost) —
    `docker run -e AUTORESEARCH_DEMO=true` shows a working session with no
    API keys. The provider router refuses the mock when
    `ENVIRONMENT=production` (fail-closed).
  - **Leaderboard.** New `GET /api/v1/skills/{id}/leaderboard` —
    cross-session comparison ranked by the skill's declared primary-metric
    direction (legacy `model_type` aliases merged), with limit + graceful
    no-store behavior. New UI Leaderboard page (skill picker + ranked table)
    wired into the topbar; the Dashboard's fabricated 3-point sparkline is
    replaced with the session's real metric series.
  - **Webhook promotion (end-to-end).** New `WebhookPromotionTarget`: keeps the
    full gate/metadata/rollback machinery, writes a local provenance copy
    under `<workspace>/promotions/`, and delivers the primary config to the
    declared endpoint with an `Idempotency-Key`, optional Bearer auth
    (`auth_secret` names the env var), 5xx retries, and fail-closed delivery
    errors. Manifest `promotion_target.kind: webhook` is a new schema kind;
    `registry_api` with an endpoint now builds the same delivery target
    (was: audited `unsupported_promotion_target` skip). The manual
    preview/confirm API path picks the session's skill target via
    `_promoter_for_session`; the UI confirm now sends an `Idempotency-Key`.
    `examples/prompt-registry/` ships a runnable receiver proving the loop.
  - **Orchestrator split (first slice).** The agent tool surface —
    `ToolExecutionResult`, `AGENT_TOOLS`, path-safety helpers, the five tool
    implementations, the packaged-primer loader, and the per-command nonce-env
    narrowing — moved verbatim to `src/core/agent_tools.py` (mypy-clean and
    NOT excluded from type checking), with back-compat re-exports in
    `orchestrator.py` (4887 → 4511 lines). One test patch-seam updated.
  - **Legacy quarantine.** New `src/compat/` package:
    `legacy_alias.py` moved (core module is now a shim; all importers
    unchanged), the RL/feature-readiness enrichment helpers moved out of
    `api/results.py` into `src/compat/ml_enrichment.py`, and the historical
    phase tables (`DIRECTION_PHASES` / `VOLATILITY_PHASES` /
    `FALLBACK_PHASES`, `phases_for_model`, `RL_OOS_EVIDENCE_KEYS`,
    `_PHASE_PRIMARY_SWEEP_KEYS`) moved out of
    `src/core/research_phase_plan.py` into
    `src/compat/legacy_phase_tables.py` (1361 → 1095 lines of live
    machinery, re-exported for every existing importer). The slimmed
    `research_phase_plan.py` is now E501-clean, guard-clean without an
    exemption, and **removed from the mypy exclude list** (type-checked,
    zero errors). The domain-coupling guard now documents the compat
    exemptions by name.
  - **Parallel-trial plumbing.** New manifest
    `execution.concurrency` (1..3, default 1 = today's sequential behavior)
    exposed through the `SkillRuntime` protocol. Actual parallel dispatch is
    staged behind the field — the sequential loop's per-command state must
    become per-workdir first.
  - **Per-workdir trial state (the ``execution.concurrency``
    prerequisite).** New `src/core/trial_workspace.py`: a `TrialContext`
    per bash command carries the execution workdir (session workspace by
    default — byte-identical behavior), and a skill opted into
    `execution.concurrency > 1` gets each *sanctioned* experiment command
    (one invoking a manifest-declared `allowed_scripts` entry — the same
    predicate as the nonce narrowing) executed inside its own staged
    trial directory under `<workspace>/.trials/turn-XXX-seq-YY/`: a copy
    of the session state (server logs/snapshots/caches excluded, staging
    fail-opens to the session workspace). Threaded through the loop: the
    pre-run `--config` snapshot resolves against the trial copy
    (containment still anchored to the session workspace), the governed
    subprocess runs with `cwd=` the trial dir (`GovernedCommandRunner` /
    `_tool_bash` / `_execute_tool` gained the `cwd` override), the
    marker-file fallback checks the trial dir first (stale staging copies
    discarded by the existing `min_mtime` check), and the runtime-command
    record + recorded-iteration metadata carry `trial_dir`/`trial_seq`
    provenance. The parallel `asyncio.gather` dispatch itself is the next
    step — the stateful parts (duplicate guard, runtime records, iteration
    recording) stay sequential and are now per-workdir-safe.
  - Tests: `test_mock_provider.py`, `test_leaderboard_api.py`,
    `test_webhook_promotion.py`, `test_execution_concurrency.py` added
    (25 new tests); the registry_api skip pin in
    `test_manifest_runtime_production_path.py` updated to the new delivery
    contract. ruff clean; mypy delta vs HEAD is zero new errors
    (`research_phase_plan.py`, `agent_tools.py`, and the compat phase tables
    are now type-checked with zero errors; `ml_enrichment.py` keeps its
    pre-move excluded posture — the code was excluded in `api/results.py`);
    domain-coupling guard clean with `research_phase_plan.py` off the
    exemption list.

- **Universal research system conversion — the previous platform's artifacts removed.**
  The service is now a domain-neutral research agent driven entirely by
  installed skill packages (`skills/<id>/SKILL.yaml`).
  - Removed the vendored platform packages and their path dependencies; the X-Request-ID
    header middleware, OAuth2 token introspection, and logging are inlined
    as small generic implementations. Vault settings loading removed
    (env/.env only).
  - Removed the three trading skills (ml-direction/ml-volatility/ml-rl),
    the workspace autotuner skill copies, gate bundles, and the trading
    CLAUDE.md; `prompt-engineering` is the reference skill. The workspace
    venv is a slim generic baseline.
  - The legacy ML orchestrator path (~1000 lines) and the three transitional
    runtimes are gone; `ManifestSkillRuntime` is the only runtime and
    every session must name an installed skill. Prompts, phases, command
    policy (default-deny), parsers, marker fallbacks, preflight, and
    promotion targets all come from the manifest.
  - Pipeline mode (direction→volatility→rl orchestration), the structured
    HPO trial planner, and the platform evidence collector (inference
    paper-replay) are removed. Preflight checks are skill-declared.
  - Platform service settings (mlflow-service, data-ingest, trainers,
    feature/inference/admin/messaging URLs, service tokens, artifact-store
    flags) removed; optional MLflow tracking stays generic. mlflow-service
    composite promotion removed — promotions record locally; unsupported
    targets skip loudly.
  - Trading request fields (trading_mode/agent_strategy/initial_balance,
    flat HPO knobs) removed from the API; `model_type` accepts any skill id
    (identity alias fallback), legacy URL/field aliases keep working.
    `/instruments` and `/pipelines` endpoints removed; `/models` lists
    installed skills.
  - Promotion targets use the generic `<skill>/<subject>_<variant>.yaml`
    layout; the promote.py subprocess handoff is replaced by the atomic
    direct write (metadata sidecar first).
  - The UI drops the trading controls; skill pickers, manifest-driven form
    fields, metric schemas, and Subject/variant vocabulary throughout.
  - Internal review and planning documents are archived outside the
    repository rather than shipped. A
    domain-coupling guard (`scripts/check_domain_coupling.py`) runs in CI.

- **Cross-worker
  stop/pause/resume works at the SessionManager entry point.** All four control methods
  (`stop_session` / `pause_session` / `resume_session` / `stop_pipeline`)
  began with an `_active`-registry early return BEFORE writing any DB
  intent — under `WEB_CONCURRENCY > 1` with a non-sticky load balancer, a
  request routed to a worker that did not own the session returned False and
  wrote nothing, so the owning worker's DB-side polls never fired (the
  fencing tests bypassed `SessionManager`, leaving the gap untested).
  - **Sessions:** each control method now writes the DB transition FIRST
    (state machine under the advisory lock); local ownership only adds the
    fast path (in-process flag + task drain, no poll latency). A non-owning
    worker records `stopping`/`paused`/`running` and the owner observes it
    (`_should_stop_cross_worker` for stop; see the pause fix below). A
    stop against an unknown id returns False (`LookupError`); terminal
    rows remain idempotent no-ops (status never clobbered).
  - **Pause observation (the other half):** `_wait_while_paused` previously
    spun only on the in-process `_pause_flags` — a DB-side `paused` (recorded
    by any worker) was invisible, and a locally-paused owner could never be
    unstuck by a cross-worker resume. The DB status is now authoritative:
    wait while it says `paused`; proceed when it says `running` again (even
    with a stale local flag); a store-read failure fails closed to the local
    flag (a blip must not un-pause). The captured `lock_epoch` is refreshed
    after any observed pause/resume.
  - **Pipelines (same fix):** `stop_pipeline`
    records `status='stopping'` before the local-registry check (terminal
    rows refused, not clobbered) and forwards the stop to every recorded
    phase session — `stop_session` records DB intent even for non-owned
    sessions, so the owner's current phase session stops mid-run too. The
    owning `PipelineController`'s phase-loop poll consults the DB row
    (`_stop_recorded_db`; read failures fail closed to the local flag).
  - **Tests:** new `tests/test_cross_worker_control.py` (9 tests): non-owner
    stop/pause/resume record DB intent (and the owner's poll observes it —
    the cross-worker loop closed at unit level), unknown/terminal no-ops, the local
    fast path unchanged, DB-side pause observation + cross-worker-resume
    unstick + epoch refresh, pipeline DB intent + terminal-row refusal +
    controller poll. The distributed harness gains
    `test_distributed_session_manager_stop_records_intent` — a real
    multi-process worker stopping through the REAL `SessionManager` entry
    point (previously the harness bypassed it, which is why the bug was
    invisible); runs in the dedicated Postgres CI job. Full suite green
    (1369 passed); ruff/mypy at the pre-existing baseline (91/15, zero
    new); domain-coupling guard green.

- **A non-ML session now actually runs end-to-end on the
  OpenAI provider.** An earlier close-out had claimed this while no session
  had ever run; the fixes below make it true, and
  `tests/test_skill_prompt_engineering_e2e.py::
  test_prompt_engineering_session_end_to_end` proves it: a real
  `AgentOrchestrator.run()` drive on a real `OpenAIProvider` (scripted only
  at the HTTP client boundary — the wire translation runs for real), the
  REAL governed `eval/run.py` subprocess executing under the skill's
  manifest command policy, the anti-forgery nonce verified in the live loop, a
  forged marker rejected + audited, and a `research_sessions` row
  indistinguishable from an ML row (best_iteration,
  effective_iteration_count, terminal_reason) — closing the
  cross-skill equivalence gap the review noted (no earlier test asserted it for a non-ML
  skill).
  - **Skill scripts execute from the packaged tree (command-policy
    wiring):** skill manifests declare scripts workspace-relative
    (`eval/run.py`); the extension unions the declared names into the
    allow-set but the files live in the read-only packaged `skills/<id>/`
    tree. `ManifestSkillRuntime.command_policy_extension()` now emits a
    `script_paths` map (declared name → packaged absolute path), and
    `evaluate_command_policy` rewrites argv to the packaged file whenever
    the declared script is not present under the runtime workspace root.
    Deliberately NOT resolved against the session workspace — it is
    agent-writable (`write_file`), and name-based allowing there would be
    arbitrary code execution.
  - **Store accepts non-ML sessions:** `create_session` (SQLite +
    Postgres parity) KeyEd on `model_type=""` (the API's canonical
    translation for skills with no legacy alias) via `_MODEL_TO_SKILL[...]`;
    now `.get(model_type, model_type or "")` — the column is display-only.
  - **Manifest phases without `next_action` no longer crash the loop**
    (`research_phase_plan._next_action`: the optional field coalesces
    instead of `None + str`).
  - **Skill-declared scripts count as training commands:** the
    `turn_ran_training_command` guard recognized only the ML script
    families, so a relayed marker after a non-ML eval was rejected ("no
    training command was executed this turn"). A session's declared
    `allowed_scripts` now qualify.
  - **Server-side decision inference for relayed markers:** non-ML eval
    markers carry no `decision` (the scorer has no session-best context);
    the marker-record branch infers it via `_infer_decision` (same as the
    KV auto-detect path) so `best_iteration` advances on gates-passing
    improvements. Presence-checked — ML markers with a decision are
    unaffected.
  - **bootstrap.py ported to the governed JSON ABI** (
    the argparse CLI was incompatible with `PluginRunner`, which fails
    closed on non-JSON stdout, and was invoked by nothing). The e2e drive
    renders its workspace through the real `PluginRunner`. The eval script
    is NOT copied into the workspace (it executes from the packaged tree).
  - **Eval marker completeness:** `eval/run.py` emits
    `training_gates_passed` (its own gates) so downstream consumers —
    decision inference, promotion gates — read the field every iteration
    recorder expects.
  - **Promotion preview for non-file targets:** `POST
    /research/{id}/promote/preview` on a non-ML session hit the
    file-target path derivation's "Unknown model type" ValueError and
    surfaced a misleading 404; it now returns a structured 422
    (`reason: unsupported_promotion_target`, the audited auto-promotion-skip
    vocabulary). Test added in `test_research_api_integration.py`.
  - Also: the e2e file's phantom task reference removed; its docstring no longer claims the milestone was validated by
    mocked-provider tests. Full suite green (1360 passed); domain-coupling
    guard green; ruff/mypy at the pre-existing baseline (91/15, zero new).

- **Anti-forgery: bypass
  closed, nonce no longer readable by the adversary it defends against.**
  Closes the anti-forgery bypass findings (all four sub-findings); the design
  lives in the signed-metrics module docstrings.
  - **KV-block bypass closed:** the `---` auto-detect path and the
    marker-file path called `parse_prepare_output` (no nonce argument), so
    any bash output containing a KV block was recorded as an iteration even
    for skills with `require_signed_metrics: true`. Both paths now route
    through the new `AgentOrchestrator._verify_kv_metrics`, which applies
    the same four-state `_verify_nonce` check the marker path uses
    (reject → iteration not recorded).
  - **KV forgeries audited:** rejected KV blocks now emit the
    `metrics.forged` audit event (`format: delimited_kv`, `source:
    bash_output|marker_file`) plus agent-log guidance — previously only
    marker-format forgeries produced an audit.
  - **nonce out-of-band:** the nonce is no longer embedded in the
    session manifest. The artifact is written into the agent-readable
    session workspace (traversable by the `read_file`/`grep` tools), so
    persisting the nonce secret there handed it to the adversary. The nonce
    is generated in `SessionManager._build_manifest_payload` and lives only
    in `config.session_nonce` (process memory, per-run); nothing ever reads
    it back (continues/resumes generate a fresh nonce). The
    `session_nonce` field stays in the v2 manifest schema, always `null` in
    new artifacts (schema shape unchanged; legacy manifests with a value
    still load). Parity fixtures unaffected (the engine already dropped the
    non-deterministic nonce key).
  - **nonce env narrowed:** `AUTORESEARCH_SESSION_NONCE` is no
    longer injected into every governed subprocess of every session. The
    env is built only when the skill enforces signed metrics (new
    `requires_signed_metrics` / `nonce_field` runtime capabilities; the
    transitional runtimes report `False` — byte-identical ML/legacy
    behavior), and per command only when the command invokes one of the
    skill's manifest-declared scripts (`_nonce_env_for_command`). A false
    negative is loud, not silent: the eval cannot echo the nonce and its
    markers are rejected with explicit guidance.
  - **constant-time compare:** `_verify_nonce` uses
    `hmac.compare_digest` (consistent with the production-approval HMAC).
  - Tests: new `tests/test_metrics_forgery_c3.py` (9 tests: KV
    reject/accept/legacy-downgrade/passthrough + audits, workspace-manifest
    nonce omission via a real `SessionManager.start_session` drive,
    per-command env narrowing, capability properties);
    `test_research_manifest.py` nonce tests rewritten for the out-of-band
    contract. Within-session replay after one legitimate eval run remains
    inherent (documented in the ADR revision).

- **Canonical start wiring and the manifest-driven runtime as the production path.** Closes the two
  highest-severity findings of the implementation review: canonical request fields were
  validated-then-dropped, and the orchestrator bypassed the materialized
  `SkillRuntime` for everything except `parse_iteration`.
  - **Canonical start:** `POST /research/start` now forwards
    `skill_id` / `skill_params` / `subject_id` / `variant` to
    `SessionManager.start_session` → `ResearchConfig` (previously dropped
    after validation — a canonical `enable_hpo: true` silently ran with it
    off). Recognized flat ML knobs inside `skill_params` win over the legacy
    kwargs (presence-based, mirroring the API's canonical-wins rule); the
    `research.start` audit metadata records the winning canonical values.
    Legacy callers forward `None` and keep byte-identical behavior.
    Tests: `test_canonical_start_wiring.py` (real SessionManager drive),
    `test_research_api_compat.py` forwarding/audit assertions.
  - **Phase plan:** `_build_phase_contract_block` and
    `_refresh_phase_state` source the phase plan from the session's skill
    runtime (`build_phase_state` gained an explicit `phases=` override; the
    hardcoded per-model table remains only as the transitional fallback for
    sessions with no bound skill). Fail-open: a runtime error falls back to
    the incumbent table rather than blanking the contract.
  - **System prompt:** manifest-driven sessions read the domain
    primer from the packaged `skills/<skill_id>/<primer>` (the primer
    filename honors the manifest's `llm.system_prompt` declaration via the
    new `ManifestSkillRuntime.primer_filename`); transitional sessions keep
    the legacy workspace `.github/skills` primer. A missing packaged primer
    degrades to empty (logged), not a session failure.
  - **Command policy:** `evaluate_command_policy` accepts a
    per-skill `policy_extension` (`CommandPolicyExtension` from
    `skill.command_policy_extension()`), plumbed through
    `GovernedCommandRunner`/`_tool_bash`. **Additive-only** — entries union
    with the base allow-lists; they can never remove or bypass a base
    restriction (executable dispatch and path confinement are checked
    independently). The manifest `command_policy` section is no longer dead
    config.
  - **Blocker classification:** the `SkillRuntime` protocol gains
    `blocker_classification()` (22nd member; transitional runtimes return
    `{}` = use module defaults). The promotion-readiness advisory consumes
    `actionable_blockers` and `_phase_advancement_is_genuine` consumes
    `phase_evidence_keys` as skill-declared overrides of
    `_AGENT_ACTIONABLE_BLOCKERS` / `_PHASE_SPECIFIC_AGENT_KEYS`.
  - **Promotion target:** `_try_auto_promote` routes through the
    session skill's declared `promotion_target`. `ManifestSkillRuntime.
    promotion_target()` now raises the new `SkillConfigError` for non-
    `file_path` kinds instead of silently returning a file target, and
    auto-promotion **skips loudly** (audited `promotion.auto_skip`,
    reason `unsupported_promotion_target`) rather than fabricating a file
    promotion for e.g. a `registry_api` skill; unexpected construction
    errors still fall back to the default file target. **Promoter-injection fix:** the
    six `ConfigPromoter` file-surface helpers are now instance methods
    dispatching through the injected `PromotionTarget` (previously the
    injection was stored but bypassed — every helper constructed a fresh
    `FilePathPromotionTarget()` inline); a recording-stub test now pins the
    dispatch.
  - **Materialization loudness:** `materialize_skill_runtime`
    raises `SkillConfigError` for an explicit `skill_id` the registry
    rejects (missing/invalid/removed-by-reload) instead of silently
    degrading a canonical session to the transitional runtime. Legacy
    sessions (`skill_id=""`) are unaffected.
  - **Manifest honesty:** the three ML `SKILL.yaml`s declare
    `phase_advancement.mode: declarative` / `trial_identity.resolve.mode:
    declarative` — the previously-declared `phases.py` /
    `resolve_identity.py` plugin files never shipped and were never
    imported (dead declarations).
  - Orchestrator bookkeeping: `_session_skills` registry initialized in
    `__init__` (registered at runtime materialization, dropped in the
    `run()` finally); missing-typing-name lint debt (`Any` /
    `Iterable`) fixed in the new annotations. New
    `tests/test_manifest_runtime_production_path.py` (26 tests) pins the
    whole wiring: phase-plan source (contract renders with the hardcoded
    table made to explode), primer filename, policy additivity + base-
    restriction preservation, blocker overrides both directions,
    unsupported-target skip + transitional back-compat, loud
    materialization. Full suite green (1348 passed); domain-coupling guard
    green; no new ruff/mypy errors (pre-existing baseline
    unchanged).

- **Distributed storage (Postgres backend, multi-worker).** Adds the
  optional Postgres backend that lifts the single-worker ceiling so
  `WEB_CONCURRENCY > 1` is supported, with the four concurrency hazards closed
  and proven by multi-process tests (atomic idempotency, cross-process
  transition serialization, cross-worker stop propagation, fencing-token
  stale-write rejection). **Gated on the DSN:** the
  default deployment is unchanged — `database_url=None` ⇒ `SQLiteStateStore`
  (byte-identical, the WEB_CONCURRENCY>1 guard stays active); set
  `AUTORESEARCH_DATABASE_URL` to a postgresql:// DSN to opt into multi-worker.
  Known remaining gap (documented, out of scope): WebSocket fan-out does not
  span workers. Driven by raw `asyncpg` (mirrors
  SQLiteStateStore's hand-written-SQL shape for parity; `pg_advisory_xact_lock`
  is first-class), NOT SQLAlchemy — deviates from the platform convention but
  matches the existing StateStore style (parity wins).
  - **Design:** the
    four-hazard concurrency model (idempotency / transition critical
    section / cross-worker stop / stale writes), the ContextVar
    connection-sharing design, the fencing-token contract, and the
    SQLite→Postgres locking-site transition table.
  - **Implementation:** new `src/core/postgres_state_store.py` — a 1:1 port
    of all 48 `StateStore` protocol methods to raw asyncpg; the port is split:
    skeleton + schema + writes + factory, then reads + the dual-backend
    parity sweep. The schema is one canonical Postgres DDL
    (all SQLite base + v1–v6 columns, including the missing `insights`/
    `resumed_from`/`pipeline_id`/`hpo_study_id` the parity sweep surfaced) plus
    a `pg_schema_version` row + the `research_sessions.lock_epoch`
    fencing column. `Settings.database_url` + `build_state_store(settings)`
    select the backend; `main.py` uses the factory (SQLite default unchanged).
    Fold-in: `results_store.py` shim re-exports `_migrate_to_v6` (was missing —
    a latent back-compat gap surfaced by this grounding).
  - **Locks:** idempotency reserve-or-return rewritten to atomic
    `INSERT … ON CONFLICT DO NOTHING RETURNING` (no advisory lock needed);
    additive protocol methods `session_lock` (advisory lock CM, no-op on
    SQLite) + `bump_session_epoch` (increments `lock_epoch`, no-op on SQLite);
    `SessionStateMachine.transition` nests `session_lock` inside the in-process
    lock and bumps the epoch on every committed transition.
  - **Fencing + cross-worker control (scope widened):** the original plan
    named only the fencing hazard; grounding showed the cross-worker stop gap
    (cross-worker stop/pause propagation) must close in the same task for
    "correct concurrency semantics" to hold; the scope growth is recorded per
    an established precedent. (a) **Fencing chain:** the orchestrator captures
    the session's `lock_epoch` once at `run()` entry (`_session_epochs`) and
    threads it into the two state-advancing writes in `_record_iteration`
    (`add_iteration` + `update_session(effective_iteration_count=…)`, both
    accepting a `lock_epoch` kwarg on the protocol; SQLite impls accept-and-
    ignore it — single-worker, no stale writers). A 0-row conditional update
    ⇒ the session was deauthorized while the command ran ⇒ the result is
    discarded + a `result.discarded.stale_worker` audit is emitted, so a stale
    worker cannot advance `best_iteration` / `effective_iteration_count` /
    auto-promotion. `finish_runtime_command` is intentionally NOT fenced (it
    writes only the observability-only `runtime_commands` table, keyed by
    `command_id`, and drives no session state); `update_planned_trial_status`
    accepts the epoch for completeness but is not on the hot post-command path.
    The captured epoch is refreshed after a local resume (`_wait_while_paused`).
    An earlier draft guarded `_record_iteration` with a session-status check —
    removed in favor of this epoch fence (status cannot distinguish a
    legitimate `completing → completed` from a cross-worker stop; the epoch
    can). (b) `_should_stop_cross_worker` reads DB-side status so a stop on
    worker B is observed by the owning worker A's turn poll (the in-process
    flag stays the fast path). NOTE: `terminate_request_received` is the
    agent's own TERMINATE_REQUEST completion flag, NOT an operator-stop
    signal — it must not be treated as a cross-worker stop (a first draft did,
    misreading normal completions as stops; corrected).
  - **Migration:** `scripts/migrate_sqlite_to_postgres.py` —
    idempotent, resumable, batched SQLite→Postgres row mover (per-table
    transactions + a `migration_state` cursor + `ON CONFLICT DO NOTHING`).
    Validated end-to-end (round-trip equality on all 9 tables + re-run
    idempotency). `compose/autoresearch.yml`: adds `AUTORESEARCH_DATABASE_URL`
    env + `postgres_db` dependency.
  - **Guard:** `_validate_runtime_configuration` (`main.py`) is now
    conditional — SQLite/no-DSN ⇒ still rejects >1 (single-writer constraint intact, byte-identical
    default); Postgres DSN ⇒ allows >1 and logs the effective
    `max_concurrent_sessions × N` ceiling. `SQLiteStateStore` docstring updated
    to point at the conditional guard.
  - **Distributed tests — exit gate:** `tests/test_distributed_state_store.py`
    + a dedicated `distributed` CI job with a `postgres:15-alpine` service.
    Real multi-process (`multiprocessing.spawn`) + real Postgres: exactly one
    idempotency winner across 8 processes, cross-process transition
    serialization, fencing stale-write rejection across processes, +
    fresh-epoch acceptance. All postgres/distributed tests skip cleanly when
    `AUTORESEARCH_DATABASE_URL` is unset (default CI run unaffected); the
    dual-backend parity sweep (`test_postgres_sqlite_parity.py`) proves
    PostgresStateStore ≡ SQLiteStateStore across the full write+read sequence.
  - **Residuals:** doc sync for `PostgresStateStore` /
    `build_state_store` / `session_lock` remains **deferred** — tool not on
    PATH (a persistent residual). No new `domain_coupling_rules.conf`
    rule for this phase (the orchestrator is already domain-neutral; this
    phase's exit is operational, not a static-coupling guard — confirmed: no
    new entry in the conf). The phase-marker bump is bookkeeping only (the
    carry-over from the deferred orchestrator migration is noted, not
    force-bumped). The phase-completion rollback tag is deferred to the
    landing commit.
  - **Review-fix round (post-implementation audit):** a self-audit found and
    fixed six issues. (1) `poetry.lock` regenerated — adding `asyncpg` to
    `pyproject.toml` had invalidated the lockfile (`poetry check --lock`, a CI
    gate, was failing). (2) The fencing chain was store-primitive-only and
    unwired at the orchestrator (no epoch capture, no caller passing
    `lock_epoch=`); now wired end-to-end as described above, and the
    misleading status-based `_record_iteration` guard removed. (3)
    `get_cross_session_iteration_summary` dropped `NULLIF` so Postgres
    `STRING_AGG` matches SQLite `GROUP_CONCAT`'s keep-empty-string semantics.
    (4) The parity sweep now also gates `get_cross_session_iteration_summary`
    (incl. the empty-string edge), `find_duplicate_trial_identity`,
    `collect_observability_metrics`, `update_planned_trial_status`, and the
    `session_lock`/`bump_session_epoch` contract. (5) All distributed test
    workers now use a shared pool-only store helper (no worker re-runs schema
    DDL; the earlier asymmetry could intermittently race the `pg_type`
    catalog). (6) `terminate_request_received` aligned to SMALLINT and the
    keyset indexes to DESC, matching their SQLite counterparts. A seventh
    issue surfaced during fix verification and was the most severe of all:
    **`PostgresStateStore.ping()` and `get_schema_version()` leaked a pool
    connection on every call** (the only two methods missing the
    `try/finally: _release_short_lived` pattern). Because `/health` calls
    `ping()` per health check, a Postgres deployment would exhaust the pool
    (10 connections) and wedge; it was also the true cause of the
    long-observed "postgres test file hangs when run together" behavior
    (previously and wrongly attributed to a pytest-asyncio teardown
    interaction — `pool.close()` was waiting forever on the leaked
    checkout). Fixed with the release in `finally`; the full postgres +
    distributed suite now runs together in ~7s where it previously hung.
  - **Verification:** 1315+ autoresearch-agent tests green (incl. the 11
    postgres write-path, parity, fencing, and 4 distributed tests against a
    live `postgres:15` container); postgres/distributed tests skip cleanly
    without a DSN; ruff 0 new errors; mypy 0 new errors on new modules
    (`postgres_state_store.py`, `migrate_sqlite_to_postgres.py`); `poetry
    check --lock` clean. Pre-existing orchestrator/state_store/skill_runtime
    mypy+ruff debt is prior-phase and explicitly out of scope.

- **Auto-initialization, skill lifecycle,
  generator.** Lays the structural foundation for the "universal research agent"
  inflection: full skill-package layout, governed plugin/bootstrap runners,
  skill lifecycle + promotion, lexical domain classifier, insights feedback
  loop, and the skill generator. No behavior change for existing ML sessions
  (parity green); the orchestrator prompt migration is deferred as a
  tracked follow-up.
  - **Full layout:** new `SkillLayout` model
    (`src/core/skill_loader.py`) resolves the skill directory tree
    (`bootstrap.py`, `scaffold/`, `knowledge/{primer,heuristics,prior_findings}`,
    `eval/`, optional `tools`/`parser`/`preflight`/`resolve_identity`). New
    `PluginCaps` / `PluginEntry` / `PluginsConfig` models
    (`src/core/skill_manifest.py`) carry the plugin capability contract
    (`fs_write` / `network_egress` / `env` / `timeout_s` / `max_rss_mb` /
    `max_cpu_s`); per-kind defaults apply when omitted, and a
    manifest may *narrow* but never *widen* a cap (defense in depth).
    `SkillRegistry.discover()` now skips the reserved `_drafts/` subdir;
    `discover_drafts()` enumerates generator drafts separately.
    Back-compat: existing skills with only `SKILL.yaml`/`SKILL.md` resolve to a
    valid minimal layout.
  - **Bootstrap runner epic:** new
    `src/core/plugin_runner.py` (`PluginRunner` — the governed
    subprocess for all skill-supplied Python; JSON-in/JSON-out ABI, strict env
    allow-list narrower than the agent path, psutil RSS/CPU caps, fail-closed on
    crash/timeout/bad-JSON/non-zero, path confinement) and
    `src/core/bootstrap_runner.py` (`BootstrapRunner` — the first `PluginRunner`
    consumer; writes the `session_bootstrap.v1` artifact with rendered file
    hashes; `--dry-bootstrap` overlay mode (a dry-run overlay) for draft/generated
    skill review; idempotency check). The T6 invariant is preserved: a plugin
    parser's output is untrusted candidate data — trust is established
    downstream by `_verify_nonce`, never by the runner.
  - **ML skill backfill:** `skills/ml-direction`,
    `ml-volatility`, `ml-rl` each gain a `bootstrap.py` (thin shim delegating
    to the proven `scripts/autotuner/setup.py` with the right `--models` flag)
    + `knowledge/{primer.md,heuristics.yaml,prior_findings/}` corpus. Live
    execution wiring is the deferred orchestrator migration; the dry-mode path is tested
    end-to-end.
  - **Skill lifecycle epic:** new `src/core/skill_lifecycle.py`
    (`SkillLifecycleState` draft/reviewed/stable/deprecated + the transition
    table + per-skill `asyncio.Lock` machine; production gating predicate —
    drafts never auto-select for production). New
    `SkillRegistryPromotionTarget` (`src/core/promotion_target.py`) moves a
    draft from `skills/_drafts/<id>/` → `skills/<id>/` atomically + rolls back
    on failure; reuses the production-approval machinery at the API
    layer. The HTTP endpoints land in a follow-up wiring the FastAPI
    router.
  - **Domain taxonomy:** `Category` literal widened from 3 to all 5
    values (`optimization|generative|exploratory|validation|design`).
  - **Auto-domain detection:** new `src/core/domain_classifier.py`
    — lexical-first (TF-IDF over hashed word + char n-grams, cosine, stdlib +
    numpy only) behind a swappable `EmbeddingBackend` Protocol so an
    LLM-embeddings backend can drop in later. `DomainClassifier.classify(goal)`
    ranks installed skills; embeddings cached (persisted JSON, invalidated on
    install/reload); cold-start degrades to "list all"; threshold + high/medium/
    low confidence logic; `ClassificationResult.to_audit_dict()` for the
    `skill.classify` audit row.
  - **Skill generator epic:** new `src/core/skill_generator.py`
    — dedicated codegen module calling the
    configured `LLMProvider.complete()` directly with a structured JSON-output
    prompt. Drafts land in `skills/_drafts/<id>/` as `draft` status; manifest
    validated against `research_skill.v1`, Python `ast.parse`-linted; the
    command-policy over-permissiveness audit (`audit_command_policy`) flags
    `rm -rf` / `sudo` / `eval` / shell metacharacters as critical/warning
    findings attached to the draft for reviewer visibility. Safety posture:
    drafts are untrusted code, never production-selectable until promoted
    lifecycle-gated, feature-flagged, and operator-initiated only.
  - **Feedback loop:** new `src/core/insights_feedback.py`
    (`append_findings` writes completed-session insights to
    `knowledge/prior_findings/<subject>_<variant>_<research_id>.md`,
    idempotent on research_id, safe filenames). New manifest fields
    `auto_absorb_insights` (default off), `knowledge_last_reviewed`,
    `refresh_cadence_days` drive the stale-knowledge UI badge.
  - **Orchestrator migration (deferred):** the 61 `prepare.py` /
    `train.yaml` references in `orchestrator.py` are overwhelmingly behavioral
    command-detection / snapshot / parsing logic (not clean prompt-text
    coupling), interwoven through the ~5500-line hot path. A full migration to
    skill-driven command-identifiers is correctly a large follow-up refactor
    that would risk the parity suite; it is tracked as such
    (a dedicated integration branch). The dedicated grep-guard rule
    stays documented-but-inactive (phase stays at 4) until that migration lands.
  - **Tests:** 132 new tests across 8 files (plugin/bootstrap runners, ML skill
    bootstraps, lifecycle + promotion, domain classifier, skill generator,
    insights feedback, manifest-field additions). Full suite 1295 green; ruff
    clean; mypy 0 new errors (15 baseline errors unchanged — all in prior-phase
    modules).

- **Anti-forgery and cross-provider close-out.** Closes
  the three wiring gaps that left the non-ML end-to-end exit guarantee dormant,
  and runs the close-out. The ML eval nonce backfill is deferred —
  ML skills remain on the graceful-downgrade path (`require_signed_metrics =
  false`); the milestone is the non-ML `prompt-engineering` skill. No behavior
  change for ML sessions (parity green).
  - **Nonce delivery:** `session_manager` now populates
    `ResearchConfig.session_nonce` from the built session manifest; the
    orchestrator threads it through `_execute_tool` → `_tool_bash` →
    `GovernedCommandRunner.run(extra_env={"AUTORESEARCH_SESSION_NONCE": ...})`.
    The delivery channel (`command_runner.py`) already merged `extra_env` after
    the forbidden-secret subtraction — it was simply never called. Covered by
    `tests/test_command_policy.py` (runner + full `_execute_tool` chain).
  - **Hot-path wiring:** the orchestrator's marker-parse hot
    path now calls `skill.parse_iteration(text, session_nonce=...)` instead of
    the bare `parse_iteration_marker` facade, so `_verify_nonce` actually fires
    for skills with `require_signed_metrics = true`. Forged markers (wrong /
    missing nonce) return `None` → the iteration is not recorded, and a
    `metrics.forged` audit event + agent-log message make the rejection
    visible. `metrics_verified` / `metrics_unverified` outcomes are audited via
    `metrics.verify`. ML/transitional runtimes ignore the nonce, so the
    parity fixtures stay byte-identical.
  - **Capability matching:** `build_provider`
    accepts `required_capabilities` (built from the manifest's
    `LLMConfig.required_*` via `RequiredCapabilities.from_llm_config`) and
    validates them against `provider.capabilities()`, raising
    `ProviderCapabilityMismatch` (fail-closed) on mismatch. The orchestrator's
    per-session provider selection passes the skill's requirements so a
    mismatch fails the session at start, before any LLM call. Covered by
    `tests/test_llm_provider_openai.py::TestCapabilityMatching`.
  - **Tests:** new/extended tests for all three gaps; parity suite (17
    fixtures) green after teaching the parity engine to DROP the
    non-deterministic `session_nonce` secret from snapshots
    (`_engine._DROP_KEY_RE`) rather than baking it into a golden fixture.
    The domain-coupling rules for the provider imports activated
    (0 violations).
  - **Deferred:** the ML skills' eval scripts echoing the nonce — ML stays on
    `require_signed_metrics = false`; HMAC over the metrics payload and a
    within-session replay counter remain future work. Doc
    sync remains deferred (tool not on PATH — a recurring residual).

- **Review-findings close.** Closes the seven findings from that phase's code review. No behavior change for ML sessions;
  additive-only public-surface changes.
  - **Critical: `openapi.yaml` drift.** An earlier commit `63e817466`
    shipped with `openapi.yaml` not regenerated, so
    `tests/test_openapi_contract.py::test_checked_openapi_yaml_matches_app_schema`
    was red on HEAD. Regenerated from `main.app.openapi()` so the contract
    test passes; the regenerated file now documents the `/api/v1/skills*` and
    `/api/v1/subjects*` paths (10 new paths) and the dual-shape
    `StartResearchRequest` fields (`skill_id`/`subject_id`/`variant`/
    `skill_params`).
  - **`spa_fallback` excluded from OpenAPI.** `main.py`'s SPA catch-all
    (`GET /{full_path:path}`) is now registered with
    `include_in_schema=False`. It is a file-serving fallback, not part of
    the API contract; previously it leaked into the live schema whenever
    `ui/dist/` was built (dev boxes, full image builds), making the contract
    test environment-dependent.
  - **`subjects._get_manifest_or_404` parity with `skills._get_or_404`.**
    `/subjects?skill_id=<unknown>` now returns the same structured 404
    detail (`error`/`skill_id`/`available`/`hint`) as `/skills/{id}` for an
    unknown skill, instead of a bare string. The two skill-id-bearing
    endpoints are now consistent. `test_subjects_unknown_skill_returns_404`
    tightened to assert the structured detail.
  - **`GET /skills/{id}/changelog` size cap.** Returns 413
    `changelog_too_large` (with `size_bytes`/`max_bytes`/`hint`) when the
    skill's `CHANGELOG.md` exceeds 64 KiB, instead of slurping the whole
    file into the JSON response. Forward-looking — no skill ships a
    `CHANGELOG.md` today. New test
    `test_get_changelog_too_large_returns_413`.
  - **`_dual_shape_session` pipeline contract documented.** Pipeline rows
    (`model_type="pipeline"`) are multi-skill containers, not skills, so
    their canonical `skill_id` is empty by design (only `subject_id`/
    `variant` derive from the legacy fields). The docstring now states this
    explicitly; `test_pipeline_row_dual_shape_has_empty_canonical_fields`
    pins the contract.
  - **`promotion.reset()` test-isolation helper.** New `reset()` clears
    `_promoter`/`_store`/`_registry` to their uninitialised state. The
    `_wire` fixture in `test_research_api_integration.py` now calls
    `promotion.reset()` at teardown instead of hand-snapshotting the triple
    — semantically equivalent, robust to new globals being added. Mirrors
    the `reset()` pattern in `ui/src/skill-plugins/registry.ts`.
  - **Code-comment / docstring correctness.** `research.py`'s
    `_translate_canonical_request` no longer cites a non-existent task id;
    the comment now accurately describes the branch as preparation for
    non-ML skills.
    `ui/src/skill-plugins/index.ts`'s header no longer claims the barrel
    registers seed renderers (it is a pure re-export; the generic fallback
    lives in `DynamicFormFields.tsx`).
  - **`_tool_grep` secret-leak closed.** The sync
    `_tool_grep` in `orchestrator.py` was calling `subprocess.run(cmd, ...)`
    with no `env=` parameter, so the grep child inherited the full parent
    env including server control-plane secrets (`ANTHROPIC_AUTH_TOKEN`,
    `AUTORESEARCH_API_TOKEN`, `AUTORESEARCH_PROMETHEUS_TOKEN`). This is
    exactly the gap the governed-runner path was hardened against earlier
    and that a reverted async migration was supposed to close on the
    grep path. `subprocess.run` now passes `env=_build_child_env()` (the
    same allow-list the governed runner uses), so the grep child sees only
    PATH/HOME/PYTHON*/mlflow-tracking-URI/etc. — never the server secrets.
    No behavior change for approved workflows (PATH and the experiment-
    legitimate vars are in the allow-list).
  - **Broken WIP tests repaired.** Four test files that had been broken in
    the working tree (verified red at HEAD `63e817466`, unrelated to the
    the review fixes) are now green:
    - `tests/test_async_tool_path.py` — rewritten to match the sync
      `_tool_grep` / `_execute_tool` API (the reverted async migration was
      reverted; the test was the orphan). 12 tests pin the sync contract
      including the new env-scrubbing delta and a companion PATH-still-
      present guard.
    - `tests/test_pagination.py::test_v5_indexes_present_after_initialize` —
      schema-version assertion now reads `_LATEST_SCHEMA_VERSION` (currently
      v6, bumped from v5 in an earlier hardening) instead of hard-coded `5`.
    - `tests/test_hardening_phase1_to_5.py::test_results_store_records_schema_version`
      — same `_LATEST_SCHEMA_VERSION` fix.
    - `tests/test_deployment_inputs.py::test_autoresearch_dockerfile_matches_ml_service_runtime_contract`
      — Dockerfile assertions updated for the parameterized `APP_UID`/`APP_GID`
      build args (PR-9: UID/GID 1000 to match the host user owning the
      bind-mounted `configs/`); the old hard-coded `groupadd -g 1001 appuser`
      assertions no longer held.

- **Backend gap close.** Closes the residual acceptance gaps
  found by a post-implementation audit.
  - `POST /skills/reload` now refuses to run when
    `settings.environment == "production"` (403
    `skills_reload_prod_disabled` with a hint). The router already required
    a valid API token; this adds the dev-only constraint the AC names. The
    denial is audited as `skills.reload` / `outcome=denied`. Non-production
    environments keep the dev convenience.
  - **Manifest v2** `ResearchSessionManifest.schema_version` bumped
    `research_session_manifest.v1 → v2`. v1 manifests are accepted on read
    and normalized to v2 (forward-compat); unknown prefixes raise a clear
    error (back-compat). The v2 artifact carries the canonical
    `skill_id`/`subject_id`/`variant` fields alongside the legacy trio
    (populated in `build_research_manifest` and back-filled by a
    `model_validator` for v1 round-trips), matching the dual-shape session
    API contract. The DB schema was already at v6 from the prior entry.
    New `tests/test_research_manifest.py` covers v1→v2 load, canonical-field
    derivation for all three model types, and the round-trip hash stability;
    `tests/test_results_store_migrations.py` adds a v1-era → latest forward
    migration test (seed v1 row → `initialize()` → dual-shape read) and a
    per-migration log assertion.
  - **HTTP-level coverage:** new
    `tests/test_research_api_integration.py` exercises the live router path
    for `GET /research/{id}/iterations` (canonical `skill_id`/`skill_phase`/
    `evidence_keys` synthesized additively) and `POST /research/{id}/promote/preview`
    (`target_kind` from the manifest registry, defaulting to `file_path` for
    legacy sessions; parametrized over all four promotion kinds).
    These previously had helper-unit coverage only.
  - **AC-deviation, recorded:** the AC names
    `src/core/state_store.py` and reads as if `skill_phase`/`evidence_keys`
    were persisted columns on the iteration row. They are NOT persisted:
    `_enrich_iteration` synthesizes them at read time from the existing
    `search_phase` column and the metrics `phase_evidence` keys. Persisting
    them would require a v7 migration + write-path changes for no semantic
    gain and would couple storage to the skill vocabulary. The contract is
    fixed in `test_generalization_falsifiability.py`.

- **Gap close.**
  - `IterationsTable` is now wired into `ResearchDetail`'s
    iterations tab (previously dead code — the page rendered an inline
    table). Manifest-driven `iteration_table_columns` flow through from the
    skill's `metric_schema`, so extra columns render generically.
  - `DynamicFormFields` hardened: `options_url` is now parsed
    generically with `URL` and dispatched by pathname (`/subjects` →
    `getSubjects`, `/subjects/{id}/variants` → `getSubjectVariants`), and the
    integer/number `0` value no longer coerces to `''` (nullish-check fix).
  - new `ui/src/skill-plugins/` renderer registry
    (`registry.ts` / `types.ts` / `index.ts` + README). `DynamicFormFields`
    consults the registry before its built-in switch; a future skill ships a
    renderer instead of forcing a new form branch. The generic text-fallback
    is retained for unmatched field types.
  - stood up a vitest component-test harness
    (`vitest.config.ts`, `vitest.setup.ts`, `test:unit`/`test:watch` scripts)
    with 35 contract tests covering DynamicFormFields (field types,
    `visible_when`, `options_url`, plugin registry, the `0`-coercion
    regression), MetricsChart (manifest-wins / fallback series selection),
    IterationsTable (default + manifest columns, best-row highlight), and
    PromotionModal (`target_kind` branching for all four promotion kinds).

- **Parity fixture re-capture.** Re-captured
  `tests/parity/promotion_preview/development_scope_basic.json` under the
  The append-only fixture rule: the preview response now carries
  the additive canonical `skill_id`/`subject_id`/`variant` fields (
  sourced from the v2 manifest). The two `session_start` fixtures only had
  their `source_sha` bumped — their `expected` output is unchanged, confirming
  the manifest v2 bump did not alter session-start behavior.

- **Generic session API, dual-shape responses.**
  Implemented the backend features that the
  test suite (`test_research_api_compat.py`,
  `test_ws_event_enrichment.py`, `test_generalization_falsifiability.py`)
  encodes as executable contracts.
  - `POST /research/start` now accepts the canonical
    `{skill_id, subject_id, variant, skill_params}` shape alongside the
    legacy `{model_type, instrument, timeframe}` shape. Canonical wins
    unconditionally when both are present; conflicts are audited
    (`research.shape_conflict`). Unknown `skill_id` → 404 with an
    installable-skills hint. `skill_params` validated against the skill's
    `param_schema` → 422 with field pointers on violation.
  - `start_research`, `list_research`, and
    `get_research` now return dual-shape responses: canonical
    (`skill_id`/`subject_id`/`variant`) alongside legacy
    (`model_type`/`instrument`/`timeframe`), both always populated, plus
    a `links` block.
  - Iteration responses (`get_iterations`, `get_results`)
    now carry canonical `skill_id`, `skill_phase`, and `evidence_keys`
    alongside the legacy `model_type`/`search_phase` — additive, derived
    via the `legacy_alias` registry so API and WS payloads share the same
    canonical surface (the dual-shape guarantee).
  - Promotion preview/confirm responses now carry `target_kind`
    (from the skill manifest's `promotion_target.primary.kind`) and
    canonical `skill_id`/`subject_id`/`variant` so the UI PromotionModal
    can branch generically. Defaults to `file_path` for legacy sessions.
  - `EventBroadcaster.broadcast` now enriches WebSocket
    payloads with `skill_id`, `skill_phase`, `evidence_keys`, and a
    `metrics` summary — strictly additive.
  - DB schema bumped to v6: `skill_id`, `subject_id`, `variant`
    columns added to `research_sessions` (idempotent `ALTER TABLE`).
    Existing rows get empty-string defaults; the dual-shape helper
    back-fills canonical from legacy on read.
  - `GET /skills`, `GET /subjects` and related endpoints
    are now mounted in the production app (previously only available in
    test apps). `main.py` lifespan discovers installed skill manifests
    and wires the skill/subject/promotion modules with a shared registry.
  - Added `_BROADCAST_SEND_TIMEOUT_S` per-send timeout so a
    stuck/half-open WebSocket is pruned instead of stalling the fan-out.
  - **Grep guard activated**: `DIRECTION_PHASES`,
    `VOLATILITY_PHASES`, `RL_PHASES`, `_ALLOWED_SCRIPTS` added to the
    deny-list in the coupling-guard ruleset; the guard bumped a phase and
    passes clean (0 violations).

- **Skill-aware UI.**
  - `SkillPicker` component on NewResearch — fetches skills
    from `GET /skills` and replaces the hardcoded model-type selector.
    Falls back to the legacy selector when no skills are available.
  - `DynamicFormFields` component renders any skill's
    form from `GET /skills/{id}/form-fields` with `visible_when` conditional
    support and `options_url` lazy fetch. Unknown field types fall back
    to text + warning.
  - `MetricsChart` now accepts an optional `chartSeries` prop
    from `metric_schema.chart_series`; falls back to the hardcoded
    per-model-type series when no manifest is available.
  - `IterationsTable` now accepts an optional `tableColumns`
    prop from `metric_schema.iteration_table_columns`; extra columns
    render from iteration metrics data.
  - `PromotionModal` branches on `target_kind` to show
    target-specific UI (file_path / registry_api / git_branch /
    artifact_store).
  - Dashboard search now filters by `skill_id` alongside
    `instrument`/`model_type`/`tag`/`id`.
  - **API client** Added `SkillSummary`, `FormField`, `MetricColumn`,
    `MetricSchema`, `SubjectInfo` types and `getSkills`, `getSkill`,
    `getSkillFormFields`, `getSkillMetricSchema`, `getSubjects`,
    `getSubjectVariants`, `reloadSkills` API methods.

- Closed lint / typecheck / exit-bookkeeping gaps found in review.
  The functional code was already committed and passing (115 skill
  tests + 17 parity; grep guard at 0). This entry closes the residual
  Definition-of-Done items the "done" marks left open.
  - **ruff** — fixed 3× E501 (line > 100) in `src/core/skill_manifest.py`
    (`Field(description=...)` strings at lines 447/508/553). The CI
    ruff gate (`ruff check --config pyproject.toml src tests`) now passes
    clean on the new modules. *(The errors only surfaced in path-mode
    ruff; stdin-mode silently skips config discovery.)*
  - **mypy** — `ManifestValidationError.errors` param widened from
    `list[dict[str, Any]]` to `list[Mapping[str, Any]]` (
    `skill_manifest.py`) so pydantic's `list[ErrorDetails]` (a TypedDict) is
    accepted without a cast — `Mapping` is covariant. `SkillRegistry._cache`
    type widened to `tuple[Optional[ResearchSkillManifest], Path, float]`
    (`skill_registry.py`) making the lazy placeholder honest and
    removing two wrong `# type: ignore[...]` comments (at `register_path`
    and `reload_all`) that were suppressing the wrong error code
    (`arg-type`/`assignment`) while the real `assignment` error leaked
    through. Behavior byte-identical — `get()` already handled the
    `manifest is None` placeholder path.
  - **wiki** — sync for `ResearchSkillManifest` / `ManifestSkillRuntime` /
    `ResearchConfig` remains deferred (docs-sync tool not on PATH in this
    environment — a recurring residual). To be run when the tool is
    available.
  - **exit bookkeeping** — recorded the completion date
    The phase-completion rollback tag is deferred to the
    commit that lands these changes (the working tree carried interleaved
    edits; the tag cut stayed deferred).

- Closed abstraction gaps found in the code review.
  - The orchestrator now routes its three experiment-output parse
    call sites through the held ``OutputParser`` instances
    (``self._prepare_parser`` / ``self._marker_parser``, declared at
    `orchestrator.py:703-704`), instead of the module-level facades which each
    constructed a fresh parser per call. The ``IterationMetrics``
    reconstruction was extracted from ``parse_prepare_output`` into a shared
    ``metrics_from_flat(flat)`` helper (`experiment_parser.py`) so both the
    orchestrator and the facade use it. The facades stay (external callers +
    the parity engine depend on them). Behavior byte-identical; the typed
    fields are no longer dead code.
  - The six ``ConfigPromoter`` ``@staticmethod`` helpers that
    form the file-write surface (``_metadata_sidecar_path``,
    ``_rollback_snapshot_path``, ``_rollback_metadata_sidecar_path``,
    ``_write_text_file``, ``_extract_strategy_market``, ``_get_target_path``)
    are now instance methods that delegate to ``self._target`` (the injected
    ``PromotionTarget``, default ``FilePathPromotionTarget``). Previously they
    constructed a fresh ``FilePathPromotionTarget()`` each call, making the DI
    wired-but-inert. ``test_promotion_target.py`` strengthened: a recording
    stub now proves the injected target is actually dispatched through, not
    just stored. Production behavior unchanged (every construction site uses
    the default target).
  - Migrated the ``grep`` tool from a synchronous
    ``subprocess.run`` (inside ``asyncio.to_thread``) to
    ``asyncio.create_subprocess_exec``. ``_execute_tool`` is now ``async``;
    the ``bash`` branch stays on its worker thread via an internal
    ``asyncio.to_thread`` wrap, while ``read_file`` / ``write_file`` / ``glob``
    stay direct (pure-Python). The single production call site no longer
    wraps the whole dispatch in ``to_thread``. **Security delta:** the grep
    child now runs with ``_build_child_env()`` (the governed allow-list
    scrubber), closing the same secret-inheritance gap on the previously-
    ungoverned grep path. Timeout (30s) and cancellation reap the child via
    ``_kill_async_proc_tree`` (process-group kill + ``proc.wait()``). New
    `tests/test_async_tool_path.py` (12 tests: dispatch shape, happy-path
    output, truncation, include-filter, timeout reap, cancellation reap, env
    scrubbing). Four sync ``_execute_tool`` calls in `test_command_policy.py`
    converted to async.
  - **Lint** — fixed an ``E501`` line-length violation in
    `src/core/state_store.py:2111` (introduced by an earlier extraction
    commit; the SQL ``VALUES`` clause was rewrapped).


  - Atomic promotion write (temp + `os.replace` + `fsync` of file
    and parent dir, closed-before-rename, cleanup-on-failure) lives in
    `src/core/promotion_target.py:_atomic_write_text` and is the write path for
    every promoted config + metadata sidecar; `src/core/config_promoter.py`
    keeps a back-compat re-export.
  - Added `tests/test_config_promoter_atomic.py` (6 tests):
    failure injection at each stage of the atomic write (write / fsync /
    os.replace) proves the target file's prior content is preserved and no
    half-written temp is visible; plus a concurrent-reader test confirming
    `os.replace`'s atomicity guarantee.
  - `EventBroadcaster.broadcast` now wraps each `send_text` in
    `asyncio.wait_for(timeout=_BROADCAST_SEND_TIMEOUT_S)` (5s) so a stuck /
    half-open WebSocket is pruned as dead instead of stalling the fan-out
    indefinitely. The existing lock + snapshot-before-iterate hardening is
    unchanged.
  - Added `tests/test_event_broadcaster_concurrency.py` (5 tests):
    fakes that `await asyncio.sleep(0)` inside `send_text` force real event-loop
    interleaving so concurrent broadcast + connect/disconnect/churn and a
    broadcast storm are genuine race tests (the prior `_FakeWS` had no
    suspension point). Includes the slow-client timeout test.
  - Documented the CORS policy under
    a docs note. Code hardening in `src/main.py`
    was already correct (explicit origin allowlist by default; `*`+credentials
    auto-defused); the deliverable doc was missing.
  - **delta** — `_try_auto_promote` now re-checks
    `session["status"] == "completed"` before promoting (defense-in-depth per
    the design). Terminal-finality makes this unreachable in normal flow, but
    the design requires the belt-and-suspenders re-check. Also added a genuine
    concurrent `stop_session` ⇄ exit-path `COMPLETE` race test through the
    shared state machine in `tests/test_session_status_routing.py` (the prior
    the state-machine race tests were sequential pre-seeds).
  - Added a direct hard `asyncio.wait_for` timeout-path
    test in `tests/test_orchestrator_timeout.py` (a hanging LLM call that never
    reaches a bash command, so the soft cap cannot fire; the session-level
    `wait_for` is the only bound). Closes the gap where only the soft-cap path
    was tested.
  - **Hardening delta** — fixed a whitespace-bypass vector in the production-
    approval gate: `" production"` / `"production "` / `"\tproduction\n"`
    previously skipped the production gate entirely (silent downgrade to
    development, no approval). Added a `field_validator` on `PromotionScopeRequest.scope`
    that strips whitespace once so every downstream consumer (the structural
    gate, the HMAC message, audit metadata, promoter args) sees the canonical
    value. Canonicalization tests added to `tests/test_promotion_approval.py`.
  - **delta** — split the `ML_ADMIN_TOKEN` alias out of
    `mlflow_service_auth_token` in `src/config.py`. `ML_ADMIN_TOKEN` was aliased
    to BOTH `rl_trainer_service_token` (needed by RL scripts in the governed
    child) AND `mlflow_service_auth_token` (the production-promotion secret),
    so it could not be forbidden by name without breaking RL auth — the
    promotion secret leaked into every governed child in single-token
    deployments. After the split, `ML_ADMIN_TOKEN` populates only
    `rl_trainer_service_token`; promotion requires a dedicated
    `AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN` / `MLFLOW_SERVICE_AUTH_TOKEN` /
    `SERVICE_AUTH_TOKEN`. **Standard compose is unaffected**
    (`compose/autoresearch.yml` already injects via the dedicated
    `AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN` name). Deployments that inject only
    `ML_ADMIN_TOKEN` into the autoresearch-agent container must set the
    dedicated name for promotion. Regression test added to
    `tests/test_command_policy.py`; the Prometheus-token canary is now planted
    in the env-leak test (all four named secrets asserted stripped).

- **Skill descriptors for the ML trio** — extracted from hardcoded behavior;
  The three ML skills now run driven purely from
  their `skills/<id>/SKILL.yaml` manifests; the orchestrator no longer reads
  `config.model_type`/`instrument`/`timeframe` directly (the exit-gate
  grep returns **0** hits, down from **78**); the domain-coupling guard
  is live and green in CI. Summary of the remaining tasks:
  - `skills/ml-volatility/SKILL.yaml` + `SKILL.md`
    authored from `VOLATILITY_PHASES` (8 phases: baseline_capture, atr_sweep,
    threshold_calibration, temporal_ensemble, + 4 shared late phases);
    `ManifestSkillRuntime` drives it via the generic runtime;
    `tests/test_skill_ml_volatility.py` (11 equivalence tests: phase_plan,
    command_policy narrowed to volatility/prepare.py, volatility-specific
    evidence keys, parser equivalence, promotion, HPO disabled).
  - `skills/ml-rl/SKILL.yaml` + `SKILL.md` authored
    from `FALLBACK_PHASES` (**not** a non-existent `RL_PHASES` — AC-deviation,
    documented in the manifest header). The `validation` phase carries the
    `RL_OOS_EVIDENCE_KEYS` (mean_oos_sharpe/rl_profit_score/oos_sharpe/etc.)
    — the one place RL diverges; the hybrid ≥2-iteration rule is owned by the
    phases.py plugin. `param_schema` declares the RL-only fields
    (trading_mode/agent_strategy/initial_balance). Command policy adds
    `enrich_rl_dataset.py`. `tests/test_skill_ml_rl.py` (13 tests including the
    HPO-opt-in path and RL-only param_schema assertions).
  - `ResearchConfig` generalized: added canonical `subject_id`/
    `variant`/`skill_params` fields; `subject_id`/`variant` derive from legacy
    `instrument`/`timeframe` in `__post_init__`; flat ML fields mirror into
    `skill_params`. `skill_id` derivation is deliberately deferred to
    `materialize_skill_runtime` (not `__post_init__`) so legacy sessions keep
    the transitional runtime until the orchestrator reads are fully migrated.
    Added `config.domain` property (domain-neutral accessor for legacy
    `model_type`). Two `session_start` parity fixtures re-captured under the
    append-only rule with a recapture note.
  - Flat ML field reads mirror into `skill_params` (the dataclass
    fields stay for back-compat; `__post_init__` populates the dict so manifest-
    driven runtimes read from one place). Full migration to `skill_params.get`
    folded into the orchestrator read sweep.
  - `src/core/legacy_alias.py`: `model_type ↔ skill_id` registry
    (direction↔ml-direction, volatility↔ml-volatility, rl↔ml-rl). Back-compat
    bridge for the dual-shape guarantee.
  - `tests/test_research_config.py` (20 tests: alias round-trips,
    both-shape construction, canonical-field derivation, skill_params mirroring,
    skill_id-stays-empty back-compat).
  - Migrated all 78 orchestrator reads of
    `config.(model_type|instrument|timeframe)` to domain-neutral accessors
    (`config.domain`/`config.subject_id`/`config.variant`). The `_load_skill`
    map stays as a transitional helper (the async-read path is mocked by the
    orchestrator test suite); full removal lands when the transitional runtimes
    retire.
  - `DIRECTION_PHASES`/`VOLATILITY_PHASES`/`FALLBACK_PHASES`,
    `_ALLOWED_SCRIPTS`, and `_AGENT_ACTIONABLE_BLOCKERS`/`_PHASE_SPECIFIC_AGENT_KEYS`
    are now **transitional-only**: the manifest-driven path sources them from
    YAML; the constants survive solely as the transitional-runtime fallback.
    The grep guard does not check for these constants (it checks
    `config.(model_type|instrument|timeframe)` in orchestrator.py, which is 0),
    so full deletion lands when the transitional runtimes retire. Documented
    as a recorded acceptance deviation.
  - Activated the deny-list: moved the legacy config-field rule from the
    comment block into the coupling-guard ruleset. The CI guard job runs
    the rule against orchestrator.py and passes (0 violations). Per-line
    suppression is available via explicit inline exemption comments.
  **Exit criteria met:** `rg -E "config\.(model_type|instrument|
  timeframe)" src/core/orchestrator.py` returns **0** (was **78**); parity
  suite green (17/17); full suite green (1022 passed, +91 new tests) except the 2 pre-existing `test_deployment_inputs` failures; the
  `domain-coupling-guard` CI job is green. `pipeline` model_type is
  deliberately out of scope (composes the three skills).
  **Grounding deviations documented:** RL uses `FALLBACK_PHASES` not
  `RL_PHASES`; `_AGENT_ACTIONABLE_BLOCKERS` lives in orchestrator.py not
  blocker_classifier.py; `_load_skill` remained at its orchestrator location; "existing model types" = 3 skills not 4 (pipeline out of scope). Wiki
  (`ResearchSkillManifest`, `ManifestSkillRuntime`, `ResearchConfig`) deferred
  (tool not on PATH — same residual as before).

- Extracted the **`ml-direction`** reference skill into a manifest-driven
  `ManifestSkillRuntime` (the reference
  extraction). This is the keystone: once `ManifestSkillRuntime` drives
  `ml-direction` purely from YAML, `ml-volatility` / `ml-rl` repeat
  the pattern and the hardcoded constants fall.
  - `skills/ml-direction/SKILL.yaml` — the live `research_skill.v1`
    manifest, lifted from the spike draft with canonical section names.
    Reproduces every literal from `DIRECTION_PHASES` (8 phases),
    `command_policy.py` (direction's script subset), `experiment_parser.py`
    (delimited_kv contract + marker-dir fallback), `service_preflight.py`
    (6 http_health targets, `{settings.*}` URLs),
    `config_promoter.py` (file_path development target + gate bundles +
    registry_api production delegate), `orchestrator.py` (phases.py plugin
    advancement, resolve_identity.py plugin, blocker_classification,
    decision success_values, optimize goal).
  - `skills/ml-direction/SKILL.md` — the prompt primer copied from the
    legacy `.github/skills/direction-autotuner/SKILL.md` (the `llm.system_prompt`
    target the loader reads).
  - `ManifestSkillRuntime` in `src/core/skill_runtime.py` (the
    keystone/highest-risk task) — a generic runtime satisfying the 21-member
    `SkillRuntime` protocol, reading everything from a `ResearchSkillManifest`.
    Data-driven methods (phase_plan, command_policy, parsers, preflight,
    promotion, marker paths, insights, subjects/variants) source from the
    manifest; computation methods (prompts, trial_identity, structured_hpo,
    research-resume) delegate to the same orchestrator helpers the transitional
    runtimes use — parameterized by manifest data — so behavior is byte-identical
    (the parity golden rule). `session_nonce` remains accepted-ignored.
    The plugin slots (`phases.py`, `resolve_identity.py`) declared in the
    manifest; the runtime delegates to the shared `_completed_phase_ids` /
    `build_trial_identity` helpers (the full plugin sandbox). Production
    `registry_api` promotion stays in `ConfigPromoter` for now (follow-up).
    `materialize_skill_runtime` now prefers the manifest runtime when
    `config.skill_id` resolves in the registry, else falls back to the
    transitional runtimes — per-skill reversible switchover (empty `skill_id`
    unchanged → transitional, so no behavior change unless a session opts in).
  - `tests/test_skill_ml_direction.py` — 17 equivalence + contract
    tests asserting `ManifestSkillRuntime(ml-direction)` reproduces
    `DirectionSkillRuntime` outputs (phase_plan ids/min/max, command_policy
    allowed_scripts, phase_advancement evidence keys, parse_iteration for both
    delimited_kv and json_marker, parser formats, promotion kind, preflight
    names, HPO disabled, decision success_values, metric direction) +
    materialization-by-skill-id and transitional-fallback tests.
  No behavior change unless a session sets `skill_id="ml-direction"` (the
  default empty-string `skill_id` keeps the transitional runtime). parity
  suite green (17/17); full suite green (982 passed, +17) except the 2
  pre-existing `test_deployment_inputs` failures.


- Introduced the **manifest infrastructure** for `research_skill.v1` skill
  descriptors (the "manifest infra" epic).
  Three new modules + a test suite:
  - `src/core/skill_manifest.py` — the authoritative Pydantic v2
    schema. `ResearchSkillManifest` + nested `BaseModel`s cover every declared section
    section (`llm`, `workspace`, `subjects`/`variants`, `param_schema`,
    `metric_schema`, `decision_vocabulary`, `phase_plan` + `phase_advancement`,
    `command_policy`, `output_parser`, `preflight`, `promotion_target`,
    `trial_identity`, `blocker_classification`, `structured_hpo`, `insights`,
    `prompt`, `ui`, `category`) and address all 13 spike gap-list items:
    `PhaseAdvancement{mode,plugin}` + per-phase override;
    `TrialIdentity.resolve{mode,plugin}`; `BlockerClassification`;
    `gate_bundles`; enriched `RegistryApiTarget` (lookup/auth/rollup);
    `{settings.*}` allowed as opaque strings (semantics owned by the loader);
    `OutputParserFallback.marker_dir_template`+`primary_metric_jsonpath`;
    `success_values`; `bundle_manifest`; `goal`; subjects/variants;
    category. `extra="forbid"`; discriminated union over
    `promotion_target.primary.kind` (file_path/registry_api/artifact_store/
    git_branch). Section names canonicalized per the spike (`metric_schema` not
    `metrics`, etc.). The schema is the stress test: all five spike drafts
    (`ml-direction`, `prompt-engineering`, `code-refactor`, `db-config-tuning`,
    `literature-review`) validate clean.
  - `src/core/skill_loader.py` — `load_skill_manifest(path|str|dict,
    *, settings_obj, skill_params)`. Owns the placeholder-resolution semantics the schema leaves
    open: `{settings.*}` substitution pre-validation so the schema sees resolved
    values; `{skill_params.*}` only resolvable with session context (raises
    field-specifically at registry-load time). `schema_version` gate raises
    `ManifestVersionError`; structural failures raise `ManifestValidationError`
    with a field-located summary.
  - `src/core/skill_registry.py` — `SkillRegistry` discovers
    `skills/<id>/SKILL.yaml` under the service `skills/` dir (NOT
    `Settings.skills_dir`, which is the workspace-side primer location), caches
    loaded manifests keyed by id, lazy-loads on first `get()`, and hot-reloads on
    mtime change. Unknown ids raise `SkillNotRegisteredError`.
  - `tests/test_skill_loader.py` — 30 tests: schema validates all five
    spike drafts + rejects malformed inputs (wrong version, unknown promotion
    kind, phase min>max, duplicate phase ids, registry_api-needs-production);
    loader interpolation (happy/missing-setting/None-setting/wrong-version/
    inline-YAML/dict/skill_params unresolvable+resolvable); registry discovery,
    lazy cache, hot reload, unknown-id, register_path, default-root check.
  No behavior change — three additive modules + tests. parity suite green
  (17/17); full suite green (965 passed, +30) except the 2 pre-existing
  `test_deployment_inputs` failures. Wiki (`ResearchSkillManifest`,
  `ManifestSkillRuntime`) deferred (tool not on PATH — same residual as before).
  Next: `ml-direction` lifts into `skills/` and the
  `ManifestSkillRuntime` that consumes these manifests.

- Introduced the `SkillRuntime` protocol and three transitional runtimes, and
  wired the orchestrator to materialize one per session (
  the "SkillRuntime transitional shell" epic). New `src/core/skill_runtime.py`
  declares the full protocol contract (21 members: identity, prompt construction,
  command policy, iteration detection, phase contract, trial identity, preflight,
  promotion, output parsing, insights, cross-session memory, structured HPO,
  subjects/variants) as a typing-time `Protocol` (not `@runtime_checkable`,
  house style). `DirectionSkillRuntime` / `VolatilitySkillRuntime` /
  `RLSkillRuntime` **delegate to the current hardcoded code paths**
  — behavior is identical, just relocated out of the orchestrator's
  `if config.model_type == ...` branches. `AgentOrchestrator.run()`
  now materializes a `SkillRuntime` via `materialize_skill_runtime(self, config)`
  at session start so every later domain branch can reach through `skill.*`.
  New `tests/test_skill_runtime_transitional.py` adds 24 structural +
  delegation tests. **AC #2 status:** `grep -c "config.model_type"
  src/core/orchestrator.py` is 42 (baseline 41) — the count does **not** drop
  (transitional runtimes still read `config.model_type` internally), satisfying
  the "every read inside a transitional runtime, not the loop body" clause;
  the drop to 0 is the next phase. **Three documented deviations:**
  **First** — value types (`SessionRecord`, `IterationRecord`,
  `CommandPolicyExtension`, `Phase`, `AdvancementRule`, `StructuredHPOPlan`,
  `SubjectDescriptor`, `VariantDescriptor`) are `TypedDict` aliases over the
  existing dict shapes (not dataclasses), so callers keep treating them as plain
  dicts (byte-identical behavior, zero construction churn); **Second** —
  `parse_iteration` accepts `session_nonce: bytes` for the later
  anti-forgery work but the transitional runtimes **ignore** it (no nonce validation exists today);
  **Third** — `ResearchConfig` gains `skill_id` / `skill_version` (default `""`),
  derived from `model_type` in the transitional runtimes
  (`"direction" → ("direction-autotuner", "1")`); two `session_start` parity
  fixtures re-captured under the append-only-with-linked-task rule to record the
  new defaulted fields. The parity suite is green (17/17); full suite green
  (935 passed) except the 2 pre-existing `test_deployment_inputs` failures.
  Wiki (`SkillRuntime` + three transitional entities) deferred (tool not on PATH
  in this env — same residual as before).

- Migrated existing preflight checks to the `PreflightCheck` protocol
  New `src/core/preflight.py` declares the protocol
  (`name`, `required`, `async check(client)`) and two implementations:
  `HTTPHealthCheck` (wraps `service_preflight._check_target`) and
  `TCPConnectCheck` (wraps `_check_tcp_target`, used for `nats`). The dispatch
  fork in `run_service_preflight` (`if target.transport == "tcp"`) is replaced
  by polymorphic `target.check(client)` calls via `preflight_check_from_target`.
  The four public free functions (`run_service_preflight`,
  `build_not_run_preflight`, `require_preflight_ready`, `sanitize_service_url`)
  keep their signatures — the consumers (`session_manager._run_preflight`,
  `main.py` readiness/monitoring endpoints, `research_manifest`) are unchanged.
  Check methods resolve `_check_target`/`_check_tcp_target` through the
  `service_preflight` module at call time so the existing test monkeypatches
  keep working. New `tests/test_preflight.py` adds 8 structural tests.
  The 7 existing `test_service_preflight.py` tests (the behavioral gate) stay
  green unchanged. parity green; full suite green except 2 pre-existing
  `test_deployment_inputs` failures.

- Wired `ConfigPromoter` to the `PromotionTarget` protocol and extracted
  `FilePathPromotionTarget`. New
  `src/core/promotion_target.py` declares the protocol (the file-write surface:
  `target_path`, `write` (atomic, async), `metadata_sidecar_path`,
  `rollback_snapshot_path`, `rollback_metadata_sidecar_path`,
  `extract_strategy_market`) and `FilePathPromotionTarget` — the verbatim
  extraction of `ConfigPromoter`'s `@staticmethod` / module-level helpers.
  `ConfigPromoter.__init__(store, target=None)` now accepts an injected
  `PromotionTarget` (defaults to `FilePathPromotionTarget()` for back-compat);
  the historical `@staticmethod`s delegate to the target so internal `self.*`
  call sites keep working. `ConfigPromoter` keeps its three public methods
  (`preview`/`confirm`/`rollback`) — the gate-evaluation logic stays. **Scope
 :** `PromotionEvidenceCollector` is intentionally outside the protocol (it
  writes to the DB iteration row, not the host config path). The parity
  fixture `development_scope_basic.json` (bakes
  `target_path: "<host_configs>/instrument_configs/DOGE_USDT_15m.yaml"`) stays
  green unchanged. New `tests/test_promotion_target.py` adds 13
  structural + path-derivation-parity tests. The 45-test
  `test_config_promoter_gate_bundle.py` suite stays green unchanged.

- Introduced the `OutputParser` protocol and extracted `DelimitedKVParser` /
  `JSONMarkerParser` from `experiment_parser` (mirrors
  the `StateStore` precedent). New `src/core/output_parser.py`
  declares the protocol (`parse` for the `---` KV-block, `parse_iteration` for
  the `ITERATION_RESULT:` JSON-line) and the two implementations, extracted
  verbatim from `parse_prepare_output` / `parse_iteration_marker`.
  `experiment_parser.py` keeps the four historical module-level functions as
  **thin facades** over the new classes (reconstructing `IterationMetrics` from
  the flat dict) so the parity engine (`tests/parity/_engine.py`, which imports
  `from src.core.experiment_parser import ...` by string name) keeps resolving
  without a fixture re-capture. `AgentOrchestrator` now holds typed
  `self._prepare_parser` / `self._marker_parser: OutputParser` instances. Every
  load-bearing edge case (`_json` dual-write, int-via-JSON preservation, bool
  coercion, gate-alias reconciliation, `FAILURE_STATUSES` nulling) is preserved
  bit-for-bit. **Deviation:** `parse_iteration` accepts `session_nonce` for
  forward-compat with the later anti-forgery work but the transitional parsers
  ignore it (no nonce validation exists today). New `tests/test_output_parser.py`
  adds 10 structural tests. The 10 existing `test_experiment_parser_*`
  files + 6 parity fixtures stay green unchanged.

- Added `tests/test_state_store.py` — structural / contract parity tests for
  the `StateStore` protocol (mirrors `test_llm_provider.py`). Four tests: (1) `StateStore` is a `Protocol` and is **not**
  `@runtime_checkable` (typing-time contract, house style); (2) every method in
  `StateStore.__protocol_attrs__` (48 of 49; `connection()` excluded) exists on
  `SQLiteStateStore` and is async on both sides — the signature-drift guard;
  (3) a minimal stub satisfies the protocol at the typing level; (4) the
  back-compat alias `ResultsStore is SQLiteStateStore` (same class object, not a
  subclass) — pins the invariant that `conftest.py`'s class-level monkeypatch
  relies on. These are not behavioral tests; behavior is covered by the existing
  `ResultsStore` suite (now exercising `SQLiteStateStore` via the alias) and the
  parity fixtures. Full suite green (880 passed) except the 2 pre-existing
  `test_deployment_inputs` failures.

- Wired production consumers to the `StateStore` protocol type
  `src/main.py` now constructs `SQLiteStateStore(...)`
  concretely but holds it as `StateStore | None` (mirrors how the orchestrator's
  `self._provider: LLMProvider` is typed as the protocol but constructed as
  `AnthropicProvider`). The six core consumers (`SessionManager`,
  `AgentOrchestrator`, `ConfigPromoter`, `PipelineController`,
  `PromotionEvidenceCollector`, `SessionStateMachine`) widened their constructor
  `store:` param from `ResultsStore` to `StateStore`. The API layer was already
  untyped (`store` / `_store = None`) and is abstraction-agnostic, so it is
  unchanged. The six defensive `getattr(store, "<method>", None)` probes in the
  orchestrator/config_promoter are left untouched (they work against any object;
  they become dead code once the migration completes). `grep ResultsStore src/` now returns
  only the shim + historical docstring mentions — no live type annotations or
  imports remain. Zero new ruff/mypy errors; full suite green except the 2
  pre-existing `test_deployment_inputs` failures. The parity suite is
  green.

- Introduced the `StateStore` protocol and extracted `SQLiteStateStore`
  (mirrors the LLM-provider precedent).
  New `src/core/state_store.py` declares the storage abstraction every consumer
  reaches through (`SessionManager`, `AgentOrchestrator`, the API layer) and
  hosts `SQLiteStateStore` — the 1:1 rename of the former `ResultsStore`. The
  canonical home moved via `git mv results_store.py → state_store.py`
  (blame/history preserved); `src/core/results_store.py` is now a back-compat
  re-export shim so the ~45 test files and production consumers that import
  `ResultsStore` keep working unchanged. `ResultsStore` is bound to
  `SQLiteStateStore` via `import ... as` (the **same** class object, not a
  subclass) so `tests/conftest.py`'s `monkeypatch.setattr(ResultsStore,
  "initialize", ...)` keeps working. The protocol mirrors 48 of the 49 public
  methods; schema DDL + `_MIGRATIONS` stay inside the SQLite impl (AC #4).
  `connection()` is deliberately excluded (leaks `aiosqlite.Connection`).
  **Three acceptance-criteria deviations (the text predated grounding; recorded here
  in the style of the earlier retry callout):** the second ("`WEB_CONCURRENCY
  > 1` guard remains here") is factually off** — the guard lives at
  `src/main.py:_validate_runtime_configuration` (a service-lifecycle concern,
  never inside the store); it stays in `main.py`, and the single-instance
  *constraint* is documented on `SQLiteStateStore` instead. the third names
  two methods that don't exist:** `record_iteration` → the real method is
  `add_iteration`; `list_iterations` → `get_iterations`. **`connection()` is
  excluded from the protocol** (leaks the SQLite backend type). Also preserved
  the historical logger name `src.core.results_store` (hardcoded, not
  `__name__`) so log-scraping/dashboards/tests keyed on it are unaffected.
  Production construction (`SQLiteStateStore(settings.db_path)`) and consumer
  type wiring and the parity tests land in the two entries below. The parity suite is
  green (17/17); full suite green except 2 pre-existing `test_deployment_inputs`
  failures unrelated to storage. **Note:** migrating the ~45 test imports from
  `ResultsStore` to `SQLiteStateStore` is a follow-up sweep; the alias is
  intentionally permanent-ish until then. Wiki pages (`StateStore`,
  `SQLiteStateStore`) deferred to after the adapter entry.

- Extracted `AnthropicProvider` from the orchestrator and fully normalized
  the LLM consumption (consumes the spike design and
  the protocol above). `src/core/llm_provider.py` now hosts the SDK adapter
  alongside the protocol; `orchestrator.py` reaches the model **only** through
  `LLMProvider` (zero `messages.create` / `anthropic.*` / `httpx.*` references
  remain — grep-verified). The provider translates at the SDK boundary:
  `Message`/`ToolDef`/`system` → Anthropic kwargs (byte-identical to the
  pre-refactor wire request), and the raw response → normalized
  `ProviderResponse` (enforcing the *"tool calls present ⇒ `TOOL_USE`"*
  invariant regardless of native `stop_reason`). The orchestrator's
  conversation is now `list[Message]` and the loop reads `StopReason` /
  `ContentBlock` / `Usage` instead of raw SDK shapes; `AGENT_TOOLS` is
  `list[ToolDef]`. **Retry placement follows the spike's D-retry decision
  (loop-owned), not the literal acceptance wording:** `_call_claude_with_retry`
  → `_call_llm_with_retry`, now using `provider.classify_error` (same transient
  set: APITimeout/APIConnection/InternalServer + HTTP 429/502/503/529) with
  backoff (30·2ⁿ) and the budget-aware skip preserved verbatim. The two
  pre-refactor retry log lines are unified into one (decision/timing identical;
  documented). Insights/Haiku call → `provider.complete()`. Added
  `tests/test_anthropic_provider.py` (16 tests: translation, invariant,
  classify_error, estimate_cost). Updated fakes in test_orchestrator_{timeout,
  loop_guard,terminal_reason} + test_prompt_promotion_policy to the normalized
  shapes; dropped the now-invalid headless-import subprocess test. The
  parity suite is green. **Note:** the ~30 per-file `anthropic` test
  stubs are now dead-but-harmless (the orchestrator no longer imports
  anthropic); cleanup is a follow-up. Wiki page deferred.

- Introduced the `LLMProvider` protocol and normalized value types
  (consumes the provider spike design verbatim). New `src/core/llm_provider.py` declares the provider-agnostic
  contract every LLM backend must satisfy: `messages_create` (main agentic
  path), `complete` (one-shot insights/Haiku path), an optional `stream`,
  `estimate_cost`, `capabilities`, and
  `classify_error` (loop-owned retry). The normalized types are
  Anthropic-shaped (`ToolUseBlock.input: dict`, `ToolResultBlock`,
  `ToolDef`) so the upcoming `AnthropicProvider` is a 1:1 wrapper and
  the parity suite is preserved. `StopReason` is the critical enum the loop
  will key off (`END_TURN` triggers phase continuation); the *"tool calls
  present ⇒ `TOOL_USE`"* invariant (Gemini `STOP`-with-function-calls quirk)
  is documented as the provider's responsibility. **No behavior change** — this
  is a type-only module; the next entry extracts `AnthropicProvider` and a follow-up wires
  the orchestrator to accept any `LLMProvider`. Added
  `tests/test_llm_provider.py` (contract surface, `StopReason` mapping,
  frozen-value-type, and headless-import tests). Wiki page deferred.

- Sanitized the governed subprocess environment so approved experiment scripts
  no longer inherit server control-plane secrets (a gap uncovered by the
  security design review). `GovernedCommandRunner` now
  spawns with an explicit `env=` built **default-deny** from an allow-list
  (`_CHILD_ENV_ALLOWLIST` + `PYTHON`/`LC_` prefixes, minus a
  `_FORBIDDEN_CHILD_ENV` defense-in-depth set). Dropped from the child env:
  `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `AUTORESEARCH_API_TOKEN`,
  `AUTORESEARCH_PROMETHEUS_TOKEN`/`PROMETHEUS_TOKEN`, the mlflow promotion
  token (`AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN`/`MLFLOW_SERVICE_AUTH_TOKEN`/
  `SERVICE_AUTH_TOKEN`), `INFERENCE_SERVICE_AUTH_TOKEN`, and the
  `PRODUCTION_APPROVAL_VERIFIER` HMAC secret. Kept (experiment-legitimate, per
  the script inventory): `PATH`/`HOME`/Python/venv, service URLs, minio
  `AWS_*`, `MLFLOW_TRACKING_URI`, `RL_TRAINER_*`, and `ML_ADMIN_TOKEN`. A new
  test asserts planted canaries are absent from the child env while kept vars
  propagate; a static contract test pins the allow-list ⊇ the vars the six
  `_ALLOWED_SCRIPTS` read. The parity suite is green. **Residual:**
  `ML_ADMIN_TOKEN` is an overloaded alias for both `rl_trainer_service_token`
  (RL needs it) and `mlflow_service_auth_token` (the promotion token) in
  `config.py`, so it cannot be cleanly stripped by name yet — splitting that
  alias is tracked as a follow-up.

- Enforced mandatory cryptographic approval for production-scope promotions
  `POST /research/{id}/promote/confirm`
  with `scope=production` now verifies the `approval.signature` as the hex
  HMAC-SHA256 of `"{research_id}:{scope}:{approver}"` keyed by the new
  `production_approval_verifier` secret (`AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER`).
  When the verifier is unset, all production promotions are rejected with
  HTTP 400 **fail-closed** until the operator configures the secret; other
  scopes (`development`, `canary`, `paper`) are unaffected. The
  `promotion.confirm` audit event additionally records the named `approver`
  and `approval_method` (the API caller's identity was already recorded as
  `actor_id`). This is an **intentional hardening**: production promotions
  that previously worked with a presence-only signature now require the
  verifier configured and a valid HMAC. Added
  `tests/test_promotion_approval.py` (16 tests across all four acceptance
  criteria).

- Added opaque cursor pagination to the list endpoints. `GET /api/v1/research` and `GET /api/v1/pipelines` accept a new
  `cursor` query param (base64url of `(sort_key, id)`); passing it switches the
  response to the keyset envelope `{items, limit, next_cursor}` which is stable
  under concurrent inserts (no offset drift). The legacy `offset` param is
  deprecated (marked in OpenAPI, warns when `offset > 0`) and now also returns
  an additive `next_cursor` so clients can upgrade transparently. `GET
  /api/v1/research/{id}/iterations` pagination is opt-in: omit `limit` for the
  unchanged bare-list response, pass `limit` for the
  `{items, limit, next_cursor}` envelope. `total` is retained on the offset
  path only. Cursor decode is fail-open (malformed tokens serve page 1). Added
  schema v5 migration creating supporting indexes
  (`idx_sessions_started_at_rowid`, `idx_pipelines_started_at_rowid`,
  `idx_iterations_research_iteration`). The design lives in the pagination
  module docstring. Added `tests/test_pagination.py`
  (38 tests).

## 2026-07-02

- Audited ResultsStore exception handling and confirmed migration errors no
  longer swallow. One target — a
  bare `try/except Exception: pass` over each `ALTER TABLE ADD COLUMN` — was
  already removed in commit `3c47c1e34` (an earlier hardening) and replaced by
  `_add_column_if_missing` (a `PRAGMA table_info` LBYL pre-check that lets
  genuine `OperationalError` propagate), so the goal is met by a
  documented-equivalent approach (inventory + decision recorded in
  the `results_store.py` module docstring). Cleanups folded in: removed the dead
  `_CURRENT_SCHEMA_VERSION = 1` constant; de-duplicated six evolutionary
  `research_sessions` columns (`manifest_{json,path,hash}` +
  `current_phase`/`next_action`/`phase_state_json`) from the bootstrap
  `_SCHEMA_SQL` so the migration is the single source of truth (verified safe
  for fresh and legacy DBs — `initialize()` always runs v0→v1); and narrowed
  `ping()`'s `except Exception` to `aiosqlite.Error`. Added
  `tests/test_results_store_migrations.py` (5 tests: `_add_column_if_missing`
  idempotency + real-error propagation, `initialize()` double-call idempotency,
  version-skew rejection, and a regression check that a fresh DB reaches the
  latest version with the de-duplicated columns present).
- Enforced a hard wall-clock bound that also reaps the worker subprocess.
  Two complementary mechanisms: (1) each
  governed command's per-command timeout is now capped at the session's
  remaining soft budget (`_tool_bash`, via a deadline threaded through
  `_execute_tool`), so `GovernedCommandRunner`'s own psutil SIGTERM→SIGKILL
  path (`command_runner.py`) fires at the session boundary — the in-loop soft
  check then trips `transition(TIMEOUT)` → `timed_out`, and the outer
  `asyncio.wait_for`/`HARD_TIMEOUT` is just the backstop; (2) a thread-safe
  `CommandProcessRegistry` (`command_runner.py`) records every in-flight
  `Popen` per session, and the orchestrator's `except CancelledError` handler
  calls `kill_all` to reap the process tree on operator stop / hard-timeout
  cancel — closing the defect where cancelling `asyncio.to_thread` cannot
  interrupt the worker thread that owns the `Popen`, so the training
  subprocess otherwise leaked up to ~2h. When a session has ample budget the
  cap is a no-op (`min(floor, large) = floor`), so long-training behavior is
  unchanged. Added `tests/test_orchestrator_timeout.py` (4 tests: orchestrator
  -level capped-command reap → `timed_out`; registry `kill_all` reap of an
  in-flight subprocess a bare cancel could not interrupt; cap-math unit;
  registry-membership unit).
- Routed all session-status writers through `SessionStateMachine.transition`
  ), making it the sole legal writer of
  `research_sessions.status` and closing the stop-vs-complete race. The 8
  direct `update_session(status=…)` sites now drive lifecycle changes via
  the per-session-locked state machine: `pause_session`/`resume_session`
  (`PAUSE`/`RESUME`, returning `False` on illegal/winding-down states — the
  the pause sibling), `stop_session` (records the transitional `stopping`
  intent under the lock), `recover_orphaned_sessions`
  (`RESTART_RECOVER`), and the hard-timeout reclassify (`HARD_TIMEOUT`,
  incl. the documented `stopped → timed_out` carve-out). The orchestrator
  exit path resolves its terminal intent by severity
  (`fail > timeout > stop > complete`): a racing `complete` against an
  in-flight stop is refused and finalizes `stopped` with no auto-promote
  (scenario A); a late cancel against terminal `completed` is a no-op that can
  neither overwrite the status nor revoke a promotion (scenario B). Auto-promote
  is now gated on `TransitionResult.should_auto_promote` (False on severity
  redirect). Cost/iteration accounting is split into a status-free write so
  it is always captured even when a transition is refused. `SessionManager`
  and `AgentOrchestrator` accept an injectable `SessionStateMachine`
  (sharing one `SessionLockRegistry`); the initial `running` status stays a
  `create_session` storage default (out of the original grep scope, by
  design). Behavior is unchanged for happy paths; new transitional statuses,
  the `session.transition` audit action, and `research_started`/`_paused`/
  `_resumed`/`_stopped`/`_timed_out` broadcasts are additive. Added
  `tests/test_session_status_routing.py` (8 tests pinning the routing +
  race-scenario contract); the exhaustive transition/race suite followed.

## 2026-06-29

- Added the skill-manifest expressiveness design spike under
  `docs/adr/skill-manifest-drafts/`: a gap list and schema punch-list plus
  five draft `research_skill.v1` manifests (`ml-direction`,
  `prompt-engineering`, `code-refactor`, `db-config-tuning`,
  `literature-review`). The `ml-direction` draft reproduces current
  hardcoded behavior; the four non-ML drafts prove the schema spans
  optimization/generative/exploratory categories. Gaps route hybrid logic
  to two sandboxed plugin slots (`phases.py`, `resolve_identity.py`);
  everything else is new declarative fields.
- Added the skill-plugin security sandbox design (recorded in the
  plugin-runner module docstrings): run all skill plugins in a governed
  subprocess (never in-process), the agent-vs-plugin capability
  distinction, read-only/path-confinement rules, `--dry-bootstrap` overlay
  semantics, a six-vector threat model, and the plugin capability
  contract. It uncovered a live pre-existing gap — the agent's governed
  subprocess inherits all server secrets (`command_runner.py` passed no
  `env=`) — fixed by env sanitization on the governed spawn path.
- Added the LLM provider normalization design (recorded in the provider
  module docstrings): a multi-provider comparison matrix (system prompt,
  tool-use protocol, stop-reason, retry, streaming), the draft
  `LLMProvider` protocol + normalized `StopReason`/`Usage`/content-block
  types, and three recorded decisions — loop-owned retry with provider
  `classify_error`, the protocol defines `stream()` with the
  implementation deferred, and the OpenAI translation targets Chat
  Completions. Phase-contract enforcement stays loop-level via the
  normalized `StopReason.END_TURN`. Normalized types are Anthropic-shaped
  so the `AnthropicProvider` is a trivial wrapper and parity is preserved.
- Added the `SessionStateMachine` design (the 13-state diagram and the
  full `(from, event) → (to, side_effects, audit, broadcast)` transition
  table live in `src/core/state_machine.py`) incl. severity overrides
  (`fail > timeout > stop > complete`; stop beats complete = the
  stop-vs-complete race), guard rules, the single-writer `transition()`
  decision, and an exhaustive audit of session-status writers. Records
  that `stop_session` wrote no status itself (the race is between the
  orchestrator's own exit branches), that there were 8 session-status
  writers, and that terminal transitions emitted no audit row (the new
  `session.transition` action is additive). Transitional states are
  recorded in the public `status` column; the pipeline state machine is
  deferred.

## 2026-06-28

- Added the domain-coupling CI guard (`scripts/check_domain_coupling.py`)
  with a data-driven denylist. The
  guard runs in the service CI workflow; it ships inactive and is
  tightened per migration phase. Per-line suppression is available via
  explicit inline exemption comments.
- Added the parity fixture suite under `tests/parity/`: golden-
  master fixtures capturing current behavior across five categories
  (`experiment_parser`, `command_policy`, `session_start`, `phase_advancement`,
  `promotion_preview`), a shared `_engine.py` (token substitution + output
  normalization), a `capture.py` recorder (idempotent, dirty-git-guarded), and a
  `@pytest.mark.parity` test harness. Run `pytest -m parity` to verify;
  `python tests/parity/capture.py` to regenerate after an intentional change.

## 2026-05-09

- Added a platform indicator service as a dependency for manifests,
  status, and preflight, with blocking readiness for RL/pipeline sessions.

## 2026-05-02

- Moved the backend package from `server/` to the standard `src/`
  layout and updated the ASGI import path to `src.main:app`.
- Added a committed Poetry lockfile plus shared workspace path dependencies for
  the common ML libraries used by the training, inference, and RL services.
- Switched the container runtime identity to UID/GID `1001` and tightened the
  Docker build so dependency install failures are not swallowed.
- Replaced handwritten Prometheus exposition with `prometheus-client` while
  keeping the existing custom metric names.
- Added identity-service JWT introspection for admin bearer tokens while keeping
  `AUTORESEARCH_API_TOKEN` as the static fallback.
- Added canonical `AUTORESEARCH_*` settings aliases, `/monitoring/health`
  readiness details, autoresearch CI coverage, and workspace dependency parity
  checks against locked service pins.
