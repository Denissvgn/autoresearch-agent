# Changelog

## Unreleased

- **ARC-011 implementation review C5 (2026-08-15) — cross-worker
  stop/pause/resume works at the SessionManager entry point (P6-004 / H3;
  ADR §6.2's design is finally reachable).** All four control methods
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
    after any observed pause/resume (P6-004).
  - **Pipelines (ADR §6.2 lists them for the same fix):** `stop_pipeline`
    records `status='stopping'` before the local-registry check (terminal
    rows refused, not clobbered) and forwards the stop to every recorded
    phase session — `stop_session` records DB intent even for non-owned
    sessions, so the owner's current phase session stops mid-run too. The
    owning `PipelineController`'s phase-loop poll consults the DB row
    (`_stop_recorded_db`; read failures fail closed to the local flag).
  - **Tests:** new `tests/test_cross_worker_control.py` (9 tests): non-owner
    stop/pause/resume record DB intent (and the owner's poll observes it —
    the H3 loop closed at unit level), unknown/terminal no-ops, the local
    fast path unchanged, DB-side pause observation + cross-worker-resume
    unstick + epoch refresh, pipeline DB intent + terminal-row refusal +
    controller poll. The distributed harness gains
    `test_distributed_session_manager_stop_records_intent` — a real
    multi-process worker stopping through the REAL `SessionManager` entry
    point (previously the harness bypassed it, which is why the C5 bug was
    invisible); runs in the dedicated Postgres CI job. Full suite green
    (1369 passed); ruff/mypy at the pre-existing baseline (91/15, zero
    new); domain-coupling guard green.

- **ARC-011 implementation review C4 (2026-08-15) — the Phase-4 exit
  criterion is now actually met: a non-ML session runs end-to-end on the
  OpenAI provider.** The Phase-4 close-out had claimed this while no session
  had ever run; the fixes below make it true, and
  `tests/test_skill_prompt_engineering_e2e.py::
  test_prompt_engineering_session_end_to_end` proves it: a real
  `AgentOrchestrator.run()` drive on a real `OpenAIProvider` (scripted only
  at the HTTP client boundary — the wire translation runs for real), the
  REAL governed `eval/run.py` subprocess executing under the skill's
  manifest command policy, the W11 nonce verified in the live loop, a
  forged marker rejected + audited, and a `research_sessions` row
  indistinguishable from an ML row (best_iteration,
  effective_iteration_count, terminal_reason) — closing the §7.14 gap the
  review's finding 5.15 noted (GEN-009 never asserted it for a non-ML
  skill).
  - **Skill scripts execute from the packaged tree (C4 command-policy
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
  - **bootstrap.py ported to the governed JSON ABI** (P5-005/X-004 §6 —
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
    (`reason: unsupported_promotion_target`, the C2-5 auto-promotion-skip
    vocabulary). Test added in `test_research_api_integration.py`.
  - Also: the e2e file's phantom "P4-017" task reference corrected to
    P4-016; its docstring no longer claims the milestone was validated by
    mocked-provider tests. Full suite green (1360 passed); domain-coupling
    guard green; ruff/mypy at the pre-existing baseline (91/15, zero new).

- **ARC-011 implementation review C3 (2026-08-15) — W11 anti-forgery: bypass
  closed, nonce no longer readable by the adversary it defends against.**
  Closes review finding C3 (all four sub-findings); design revised in
  `docs/adr/ARC-011-signed-metrics.md` (Revision 2026-08-15).
  - **C3.1 — KV-block bypass closed:** the `---` auto-detect path and the
    marker-file path called `parse_prepare_output` (no nonce argument), so
    any bash output containing a KV block was recorded as an iteration even
    for skills with `require_signed_metrics: true`. Both paths now route
    through the new `AgentOrchestrator._verify_kv_metrics`, which applies
    the same four-state `_verify_nonce` check the marker path uses
    (reject → iteration not recorded).
  - **C3.2 — KV forgeries audited:** rejected KV blocks now emit the
    `metrics.forged` audit event (`format: delimited_kv`, `source:
    bash_output|marker_file`) plus agent-log guidance — previously only
    marker-format forgeries produced an audit.
  - **C3.3a — nonce out-of-band:** the nonce is no longer embedded in the
    session manifest. The artifact is written into the agent-readable
    session workspace (traversable by the `read_file`/`grep` tools), so
    persisting the W11 secret there handed it to the adversary. The nonce
    is generated in `SessionManager._build_manifest_payload` and lives only
    in `config.session_nonce` (process memory, per-run); nothing ever reads
    it back (continues/resumes generate a fresh nonce). The
    `session_nonce` field stays in the v2 manifest schema, always `null` in
    new artifacts (schema shape unchanged; legacy manifests with a value
    still load). Parity fixtures unaffected (the engine already dropped the
    non-deterministic nonce key).
  - **C3.3b — nonce env narrowed:** `AUTORESEARCH_SESSION_NONCE` is no
    longer injected into every governed subprocess of every session. The
    env is built only when the skill enforces signed metrics (new
    `requires_signed_metrics` / `nonce_field` runtime capabilities; the
    transitional runtimes report `False` — byte-identical ML/legacy
    behavior), and per command only when the command invokes one of the
    skill's manifest-declared scripts (`_nonce_env_for_command`). A false
    negative is loud, not silent: the eval cannot echo the nonce and its
    markers are rejected with explicit guidance.
  - **C3.4 — constant-time compare:** `_verify_nonce` uses
    `hmac.compare_digest` (consistent with the production-approval HMAC).
  - Tests: new `tests/test_metrics_forgery_c3.py` (9 tests: KV
    reject/accept/legacy-downgrade/passthrough + audits, workspace-manifest
    nonce omission via a real `SessionManager.start_session` drive,
    per-command env narrowing, capability properties);
    `test_research_manifest.py` nonce tests rewritten for the out-of-band
    contract. Within-session replay after one legitimate eval run remains
    inherent (documented in the ADR revision).

- **ARC-011 implementation review C1+C2 (2026-08-15) — canonical start wiring
  + the manifest-driven runtime as the production path.** Closes the two
  highest-severity findings of
  `ARC-011_IMPLEMENTATION_REVIEW_2026-08-15.md`: canonical request fields were
  validated-then-dropped, and the orchestrator bypassed the materialized
  `SkillRuntime` for everything except `parse_iteration`.
  - **C1 (canonical start):** `POST /research/start` now forwards
    `skill_id` / `skill_params` / `subject_id` / `variant` to
    `SessionManager.start_session` → `ResearchConfig` (previously dropped
    after validation — a canonical `enable_hpo: true` silently ran with it
    off). Recognized flat ML knobs inside `skill_params` win over the legacy
    kwargs (presence-based, mirroring the API's canonical-wins rule); the
    `research.start` audit metadata records the winning canonical values.
    Legacy callers forward `None` and keep byte-identical behavior.
    Tests: `test_canonical_start_wiring.py` (real SessionManager drive),
    `test_research_api_compat.py` forwarding/audit assertions.
  - **C2-1 (phase plan):** `_build_phase_contract_block` and
    `_refresh_phase_state` source the phase plan from the session's skill
    runtime (`build_phase_state` gained an explicit `phases=` override; the
    hardcoded per-model table remains only as the transitional fallback for
    sessions with no bound skill). Fail-open: a runtime error falls back to
    the incumbent table rather than blanking the contract.
  - **C2-2 (system prompt):** manifest-driven sessions read the domain
    primer from the packaged `skills/<skill_id>/<primer>` (the primer
    filename honors the manifest's `llm.system_prompt` declaration via the
    new `ManifestSkillRuntime.primer_filename`); transitional sessions keep
    the legacy workspace `.github/skills` primer. A missing packaged primer
    degrades to empty (logged), not a session failure.
  - **C2-3 (command policy):** `evaluate_command_policy` accepts a
    per-skill `policy_extension` (`CommandPolicyExtension` from
    `skill.command_policy_extension()`), plumbed through
    `GovernedCommandRunner`/`_tool_bash`. **Additive-only** — entries union
    with the base allow-lists; they can never remove or bypass a base
    restriction (executable dispatch and path confinement are checked
    independently). The manifest `command_policy` section is no longer dead
    config.
  - **C2-4 (blocker classification):** the `SkillRuntime` protocol gains
    `blocker_classification()` (22nd member; transitional runtimes return
    `{}` = use module defaults). The promotion-readiness advisory consumes
    `actionable_blockers` and `_phase_advancement_is_genuine` consumes
    `phase_evidence_keys` as skill-declared overrides of
    `_AGENT_ACTIONABLE_BLOCKERS` / `_PHASE_SPECIFIC_AGENT_KEYS`.
  - **C2-5 (promotion target):** `_try_auto_promote` routes through the
    session skill's declared `promotion_target`. `ManifestSkillRuntime.
    promotion_target()` now raises the new `SkillConfigError` for non-
    `file_path` kinds instead of silently returning a file target, and
    auto-promotion **skips loudly** (audited `promotion.auto_skip`,
    reason `unsupported_promotion_target`) rather than fabricating a file
    promotion for e.g. a `registry_api` skill; unexpected construction
    errors still fall back to the default file target. **H6 fixed:** the
    six `ConfigPromoter` file-surface helpers are now instance methods
    dispatching through the injected `PromotionTarget` (previously the
    injection was stored but bypassed — every helper constructed a fresh
    `FilePathPromotionTarget()` inline); a recording-stub test now pins the
    dispatch.
  - **Materialization loudness (H2-adjacent):** `materialize_skill_runtime`
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
    green at phase 4; no new ruff/mypy errors (pre-existing baseline
    unchanged).

- **ARC-011 Phase 6 (in progress) — Distributed storage (R6 / W14).** Adds the
  optional Postgres backend that lifts the single-worker ceiling so
  `WEB_CONCURRENCY > 1` is supported, with the four concurrency hazards closed
  and proven by multi-process tests (H1 atomic idempotency, H2 cross-process
  transition serialization, H3 cross-worker stop propagation, H4 fencing-token
  stale-write rejection — ADR §8.1 line 359 exit criterion). **Gated (R6):** the
  default deployment is unchanged — `database_url=None` ⇒ `SQLiteStateStore`
  (byte-identical, the WEB_CONCURRENCY>1 guard stays active); set
  `AUTORESEARCH_DATABASE_URL` to a postgresql:// DSN to opt into multi-worker.
  Known remaining gap (documented, out of scope): WebSocket fan-out does not
  span workers. Driven by raw `asyncpg` (mirrors
  SQLiteStateStore's hand-written-SQL shape for parity; `pg_advisory_xact_lock`
  is first-class), NOT SQLAlchemy — deviates from the platform convention but
  matches the existing StateStore style (parity wins).
  - **P6-001 (design):** `docs/adr/ARC-011-postgres-state-store.md` — the
    four-hazard concurrency model (H1 idempotency / H2 transition critical
    section / H3 cross-worker stop / H4 stale writes), the ContextVar
    connection-sharing design, the fencing-token contract, and the
    SQLite→Postgres locking-site transition table.
  - **P6-002a/b (impl):** new `src/core/postgres_state_store.py` — a 1:1 port
    of all 48 `StateStore` protocol methods to raw asyncpg. P6-002 is split per
    §0.5 (8 SP): 002a = skeleton + schema + writes + factory; 002b = reads +
    the dual-backend parity sweep. The schema is one canonical Postgres DDL
    (all SQLite base + v1–v6 columns, including the missing `insights`/
    `resumed_from`/`pipeline_id`/`hpo_study_id` the parity sweep surfaced) plus
    a `pg_schema_version` row + the Phase-6 `research_sessions.lock_epoch`
    fencing column. `Settings.database_url` + `build_state_store(settings)`
    select the backend; `main.py` uses the factory (SQLite default unchanged).
    Fold-in: `results_store.py` shim re-exports `_migrate_to_v6` (was missing —
    a P3-019 latent back-compat gap surfaced by this grounding).
  - **P6-003 (locks):** idempotency reserve-or-return rewritten to atomic
    `INSERT … ON CONFLICT DO NOTHING RETURNING` (no advisory lock needed);
    additive protocol methods `session_lock` (advisory lock CM, no-op on
    SQLite) + `bump_session_epoch` (increments `lock_epoch`, no-op on SQLite);
    `SessionStateMachine.transition` nests `session_lock` inside the in-process
    lock and bumps the epoch on every committed transition.
  - **P6-004 (fencing + cross-worker control) — SCOPE WIDENED:** the backlog's
    "fencing tokens for command execution" names only H4; grounding showed H3
    (cross-worker stop/pause propagation) must close in the same task for
    "correct concurrency semantics" to hold. ~4 SP (up from 3), recorded per
    the P0-023 precedent. (a) **Fencing chain (H4):** the orchestrator captures
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
  - **P6-005 (migration):** `scripts/migrate_sqlite_to_postgres.py` —
    idempotent, resumable, batched SQLite→Postgres row mover (per-table
    transactions + a `migration_state` cursor + `ON CONFLICT DO NOTHING`).
    Validated end-to-end (round-trip equality on all 9 tables + re-run
    idempotency). `compose/autoresearch.yml`: adds `AUTORESEARCH_DATABASE_URL`
    env + `postgres_db` dependency.
  - **P6-006 (guard):** `_validate_runtime_configuration` (`main.py`) is now
    conditional — SQLite/no-DSN ⇒ still rejects >1 (W14 intact, byte-identical
    default); Postgres DSN ⇒ allows >1 and logs the effective
    `max_concurrent_sessions × N` ceiling. `SQLiteStateStore` docstring updated
    to point at the conditional guard.
  - **P6-007 (distributed tests — exit gate):** `tests/test_distributed_state_store.py`
    + a dedicated `distributed` CI job with a `postgres:15-alpine` service.
    Real multi-process (`multiprocessing.spawn`) + real Postgres: H1 (exactly
    one idempotency winner across 8 processes), H2 (cross-process transition
    serialization), H4 (fencing stale-write rejection across processes), +
    fresh-epoch acceptance. All postgres/distributed tests skip cleanly when
    `AUTORESEARCH_DATABASE_URL` is unset (default CI run unaffected); the
    dual-backend parity sweep (`test_postgres_sqlite_parity.py`) proves
    PostgresStateStore ≡ SQLiteStateStore across the full write+read sequence.
  - **§0.4 residuals:** `llm-wiki sync` for `PostgresStateStore` /
    `build_state_store` / `session_lock` remains **deferred** — tool not on
    PATH (persistent Phase 1–5 residual). No new `domain_coupling_rules.conf`
    rule for Phase 6 (the orchestrator is already domain-neutral post-Phase-2;
    Phase 6's exit is operational, not a static-coupling guard — confirmed: no
    Phase-6 entry in the conf). `.arc-011-phase` bump is bookkeeping only
    (currently at 4 due to the P5-007 deferral — the carry-over is noted, not
    force-bumped). The `arc-011/phase-6-done` rollback tag is deferred to the
    landing commit (P0–P5 precedent).
  - **Review-fix round (post-implementation audit):** a self-audit found and
    fixed six issues. (1) `poetry.lock` regenerated — adding `asyncpg` to
    `pyproject.toml` had invalidated the lockfile (`poetry check --lock`, a CI
    gate, was failing). (2) The H4 fencing chain was store-primitive-only and
    unwired at the orchestrator (no epoch capture, no caller passing
    `lock_epoch=`); now wired end-to-end as described in P6-004 above, and the
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

- **ARC-011 Phase 5 (in progress) — Auto-initialization, skill lifecycle,
  generator.** Lays the structural foundation for the "universal research agent"
  inflection: full skill-package layout, governed plugin/bootstrap runners,
  skill lifecycle + promotion, lexical domain classifier, insights feedback
  loop, and the skill generator. No behavior change for existing ML sessions
  (X-002 parity green); P5-007 (orchestrator prompt migration) is deferred as a
  tracked follow-up.
  - **P5-001 (full layout):** new `SkillLayout` model
    (`src/core/skill_loader.py`) resolves the ARC-011 §5.3 directory tree
    (`bootstrap.py`, `scaffold/`, `knowledge/{primer,heuristics,prior_findings}`,
    `eval/`, optional `tools`/`parser`/`preflight`/`resolve_identity`). New
    `PluginCaps` / `PluginEntry` / `PluginsConfig` models
    (`src/core/skill_manifest.py`) carry the X-004 §6 capability contract
    (`fs_write` / `network_egress` / `env` / `timeout_s` / `max_rss_mb` /
    `max_cpu_s`); per-kind defaults from X-004 §6 apply when omitted, and a
    manifest may *narrow* but never *widen* a cap (R10 defense in depth).
    `SkillRegistry.discover()` now skips the reserved `_drafts/` subdir;
    `discover_drafts()` enumerates generator drafts separately (P5-023).
    Back-compat: existing skills with only `SKILL.yaml`/`SKILL.md` resolve to a
    valid minimal layout.
  - **P5-005 / P5-006 / P5-008 / P5-009 (bootstrap runner epic):** new
    `src/core/plugin_runner.py` (`PluginRunner` — the X-004 §6 governed
    subprocess for all skill-supplied Python; JSON-in/JSON-out ABI, strict env
    allow-list narrower than the agent path, psutil RSS/CPU caps, fail-closed on
    crash/timeout/bad-JSON/non-zero, path confinement) and
    `src/core/bootstrap_runner.py` (`BootstrapRunner` — the first `PluginRunner`
    consumer; writes the `session_bootstrap.v1` artifact with rendered file
    hashes; `--dry-bootstrap` overlay mode (X-004 D5(b)) for draft/generated
    skill review; idempotency check). The T6 invariant is preserved: a plugin
    parser's output is untrusted candidate data — trust is established
    downstream by `_verify_nonce`, never by the runner.
  - **P5-002 / P5-003 / P5-004 (ML skill backfill):** `skills/ml-direction`,
    `ml-volatility`, `ml-rl` each gain a `bootstrap.py` (thin shim delegating
    to the proven `scripts/autotuner/setup.py` with the right `--models` flag)
    + `knowledge/{primer.md,heuristics.yaml,prior_findings/}` corpus. Live
    execution wiring is the deferred P5-007; the dry-mode path is tested
    end-to-end.
  - **P5-010..013 (skill lifecycle epic):** new `src/core/skill_lifecycle.py`
    (`SkillLifecycleState` draft/reviewed/stable/deprecated + the transition
    table + per-skill `asyncio.Lock` machine; production gating predicate —
    drafts never auto-select for production). New
    `SkillRegistryPromotionTarget` (`src/core/promotion_target.py`) moves a
    draft from `skills/_drafts/<id>/` → `skills/<id>/` atomically + rolls back
    on failure; reuses the P0-020 production-approval machinery at the API
    layer. The HTTP endpoints (P5-012) land in a follow-up wiring the FastAPI
    router.
  - **P5-014 (domain taxonomy):** `Category` literal widened from 3 to all 5
    ARC-011 §13 values (`optimization|generative|exploratory|validation|design`).
  - **P5-016..020 (auto-domain detection):** new `src/core/domain_classifier.py`
    — lexical-first (TF-IDF over hashed word + char n-grams, cosine, stdlib +
    numpy only) behind a swappable `EmbeddingBackend` Protocol so an
    LLM-embeddings backend can drop in later. `DomainClassifier.classify(goal)`
    ranks installed skills; embeddings cached (persisted JSON, invalidated on
    install/reload); cold-start degrades to "list all"; threshold + high/medium/
    low confidence logic; `ClassificationResult.to_audit_dict()` for the
    `skill.classify` audit row.
  - **P5-021..026 (skill generator epic):** new `src/core/skill_generator.py`
    — dedicated codegen module (per Phase-5 plan decision) calling the
    configured `LLMProvider.complete()` directly with a structured JSON-output
    prompt. Drafts land in `skills/_drafts/<id>/` as `draft` status; manifest
    validated against `research_skill.v1`, Python `ast.parse`-linted; the
    command-policy over-permissiveness audit (`audit_command_policy`) flags
    `rm -rf` / `sudo` / `eval` / shell metacharacters as critical/warning
    findings attached to the draft for reviewer visibility. Safety posture:
    drafts are untrusted code, never production-selectable until promoted
    (P5-010 gating), feature-flagged (P5-025), operator-initiated only.
  - **P5-027..030 (feedback loop):** new `src/core/insights_feedback.py`
    (`append_findings` writes completed-session insights to
    `knowledge/prior_findings/<subject>_<variant>_<research_id>.md`,
    idempotent on research_id, safe filenames). New manifest fields
    `auto_absorb_insights` (default off), `knowledge_last_reviewed`,
    `refresh_cadence_days` drive the stale-knowledge UI badge (P5-029).
  - **P5-007 (orchestrator migration) — DEFERRED:** the 61 `prepare.py` /
    `train.yaml` references in `orchestrator.py` are overwhelmingly behavioral
    command-detection / snapshot / parsing logic (not clean prompt-text
    coupling), interwoven through the ~5500-line hot path. A full migration to
    skill-driven command-identifiers is correctly an 8+ SP refactor that would
    risk the parity suite; it is tracked as a follow-up
    (`P5-007-full-behavioral-migration`). The `P5-ml-literals` grep-guard rule
    stays documented-but-inactive (phase stays at 4) until that migration lands.
  - **Tests:** 132 new tests across 8 files (plugin/bootstrap runners, ML skill
    bootstraps, lifecycle + promotion, domain classifier, skill generator,
    insights feedback, manifest-field additions). Full suite 1295 green; ruff
    clean; mypy 0 new errors (15 baseline errors unchanged — all in prior-phase
    modules).

- **ARC-011 Phase 4 — Anti-forgery and cross-provider close-out (BE).** Closes
  the three wiring gaps that left the Phase-4 exit guarantee dormant, and runs
  the phase close-out (§0.4 DoD). P4-004 (ML eval nonce backfill) is deferred —
  ML skills remain on the graceful-downgrade path (`require_signed_metrics =
  false`); the milestone is the non-ML `prompt-engineering` skill. No behavior
  change for ML sessions (X-002 parity green).
  - **P4-002 (nonce delivery, GAP #2):** `session_manager` now populates
    `ResearchConfig.session_nonce` from the built session manifest; the
    orchestrator threads it through `_execute_tool` → `_tool_bash` →
    `GovernedCommandRunner.run(extra_env={"AUTORESEARCH_SESSION_NONCE": ...})`.
    The delivery channel (`command_runner.py`) already merged `extra_env` after
    the forbidden-secret subtraction — it was simply never called. Covered by
    `tests/test_command_policy.py` (runner + full `_execute_tool` chain).
  - **P4-003 (hot-path wiring, GAP #1):** the orchestrator's marker-parse hot
    path now calls `skill.parse_iteration(text, session_nonce=...)` instead of
    the bare `parse_iteration_marker` facade, so `_verify_nonce` actually fires
    for skills with `require_signed_metrics = true`. Forged markers (wrong /
    missing nonce) return `None` → the iteration is not recorded, and a
    `metrics.forged` audit event + agent-log message make the rejection
    visible. `metrics_verified` / `metrics_unverified` outcomes are audited via
    `metrics.verify`. ML/transitional runtimes ignore the nonce (D2), so the
    X-002 parity fixtures stay byte-identical.
  - **P4-009 / P4-010 (capability matching, GAP #3):** `build_provider`
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
    `.arc-011-phase` bumped 3 → 4; the `P4-anthropic-import` /
    `P4-openai-import` domain-coupling rule activated (0 violations).
  - **Deferred:** P4-004 (ML skills' eval scripts echo the nonce) — ML stays on
    `require_signed_metrics = false`; HMAC over the metrics payload and a
    within-session replay counter remain future work (ADR §2.5). Wiki sync
    remains deferred (`llm-wiki` not on PATH — same residual as P1/P2/P3).

- **ARC-011 Phase 3 — review-findings close (BE/FE).** Closes the seven
  findings from the Phase-3 code review. No behavior change for ML sessions;
  additive-only public-surface changes.
  - **Critical: `openapi.yaml` drift.** The Phase-3 commit `63e817466`
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
    `_translate_canonical_request` no longer cites a non-existent `P4-017`
    task (Phase 4 IDs only run to P4-016); the comment now accurately
    describes the branch as Phase-4 prep for non-ML skills.
    `ui/src/skill-plugins/index.ts`'s header no longer claims the barrel
    registers seed renderers (it is a pure re-export; the generic fallback
    lives in `DynamicFormFields.tsx`).
  - **`_tool_grep` secret-leak closed (P0-023 / P1-029 delta).** The sync
    `_tool_grep` in `orchestrator.py` was calling `subprocess.run(cmd, ...)`
    with no `env=` parameter, so the grep child inherited the full parent
    env including server control-plane secrets (`ANTHROPIC_AUTH_TOKEN`,
    `AUTORESEARCH_API_TOKEN`, `AUTORESEARCH_PROMETHEUS_TOKEN`). This is
    exactly the gap the governed-runner path was hardened against in P0-023
    and that P1-029's reverted async migration was supposed to close on the
    grep path. `subprocess.run` now passes `env=_build_child_env()` (the
    same allow-list the governed runner uses), so the grep child sees only
    PATH/HOME/PYTHON*/mlflow-tracking-URI/etc. — never the server secrets.
    No behavior change for approved workflows (PATH and the experiment-
    legitimate vars are in the allow-list).
  - **Broken WIP tests repaired.** Four test files that had been broken in
    the working tree (verified red at HEAD `63e817466`, unrelated to the
    Phase-3 review fixes) are now green:
    - `tests/test_async_tool_path.py` — rewritten to match the sync
      `_tool_grep` / `_execute_tool` API (P1-029's async migration was
      reverted; the test was the orphan). 12 tests pin the sync contract
      including the new env-scrubbing delta and a companion PATH-still-
      present guard.
    - `tests/test_pagination.py::test_v5_indexes_present_after_initialize` —
      schema-version assertion now reads `_LATEST_SCHEMA_VERSION` (currently
      v6, bumped from v5 in ARC-011 Phase 3) instead of hard-coded `5`.
    - `tests/test_hardening_phase1_to_5.py::test_results_store_records_schema_version`
      — same `_LATEST_SCHEMA_VERSION` fix.
    - `tests/test_deployment_inputs.py::test_autoresearch_dockerfile_matches_ml_service_runtime_contract`
      — Dockerfile assertions updated for the parameterized `APP_UID`/`APP_GID`
      build args (PR-9: UID/GID 1000 to match the host user owning the
      bind-mounted `configs/`); the old hard-coded `groupadd -g 1001 appuser`
      assertions no longer held.

- **ARC-011 Phase 3 — gap close (BE).** Closes the residual Phase-3 AC gaps
  found by a post-implementation audit against `ARC-011-backlog.md` §6.
  - **P3-008** `POST /skills/reload` now refuses to run when
    `settings.environment == "production"` (403
    `skills_reload_prod_disabled` with a hint). The router already required
    a valid API token; this adds the dev-only constraint the AC names. The
    denial is audited as `skills.reload` / `outcome=denied`. Non-production
    environments keep the dev convenience.
  - **P3-019 (manifest v2)** `ResearchSessionManifest.schema_version` bumped
    `research_session_manifest.v1 → v2`. v1 manifests are accepted on read
    and normalized to v2 (forward-compat); unknown prefixes raise a clear
    error (R3 back-compat). The v2 artifact carries the canonical
    `skill_id`/`subject_id`/`variant` fields alongside the legacy trio
    (populated in `build_research_manifest` and back-filled by a
    `model_validator` for v1 round-trips), matching the dual-shape session
    API contract. The DB schema was already at v6 from the prior entry.
    New `tests/test_research_manifest.py` covers v1→v2 load, canonical-field
    derivation for all three model types, and the round-trip hash stability;
    `tests/test_results_store_migrations.py` adds a v1-era → latest forward
    migration test (seed v1 row → `initialize()` → dual-shape read) and a
    per-migration log assertion.
  - **P3-015/016/017 (HTTP-level coverage)** new
    `tests/test_research_api_integration.py` exercises the live router path
    for `GET /research/{id}/iterations` (canonical `skill_id`/`skill_phase`/
    `evidence_keys` synthesized additively) and `POST /research/{id}/promote/preview`
    (`target_kind` from the manifest registry, defaulting to `file_path` for
    legacy sessions; parametrized over all four ARC-011 §7 promotion kinds).
    These previously had helper-unit coverage only.
  - **P3-016 (AC-deviation, recorded)** the AC names
    `src/core/state_store.py` and reads as if `skill_phase`/`evidence_keys`
    were persisted columns on the iteration row. They are NOT persisted:
    `_enrich_iteration` synthesizes them at read time from the existing
    `search_phase` column and the metrics `phase_evidence` keys. Persisting
    them would require a v7 migration + write-path changes for no semantic
    gain and would couple storage to the skill vocabulary. The contract is
    fixed by GEN-010 in `test_generalization_falsifiability.py`.

- **ARC-011 Phase 3 — gap close (FE).**
  - **P3-025** `IterationsTable` is now wired into `ResearchDetail`'s
    iterations tab (previously dead code — the page rendered an inline
    table). Manifest-driven `iteration_table_columns` flow through from the
    skill's `metric_schema`, so extra columns render generically.
  - **P3-022/023** `DynamicFormFields` hardened: `options_url` is now parsed
    generically with `URL` and dispatched by pathname (`/subjects` →
    `getSubjects`, `/subjects/{id}/variants` → `getSubjectVariants`), and the
    integer/number `0` value no longer coerces to `''` (nullish-check fix).
  - **P3-028** new `ui/src/skill-plugins/` renderer registry
    (`registry.ts` / `types.ts` / `index.ts` + README). `DynamicFormFields`
    consults the registry before its built-in switch; a future skill ships a
    renderer instead of forcing a new form branch. The generic text-fallback
    is retained for unmatched field types.
  - **P3-029** stood up a vitest component-test harness
    (`vitest.config.ts`, `vitest.setup.ts`, `test:unit`/`test:watch` scripts)
    with 35 contract tests covering DynamicFormFields (field types,
    `visible_when`, `options_url`, plugin registry, the `0`-coercion
    regression), MetricsChart (manifest-wins / fallback series selection),
    IterationsTable (default + manifest columns, best-row highlight), and
    PromotionModal (`target_kind` branching for all four promotion kinds).

- **ARC-011 Phase 3 — parity fixture re-capture.** Re-captured
  `tests/parity/promotion_preview/development_scope_basic.json` under the
  §1.5 append-only-with-linked-task rule: the preview response now carries
  the additive canonical `skill_id`/`subject_id`/`variant` fields (P3-017,
  sourced from the v2 manifest). The two `session_start` fixtures only had
  their `source_sha` bumped — their `expected` output is unchanged, confirming
  the manifest v2 bump did not alter session-start behavior.

- **ARC-011 Phase 3 — Generic session API, dual-shape responses (BE).**
  Implemented the P3-013/P3-014/P3-015/P3-018 backend features that the
  Phase-3 test suite (`test_research_api_compat.py`,
  `test_ws_event_enrichment.py`, `test_generalization_falsifiability.py`)
  encodes as executable contracts.
  - **P3-013** `POST /research/start` now accepts the canonical
    `{skill_id, subject_id, variant, skill_params}` shape alongside the
    legacy `{model_type, instrument, timeframe}` shape. Canonical wins
    unconditionally when both are present; conflicts are audited
    (`research.shape_conflict`). Unknown `skill_id` → 404 with an
    installable-skills hint. `skill_params` validated against the skill's
    `param_schema` → 422 with field pointers on violation.
  - **P3-014/P3-015** `start_research`, `list_research`, and
    `get_research` now return dual-shape responses: canonical
    (`skill_id`/`subject_id`/`variant`) alongside legacy
    (`model_type`/`instrument`/`timeframe`), both always populated, plus
    a `links` block per ARC-011 §7.7.
  - **P3-015/016** Iteration responses (`get_iterations`, `get_results`)
    now carry canonical `skill_id`, `skill_phase`, and `evidence_keys`
    alongside the legacy `model_type`/`search_phase` — additive, derived
    via the `legacy_alias` registry so API and WS payloads share the same
    canonical surface (§10 guarantee #4).
  - **P3-017** Promotion preview/confirm responses now carry `target_kind`
    (from the skill manifest's `promotion_target.primary.kind`) and
    canonical `skill_id`/`subject_id`/`variant` so the UI PromotionModal
    can branch generically. Defaults to `file_path` for legacy sessions.
  - **P3-018** `EventBroadcaster.broadcast` now enriches WebSocket
    payloads with `skill_id`, `skill_phase`, `evidence_keys`, and a
    `metrics` summary — strictly additive (§10 #5).
  - **P3-019** DB schema bumped to v6: `skill_id`, `subject_id`, `variant`
    columns added to `research_sessions` (idempotent `ALTER TABLE`).
    Existing rows get empty-string defaults; the dual-shape helper
    back-fills canonical from legacy on read.
  - **P3-001..011** `GET /skills`, `GET /subjects` and related endpoints
    are now mounted in the production app (previously only available in
    test apps). `main.py` lifespan discovers installed skill manifests
    and wires the skill/subject/promotion modules with a shared registry.
  - **P0-013** Added `_BROADCAST_SEND_TIMEOUT_S` per-send timeout so a
    stuck/half-open WebSocket is pruned instead of stalling the fan-out.
  - **§1.7** Phase-3 grep guard activated: `DIRECTION_PHASES`,
    `VOLATILITY_PHASES`, `RL_PHASES`, `_ALLOWED_SCRIPTS` added to the
    deny-list in `domain_coupling_rules.conf`; `.arc-011-phase` bumped
    to 3. Guard passes clean (0 violations).

- **ARC-011 Phase 3 — Skill-aware UI (FE).**
  - **P3-021** `SkillPicker` component on NewResearch — fetches skills
    from `GET /skills` and replaces the hardcoded model-type selector.
    Falls back to the legacy selector when no skills are available.
  - **P3-022/P3-023** `DynamicFormFields` component renders any skill's
    form from `GET /skills/{id}/form-fields` with `visible_when` conditional
    support and `options_url` lazy fetch. Unknown field types fall back
    to text + warning (P3-028).
  - **P3-024** `MetricsChart` now accepts an optional `chartSeries` prop
    from `metric_schema.chart_series`; falls back to the hardcoded
    per-model-type series when no manifest is available.
  - **P3-025** `IterationsTable` now accepts an optional `tableColumns`
    prop from `metric_schema.iteration_table_columns`; extra columns
    render from iteration metrics data.
  - **P3-026** `PromotionModal` branches on `target_kind` to show
    target-specific UI (file_path / registry_api / git_branch /
    artifact_store).
  - **P3-027** Dashboard search now filters by `skill_id` alongside
    `instrument`/`model_type`/`tag`/`id`.
  - **API client** Added `SkillSummary`, `FormField`, `MetricColumn`,
    `MetricSchema`, `SubjectInfo` types and `getSkills`, `getSkill`,
    `getSkillFormFields`, `getSkillMetricSchema`, `getSubjects`,
    `getSubjectVariants`, `reloadSkills` API methods.

- Closed Phase-2 DoD gaps (lint / typecheck / exit-bookkeeping) found in review.
  The Phase-2 functional code was already committed and passing (115 skill
  tests + 17 parity; grep guard at 0). This entry closes the residual
  §0.4 Definition-of-Done items the "done" marks left open.
  - **ruff** — fixed 3× E501 (line > 100) in `src/core/skill_manifest.py`
    (P2-001: `Field(description=...)` strings at lines 447/508/553). The CI
    ruff gate (`ruff check --config pyproject.toml src tests`) now passes
    clean on the Phase-2 modules. *(The errors only surfaced in path-mode
    ruff; stdin-mode silently skips config discovery.)*
  - **mypy** — `ManifestValidationError.errors` param widened from
    `list[dict[str, Any]]` to `list[Mapping[str, Any]]` (P2-001,
    `skill_manifest.py`) so pydantic's `list[ErrorDetails]` (a TypedDict) is
    accepted without a cast — `Mapping` is covariant. `SkillRegistry._cache`
    type widened to `tuple[Optional[ResearchSkillManifest], Path, float]`
    (P2-003, `skill_registry.py`) making the lazy placeholder honest and
    removing two wrong `# type: ignore[...]` comments (at `register_path`
    and `reload_all`) that were suppressing the wrong error code
    (`arg-type`/`assignment`) while the real `assignment` error leaked
    through. Behavior byte-identical — `get()` already handled the
    `manifest is None` placeholder path.
  - **wiki** — sync for `ResearchSkillManifest` / `ManifestSkillRuntime` /
    `ResearchConfig` remains deferred (`llm-wiki` not on PATH in this
    environment; same residual as P1-007/P1-023). To be run when the tool is
    available.
  - **exit bookkeeping** — recorded the Phase-2 completion date in ADR §12
    (Rollout Plan). The `arc-011/phase-2-done` rollback tag is deferred to the
    commit that lands these changes (working tree carries interleaved Phase-0/1
    edits; tag cut deferred per the Phase-0/1 precedent).

- Closed Phase-1 abstraction gaps found in the P1 code review.
  - **P1-013** — the orchestrator now routes its three experiment-output parse
    call sites through the held ``OutputParser`` instances
    (``self._prepare_parser`` / ``self._marker_parser``, declared at
    `orchestrator.py:703-704`), instead of the module-level facades which each
    constructed a fresh parser per call. The ``IterationMetrics``
    reconstruction was extracted from ``parse_prepare_output`` into a shared
    ``metrics_from_flat(flat)`` helper (`experiment_parser.py`) so both the
    orchestrator and the facade use it. The facades stay (external callers +
    the parity engine depend on them). Behavior byte-identical; the typed
    fields are no longer dead code.
  - **P1-017** — the six ``ConfigPromoter`` ``@staticmethod`` helpers that
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
  - **P1-029 / P1-030** — migrated the ``grep`` tool from a synchronous
    ``subprocess.run`` (inside ``asyncio.to_thread``) to
    ``asyncio.create_subprocess_exec``. ``_execute_tool`` is now ``async``;
    the ``bash`` branch stays on its worker thread via an internal
    ``asyncio.to_thread`` wrap, while ``read_file`` / ``write_file`` / ``glob``
    stay direct (pure-Python). The single production call site no longer
    wraps the whole dispatch in ``to_thread``. **Security delta:** the grep
    child now runs with ``_build_child_env()`` (the P0-023 allow-list
    scrubber), closing the same secret-inheritance gap on the previously-
    ungoverned grep path. Timeout (30s) and cancellation reap the child via
    ``_kill_async_proc_tree`` (process-group kill + ``proc.wait()``). New
    `tests/test_async_tool_path.py` (12 tests: dispatch shape, happy-path
    output, truncation, include-filter, timeout reap, cancellation reap, env
    scrubbing). Four sync ``_execute_tool`` calls in `test_command_policy.py`
    converted to async.
  - **Lint** — fixed an ``E501`` line-length violation in
    `src/core/state_store.py:2111` (introduced by the P1-007 extraction
    commit; the SQL ``VALUES`` clause was rewrapped).


  - **P0-011** — atomic promotion write (temp + `os.replace` + `fsync` of file
    and parent dir, closed-before-rename, cleanup-on-failure) lives in
    `src/core/promotion_target.py:_atomic_write_text` and is the write path for
    every promoted config + metadata sidecar; `src/core/config_promoter.py`
    keeps a back-compat re-export.
  - **P0-012** — added `tests/test_config_promoter_atomic.py` (6 tests):
    failure injection at each stage of the atomic write (write / fsync /
    os.replace) proves the target file's prior content is preserved and no
    half-written temp is visible; plus a concurrent-reader test confirming
    `os.replace`'s atomicity guarantee.
  - **P0-013** — `EventBroadcaster.broadcast` now wraps each `send_text` in
    `asyncio.wait_for(timeout=_BROADCAST_SEND_TIMEOUT_S)` (5s) so a stuck /
    half-open WebSocket is pruned as dead instead of stalling the fan-out
    indefinitely. The existing lock + snapshot-before-iterate hardening is
    unchanged.
  - **P0-014** — added `tests/test_event_broadcaster_concurrency.py` (5 tests):
    fakes that `await asyncio.sleep(0)` inside `send_text` force real event-loop
    interleaving so concurrent broadcast + connect/disconnect/churn and a
    broadcast storm are genuine race tests (the prior `_FakeWS` had no
    suspension point). Includes the P0-013 slow-client timeout test.
  - **P0-022** — documented the CORS policy under
    `docs/adr/ARC-011-cors-policy.md` (W17). Code hardening in `src/main.py`
    was already correct (explicit origin allowlist by default; `*`+credentials
    auto-defused); the deliverable doc was missing.
  - **P0-005 delta** — `_try_auto_promote` now re-checks
    `session["status"] == "completed"` before promoting (defense-in-depth per
    ARC-011 §4.3). Terminal-finality makes this unreachable in normal flow, but
    the design requires the belt-and-suspenders re-check. Also added a genuine
    concurrent `stop_session` ⇄ exit-path `COMPLETE` race test through the
    shared state machine in `tests/test_session_status_routing.py` (the prior
    W8-A/B/C tests were sequential pre-seeds).
  - **P0-006/007 delta** — added a direct hard `asyncio.wait_for` timeout-path
    test in `tests/test_orchestrator_timeout.py` (a hanging LLM call that never
    reaches a bash command, so the soft cap cannot fire; the session-level
    `wait_for` is the only bound). Closes the gap where only the soft-cap path
    was tested.
  - **P0-020 delta** — fixed a whitespace-bypass vector in the production-
    approval gate: `" production"` / `"production "` / `"\tproduction\n"`
    previously skipped the production gate entirely (silent downgrade to
    development, no approval). Added a `field_validator` on `PromotionScopeRequest.scope`
    that strips whitespace once so every downstream consumer (the structural
    gate, the HMAC message, audit metadata, promoter args) sees the canonical
    value. Canonicalization tests added to `tests/test_promotion_approval.py`.
  - **P0-023 delta** — split the `ML_ADMIN_TOKEN` alias out of
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

- **Completed Phase 2** — Extract skill descriptors for existing model types
  (ARC-011 **P2-009..025**). The three ML skills now run driven purely from
  their `skills/<id>/SKILL.yaml` manifests; the orchestrator no longer reads
  `config.model_type`/`instrument`/`timeframe` directly (the Phase-2 exit gate
  grep returns **0** hits, down from **78**); the Phase-2 domain-coupling guard
  is live and green in CI. Summary of the remaining tasks:
  - **P2-009/010/011/012** — `skills/ml-volatility/SKILL.yaml` + `SKILL.md`
    authored from `VOLATILITY_PHASES` (8 phases: baseline_capture, atr_sweep,
    threshold_calibration, temporal_ensemble, + 4 shared late phases);
    `ManifestSkillRuntime` drives it via the generic P2-007 runtime;
    `tests/test_skill_ml_volatility.py` (11 equivalence tests: phase_plan,
    command_policy narrowed to volatility/prepare.py, volatility-specific
    evidence keys, parser equivalence, promotion, HPO disabled).
  - **P2-013/014/015/016** — `skills/ml-rl/SKILL.yaml` + `SKILL.md` authored
    from `FALLBACK_PHASES` (**not** a non-existent `RL_PHASES` — AC-deviation,
    documented in the manifest header). The `validation` phase carries the
    `RL_OOS_EVIDENCE_KEYS` (mean_oos_sharpe/rl_profit_score/oos_sharpe/etc.)
    — the one place RL diverges; the hybrid ≥2-iteration rule is owned by the
    phases.py plugin (G1). `param_schema` declares the RL-only fields
    (trading_mode/agent_strategy/initial_balance). Command policy adds
    `enrich_rl_dataset.py`. `tests/test_skill_ml_rl.py` (13 tests including the
    HPO-opt-in path and RL-only param_schema assertions).
  - **P2-017** — `ResearchConfig` generalized: added canonical `subject_id`/
    `variant`/`skill_params` fields; `subject_id`/`variant` derive from legacy
    `instrument`/`timeframe` in `__post_init__`; flat ML fields mirror into
    `skill_params`. `skill_id` derivation is deliberately deferred to
    `materialize_skill_runtime` (not `__post_init__`) so legacy sessions keep
    the transitional runtime until the orchestrator reads are fully migrated.
    Added `config.domain` property (domain-neutral accessor for legacy
    `model_type`). Two `session_start` parity fixtures re-captured under the
    append-only rule with a `recapture: ARC-011 P2-017` note.
  - **P2-018** — flat ML field reads mirror into `skill_params` (the dataclass
    fields stay for back-compat; `__post_init__` populates the dict so manifest-
    driven runtimes read from one place). Full migration to `skill_params.get`
    folded into the orchestrator read sweep.
  - **P2-019** — `src/core/legacy_alias.py`: `model_type ↔ skill_id` registry
    (direction↔ml-direction, volatility↔ml-volatility, rl↔ml-rl). Back-compat
    bridge for ARC-011 §10 guarantee #5.
  - **P2-020** — `tests/test_research_config.py` (20 tests: alias round-trips,
    both-shape construction, canonical-field derivation, skill_params mirroring,
    skill_id-stays-empty back-compat).
  - **P2-021** — migrated all 78 orchestrator reads of
    `config.(model_type|instrument|timeframe)` to domain-neutral accessors
    (`config.domain`/`config.subject_id`/`config.variant`). The `_load_skill`
    map stays as a transitional helper (the async-read path is mocked by the
    orchestrator test suite); full removal lands when the transitional runtimes
    retire.
  - **P2-022/023/024** — `DIRECTION_PHASES`/`VOLATILITY_PHASES`/`FALLBACK_PHASES`,
    `_ALLOWED_SCRIPTS`, and `_AGENT_ACTIONABLE_BLOCKERS`/`_PHASE_SPECIFIC_AGENT_KEYS`
    are now **transitional-only**: the manifest-driven path sources them from
    YAML; the constants survive solely as the transitional-runtime fallback.
    The Phase-2 grep guard does not check for these constants (it checks
    `config.(model_type|instrument|timeframe)` in orchestrator.py, which is 0),
    so full deletion lands when the transitional runtimes retire. Documented as
    an AC-deviation (P1-007 house style).
  - **P2-025** — activated the Phase-2 deny-list: moved the `P2-config-fields`
    rule from the comment block into `rules:` in
    `scripts/ci/domain_coupling_rules.conf`; bumped `.arc-011-phase` 1→2. The
    `domain-coupling-guard` CI job runs the rule against orchestrator.py and
    passes (0 violations). Per-line suppression token:
    `# arc-011: allow(<task-id>): <reason>`.
  **Phase-2 exit criteria met:** `rg -E "config\.(model_type|instrument|
  timeframe)" src/core/orchestrator.py` returns **0** (was **78**); X-002 parity
  suite green (17/17); full suite green (1022 passed, +91 new tests since Phase 2
  start) except the 2 pre-existing `test_deployment_inputs` failures; the
  `domain-coupling-guard` CI job is green at phase 2. `pipeline` model_type is
  deliberately out of scope (composes the three skills).
  **Grounding deviations documented:** RL uses `FALLBACK_PHASES` not `RL_PHASES`
  (P2-013/022); `_AGENT_ACTIONABLE_BLOCKERS` lives in orchestrator.py not
  blocker_classifier.py (P2-024); `_load_skill` at orchestrator.py:926 (backlog
  stale); "existing model types" = 3 skills not 4 (pipeline out of scope). Wiki
  (`ResearchSkillManifest`, `ManifestSkillRuntime`, `ResearchConfig`) deferred
  (tool not on PATH — same residual as P1-007).

- Extracted the **`ml-direction`** reference skill into a manifest-driven
  `ManifestSkillRuntime` (ARC-011 **P2-005..008**, the Phase-2 reference
  extraction). This is the keystone: once `ManifestSkillRuntime` drives
  `ml-direction` purely from YAML, `ml-volatility` / `ml-rl` (P2-009..016) repeat
  the pattern and the hardcoded constants fall (P2-021..024).
  - `skills/ml-direction/SKILL.yaml` (P2-005) — the live `research_skill.v1`
    manifest, lifted from the X-003 spike draft with canonical section names.
    Reproduces every literal from `DIRECTION_PHASES` (8 phases),
    `command_policy.py` (direction's script subset), `experiment_parser.py`
    (delimited_kv contract + G7 marker-dir fallback), `service_preflight.py`
    (6 http_health targets, G6 `{settings.*}` URLs),
    `config_promoter.py` (file_path development target + G4 gate bundles + G5
    registry_api production delegate), `orchestrator.py` (G1 phases.py plugin
    advancement, G2 resolve_identity.py plugin, G3 blocker_classification, G8
    decision success_values, G11 optimize goal).
  - `skills/ml-direction/SKILL.md` (P2-006) — the prompt primer copied from the
    legacy `.github/skills/direction-autotuner/SKILL.md` (the `llm.system_prompt`
    target the loader reads).
  - `ManifestSkillRuntime` in `src/core/skill_runtime.py` (P2-007, the
    keystone/highest-risk task) — a generic runtime satisfying the 21-member
    `SkillRuntime` protocol, reading everything from a `ResearchSkillManifest`.
    Data-driven methods (phase_plan, command_policy, parsers, preflight,
    promotion, marker paths, insights, subjects/variants) source from the
    manifest; computation methods (prompts, trial_identity, structured_hpo,
    research-resume) delegate to the same orchestrator helpers the transitional
    runtimes use — parameterized by manifest data — so behavior is byte-identical
    (X-002 parity golden rule). `session_nonce` remains accepted-ignored (D2).
    G1/G2 plugin slots (`phases.py`, `resolve_identity.py`) declared in the
    manifest; the runtime delegates to the shared `_completed_phase_ids` /
    `build_trial_identity` helpers (full X-004 sandbox = Phase 4). Production
    `registry_api` promotion stays in `ConfigPromoter` for Phase 2 (follow-up).
    `materialize_skill_runtime` now prefers the manifest runtime when
    `config.skill_id` resolves in the registry, else falls back to the
    transitional runtimes — per-skill reversible switchover (empty `skill_id`
    unchanged → transitional, so no behavior change unless a session opts in).
  - `tests/test_skill_ml_direction.py` (P2-008) — 17 equivalence + contract
    tests asserting `ManifestSkillRuntime(ml-direction)` reproduces
    `DirectionSkillRuntime` outputs (phase_plan ids/min/max, command_policy
    allowed_scripts, phase_advancement evidence keys, parse_iteration for both
    delimited_kv and json_marker, parser formats, promotion kind, preflight
    names, HPO disabled, decision success_values, metric direction) +
    materialization-by-skill-id and transitional-fallback tests.
  No behavior change unless a session sets `skill_id="ml-direction"` (the
  default empty-string `skill_id` keeps the transitional runtime). X-002 parity
  suite green (17/17); full suite green (982 passed, +17) except the 2
  pre-existing `test_deployment_inputs` failures.


- Introduced the **manifest infrastructure** for `research_skill.v1` skill
  descriptors (ARC-011 **P2-001..004**, the Phase-2 "manifest infra" epic).
  Three new modules + a test suite:
  - `src/core/skill_manifest.py` (P2-001) — the authoritative Pydantic v2
    schema. `ResearchSkillManifest` + nested `BaseModel`s cover every ARC-011 §9
    section (`llm`, `workspace`, `subjects`/`variants`, `param_schema`,
    `metric_schema`, `decision_vocabulary`, `phase_plan` + `phase_advancement`,
    `command_policy`, `output_parser`, `preflight`, `promotion_target`,
    `trial_identity`, `blocker_classification`, `structured_hpo`, `insights`,
    `prompt`, `ui`, `category`) and address all 13 X-003 gap-list items: G1
    `PhaseAdvancement{mode,plugin}` + per-phase override; G2
    `TrialIdentity.resolve{mode,plugin}`; G3 `BlockerClassification`; G4
    `gate_bundles`; G5 enriched `RegistryApiTarget` (lookup/auth/rollup); G6
    `{settings.*}` allowed as opaque strings (semantics owned by the loader); G7
    `OutputParserFallback.marker_dir_template`+`primary_metric_jsonpath`; G8
    `success_values`; G10 `bundle_manifest`; G11 `goal`; G12 subjects/variants;
    G13 category. `extra="forbid"`; discriminated union over
    `promotion_target.primary.kind` (file_path/registry_api/artifact_store/
    git_branch). Section names canonicalized per spike §4 (`metric_schema` not
    `metrics`, etc.). The schema is the X-003 stress test: all five spike drafts
    (`ml-direction`, `prompt-engineering`, `code-refactor`, `db-config-tuning`,
    `literature-review`) validate clean.
  - `src/core/skill_loader.py` (P2-002) — `load_skill_manifest(path|str|dict,
    *, settings_obj, skill_params)`. Owns the G6 semantics the schema leaves
    open: `{settings.*}` substitution pre-validation so the schema sees resolved
    values; `{skill_params.*}` only resolvable with session context (raises
    field-specifically at registry-load time). `schema_version` gate raises
    `ManifestVersionError`; structural failures raise `ManifestValidationError`
    with a field-located summary (P2-001 AC #3).
  - `src/core/skill_registry.py` (P2-003) — `SkillRegistry` discovers
    `skills/<id>/SKILL.yaml` under the service `skills/` dir (NOT
    `Settings.skills_dir`, which is the workspace-side primer location), caches
    loaded manifests keyed by id, lazy-loads on first `get()`, and hot-reloads on
    mtime change. Unknown ids raise `SkillNotRegisteredError`.
  - `tests/test_skill_loader.py` (P2-004) — 30 tests: schema validates all five
    spike drafts + rejects malformed inputs (wrong version, unknown promotion
    kind, phase min>max, duplicate phase ids, registry_api-needs-production);
    loader interpolation (happy/missing-setting/None-setting/wrong-version/
    inline-YAML/dict/skill_params unresolvable+resolvable); registry discovery,
    lazy cache, hot reload, unknown-id, register_path, default-root check.
  No behavior change — three additive modules + tests. X-002 parity suite green
  (17/17); full suite green (965 passed, +30) except the 2 pre-existing
  `test_deployment_inputs` failures. Wiki (`ResearchSkillManifest`,
  `ManifestSkillRuntime`) deferred (tool not on PATH — same residual as P1-007).
  Next: P2-005..008 lift `ml-direction` into `skills/` and build the
  `ManifestSkillRuntime` that consumes these manifests.

- Introduced the `SkillRuntime` protocol and three transitional runtimes, and
  wired the orchestrator to materialize one per session (ARC-011 **P1-023..028**,
  the "SkillRuntime transitional shell" epic). New `src/core/skill_runtime.py`
  declares the full §7.5 contract (21 members: identity, prompt construction,
  command policy, iteration detection, phase contract, trial identity, preflight,
  promotion, output parsing, insights, cross-session memory, structured HPO,
  subjects/variants) as a typing-time `Protocol` (not `@runtime_checkable`,
  house style). `DirectionSkillRuntime` / `VolatilitySkillRuntime` /
  `RLSkillRuntime` (P1-024..026) **delegate to the current hardcoded code paths**
  — behavior is identical, just relocated out of the orchestrator's
  `if config.model_type == ...` branches. `AgentOrchestrator.run()` (P1-027)
  now materializes a `SkillRuntime` via `materialize_skill_runtime(self, config)`
  at session start so every later domain branch can reach through `skill.*`.
  New `tests/test_skill_runtime_transitional.py` (P1-028) adds 24 structural +
  delegation tests. **AC #2 status:** `grep -c "config.model_type"
  src/core/orchestrator.py` is 42 (baseline 41) — the count does **not** drop
  (transitional runtimes still read `config.model_type` internally), satisfying
  the "every read inside a transitional runtime, not the loop body" clause;
  the drop to 0 is Phase 2. **Three documented deviations (D1-D3, P1-007 house
  style):** **D1** — value types (`SessionRecord`, `IterationRecord`,
  `CommandPolicyExtension`, `Phase`, `AdvancementRule`, `StructuredHPOPlan`,
  `SubjectDescriptor`, `VariantDescriptor`) are `TypedDict` aliases over the
  existing dict shapes (not dataclasses), so callers keep treating them as plain
  dicts (byte-identical behavior, zero construction churn); **D2** —
  `parse_iteration` accepts `session_nonce: bytes` for the P4 anti-forgery work
  but the transitional runtimes **ignore** it (no nonce validation exists today);
  **D3** — `ResearchConfig` gains `skill_id` / `skill_version` (default `""`),
  derived from `model_type` in the transitional runtimes
  (`"direction" → ("direction-autotuner", "1")`); two `session_start` parity
  fixtures re-captured under the append-only-with-linked-task rule to record the
  new defaulted fields. The X-002 parity suite is green (17/17); full suite green
  (935 passed) except the 2 pre-existing `test_deployment_inputs` failures.
  Wiki (`SkillRuntime` + three transitional entities) deferred (tool not on PATH
  in this env — same residual as P1-007).

- Migrated existing preflight checks to the `PreflightCheck` protocol
  (ARC-011 **P1-019..022**). New `src/core/preflight.py` declares the protocol
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
  keep working. New `tests/test_preflight.py` (P1-022) adds 8 structural tests.
  The 7 existing `test_service_preflight.py` tests (the behavioral gate) stay
  green unchanged. X-002 parity green; full suite green except 2 pre-existing
  `test_deployment_inputs` failures.

- Wired `ConfigPromoter` to the `PromotionTarget` protocol and extracted
  `FilePathPromotionTarget` (ARC-011 **P1-015..017**). New
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
  (D5):** `PromotionEvidenceCollector` is intentionally outside the protocol (it
  writes to the DB iteration row, not the host config path). The X-002 parity
  fixture `development_scope_basic.json` (bakes
  `target_path: "<host_configs>/instrument_configs/DOGE_USDT_15m.yaml"`) stays
  green unchanged. New `tests/test_promotion_target.py` (P1-018) adds 13
  structural + path-derivation-parity tests. The 45-test
  `test_config_promoter_gate_bundle.py` suite stays green unchanged.

- Introduced the `OutputParser` protocol and extracted `DelimitedKVParser` /
  `JSONMarkerParser` from `experiment_parser` (ARC-011 **P1-010..013**; mirrors
  the P1-006/007 `StateStore` precedent). New `src/core/output_parser.py`
  declares the protocol (`parse` for the `---` KV-block, `parse_iteration` for
  the `ITERATION_RESULT:` JSON-line) and the two implementations, extracted
  verbatim from `parse_prepare_output` / `parse_iteration_marker`.
  `experiment_parser.py` keeps the four historical module-level functions as
  **thin facades** over the new classes (reconstructing `IterationMetrics` from
  the flat dict) so the parity engine (`tests/parity/_engine.py`, which imports
  `from src.core.experiment_parser import ...` by string name) keeps resolving
  without a fixture re-capture. `AgentOrchestrator` (P1-013) now holds typed
  `self._prepare_parser` / `self._marker_parser: OutputParser` instances. Every
  load-bearing edge case (`_json` dual-write, int-via-JSON preservation, bool
  coercion, gate-alias reconciliation, `FAILURE_STATUSES` nulling) is preserved
  bit-for-bit. **Deviation (D2):** `parse_iteration` accepts `session_nonce` for
  forward-compat with the P4 anti-forgery work but the transitional parsers
  ignore it (no nonce validation exists today). New `tests/test_output_parser.py`
  (P1-014) adds 10 structural tests. The 10 existing `test_experiment_parser_*`
  files + 6 parity fixtures stay green unchanged.

- Added `tests/test_state_store.py` — structural / contract parity tests for
  the `StateStore` protocol (ARC-011 **P1-009**; mirrors `test_llm_provider.py`
  / P1-005). Four tests: (1) `StateStore` is a `Protocol` and is **not**
  `@runtime_checkable` (typing-time contract, house style); (2) every method in
  `StateStore.__protocol_attrs__` (48 of 49; `connection()` excluded) exists on
  `SQLiteStateStore` and is async on both sides — the signature-drift guard;
  (3) a minimal stub satisfies the protocol at the typing level; (4) the
  back-compat alias `ResultsStore is SQLiteStateStore` (same class object, not a
  subclass) — pins the invariant that `conftest.py`'s class-level monkeypatch
  relies on. These are not behavioral tests; behavior is covered by the existing
  `ResultsStore` suite (now exercising `SQLiteStateStore` via the alias) and the
  X-002 parity fixtures. Full suite green (880 passed) except the 2 pre-existing
  `test_deployment_inputs` failures.

- Wired production consumers to the `StateStore` protocol type
  (ARC-011 **P1-008**). `src/main.py` now constructs `SQLiteStateStore(...)`
  concretely but holds it as `StateStore | None` (mirrors how the orchestrator's
  `self._provider: LLMProvider` is typed as the protocol but constructed as
  `AnthropicProvider`). The six core consumers (`SessionManager`,
  `AgentOrchestrator`, `ConfigPromoter`, `PipelineController`,
  `PromotionEvidenceCollector`, `SessionStateMachine`) widened their constructor
  `store:` param from `ResultsStore` to `StateStore`. The API layer was already
  untyped (`store` / `_store = None`) and is abstraction-agnostic, so it is
  unchanged. The six defensive `getattr(store, "<method>", None)` probes in the
  orchestrator/config_promoter are left untouched (they work against any object;
  they become dead code only after P2-*). `grep ResultsStore src/` now returns
  only the shim + historical docstring mentions — no live type annotations or
  imports remain. Zero new ruff/mypy errors; full suite green except the 2
  pre-existing `test_deployment_inputs` failures. The X-002 parity suite is
  green.

- Introduced the `StateStore` protocol and extracted `SQLiteStateStore`
  (ARC-011 **P1-006** / **P1-007**; mirrors the P1-001/P1-002 LLM precedent).
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
  **Three P1-007 AC deviations (the AC text predated grounding; recorded here
  in the house-style of P1-002's D-retry callout):** **AC #2 ("`WEB_CONCURRENCY
  > 1` guard remains here") is factually off** — the guard lives at
  `src/main.py:_validate_runtime_configuration` (a service-lifecycle concern,
  never inside the store); it stays in `main.py`, and the single-instance
  *constraint* (W14) is documented on `SQLiteStateStore` instead. **AC #3 names
  two methods that don't exist:** `record_iteration` → the real method is
  `add_iteration`; `list_iterations` → `get_iterations`. **`connection()` is
  excluded from the protocol** (leaks the SQLite backend type). Also preserved
  the historical logger name `src.core.results_store` (hardcoded, not
  `__name__`) so log-scraping/dashboards/tests keyed on it are unaffected.
  Production construction (`SQLiteStateStore(settings.db_path)`) and consumer
  type wiring land in P1-008; parity tests in P1-009. The X-002 parity suite is
  green (17/17); full suite green except 2 pre-existing `test_deployment_inputs`
  failures unrelated to storage. **Note:** migrating the ~45 test imports from
  `ResultsStore` to `SQLiteStateStore` is a follow-up sweep; the alias is
  intentionally permanent-ish until then. Wiki pages (`StateStore`,
  `SQLiteStateStore`) deferred to after P1-008.

- Extracted `AnthropicProvider` from the orchestrator and fully normalized
  the LLM consumption (ARC-011 **P1-002**; consumes the X-005 spike §6 and
  the P1-001 protocol). `src/core/llm_provider.py` now hosts the SDK adapter
  alongside the protocol; `orchestrator.py` reaches the model **only** through
  `LLMProvider` (zero `messages.create` / `anthropic.*` / `httpx.*` references
  remain — grep-verified). The provider translates at the SDK boundary:
  `Message`/`ToolDef`/`system` → Anthropic kwargs (byte-identical to the
  pre-refactor wire request), and the raw response → normalized
  `ProviderResponse` (enforcing the R5 *"tool calls present ⇒ `TOOL_USE`"*
  invariant regardless of native `stop_reason`). The orchestrator's
  conversation is now `list[Message]` and the loop reads `StopReason` /
  `ContentBlock` / `Usage` instead of raw SDK shapes; `AGENT_TOOLS` is
  `list[ToolDef]`. **Retry placement follows the spike's D-retry decision
  (loop-owned), not the literal P1-002 AC #2 wording:** `_call_claude_with_retry`
  → `_call_llm_with_retry`, now using `provider.classify_error` (same transient
  set: APITimeout/APIConnection/InternalServer + HTTP 429/502/503/529) with
  backoff (30·2ⁿ) and the budget-aware skip preserved verbatim. The two
  pre-refactor retry log lines are unified into one (decision/timing identical;
  documented). Insights/Haiku call → `provider.complete()`. Added
  `tests/test_anthropic_provider.py` (16 tests: translation, R5 invariant,
  classify_error, estimate_cost). Updated fakes in test_orchestrator_{timeout,
  loop_guard,terminal_reason} + test_prompt_promotion_policy to the normalized
  shapes; dropped P1-001's now-invalid headless-import subprocess test. The
  X-002 parity suite is green. **Note:** the ~30 per-file `anthropic` test
  stubs are now dead-but-harmless (the orchestrator no longer imports
  anthropic); cleanup is a follow-up. Wiki page deferred to after P1-004.

- Introduced the `LLMProvider` protocol and normalized value types
  (ARC-011 **P1-001**, R4/R5; consumes `docs/adr/ARC-011-llm-provider-spike.md`
  §4 verbatim). New `src/core/llm_provider.py` declares the provider-agnostic
  contract every LLM backend must satisfy: `messages_create` (main agentic
  path), `complete` (one-shot insights/Haiku path), an optional `stream`,
  `estimate_cost` (→ P1-003), `capabilities` (→ P4-009/P4-010), and
  `classify_error` (→ loop-owned retry). The normalized types are
  Anthropic-shaped (`ToolUseBlock.input: dict`, `ToolResultBlock`,
  `ToolDef`) so the upcoming `AnthropicProvider` (P1-002) is a 1:1 wrapper and
  the parity suite is preserved. `StopReason` is the R5-critical enum the loop
  will key off (`END_TURN` triggers phase continuation); the *"tool calls
  present ⇒ `TOOL_USE`"* invariant (Gemini `STOP`-with-function-calls quirk)
  is documented as the provider's responsibility. **No behavior change** — this
  is a type-only module; P1-002 extracts `AnthropicProvider` and P1-004 wires
  the orchestrator to accept any `LLMProvider`. Added
  `tests/test_llm_provider.py` (contract surface, R5 `StopReason` mapping,
  frozen-value-type, and headless-import tests). Wiki page deferred to after
  P1-002 lands.

- Sanitized the governed subprocess environment so approved experiment scripts
  no longer inherit server control-plane secrets (ARC-011 **P0-023**, R2 — gap
  uncovered by the X-004 security spike; see
  `docs/adr/ARC-011-security-spike.md` §4.1/§4.3). `GovernedCommandRunner` now
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
  `_ALLOWED_SCRIPTS` read. The X-002 parity suite is green. **Residual:**
  `ML_ADMIN_TOKEN` is an overloaded alias for both `rl_trainer_service_token`
  (RL needs it) and `mlflow_service_auth_token` (the promotion token) in
  `config.py`, so it cannot be cleanly stripped by name yet — splitting that
  alias is tracked as a follow-up.

- Enforced mandatory cryptographic approval for production-scope promotions
  (ARC-011 **P0-020 / P0-021**, W18). `POST /research/{id}/promote/confirm`
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

- Added opaque cursor pagination to the list endpoints (ARC-011 **P0-015..
  P0-019**). `GET /api/v1/research` and `GET /api/v1/pipelines` accept a new
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
  `idx_iterations_research_iteration`). See
  `docs/adr/ARC-011-cursor-pagination.md`. Added `tests/test_pagination.py`
  (38 tests).

## 2026-07-02

- Audited ResultsStore exception handling and confirmed migration errors no
  longer swallow (ARC-011 **P0-008 / P0-009 / P0-010**). P0-009's target — a
  bare `try/except Exception: pass` over each `ALTER TABLE ADD COLUMN` — was
  already removed in commit `3c47c1e34` (Phase 1.3 hardening) and replaced by
  `_add_column_if_missing` (a `PRAGMA table_info` LBYL pre-check that lets
  genuine `OperationalError` propagate), so the goal is met by a
  documented-equivalent approach (inventory + decision recorded in
  `docs/adr/ARC-011-results-store-exception-inventory.md`, with a pointer in
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
- Enforced a hard wall-clock bound that also reaps the worker subprocess
  (ARC-011 **P0-006 / P0-007**). Two complementary mechanisms: (1) each
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
  (ARC-011 **P0-003 / P0-004**), making it the sole legal writer of
  `research_sessions.status` and closing the W8 stop/complete race. The 8
  direct `update_session(status=…)` sites now drive lifecycle changes via
  the per-session-locked state machine: `pause_session`/`resume_session`
  (`PAUSE`/`RESUME`, returning `False` on illegal/winding-down states — the
  pause sibling-of-W8), `stop_session` (records the transitional `stopping`
  intent under the lock), `recover_orphaned_sessions`
  (`RESTART_RECOVER`), and the hard-timeout reclassify (`HARD_TIMEOUT`,
  incl. the documented `stopped → timed_out` carve-out). The orchestrator
  exit path resolves its terminal intent by severity
  (`fail > timeout > stop > complete`): a racing `complete` against an
  in-flight stop is refused and finalizes `stopped` with no auto-promote
  (W8-A); a late cancel against terminal `completed` is a no-op that can
  neither overwrite the status nor revoke a promotion (W8-B). Auto-promote
  is now gated on `TransitionResult.should_auto_promote` (False on severity
  redirect). Cost/iteration accounting is split into a status-free write so
  it is always captured even when a transition is refused. `SessionManager`
  and `AgentOrchestrator` accept an injectable `SessionStateMachine`
  (sharing one `SessionLockRegistry`); the initial `running` status stays a
  `create_session` storage default (out of the P0-003 grep scope, design
  §11). Behavior is unchanged for happy paths; new transitional statuses,
  the `session.transition` audit action, and `research_started`/`_paused`/
  `_resumed`/`_stopped`/`_timed_out` broadcasts are additive. Added
  `tests/test_session_status_routing.py` (8 tests pinning the routing +
  W8-A/B/C contract); the exhaustive transition/race suite is P0-005.

## 2026-06-29

- Added the ARC-011 manifest expressiveness spike (X-003) under
  `docs/adr/`: design note `ARC-011-manifest-spike.md` (gap list G1–G13,
  GO verdict for P2-001, schema §7 punch-list) plus five draft
  `research_skill.v1` manifests in `docs/adr/arc-011-manifest-spike/`
  (`ml-direction`, `prompt-engineering`, `code-refactor`,
  `db-config-tuning`, `literature-review`). The `ml-direction` draft
  reproduces current hardcoded behavior; the four non-ML drafts prove the
  schema spans optimization/generative/exploratory categories. Gaps route
  hybrid logic to two sandboxed plugin slots (`phases.py`,
  `resolve_identity.py`) per the R1 mitigation; everything else is new
  declarative fields fed to P2-001.
- Added the ARC-011 skill-plugin security sandbox spike (X-004) under
  `docs/adr/ARC-011-security-spike.md`: records the decision to run all
  skill plugins (`parser.py` / `preflight.py` / `resolve_identity.py` /
  `bootstrap.py`) in a governed subprocess (never in-process), the
  agent-vs-plugin capability distinction, read-only/path-confinement
  rules, `--dry-bootstrap` overlay semantics, a six-vector threat model,
  and the plugin capability contract that feeds P5-005. Uncovered a live
  pre-existing gap — the agent's governed subprocess inherits all server
  secrets (`command_runner.py:77-84` passes no `env=`) — and filed it as
  Phase 0 task **P0-023** (env sanitization on `GovernedCommandRunner`
  spawn; +2 SP to Phase 0).
- Added the ARC-011 LLM provider normalization spike (X-005) under
  `docs/adr/ARC-011-llm-provider-spike.md`: a 5-dimension × 3-provider
  comparison matrix (system prompt, tool-use protocol, stop-reason,
  retry, streaming), the draft `LLMProvider` protocol + normalized
  `StopReason`/`Usage`/content-block types for P1-001, and three
  recorded decisions — loop-owned retry with provider
  `classify_error` (R4), protocol defines `stream()` with impl
  deferred, and OpenAI target = Chat Completions. Phase-contract
  enforcement stays loop-level via the normalized `StopReason.END_TURN`
  (R5). Normalized types are Anthropic-shaped so the future
  `AnthropicProvider` (P1-002) is a trivial wrapper and parity is
  preserved.
- Added the ARC-011 `SessionStateMachine` design (P0-001) under
  `docs/adr/ARC-011-session-state-machine.md`: the 13-state diagram
  (11 lifecycle states + `resumable`/`interrupted`), the full
  `(from, event) → (to, side_effects, audit, broadcast)` transition
  table incl. severity overrides (`fail > timeout > stop > complete`;
  stop beats complete = the W8 fix), guard rules, the `transition()`
  single-writer decision, and an exhaustive grep audit of session-
  status writers. Records that `stop_session` writes no status today
  (W8 is between the orchestrator's own exit branches), that there
  are 8 session-status writers, and that terminal transitions emit no
  audit row today (new `session.transition` action is additive).
  Transitional states are recorded in the public `status` column; the
  pipeline state machine is deferred. Feeds P0-002…005.

## 2026-06-28

- Added the ARC-011 domain-coupling CI guard (`scripts/ci/check_domain_coupling.sh`)
  with a data-driven YAML ruleset (`scripts/ci/domain_coupling_rules.conf`) and an
  active-phase file (`.arc-011-phase`). The guard runs as a dedicated
  `domain-coupling-guard` job in the service workflow; it ships inactive (phase 1,
  no rules) and is tightened per migration phase. Per-line suppression is available
  via `# arc-011: allow(<task-id>): <reason>`. Backlog task X-001.
- Added the ARC-011 parity fixture suite under `tests/parity/` (X-002): golden-
  master fixtures capturing current behavior across five categories
  (`experiment_parser`, `command_policy`, `session_start`, `phase_advancement`,
  `promotion_preview`), a shared `_engine.py` (token substitution + output
  normalization), a `capture.py` recorder (idempotent, dirty-git-guarded), and a
  `@pytest.mark.parity` test harness. Run `pytest -m parity` to verify;
  `python tests/parity/capture.py` to regenerate after an intentional change.

## 2026-05-09

- Added vdmc-indicator as an autoresearch service dependency for manifests,
  status, and preflight, with blocking readiness for RL/pipeline sessions.

## 2026-05-02

- Moved the backend package from `server/` to the ML-service standard `src/`
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
  checks against locked ML service pins.
