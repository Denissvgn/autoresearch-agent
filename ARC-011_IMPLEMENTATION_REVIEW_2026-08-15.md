# ARC-011 Implementation Review — Gaps, Discrepancies, and Bugs

**Document type:** Post-implementation audit report
**Date:** 2026-08-15
**Resolution addendum (same day):** findings **C1**, **C2** (all five
sub-items), **C3** (all four sub-findings — KV bypass closed, KV forgeries
audited, nonce moved out of the workspace manifest + env delivery narrowed,
constant-time compare), **C4** (the Phase-4 exit criterion is now actually
met — a real end-to-end prompt-engineering session runs on the OpenAI
provider, proven by `test_prompt_engineering_session_end_to_end`; the
command-policy/`create_session`/`next_action`/training-command/decision
wiring gaps it exposed are fixed), and **H6** are now fixed in the working
tree — see the "ARC-011 implementation review C1+C2", "review C3", and
"review C4" entries in `CHANGELOG.md`, plus
`tests/test_manifest_runtime_production_path.py`,
`tests/test_metrics_forgery_c3.py`,
`tests/test_skill_prompt_engineering_e2e.py`, and
`tests/test_canonical_start_wiring.py`, and the Revision 2026-08-15 note in
`docs/adr/ARC-011-signed-metrics.md`. The remaining findings are open.
**Scope:** All ARC-011 phases (X, 0–6) in `services/autoresearch-agent/`, against
[`docs/adr/ARC-011-backlog.md`](../../docs/adr/ARC-011-backlog.md) and the per-phase
close-out claims in `CHANGELOG.md`.
**Reviewed tree:** branch `researcher_sep`, commit `0622b6b24` ("Phase6 implementation")
**plus uncommitted working-tree changes** (the Phase-6 "review-fix round": pool-leak fix,
epoch-fence wiring, parity/test additions — reviewed as part of this audit and found
sound; see §7).
**Method:** every claim below was verified by reading the current source (file:line
evidence given), running the CI-exact gates locally (pytest / ruff / mypy / the
domain-coupling guard / UI vitest), and empirically probing suspected defects. Where a
finding rests on an exploration agent's report, the load-bearing ones were re-verified
directly in the source by the reviewer.

---

## 1. Executive summary

The program is **functionally far along and unusually well-tested** — 1,315 tests pass,
the domain-coupling guard is green at its activated target, and Phases 0–4 each delivered
real, verified artifacts. However, this audit found **5 critical, 9 high, 15 medium**
findings. The headline problems are:

1. **The "universal" path is not the production path.** Canonical API requests are
   validated and then **silently dropped** (`skill_params`, `skill_id` never reach the
   session), so every production session runs the *transitional* runtime; the
   manifest-driven runtime, manifest command policy, and manifest prompts are dead code
   in production (§3.1, §3.2). The Phase-2/3 exit criteria hold only at
   equivalence-test level.
