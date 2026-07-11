# Changelog

## Unreleased

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