2. **The W11 anti-forgery contract is bypassable and its secret is exposed to the
   adversary it defends against** (§3.3), and the Phase-4 exit criterion ("non-ML skill
   runs end-to-end on OpenAI") is **overclaimed** — the e2e test runs no session, and the
   skill's manifest command policy is dead config that would block a real session
   (§3.4).
3. **The CI quality gates are red and have been for the whole program**: ruff exits 1
   with 91 errors and mypy with 15 errors — at HEAD, in the working tree, and (for ruff)
   already 89 errors at the Phase-2 close-out commit that claimed "ruff 0 errors
   (CI-exact config)". The gates only trigger on `main`; this work lives on
   `researcher_sep`, so the claims were never machine-checked (§3.5).
4. **Phase 5 is largely library code without production wiring**, and several of its
   tasks are missing outright while two claims about it in `CHANGELOG.md` / module
   docstrings are false (§3.9, §3.10).
5. **Phase 6's cross-worker stop (H3) is broken at the entry point** —
   `stop/pause/resume_session` early-return before writing DB intent when the session
   isn't in the local registry, which is exactly the multi-worker case H3 exists for
   (§3.5 in the Phase-6 section) — plus a data-loss bug in the SQLite→Postgres migration
   script and a documented DSN form that crashes at startup.

None of these invalidate the architecture; most are wiring/completion gaps, not design
errors. §8 gives a prioritized remediation list.

---

## 2. Verification runs (CI-exact, unless noted)

| Gate | Command (as CI runs it) | Result | Verdict |
|---|---|---|---|
| Pytest | `pytest tests -q` (env: `ANTHROPIC_BASE_URL=http://anthropic.invalid …`) | **1315 passed, 24 skipped** in 15.7 s | ✅ green (skips = postgres/distributed markers without `AUTORESEARCH_DATABASE_URL`) |
| Ruff | `ruff check --config pyproject.toml src tests` (pinned 0.2.2 = poetry.lock) | **91 errors, exit 1** | ❌ CI-failing |
| Mypy | `mypy src --no-error-summary` | **15 errors, exit 1** | ❌ CI-failing |
| Domain-coupling guard | `scripts/ci/check_domain_coupling.sh` | phase 4, 3/3 rules, **0 violations** | ✅ green |
| UI unit tests | `npx vitest run` (ui/) | **35/35 pass** | ✅ green |
| Distributed (Postgres) job | `pytest -m "postgres or distributed"` | not runnable here (no live Postgres); skips cleanly in the default suite; dedicated CI job exists | ⚠️ unverified locally |

Ruff error breakdown: 44× E501, 31× I001, 10× B904, 3× B905, 1× E741, 1× B008, 1× B007.
Mypy errors by file: `skill_runtime.py` (7), `state_store.py` (3), `output_parser.py`
(3), `skill_registry.py` (1), `llm_provider.py` (1) — **all five are ARC-011-created
files**, so "prior-phase debt, out of scope" is ARC-011's own debt.

Also checked: the same 91 ruff errors exist at HEAD (committed), and **89 errors at
`0ef8e741e`** ("close Phase-2 DoD lint and typecheck gaps") with the *same pinned ruff
version* — i.e. the close-out's "ruff 0 errors (CI-exact config)" claim does not
reproduce at its own commit. The reconciliation: that claim was scoped to "all Phase-2
modules", while the CI gate runs on the whole tree — and the CI workflow only triggers
on push/PR to `main`, so it never ran on this branch's commits.

---

## 3. Critical findings

### C1. Canonical request fields are validated, then silently dropped (P3-013) — the API's canonical shape is a facade

`_translate_canonical_request` (`src/api/research.py:185-260`) validates `skill_id`,
`skill_params`, `subject_id`, `variant` (including param-schema 422s with field
pointers), but the `start_session` call (`src/api/research.py:568-585`) passes **only the
legacy fields**; `_start_session_unlocked` (`src/core/session_manager.py:227-290`) has
no such parameters. Consequences:

- A canonical request `{"skill_id": "ml-direction", "skill_params": {"enable_hpo": true,
  "hpo_trials": 100}}` runs with `enable_hpo=False, hpo_trials=20` — **silently**.
- `ResearchConfig.skill_id` is never set by the API, so `materialize_skill_runtime`
  (`src/core/skill_runtime.py:887-923`) always falls back to the **transitional**
  runtime; `ManifestSkillRuntime` is unreachable in production (compounds C2).
- The start audit metadata (`_start_metadata`, `research.py:56-74`) omits
  skill_id/skill_params — the shape_conflict audit exists but the winning values are
  never recorded or used.
- `tests/test_research_api_compat.py:320-333` only asserts 201; no test asserts the
  canonical params take effect.

### C2. The manifest-driven runtime is not the production path (Phase-2 exit criterion unmet end-to-end)

The Phase-2 exit criterion — "existing model types work driven purely by their manifests"
— holds only in the equivalence tests. In the orchestrator:

- Phase plan comes from the hardcoded `phases_for_model(config.domain)`
  (`src/core/orchestrator.py:1448` → constants in `research_phase_plan.py`), not
  `skill.phase_plan()`.
- The system prompt comes from the **old `_load_skill` map**
  (`orchestrator.py:2834` → `:1017-1027`), which reads
  `{workspace}/.github/skills/direction-autotuner/SKILL.md` — *not* the
  `skills/ml-direction/SKILL.md` the manifests package. `ManifestSkillRuntime.
  system_prompt()` (`skill_runtime.py:606-615`) is dead in production.
- `command_policy_extension()` has **zero consumers** (grep-verified) — the real gate is
  the hardcoded `_ALLOWED_SCRIPTS` (`src/core/command_policy.py:12`).
- The manifest `blocker_classification` section has zero consumers.
- `ManifestSkillRuntime.promotion_target()` returns `FilePathPromotionTarget()`
  unconditionally (`skill_runtime.py:787-802`) — a `registry_api`/`git_branch`/
  `artifact_store` primary silently gets a file target (marked Phase-2 follow-up).
- ML manifests declare plugins that don't exist on disk (`phase_advancement.plugin:
  phases.py`, `resolve_identity.py`, `scripts/list_subjects.py`).

The only runtime method the orchestrator calls is `skill.parse_iteration`
(`orchestrator.py:3746`). Combined with C1, every production session is
transitional-runtime + hardcoded constants; the P2-021 grep-guard zero (which is real —
re-verified) measures accessor renames, not manifest-drivenness.

### C3. W11 anti-forgery: one live bypass, and the nonce is readable by the adversary it defends against (P4-001..006)

What's solid: `_verify_nonce` (`src/core/output_parser.py:396-451`) implements the
four-state machine exactly as documented; the nonce is 256-bit per-session
(`research_manifest.py:278`); the chain manifest → `ResearchConfig.session_nonce` →
`AUTORESEARCH_SESSION_NONCE` in the governed child env → echoed `server_nonce` →
verified parse is wired and tested (`tests/test_metrics_forgery.py`, 11 tests); graceful
downgrade + `metrics_verified`/`metrics_unverified` audit distinction work.

What's broken:

1. **KV-block bypass (live):** the `---` auto-detect path
   (`orchestrator.py:3401-3411`) calls bare `parse_prepare_output(tool_result)` with
   **no nonce argument**. Any bash tool result containing a `---\nstatus: completed…`
   block is recorded as an iteration with metrics even for skills with
   `require_signed_metrics: true` — the agent can forge metrics by simply printing a KV
   block instead of a JSON marker.
2. **No `metrics.forged` audit for KV-format forgeries:** the forged-detection branch
   (`orchestrator.py:3824`) re-parses only with the JSON-marker facade, which returns
   `None` for `---` blocks, so KV forgeries are silently dropped rather than audited.
3. **The nonce is not secret from the agent** (the W11 adversary):
   `research_manifest.json` — containing `session_nonce` in cleartext — is written into
   the session workspace (`session_manager.py:557-570`), and the agent's `read_file`
   tool reads any workspace file (`orchestrator.py:615-623` via `_safe_path`);
   `AUTORESEARCH_SESSION_NONCE` is injected into **every** governed bash subprocess
   (`orchestrator.py:3211-3222`), so any sanctioned `env`-dumping script leaks it
   (`test_command_policy.py:378-400` builds exactly such a script as a *sanctioned*
   one); and every legitimate marker the agent relays contains it. After one eval run
   the agent can forge any subsequent marker. The contract currently deters only
   *cross-session* replay (correctly rejected), not the modeled insider.
4. Minor: the comparison is not constant-time (`output_parser.py:443`, `!=` rather than
   `hmac.compare_digest`) — low practical risk for a 256-bit value, but inconsistent
   with the fail-closed posture used elsewhere (e.g. the production-approval HMAC).

### C4. Phase-4 exit criterion overclaimed: no non-ML session has ever run end-to-end (P4-016)

The backlog's Phase-4 close-out states "the exit criterion is met: a non-ML skill
(`prompt-engineering`) runs end-to-end on the OpenAI provider". Actual state:

- `tests/test_skill_prompt_engineering_e2e.py` (12 tests) runs **no session**: it uses a
  `MagicMock` orchestrator, stubs the `openai` module itself when absent
  (`:20-28`), and checks manifest fields, provider construction (no LLM call), the eval
  subprocess, and parser nonce behavior. No baseline → iterations → promotion-preview
  flow, no `research_sessions` row, no UI assertions. (The test also references a
  nonexistent task ID "P4-017".)
- **Blocking gap:** the skill's manifest `command_policy` (allowing `eval/run.py`,
  `SKILL.yaml:120-131`) is dead config (see C2) — `evaluate_command_policy`
  (`command_policy.py:12-19`) hardcodes the six autotuner scripts, so a real
  prompt-engineering session could never execute its own eval via the bash tool. The
  flagship Phase-4 flow is unrunnable as shipped.
- `skills/prompt-engineering/eval/run.py`'s scorer is a deterministic hash stub
  (documented in-file) and `bootstrap.py` uses an argparse CLI ABI that is incompatible
  with the Phase-5 `PluginRunner` JSON ABI (`plugin_runner.py:336-343` fails closed on
  non-JSON output) and is invoked by nothing.

### C5. Cross-worker stop/pause/resume broken at the entry point — Phase-6 H3 unreachable in a real deployment (P6-004)

`SessionManager.stop_session` begins `active = self._active.get(research_id); if not
active: return False` (`session_manager.py:1122-1124`; same pattern in
`pause_session :1194-1195` and `resume_session :1210-1211`) — **before** any DB
transition. Under `WEB_CONCURRENCY > 1` with a non-sticky LB, a stop routed to worker B
(where `_active` is empty) returns False and writes nothing; worker A's
`_should_stop_cross_worker` DB poll (`orchestrator.py:948-975`) never sees intent. The
ADR (`ARC-011-postgres-state-store.md` §6.2) explicitly assumes B writes the
transition — the implementation contradicts its own design. The fencing tests bypass
`SessionManager` entirely (drive `sm.transition` directly in `test_fencing_tokens.py`),
so the gap is untested. Related H3 gaps: cross-worker **pause** polling is not
implemented (only stop, and only while the local pause flag is set,
`orchestrator.py:977-988`), and `pipeline_controller._stop_flags` has no DB path.

---

## 4. High findings

### H1. CI quality gates red for the entire program (DoD #4 unmet)

See §2. Beyond the raw counts: the Phase-2 close-out's "ruff 0 errors (CI-exact
config)" claim does not reproduce (89 errors at its own commit, same pinned ruff
0.2.2); later close-outs shifted to "0 **new** errors" framings while the tree
accumulated debt; and because the CI workflow triggers only on `main`, none of the
phase-close-out "CI green" statements were ever executed against this branch. Every
§0.4 DoD item #4 ("Lint + typecheck clean") signed off in the backlog is therefore
unverified-to-false at the tree level. (34 of the 91 ruff errors are auto-fixable.)

### H2. Skill hot-reload doesn't rediscover — the advertised add-a-skill flow is broken (P2-003/P3-008, vs §7.14)

`reload_all()` (`src/core/skill_registry.py:189-197`) iterates only cached ids;
`available()` (`:142-148`) skips `discover()` once `_scanned` is latched. Empirically
confirmed: drop a new `skills/<id>/` + `POST /skills/reload` → `GET /skills` still
returns the old set (only direct `GET /skills/{new_id}` works, via lazy `get()` lookup).
This breaks exactly the flow the backlog's Phase-3 exit criterion and the 404-hint text
advertise (`api/skills.py:188-192`). The P3-030 falsifiability test masks it by
constructing a fresh registry. Adjacent registry issues:
`materialize_skill_runtime` swallows **all** registry exceptions
(`skill_runtime.py:906`) — a corrupt manifest silently degrades a canonical session to
the transitional runtime (contradicting `skill_registry.py:26-27`'s "surfaced loudly");
and `_model_type_from_skill_id` (`skill_runtime.py:926-931`) doesn't know canonical
`ml-*` ids, so the transitional fallback for a canonical skill_id is broken. Also
`main.py:139`'s "same registry instance" comment is wrong — `api/research.py` and
`skill_runtime.py` use the separate `default_registry`.

### H3. SQLite→Postgres migration silently loses rows (P6-005)

`scripts/migrate_sqlite_to_postgres.py:144-161`: composite-PK tables (e.g.
`idempotency_records`, PK `operation, parent_id, key_hash`) page on the **first PK
column only** — `WHERE "operation" > cursor ORDER BY "operation" LIMIT 500`. Any rows
beyond the first 500 sharing one `operation` value are **permanently skipped** (very
plausible: one operation type across thousands of sessions). The inline comment's
"ON CONFLICT makes re-runs idempotent regardless of cursor exactness" does not cover
rows the cursor jumps over. Also: dead duplicated batch query `:132-138` (executed
twice; first `new_cursor` computed then discarded), "sanity" check verifies table
presence but not schema version (`:223-237`), and **no automated test exists** for the
script — the CHANGELOG's "validated end-to-end" was a manual run.

### H4. Documented `postgresql+asyncpg://` DSN crashes at startup (P6-006)

`is_postgres_dsn` accepts `postgresql+asyncpg://` (`postgres_state_store.py:2465-2472`)
and `config.py:599` documents it as a valid form — but `initialize()` passes the raw DSN
to `asyncpg.create_pool` (`:371-376`) with no `+asyncpg` → `` normalization (every
other consumer does the replace). Result: that documented configuration selects the
Postgres backend, lifts the multi-worker guard, then dies in `create_pool`.

### H5. P0-023 incomplete: the mlflow promotion token still reaches every governed child, and one spawn path bypasses sanitization entirely

- `ML_ADMIN_TOKEN` is intentionally kept in the allow-list
  (`command_runner.py:71-75`); in `config.py` it aliases **both**
  `rl_trainer_service_token` (legitimate) *and* `mlflow_service_auth_token` (the
  production-promotion token the P0-023 AC explicitly required stripping). Documented
  in-code as a follow-up — but the AC is checked done in the backlog while the token
  still leaks.
- `_update_research_resume` spawns `scripts/autotuner/resume.py` via
  `asyncio.create_subprocess_exec` with **no `env=`**
  (`orchestrator.py:1696-1700`) — full parent-env inheritance (all control-plane
  secrets) and no `GovernedCommandRunner` policy. Same leak class P0-023 was written to
  close; `resume.py` is in the P0-023 inventory.

### H6. `ConfigPromoter`'s injected `PromotionTarget` is dead — and the CHANGELOG claim about fixing it is false (P1-016/P1-017)

`self._target` is assigned (`config_promoter.py:123`) and never read; every historical
helper still constructs a fresh `FilePathPromotionTarget()` inline (`:2103, :2114,
:2122, :2140, :3127, :3139`). An injected custom target is ignored. The CHANGELOG
(~line 515) claims this was fixed with "a recording stub [test] that proves the
injected target is actually dispatched through" — no such test exists
(`test_promotion_target.py:154-168` only asserts storage). Either the fix was reverted
or never landed.

### H7. Plugin-runner "sandbox" overstates its confinement (P5-005 / X-004)

`src/core/plugin_runner.py` is genuinely good on process isolation (subprocess, no
shell, `start_new_session`, fail-closed on crash/timeout/bad JSON, path-confinement of
the plugin *file*, strict env scrubbing, RSS cap). But:

- **Declared env caps are dropped at the call site**: `_run_sync` calls
  `_build_plugin_env()` without `declared_env_keys` (`:262`) — `caps.env` is silently
  ignored (doubly dead because default caps force `env=[]` and widening is rejected).
- **`fs_write` and `network_egress` caps are not enforced at all** — no OS-level
  confinement (no user namespace/seccomp/landlock); plugins run as the server user and
  can write anywhere writable and egress freely.
- **CPU cap logic is ineffective**: `:432` compares the CPU delta of one 0.1 s poll
  interval against the entire `max_cpu_s` budget — a single-threaded CPU burner never
  trips it (it's a thread-explosion detector, not the documented cap).

### H8. Phase 5 is library code without production wiring (multiple tasks)

Verified by call-site greps — zero production consumers for each:

| Component | Status |
|---|---|
| `BootstrapRunner` (P5-005/006) | never invoked at session start; `session_bootstrap.v1.json` never written by any production code |
| Lifecycle gating (P5-010) | `selectable_for`/`SkillLifecycleMachine` never consulted; draft exclusion works only implicitly via `_drafts/` discovery skip; a `deprecated` skill is still perfectly startable; state is in-memory only (lost on restart; unknown ids default **stable** — fail-open if ever wired naively) |
| `SkillRegistryPromotionTarget` (P5-011) | implemented + tested, no consumer (P5-012 endpoints missing) |
| Domain classifier (P5-016) | never called by the API; no `goal` in `/research/start` (P5-017 missing); `skill.classify` audit never written (P5-018 missing); `auto_select_threshold` not in `Settings` (P5-019 partial) |
| Insights feedback (P5-027) | `append_findings` never called on session completion |
| `auto_absorb_insights` (P5-028) | manifest field exists; no consumer, no review queue |

P5-007 (server-side setup → skill bootstrap) is honestly deferred (CHANGELOG +
`.arc-011-phase` stays at 4) — that one is *documented*, unlike the above.

### H9. Missing Phase-5 tasks and two false claims

- **P5-012 missing**: no `POST /skills/{id}/promote/preview|confirm` anywhere (API,
  OpenAPI); CHANGELOG admits "lands in a follow-up" but the backlog decomposition still
  lists it as the dependency sink for P5-024.
- **P5-017, P5-018, P5-024 missing** (see H8).
- **P5-021 deviation**: `skills/meta-skill-generator/` does not exist; replaced by
  `src/core/skill_generator.py` (documented only in the commit message, not the
  backlog).
- **P5-025 falsely claimed**: `skill_generator.py:15` states
  `Settings.skill_generator_enabled` (default off) exists — **no such field in
  `config.py`**, no flag check, no endpoint, no auth gate. The CHANGELOG repeats the
  claim. The generator is callable by anyone who can import it.
- **P5-029 falsely claimed**: the CHANGELOG says `knowledge_last_reviewed` /
  `refresh_cadence_days` "drive the stale-knowledge UI badge" — the stale computation
  exists only as a test-local helper and there is no badge anywhere in `ui/src`.

---

## 5. Medium findings

1. **Inverted `validation_alias`** (`skill_manifest.py:647, 680`):
   `RegistryApiTarget.endpoint` / `GitBranchTarget.target_branch_template` declare
   `validation_alias=...` without `populate_by_name=True`, so the *documented primary
   names* are rejected (`extra_forbidden`) and only the aliases validate — empirically
   confirmed. Masked today because the only validated registry_api primary uses the
   alias, and the ML skills' `endpoint:` keys sit inside `scopes[].delegate`, which
   `PromotionScope` swallows unvalidated via `extra="allow"` — i.e. the G5 production
   REST descriptions are never schema-checked at all.
2. **Sessions stuck in transitional states are never recovered** (P0 design gap):
   `_apply` commits the transitional write and terminal write as two separate committed
   `update_session` calls (`state_machine.py:511-516`); a crash in between persists
   `stopping/completing/timing_out/failing`, but `recover_orphaned_sessions` scans only
   `running|paused` (`session_manager.py:134-136`) and `continue_session` rejects those
   statuses (`:598-605`) — permanently stuck rows.
3. **`POST /skills/reload` prod guard misses `environment="prod"`**
   (`api/skills.py:302` exact-matches `"production"` while `main.py:63` treats `prod`
   as production).
4. **P1-029 backlog deliverable is stale/false**: the async grep migration was
   **reverted** — `_execute_tool` is sync (`orchestrator.py:532`), `_tool_grep` uses
   sync `subprocess.run` (`:651-687`), `_kill_async_proc_tree` does not exist, the
   production call site wraps dispatch in `to_thread` (`:3212`), and
   `test_async_tool_path.py` pins the *sync* contract (its docstring says "reverted").
   Only the env-scrub delta survived. Backlog §4.3 still narrates the async design as
   the delivered state.
5. **SQLite epoch comment/behavior mismatch** (Phase-6 uncommitted code): comments claim
   the epoch "stays None" on SQLite (`orchestrator.py:2773-2775, 993, 4694-4696`) but
   the code stores `0` (`:2777-2779`); the discard branch can fire on SQLite when the
   session row is missing.
6. **Provider capability check skipped on the default path**
   (`orchestrator.py:2811-2821`): validation only runs when `llm.provider !=
   "anthropic"` — a skill on the default provider with
   `required_max_context_tokens: 400000` is never validated; the fail-closed claim
   holds only for non-default providers.
7. **Loader version gate is N-only** (`skill_loader.py:413-418` raises on anything ≠
   `research_skill.v1`); the AC's "supports N and N−1" is scaffolding, not exercised.
   Also `{skill_params.*}` placeholders are unusable via the registry
   (`skill_registry.py:185-187` never passes `skill_params`), so manifests referencing
   them fail at load in the live path.
8. **Production-approval signature is not artifact-bound**
   (`api/promotion.py:154-194`): the HMAC covers
   `"{research_id}:{scope}:{approver}"` only — an approval is replayable for any
   iteration/config of that session by the same approver.
9. **Cost accounting bypassed** (P1-003): `estimate_cost` exists on the protocol but
   the orchestrator never calls it — cost is inlined with `_CLAUDE_*` constants
   (`orchestrator.py:60, 2938-2978`); exercised only by tests.
10. **Distributed/parity test coverage caveats** (P6-007): H3 is not exercised in the
    multi-process harness; the H2 test's docstring says "stop vs complete" but spawns
    two stop workers and asserts weakly (`changed >= 1`); the parity sweep omits ~13
    protocol methods (`update_iteration`, the pipeline family, reverse pagination,
    `record_promotion_rollback`, …).
11. **Phase-6 latent concurrency sharp edges**: idempotency INSERT→SELECT window
    (`postgres_state_store.py:540-548`, concurrent delete → double-proceed);
    `session_lock` re-entrancy joins the outer txn for *any* session id
    (`:466-468`); advisory key is 32-bit `hashtext` (collisions over-serialize — safe);
    best-metric read-then-conditional-write outside any lock (`:985-1004`, safe only
    under one-owner-per-session); fencing is **fail-open** on store errors (epoch
    capture/refresh swallow exceptions → unconditional writes).
12. **ADR `ARC-011-postgres-state-store.md` drift**: still `Status: DRAFT` post-impl;
    says "48 protocol methods" (actual 50); §11's `max_overflow=20` mitigation is not
    implementable on a raw asyncpg pool (hard cap 10; the 11th acquire blocks).
13. **Backlog document staleness**: Phase 5 (§8) and Phase 6 (§9) sections carry no
    completion status at all despite being implemented; Files columns stale (P6-002/003
    say `state_store.py` vs actual `postgres_state_store.py`; P6-004 says
    `command_runner.py` vs actual orchestrator/store); P1-029 narrative stale (see #4);
    `/research/{id}/iterations` pagination is opt-in (full list when `limit` omitted,
    `api/results.py:542-568`) vs the AC's "callers omitting the cursor get page 1 with
    default limit"; the X-003 "five spike drafts validate clean" deliverable overstates
    (4/5 fail without a full `skill_params` set supplied).
14. **Pipeline statuses bypass the state machine** (`session_manager.py:1025, 1086`,
    `pipeline_controller.py` at 8 sites) — documented as out-of-scope (P0-024), but the
    W8-class race remains open for pipelines; likewise `_run_and_cleanup`'s hard-timeout
    transition failure is only logged (`session_manager.py:396-399`).
15. **GEN-009 does not test what it claims**: the "non-ML row indistinguishable from ML
    row except skill_id" assertion iterates only the 3 ML model types (docstring
    admits it) — with `prompt-engineering` present, the falsifiability suite still
    never asserts the actual §7.14 property.

---

## 6. Low findings / code hygiene

- Test-count drift vs backlog claims (24→20 transitional, 13→11 promotion-target,
  10→9 output-parser, 8→7 preflight) — later-phase rewrites, not missing behavior.
- Dead code: `_phase_evidence_keys_subset` provable no-op
  (`skill_manifest.py:905-916`); `_skill_text` primer placeholder never used
  (`domain_classifier.py:362-368` — embeddings omit the SKILL.md primer, contra the
  AC); duplicated module-level `_atomic_write_text` in `config_promoter.py:57-87`
  (should delegate to `promotion_target`).
- `skills/ml-*/bootstrap.py:38-45` reads `AUTORESEARCH_WORKSPACE_ROOT`, which is **not**
  in the plugin env allow-list (`plugin_runner.py:92-105`) — dead lookup.
- `subjects.py:109-111, 152-154`: hardcoded timeframe list inside the "generic"
  subject module; the declared manifest `enumerator` is never executed.
- `build_provider("openai")` with no API key constructs with an empty key — misconfig
  surfaces at first call, not session start; `stop_sequences=[]` would be sent as
  `stop: []`.
- Copy-paste logger name `"src.core.results_store"` in
  `postgres_state_store.py:49`.
- `stop_session` returns False without recording intent when a running DB session has
  no in-process `_active` entry (single-worker edge; see C5 for the multi-worker
  consequence).
- `llm-wiki sync` deferred in every phase close-out (P1→P6) — the tool was never on
  PATH; all six deferrals remain open (DoD #5 / §12.8).
- Phase-exit tags (`arc-011/phase-<N>-done`) never cut for any phase (deferred every
  time per "precedent").

---

## 7. What is verified good (credit where due)

- **Phase 0 core**: state machine with severity-override transition table, per-session
  lock, single-writer invariant holds (grep-verified: only `create_session`'s INSERT
  default bypasses, per the documented §11 decision); hard wall-clock bound works
  (in `session_manager._run_and_cleanup`, incl. `stopped → timed_out` reclassify);
  migration errors surface via LBYL pragma pre-check (stronger than the AC);
  atomic promotion writes; broadcaster lock+snapshot; cursor pagination (27 tests);
  production-approval HMAC fail-closed.
- **Phase 1 protocols**: 50/51 StateStore methods mirrored (`connection()`
  intentionally excluded); LLM/OutputParser/Preflight extractions clean;
  `results_store.py` re-export shim preserves the historical logger name; retry logic
  loop-owned per the X-005 decision with `classify_error` preserved semantics.
- **Phase 2**: manifest schema breadth is real (13 sections, discriminated union over
  4 promotion kinds, `extra=forbid`); three ML manifests complete and loader-clean;
  grep guard 0 hits re-verified live; `legacy_alias` round-trips.
- **Phase 3**: all 10 skill/subject endpoints + OpenAPI docs; dual-shape responses;
  read-time iteration enrichment; WS additive enrichment; manifest v2 with v1
  normalization; UI renderer (7 field types, `visible_when`, plugin registry) with
  35/35 vitest green.
- **Phase 4**: `OpenAIProvider` translation quality is genuinely good (malformed-JSON
  degrade, R5 invariant, retry parity, ~30 tests); nonce four-state machine itself is
  correct and well-tested (its weaknesses are the wiring, per C3).
- **Phase 5**: the library modules themselves (classifier's offline TF-IDF backend with
  swappable embedding protocol, generator's validation-before-write, lifecycle
  transition table) are tested and sane — the gap is wiring (H8), not quality.
- **Phase 6**: `PostgresStateStore` implements all 50 protocol methods with no stubs;
  H1/H2/H4 primitives are correct and tested at three levels; the guard lift is
  conditional and byte-identical by default; the distributed tests are real
  multi-process + real Postgres with a dedicated CI job. **The uncommitted working
  tree is strictly an improvement** — the `ping()`/`get_schema_version()` pool-leak
  fix alone was production-blocking, and replacing the status-based discard guard
  with the epoch fence is correct (the old guard mis-fired on legitimate
  `completing → completed` writes).

---

## 8. Prioritized remediation recommendations

**P0 — correctness/security of shipped behavior**
1. Wire canonical `skill_id`/`skill_params`/`subject_id`/`variant` through
   `start_session` → `ResearchConfig` (C1); add a test asserting a canonical param
   actually takes effect. This single fix also unlocks the manifest runtime in
   production (C2) once combined with #2.
2. Close the KV-block nonce bypass: route `parse_prepare_output` through
   `skill.parse_iteration` (or otherwise `_verify_nonce`), and emit `metrics.forged`
   for rejected KV blocks (C3.1/3.2). Separately, decide the nonce-threat model: either
   document that W11 only covers cross-session forgery, or stop writing the nonce into
   the workspace manifest / restrict `read_file` from it (C3.3).
3. Fix `SessionManager.stop/pause/resume` to write DB intent before the `_active`
   early-return (C5) — this is what makes Phase 6's H3 real. Extend the distributed
   harness to exercise it through `SessionManager`.
4. Fix the migration script's composite-PK paging (page on the full PK tuple) + add an
   automated test (H3); normalize `postgresql+asyncpg://` in `initialize()` (H4).

**P1 — make the program's own gates true**
5. Clear the ruff/mypy debt (34 ruff errors auto-fixable; the 15 mypy errors are all in
   ARC-011 files) and run the CI workflow on this branch (add `researcher_sep` to the
   trigger or open the PR) so close-out claims are machine-checked (H1).
6. Fix `reload_all()` to rescan + delatch `_scanned`; stop swallowing registry errors in
   `materialize_skill_runtime` (H2).
7. Strip/split `ML_ADMIN_TOKEN` aliasing (H5) and add `env=` to the resume.py spawn
   (H5b).
8. Correct the two false CHANGELOG/docstring claims (P5-025 flag, P5-029 badge) and the
   P1-016 recording-stub claim — or land the actual fixes (H6, H9).

**P2 — complete the "universal" promise**
9. Consume `command_policy_extension`, `phase_plan`, `system_prompt`, and
   `blocker_classification` from the runtime in the orchestrator (C2/C4) — this is the
   remaining substance of the Phase-2 exit criterion and the blocker for a genuine
   P4-016 e2e test.
10. Wire Phase-5 lifecycle gating, bootstrap-at-session-start, classifier goal flow,
    and insights append (H8); land P5-012 endpoints (H9).
11. Enforce (or delete) the plugin `fs_write`/`network_egress`/CPU/env caps (H7) —
    documented-but-unenforced caps are worse than none.

**P3 — hygiene**
12. Backlog updates: mark Phase 5/6 sections with their true status (partial/deferred
    per H8/H9), refresh stale Files columns and the P1-029 narrative, record the
    P5-021 deviation; lift ADR postgres doc out of DRAFT.
13. The medium list (§5) in rough order: alias inversion (5.1), transitional-state
    recovery (5.2), `prod` guard (5.3), capability check on default path (5.6),
    artifact-bound approval signature (5.8).

---

## 9. Task-level status matrix (summary)

| Phase | Claimed | Actual |
|---|---|---|
| X (pre-phase) | done | **Done** (all three spikes + guard + fixtures) |
| 0 | done | **Done with gaps**: P0-023 partial (H5); transitional-state recovery gap (5.2); pipeline statuses deferred |
| 1 | done | **Done with gaps**: P1-016/017 dead injection (H6); P1-029 deliverable reverted (5.4); P1-003 cost iface unused (5.9) |
| 2 | done, exit criterion "grep 0 hits" | Grep guard genuinely 0, **but** the manifest runtime is not the production path (C2); loader N−1 gate not real (5.7); registry reload broken (H2) |
| 3 | done (after gap close-out) | Endpoints/UI/dual-shape solid; **canonical params dropped (C1)**; falsifiability suite misses the non-ML assertion (5.15); iterations pagination opt-in (5.13) |
| 4 | done, "exit criterion met" | Anti-forgery wired **but bypassable (C3)**; **e2e overclaimed (C4)** — no session has run; cross-provider provider itself solid |
| 5 | not marked in backlog; commits landed | **Library-only**: 6 components unwired (H8); 5 tasks missing, 2 claims false (H9); P5-007 honestly deferred |
| 6 | not marked in backlog; commits landed + uncommitted fixes | Store primitives solid; **H3 broken at SessionManager entry (C5)**; migration data loss (H3); DSN crash (H4); ADR drift (5.12) |

Program-level §12 completion criteria: **not met** (needs ≥2 non-ML skills e2e with zero
code changes, generator→promote cycle, green gates, wiki sync — each currently blocked
by findings above).

---

**Reviewer note:** findings above cite the working tree as of 2026-08-15. The
uncommitted Phase-6 review-fix changes were reviewed as part of the tree and are
described in §7; nothing in this report should be read as a reason to hold that diff —
several findings (C5, H3, H4) are in *committed* Phase-6 code that the uncommitted
round did not address.
