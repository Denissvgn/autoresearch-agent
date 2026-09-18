# ARC-012 — Release-readiness backlog (Option B: make non-ML sessions real)

Status: **open** — decisions D1-D4 recorded 2026-09-17 (§2, closes P7-001);
**Wave 1 (P7-002..P7-008) done 2026-09-18** — B1/B3 closed and verified
through the real start path; **Wave 2 (P7-009/P7-010) done 2026-09-18** —
B2/S1 closed (crash terminal-state persistence + fail-fast start);
**Wave 3 (P7-011..P7-015) done 2026-09-18** — the non-ML e2e proof exists
and passes (P7-016 blocked on a clean commit by design).
Created: 2026-09-16
Owner: maintainer (manual publish)
Absorbs: `ARC-011` finding **C4 / P4-016** ("no non-ML session has ever run
end-to-end"), which this document closes for real.

> Task IDs continue the house convention and open a new phase **P7**
> (Phase 7 = release readiness). Highest pre-existing ID was `P6-007`. Every
> task lists: why, files, approach, acceptance criteria, dependencies, size, risk.

---

## 0. Purpose and scope

The seven blockers from the publish-readiness review are **already fixed and
verified** (§1.1). What remains is the difference between "the tests pass" and
"the shipped artifact does what the README claims".

Decision taken: **ship with Option B** — make non-ML session bootstrap real, so
the bundled skills (`prompt-engineering`, `code-refactor`, `db-config-tuning`)
can start, run, and promote through the public API and UI. This is the only
option that makes the project's headline claim true, and the codebase is far
closer to it than the 500 suggests (§1.4).

**Done means:** a clean checkout + `docker compose up` lets an operator start a
session for any bundled skill, watch it reach iterations, and preview/confirm a
promotion — proven by an API-level end-to-end test that did not exist before.

---

## 1. Verified current state (evidence, not recollection)

Everything below was reproduced against the **built Docker image**, not
inferred from source.

### 1.1 Already fixed (do not re-open)

| # | Blocker | Status |
|---|---|---|
| 1 | Production-approval alias bypass (`prod`/`live`/whitespace) | Fixed — canonical scope normalization before the gate |
| 2 | Webhook rollback reported success without restoring remote | Fixed — `target_descriptor`-driven `restore()`, operation-scoped idempotency key |
| 3 | Approval not bound to the approved candidate | Fixed — v2 (`production-approval.v2`), candidate + target identity signed |
| 4 | Evaluator silent hash-derived "success" metrics | Fixed — demo-only fallback; live failures are `eval_error` |
| 5 | Wheel/sdist omitted bundled skills | Fixed — explicit include allowlist; CI archive + installed-wheel smoke |
| 6 | Compose overrides did not match the docs | Fixed — `${VAR-default}` (unset-only) + loopback port default |
| 7 | Output limits did not bound memory | Fixed — quota-limited session logs + head/tail buffers |

Verification: **1278 passed, 30 skipped**; `ruff` clean; `mypy src` clean;
domain-coupling guard clean; UI 36 passed + `tsc` + `vite build`; wheel installs
outside the checkout and discovers all 3 skills; image `/health`,
`/health/ready`, `/api/v1/skills` all 200.

### 1.2 BLOCKER B1 — no session can be started (HTTP 500)

```
POST /api/v1/research/start {"skill_id":"prompt-engineering", ...}  ->  500
pydantic_core.ValidationError: ResearchSessionManifest.model_type
  String should match pattern '^(direction|volatility|rl)$'
  input_value='prompt-engineering'
```

- Constraint lives at `src/core/research_manifest.py:37`.
- Root cause: `skill_id_to_model_type("prompt-engineering")` returns
  `"prompt-engineering"` (pass-through), so the intended
  `if not mt: req.model_type = ""` branch at `src/api/research.py:200-216` is
  **dead code**. Its own comment claims it is unreachable because "today every
  installed skill has a legacy model_type alias" — no longer true.
- The intended `""` value would *also* fail the same pattern.
- Identical failure for `code-refactor` and `db-config-tuning`.
- `ui/src/pages/NewResearch.tsx:32,87` is already skill-aware and sends
  `skill_id`, so the UI's primary flow hits the same 500.

### 1.3 BLOCKER B2 — the legacy path 201s, then dies silently

```
POST /api/v1/research/start {"model_type":"direction", ...}  ->  201 Created
ERROR session_manager - Background research task res_... crashed:
  SkillConfigError: session has no skill_id — every session must name an
  installed skill (legacy model_type-only sessions are no longer supported)
```

- Raised at `src/core/skill_runtime.py:916`; the orchestrator is **already
  fully manifest-driven** and refuses legacy sessions by design.
- The row stays `status="running"`, `error_message=null` indefinitely →
  **zombie session**. `_attach_done_callback`
  (`src/core/session_manager.py:80-125`) only logs + broadcasts; it never
  persists a terminal state. `recover_orphaned_sessions` only fires after a
  process restart.
- `ml-direction` is **not installed** (the registry offers only the 3 bundled
  skills), so this path is doubly dead.

### 1.4 The good news — non-ML plumbing mostly already exists

This is why Option B is tractable. Already implemented:

- `materialize_skill_runtime` is the only session runtime path and requires
  `config.skill_id` (`src/core/skill_runtime.py:903-931`).
- Phase plans are already skill-driven: `phases = skill_runtime.phase_plan()`
  (`src/core/orchestrator.py:4476-4479`) passed into
  `build_phase_state(phases=...)` (`:4498`); the per-model table is a
  documented fallback only.
- Storage already tolerates `model_type=""` for non-ML sessions
  (`src/core/state_store.py:1593`, `src/core/postgres_state_store.py:671`).
- Per-session promotion target selection exists (`_promoter_for_session`,
  `src/api/promotion.py:266-282`) and builds a `WebhookPromotionTarget` for
  `webhook` / `registry_api`.
- `FilePathPromotionTarget.target_path` is domain-neutral
  (`<host_configs>/<skill>/<subject>_<variant>.yaml`,
  `src/core/promotion_target.py:150-166`).
- `_default_objective` / `_default_model_family` already fall back generically
  for unknown ids (`src/core/research_manifest.py:284-302`).
- Skills already declare what is needed: `code-refactor` →
  `promotion_target.primary.kind: file_path` + `path_template`;
  `prompt-engineering` → `kind: registry_api` + `register_endpoint`.

**Conclusion:** the blocker is concentrated in *manifest construction and
validation*, plus failure semantics — not an orchestrator rewrite.

### 1.5 BLOCKER B3 — promotion preview is ML-shaped for non-ML sessions

`ConfigPromoter.preview` derives `target_path` up front
(`src/core/config_promoter.py:179`) and compares/rolls back against
`FilePathPromotionTarget`-style paths, while the session's real target may be
`registry_api` (prompt-engineering) or a skill `path_template`
(code-refactor). The declared `path_template` is ignored for non-ML sessions,
and the failure surfaces via the vestigial `"Unknown model type"` branch
(`src/api/promotion.py:310-337`) — a string that **no longer exists anywhere in
`src/`** (verified: 0 matches outside that branch).

### 1.6 Secondary gaps

- **S1** `start_research` returns 201 before the background task does any work,
  so an immediately-fatal session looks successful (see B2).
- **S2** 9 documents referenced by code/tests are **absent**:
  `docs/adr/ARC-011-backlog.md`, `ARC-011-cursor-pagination.md`,
  `ARC-011-llm-provider-spike.md`, `ARC-011-manifest-spike.md`,
  `ARC-011-postgres-state-store.md`,
  `ARC-011-results-store-exception-inventory.md`, `ARC-011-security-spike.md`,
  `ARC-011-session-state-machine.md`,
  `docs/ml/autoresearch_agent_hardening_backlog.md`.
- **S3** Parity fixture provenance is stale: `source_sha` in
  `tests/parity/promotion_preview/development_scope_basic.json` still points at
  `f2300939...`; the fixture was hand-edited. No test asserts it.
- **S4** `poetry check` emits deprecation warnings (`[tool.poetry.authors]`,
  `[tool.poetry.scripts]` → prefer `[project.*]`).
- **S5** Version is `0.1.0` uniformly; no tag / release-notes decision made.
- **S6** Real Docker *distribution* (multi-worker Postgres) and the CI
  `distributed` job were never executed in this environment; the UI CI flags
  (`--pool=forks --maxWorkers=1`) were not exercised locally.

---

## 2. Decisions D1–D4 — RECORDED 2026-09-17 (closes P7-001)

**Decision principle (the lens used for all four calls):** the product is a
*universal* autonomous research system — adding a domain means adding a
`skills/<id>/` directory, never a core-code change. Each option was tested
against one question: *does this reduce the number of places that know about
specific skills?* Operationally that means: `skill_id` + the skill manifest
are the only session vocabulary; nothing runtime may branch on a skill-specific
literal; legacy ML vocabulary is frozen history — readable forever, writable
never.

**D1 — What does `model_type` mean after this change? — DECIDED: D1a,
refined.** `model_type` becomes a *derived, write-dead legacy alias*:

- Manifest v3 (`research_session_manifest.v3`): `skill_id` required +
  non-blank (authoritative); `model_type` optional, default `""`.
- Refinement vs the original D1a sketch ("optional + unvalidated"): the field
  keeps a **closed-vocabulary pattern `^(direction|volatility|rl)?$`** —
  empty means "no legacy alias". An unvalidated field would let typos and
  de-facto new values ("Direction", future skill ids) accrete in a field
  whose entire purpose is to be frozen history.
- Invariant: **no runtime behaviour may branch on `model_type`** — paths,
  phase plans, promotion targets, and gate bundles derive from the skill
  manifest only. `model_type` may be *rendered* (dual-shape API responses,
  historical rows), never *decided on*.
- Collision fix this decision mandates (latent bug today): when `model_type`
  is empty, path derivation must fall back to `skill_id` — never the literal
  `"skill"`. `promotion_target.py:165` and `:279` do
  `str(model_type or "skill")`, so as-is every non-ML skill would write into
  the *same* `<root>/skill/` directory across skills.
- D1b (drop the field entirely) stays deferred (§8): this release makes it
  write-dead, which turns the later drop into a mechanical change. D1c stays
  rejected (re-couples the schema to the installed set).

**D2 — Release scope/version — DECIDED: `0.1.0` final, single tag, hard-gated
on the e2e proof.** There is no installed base (no tag was ever published),
so an `-rc` cycle buys nothing: 0.x semver already licenses the breaking
`hmac-sha256-v2` approval change and the start-API 4xx change, provided the
CHANGELOG calls them out (P7-019). The gate moves from the version suffix to
the checklist:

- Tag `v0.1.0` **only after** the full §6 verification on a clean checkout
  *including* the P7-011 non-ML e2e and the P7-022 scripted Docker smoke;
  P7-021 makes the e2e a required CI check.
- Interim builds before Wave 3 is green are pre-release-suffixed
  (`0.1.0rc1` wheels, `0.1.0-rc` image tags) and are never published as
  `latest`/final. ARC-011 C4 happened precisely because untested claims
  shipped; the label must not outrun the proof.
- Closes S5: version `0.1.0` consistent in all four places, tag matches;
  release notes lead with the breaking approval change and state which
  skills are executable and at what maturity.

**D3 — Keep the legacy `direction|volatility|rl` trio? — DECIDED: read-only
vocabulary + translation shim; no "legacy = reject" rule.**

- Read path: the three values remain valid *output* values forever
  (historical rows, parity fixtures, pre-migration rendering).
- Write path: a request carrying `model_type` without `skill_id` is
  translated through the alias map (`direction → ml-direction`) and then
  subjected to the **same installed-skill check as any canonical request**.
  `ml-direction` is not installed → 4xx `skill_not_found` naming the
  translated id + available skills (shared vocabulary with P7-006/P7-010,
  enforced by P7-010). If an ML skill is ever reinstalled, legacy callers
  work again with zero code change.
- Explicitly rejected: rejecting a request *because it is legacy*. One
  source of truth (the skill registry) decides what can start a session; the
  alias stays a pure translation, not a policy. This keeps D3 from
  accidentally encoding "ML skills are banned forever" — §8 *defers* them,
  it does not forbid them.
- The canonical-wins conflict rule (P3-013) is unchanged.

**D4 — Promotion target for non-ML file-path skills — DECIDED: honour the
declared `path_template` always; the generic layout survives only as the
*default template*.** `path_template` is already a required field for
`kind: file_path` (`skill_manifest.py:636`), so "honour when present, else
generic" collapses to "honour always" — the generic layout is not a second
code path but a default.

- One template engine: render `path_template` with the closed placeholder set
  `{skill_id}`, `{subject_id}`, `{variant}`, `{scope}`, `{iteration}`, plus
  the host-configs root. Unknown placeholders fail at **skill-discovery/load
  time**, not at first promotion (universal rule: skills validate at
  install, and a manifest must never fail only once someone promotes).
- Confinement (safety, added by this decision; refined during P7-007
  implementation to compose with the G6 loader): unknown placeholders and
  `..` traversal are rejected at skill-load time; relative templates resolve
  under `settings.host_configs_path` (the existing bind-mount boundary);
  rendered `subject_id`/`variant` segments are sanitized (no `/`, `..` —
  they are request-supplied). Absolute templates are **not** blanket-rejected
  because the G6 loader legitimately produces them by resolving
  `{settings.host_configs_path}` *before* validation (operator-controlled
  config, the sanctioned escape hatch) — a blanket rejection broke 30+
  loader/CLI fixtures and the generator.
- Default template (ML trio and any session without a skill-declared
  template): `{host_configs_root}/{skill_slug}/{subject_id}_{variant}.yaml`
  where `skill_slug = model_type if model_type else skill_id`. This keeps
  the X-002 fixture byte-identical (it bakes
  `<host_configs>/direction/DOGE_USDT_15m.yaml` — the legacy alias, not
  `ml-direction`) *and* fixes the D1 `"" → "skill"` collision in one rule.
- `registry_api`/`webhook` targets are unaffected (already resolved from the
  skill runtime via `_promoter_for_session`); D4's scope is the `file_path`
  branch, and P7-007 must route the orchestrator's auto-promote path through
  the same resolution so there is exactly one target-resolution site.

---

## 3. Task decomposition

Legend — Size: S (<= half day), M (1-2 days), L (3+ days). Risk: low/med/high.
Every task ends with the repo's gate: `ruff check --config pyproject.toml src
tests` + `mypy src` + `pytest -q` (venv details in §6).

### Wave 0 — Decisions

**P7-001 — Record D1-D4 decisions here — DONE 2026-09-17**
- Why: Waves 1-2 encode these choices; deciding late causes rework.
- Files: this backlog (§2).
- Acceptance: D1-D4 each marked decided, with the chosen option + date.
  **Met** — §2 now records all four as decided (D1: D1a refined; D2: `0.1.0`
  final hard-gated; D3: read-only vocabulary + translation shim; D4: declared
  `path_template` always, generic layout as default template).
- Deps: none. Size: S. Risk: low.

### Wave 1 — Manifest-driven non-ML bootstrap (closes B1)

**P7-002 — Manifest schema v3: skill identity is authoritative — DONE 2026-09-18**
- Why: the `model_type` regex is the direct cause of the 500 and encodes an
  ML-only world view.
- Files: `src/core/research_manifest.py`.
- Approach: per D1 (§2) — add `CURRENT_SCHEMA_VERSION =
  research_session_manifest.v3`; make `skill_id` required + non-blank; make
  `model_type` an optional legacy alias with the **closed-vocabulary pattern
  `^(direction|volatility|rl)?$`** (default `""`; rejects typo/de-facto new
  values while admitting "no alias"), not "unvalidated"; keep v1/v2
  readable and normalized (extend the existing
  `_accept_known_schema_versions` / `_derive_canonical_fields` machinery).
- Acceptance: v2 manifests still load; v3 builds for all 3 bundled skills;
  `build_research_manifest(model_type="prompt-engineering")` no longer raises;
  `mypy` clean.
- Deps: P7-001. Size: S. Risk: medium (persisted + parity-tested schema).

**P7-003 — Skill-driven manifest builder — DONE 2026-09-18**
- Implementation note: split into `_ml_manifest_defaults` (byte-identical
  for the legacy trio — parity stayed green) and `_skill_manifest_defaults`
  (sections sourced from SKILL.yaml incl. a new `skill` section; ML-only
  sections stay `None` instead of being fabricated). Unresolvable skill ids
  raise instead of fabricating provenance.
- Why: `build_research_manifest` fabricates ML/domain sections
  (`experiment_matrix_v1`, `reports/direction-tuning/...`, `mlflow_experiment`,
  `roster`, `baseline_config.workspace_config` → `.../train.yaml`) for *any*
  session. For a prompt-engineering session that is fabricated provenance —
  worse than an error.
- Files: `src/core/research_manifest.py` — split into
  `_build_ml_manifest_sections(...)` and `_build_skill_manifest_sections(...)`,
  consuming the skill manifest's `workspace.session_path_template`,
  `phase_plan`, `metric_schema`, `promotion_target`, `preflight`,
  `command_policy`.
- Approach: keep the ML branch byte-identical for the legacy trio (parity
  fixtures depend on it); non-ML sessions get sections sourced from SKILL.yaml
  with no invented paths. A manifest must never claim artefacts the skill does
  not produce.
- Acceptance: for each bundled skill the built manifest contains no
  `direction-tuning` / `experiment_matrix_v1` / `runs/autotuner` strings; the
  workspace follows `session_path_template`; the ML-trio manifest is unchanged
  (asserted by the X-002 parity fixture).
- Deps: P7-002. Size: M. Risk: medium.

**P7-004 — Section requirements become profile-based — DONE 2026-09-18**
- Implementation note: profiles keyed off the presence of the skill-sourced
  `skill` section (skill profile = universal four: budget, promotion_policy,
  preflight, runtime; legacy-ML profile = the full incumbent set). Both
  directions regression-tested.
- Why: `_require_manifest_sections` demands `gate_bundle`, `roster`, `tsfm`,
  `adaptive_features`, `split_ids`, `cost_model` — all ML concepts. A
  generative skill has no `roster`/`tsfm`.
- Files: `src/core/research_manifest.py`.
- Approach: replace the single hardcoded `required` tuple with a per-category
  profile keyed off the skill manifest's `category`
  (`generative`/`optimization`/`ML`) plus a `default` profile.
- Acceptance: non-ML manifests validate without ML-only sections; an ML
  manifest missing `roster` still fails (regression test).
- Deps: P7-003. Size: S. Risk: medium.

**P7-005 — `_build_manifest_payload` passes skill identity, not `model_type` — DONE 2026-09-18**
- Implementation note: also derives the session workspace from the skill's
  `session_path_template` (`runs/<skill>/<subject>/<variant>` under the
  workspace root — new `src/core/skill_paths.py` renderer), fixes the
  duplicate-session check to key on skill identity (two different non-ML
  skills on the same subject no longer falsely collide via `model_type=""`),
  and persists `skill_id`/`subject_id`/`variant` natively in both stores'
  `create_session` (the columns existed since P3-019 but were never
  written). The continue path inherits the parent's canonical identity.
- Why: `SessionManager._build_manifest_payload` (`src/core/session_manager.py:508-525`)
  passes `model_type=config.model_type`; for non-ML sessions that is either the
  skill id or `""` depending on the caller — fragile, and the two callers
  disagree today.
- Files: `src/core/session_manager.py`.
- Approach: pass `skill_id=config.skill_id` explicitly and derive the legacy
  alias inside the builder (one place). When `config.workspace_path` is empty,
  derive the session workspace from the skill's `session_path_template`.
- Acceptance: a session started with only `skill_id` gets a manifest with the
  correct `skill_id`/`subject_id`/`variant` and a skill-derived workspace; no
  `model_type` guessing at the call site.
- Deps: P7-003. Size: S. Risk: medium.

**P7-006 — API translation: non-ML skills map to an empty legacy alias — DONE 2026-09-18**
- Implementation note: beyond the `is_known_model_type` discriminator, the
  translation now defaults an omitted `subject_id`/`variant` from the skill's
  first static entries (a bare `{"skill_id": ...}` start works) and rejects
  path-unsafe subject/variant segments with a 422 at the boundary.
- Why: the `if not mt: req.model_type = ""` branch (`src/api/research.py:200-216`)
  is dead because the pass-through never returns empty. Its comment is stale.
- Files: `src/api/research.py`, `src/core/legacy_alias.py` (document the
  contract), `tests/test_skill_prompt_engineering_e2e.py` (the assertion at
  `:184-185` currently pins `req.model_type == "prompt-engineering"`; it must
  move to the new contract).
- Approach: use "is this a known legacy ML alias?" (`is_known_model_type`,
  already present) as the discriminator instead of truthiness of
  `skill_id_to_model_type`). Canonical `skill_id` stays authoritative; unknown
  skills yield `model_type=""` (accepted by the v3 closed pattern per D1).
- Acceptance: `POST /research/start {"skill_id":"prompt-engineering",...}`
  → 201 with `skill_id="prompt-engineering"` and `model_type=""` plus a working
  manifest; a conflicting legacy `model_type` is still surfaced in `conflicts`.
- Deps: P7-002. Size: S. Risk: low.

**P7-007 — Promotion target resolution for non-ML skills (closes B3) — DONE 2026-09-18**
- Implementation note: ONE resolution site —
  `promotion_target.promotion_target_from_manifest` — shared by
  `SkillRuntime.promotion_target()` (orchestrator auto-promote) and the
  API's `_promoter_for_session`; `file_path` skills now promote through
  their declared `path_template` (rendered per D4, load-time validated in
  the skill-manifest model). `ConfigPromoter.preview` passes the session's
  `skill_id` into path derivation (the `"" → "skill"` collision is fixed:
  slug = legacy alias else skill id). Promotion-safety suites re-run green.
- Why: preview/confirm derive the target from legacy `model_type` dispatch and
  ignore the skill's declared `path_template`; the real target may be
  `registry_api` (prompt-engineering) or `file_path` + `path_template`
  (code-refactor).
- Files: `src/core/config_promoter.py` (`preview`/`confirm`/`rollback`),
  `src/core/promotion_target.py` (`FilePathPromotionTarget.target_path` gains an
  optional `path_template`), `src/core/skill_runtime.py`
  (`promotion_target()` already resolves kinds).
- Approach: resolve the `PromotionTarget` from the session's skill runtime
  (already done for the API path via `_promoter_for_session`) and pass it into
  `ConfigPromoter`; make the orchestrator's auto-promote path do the same, so
  target resolution lives in exactly one site. Per D4 (§2):
  `registry_api`/`webhook` → `WebhookPromotionTarget`; `file_path` renders the
  skill's declared `path_template` with the closed placeholder set
  (`{skill_id}`, `{subject_id}`, `{variant}`, `{scope}`, `{iteration}`) —
  unknown placeholders rejected at skill load, relative templates confined
  under `settings.host_configs_path`, rendered segments sanitized (no `/`,
  `..`). The generic layout becomes the *default template*
  `{host_configs_root}/{skill_slug}/{subject_id}_{variant}.yaml` with
  `skill_slug = model_type if model_type else skill_id` (keeps X-002
  byte-identical; fixes the `"" → "skill"` multi-skill collision).
- Acceptance: preview succeeds for `prompt-engineering` reporting
  `target_kind: registry_api` + the skill's endpoint; the `code-refactor`
  preview path matches its `path_template`; rollback still validates the
  persisted `target_descriptor` (the earlier remote-restore fix stays intact).
- Deps: P7-005. Size: M. Risk: medium-high (touches the just-hardened promotion
  safety path — re-run `tests/test_release_promotion_safety.py` explicitly).

**P7-008 — Retire the vestigial `"Unknown model type"` branch — DONE 2026-09-18**
- Why: the string no longer exists in `src/` (verified 0 matches); the branch
  returns a misleading 422 and can mask real errors.
- Files: `src/api/promotion.py:310-337`.
- Approach: delete the string-sniffing branch; map genuine
  `SkillConfigError`/unknown-skill cases to a structured 4xx naming the skill id
  and let real validation errors surface normally.
- Acceptance: unknown skill → explicit 4xx reason; no behaviour depends on a
  deleted message string; `tests/test_webhook_promotion.py` fallback test still
  passes (it asserts the fallback, not the message).
- Deps: P7-007. Size: S. Risk: low.

### Wave 2 — Failure semantics (closes B2 + S1)

**P7-009 — Persist a terminal state when a background task crashes — DONE 2026-09-18**
- Implementation note: the done-callback schedules
  `_finalize_crashed_session` (via `loop.create_task`, strong-ref set —
  fire-and-forget tasks must not be GC-able mid-write), which routes the
  write through the state machine (`FAIL` with `error_message` truncated to
  2000, `terminal_reason=background_task_crashed:<ExcType>`,
  `completed_at`, broadcast merged with `source: task_done_callback`).
  Terminal finality keeps orchestrator-authored statuses untouched
  (`changed=False` → log only); IllegalTransition/LookupError/store failure
  fall back to the manual broadcast. One state-machine contract change was
  required: **`(paused, FAIL)` moved from illegal to legal** — a paused
  session whose task died was an unresumable zombie the orchestrator's own
  FAIL handler also could not finalize (it hit the same refused edge);
  `test_state_machine.py`'s case table moved with it. Store layers needed
  no change (`update_session` already accepts terminal fields from any
  task context). Pipeline tasks keep log+broadcast-only (no session row).
- Why: a crashed task leaves `status="running"` forever with
  `error_message=null` (zombie session, reproduced). Operators cannot tell a
  dead session from a slow one.
- Files: `src/core/session_manager.py` (`_attach_done_callback`),
  `src/core/state_store.py` + `src/core/postgres_state_store.py` (ensure the
  update path tolerates a terminal write from a sync callback via
  `asyncio.create_task`).
- Approach: in the done-callback, when the session is still `running`/`paused`,
  schedule a store update to `status="failed"` with the exception text
  (truncated) and a `terminal_reason`, then broadcast as today. Never overwrite
  a status the orchestrator already set.
- Acceptance: a session whose runtime raises before iterations shows
  `failed` + non-null `error_message` within seconds; a normally-completed
  session is untouched; covered by a regression test.
  **Met** — regression tests in `tests/test_session_failure_modes.py`
  (Wave-2 section): crashed-before-iterations → `failed` +
  `terminal_reason=background_task_crashed:SkillConfigError` +
  `completed_at`; complete-then-crash → stays `completed` untouched;
  paused-then-crash → `failed`; no-exception task → untouched.
- Deps: none (independent of Wave 1). Size: S. Risk: low.

**P7-010 — Fail fast instead of 201-then-crash — DONE 2026-09-18**
- Implementation note: two layers. (1) `SessionManager._validate_session_skill`
  materializes the skill runtime (registry lookup + manifest load, cheap and
  side-effect-free) in `start_session` AND `continue_session` before
  persisting/spawning — no row, no workspace, no task for a session that
  cannot run; `SkillConfigError` propagates. (2) The API translates first:
  `_translate_legacy_request` (D3 shim) maps a `model_type`-only request
  through the alias map into `skill_id` (+ legacy identity fields seed
  `subject_id`/`variant`), then the request faces the *same* registry check
  as a canonical one — `{"model_type":"direction"}` → 404 `skill_not_found`
  naming `ml-direction` + available skills, never a special "legacy
  rejected" error. `SkillConfigError` at the handler maps to 404
  `skill_not_found` (unregistered id) / 422 `skill_config_invalid`
  (registered id, broken manifest) / 422 `skill_id_required` (no id at all);
  the continue endpoints map it to 409. `_translate_canonical_request`'s
  registry check now also 422s a registered id whose manifest fails to load.
- Why: `start_research` returns 201 before the background task does any work,
  so a guaranteed-fatal session reports success (S1).
- Files: `src/api/research.py`, `src/core/session_manager.py`.
- Approach: validate the skill runtime (registry lookup + manifest load) during
  `start_session`, before persisting/spawning — a `SkillConfigError` becomes a
  4xx with the skill id. Keep the DB row only for sessions that actually start.
  Per D3 (§2): a legacy `model_type`-only request is *translated* through the
  alias map first, then hits the same installed-skill check — it fails as
  `skill_not_found` naming the translated id (e.g. `ml-direction`), never as a
  special "legacy rejected" error.
- Acceptance: `{"model_type":"direction"}` with no installed ML skill → 4xx
  (not 201); an unknown `skill_id` → 4xx (matching the existing
  `skill_not_found` vocabulary); a valid skill still returns 201.
  **Met** — API-level tests (real manager over a real store, scripted
  orchestrator) assert 404 + translated id + available list + no row for the
  trio and unknown ids, and 201 + dual-shape row for `prompt-engineering`;
  manager-level tests assert `SkillConfigError` before any row for
  model_type-only and unregistered ids. Contract-change fallout updated:
  `test_canonical_start_wiring` (legacy-only start now refused), the two
  preflight session starts, the C3.3a manifest-path test,
  `test_api_auth.start_payload` (canonical shape), and the compat GEN-001
  legacy tests (trio → 404 naming `ml-direction`; installed-skill legacy
  start → 201 with `model_type=""`).
- Deps: P7-009. Size: S. Risk: medium (changes an API contract — see D3).

### Wave 3 — Tests (the missing end-to-end proof)

**P7-011 — API-level non-ML end-to-end test (the test that never existed) — DONE 2026-09-18**
- Implementation note: the test exposed that the demo path was DEAD end to
  end and required six product fixes, not just a test: (1)
  ``BootstrapRunner`` existed but had no production consumer —
  ``SessionManager.start_session`` now runs the skill's ``bootstrap.py``
  after writing the manifest (fail-fast: a failed bootstrap refuses the
  start; skills without a bootstrap skip; continuations never re-bootstrap);
  (2) ``MockProvider``'s default eval command was skill-agnostic,
  relative-path and never relayed the governed eval's marker — skills now
  declare ``prompt.demo_experiment_command`` (closed placeholder vocabulary
  incl. ``{session_workspace}``, validated at load), rendered per session
  and wired as the demo provider in ``orchestrator.run``; the mock relays
  the freshest ``ITERATION_RESULT`` line from the newest tool result
  verbatim in the same response that issues the next eval (the relay
  contract — the mock invents no metrics); (3) the per-iteration config
  snapshot keyed only on ``--config`` — skills now declare
  ``command_policy.config_flag`` (``--prompt``/``--target``), used by BOTH
  the policy's confinement/copyable check and the pre-run snapshot, and the
  text-marker path attaches the turn's snapshot to relayed markers;
  (4) ``/results``+``/iterations`` enrichment derived ``skill_id`` from
  ``model_type`` (empty for non-ML) — the session's native ``skill_id``
  column now wins; (5) preview/confirm's ``target_kind`` injection had the
  same model_type blind spot — ``_promoter_for_session`` now returns
  ``(promoter, skill_id)``; (6) see P7-014 for the consistency-gating fix
  the confirm path needed. The suite runs the REAL app (lifespan, real
  SessionManager/store/bootstrap/governed commands) for both target kinds:
  201 → poll to ``completed`` → iterations populated from the governed
  eval's nonce-verified marker → /results populated → preview reports
  ``registry_api`` / ``file_path``. Known behavior note: identical re-runs
  of the same config are now correctly duplicate-rejected (stable trial
  identity via the snapshot), recorded as audit rows with
  ``duplicate_of_iteration`` set.
- Why: `tests/test_skill_prompt_engineering_e2e.py` uses a `MagicMock`
  orchestrator, seeds the DB directly, and builds `ResearchConfig` by hand — it
  never exercises the API + manifest path a real operator hits. That is exactly
  why B1 shipped unnoticed (ARC-011 review C4).
- Files: new `tests/test_non_ml_session_e2e.py`.
- Acceptance: fails against today's build with the exact manifest 500; passes
  after Wave 1; no network (demo provider + offline eval).
  **Met** — green after Wave 1 + the fixes above; fully offline (demo
  provider + each skill's offline evaluator; the workspace venv the command
  policy expects is symlinked, matching the Docker image's
  ``/app/workspace/.venv``).
- Deps: P7-006, P7-007. Size: M. Risk: medium (may expose further gaps).
  **Confirmed** — it did (six fixes above).

**P7-012 — Manifest + validator unit tests (non-ML) — DONE 2026-09-18**
- Implementation note: the core AC (v3 build per bundled skill, no ML-only
  strings, profile-based validation both ways, v1/v2 read-compat) landed with
  Wave 1 in `tests/test_research_manifest.py`
  (`test_v3_manifest_builds_for_bundled_skills_without_ml_fabrication`,
  `test_ml_profile_still_requires_ml_sections`,
  `test_skill_profile_does_not_require_ml_sections`,
  `test_v1/v2_manifest_loads_and_normalizes_to_*`). Wave 3 added the new
  declarative surface's tests: `demo_experiment_command` declared + rendered
  with absolute session paths, `config_flag` declared, unknown-placeholder
  and multi-line rejection at load time
  (`tests/test_skill_prompt_engineering_e2e.py`), and the MockProvider relay
  contract (`tests/test_mock_provider.py`: verbatim relay, newest-result
  only, custom marker prefix). No parity change (ML manifest untouched).
- Files: extend `tests/test_research_manifest.py` (or add one) and
  `tests/parity/` if the ML manifest changes.
- Acceptance: v3 build per skill; no ML-only strings in non-ML manifests;
  profile-based validation both ways; v2 read-compat. **Met.**
- Deps: P7-004. Size: S. Risk: low.

**P7-013 — Failure-path regression tests — DONE 2026-09-18 (absorbed into Wave 2)**
- Implementation note: the P7-009/P7-010 acceptance tests landed directly in
  the designated file (`tests/test_session_failure_modes.py`, Wave-2 section)
  and cover all four items below through the real SessionManager and the
  real API router.
- Files: extend `tests/test_session_failure_modes.py`.
- Acceptance: crashed background task → `failed` + `error_message`; unknown
  `skill_id` → 4xx; legacy model_type-only start → 4xx; no zombie rows.
- Deps: P7-009, P7-010. Size: S. Risk: low.

**P7-014 — Promotion e2e for both non-ML target kinds — DONE 2026-09-18**
- Implementation note: drove preview→confirm through the single resolution
  site (``_promoter_for_session`` → ``promotion_target_from_manifest``) over
  a real store with seeded gates-passing winners. This exposed (and fixed) a
  real gap: **non-ML sessions could never be CONFIRMED** — the promotion
  consistency report hard-blocked on ML serving-era evidence (mlflow artifact
  refs, inference feature/roster parity, serving rollback target, smoke
  validation) that generative skills never produce.
  ``build_consistency_report`` now takes
  ``serving_evidence_required`` (default ``True`` — legacy behavior
  byte-identical); ``ConfigPromoter.preview`` computes it from the session's
  skill resolution (an installed skill manifest ⇒ the skill's own declared
  gates + the promotion target's atomic write/rollback are the contract).
  Tests: registry_api confirm delivers to the declared ``register_endpoint``
  (mock transport, idempotency + verbatim config) and records the durable
  ``target_descriptor``; file_path confirm writes the declared
  ``path_template`` under the host-configs root; a fresh-promoter rollback
  restores the previous content at the recorded path; all pre-existing
  promotion-safety coverage stays green.
- Files: extend `tests/test_webhook_promotion.py` and
  `tests/test_release_promotion_safety.py`.
- Acceptance: a `registry_api` skill preview→confirm delivers to the declared
  endpoint (mock transport) and records `target_descriptor`; a `file_path` skill
  writes to its `path_template`; rollback still restores remotely (existing
  coverage stays green). **Met.**
- Deps: P7-007. Size: S-M. Risk: medium — the consistency-gating change is
  the one deliberate behavior relaxation (ML behavior unchanged, asserted by
  the unchanged gate-bundle/consistency suites).

**P7-015 — UI flow test for a skill session — DONE 2026-09-18**
- Implementation note: `ui/src/pages/__tests__/NewResearch.test.tsx` pins the
  start payload's canonical shape — a selected skill sends `skill_id`
  (+subject/variant), never the legacy model_type/instrument/timeframe trio,
  and submit stays disabled without a selection. `tsc --noEmit`, vitest (38
  passed) and `vite build` green.
- Files: new `ui/src/pages/__tests__/` test (or extend
  `ui/src/components/__tests__/`).
- Acceptance: `NewResearch` sends `skill_id` (not the legacy trio) for a
  selected skill; `tsc --noEmit` + `vitest` green. **Met.**
- Deps: P7-006. Size: S. Risk: low.

**P7-016 — Parity fixture provenance refresh (S3) — BLOCKED on a clean commit**
- Status: ready to run, blocked by design. The capture tool refuses on a
  dirty tree, and the tree carries the uncommitted Wave 1-3 work; committing
  is the maintainer's call (§7 manual publish checklist). Procedure once
  committed clean: `python tests/parity/capture.py` (writes `expected` +
  `source_sha` at HEAD), then `pytest -m parity`; commit the fixture diff
  with this task id. Do not hand-edit provenance.
- Why: the promotion fixture was hand-edited; `source_sha` is stale and the
  capture tool refuses to run on a dirty tree.
- Files: `tests/parity/promotion_preview/development_scope_basic.json`,
  `tests/parity/capture.py` (document the procedure).
- Approach: after Wave 1 lands and the tree is committed clean, run the capture
  tool to regenerate the fixture + `source_sha`; add a `recapture` note. Do not
  hand-edit provenance again.
- Acceptance: golden fixtures recaptured from a clean commit; `pytest -m parity`
  green.
- Deps: P7-004 (manifest shape settled). Size: S. Risk: low.

### Wave 4 — Release hygiene

**P7-017 — Documentation truth pass**
- Why: README's headline claim ("Adding a domain means adding a directory") and
  the demo flow are only true once Wave 1 lands; RUNBOOK needs the real flow.
- Files: `README.md`, `RUNBOOK.md`, `skills/*/README.md`, `CLAUDE.md` if it
  describes session start.
- Acceptance: a documented copy-pasteable `curl`/UI flow actually works against
  the built image for at least `prompt-engineering`; no claim exceeds reality.
- Deps: P7-011. Size: S. Risk: low.

**P7-018 — Fix the 9 missing doc references (S2)**
- Files: restore the referenced ADRs, or rewrite the references to point at the
  surviving docs (e.g. `docs/history/ARC-011_IMPLEMENTATION_REVIEW_2026-08-15.md`).
  Optionally add a guard so a code comment cannot reference a nonexistent doc.
- Acceptance: the referenced-doc scan (§6) returns empty; optional CI check.
- Deps: none. Size: S. Risk: low.

**P7-019 — CHANGELOG for the release**
- Files: `CHANGELOG.md`.
- Acceptance: one entry covering Wave 1/2 behaviour changes, the breaking
  approval v2 change (already drafted), and the new e2e gate.
- Deps: P7-011. Size: S. Risk: low.

**P7-020 — Poetry metadata modernization (S4, optional)**
- Files: `pyproject.toml`.
- Approach: move `authors`/`scripts`/`readme` to `[project.*]` per the warnings;
  keep `[tool.poetry]` for poetry-specific tables. Re-verify `poetry check` and
  `poetry build`.
- Acceptance: `poetry check` warning-free; build + wheel smoke unaffected.
- Deps: none. Size: S. Risk: low. Deferrable post-release.

**P7-021 — CI gates for the new guarantees (S6)**
- Files: `.github/workflows/ci.yml`.
- Approach: ensure P7-011 runs in the default `test` job; confirm the
  `distributed` job actually executes against Postgres; decide whether the UI
  `vitest` step keeps `--pool=forks --maxWorkers=1` (memory) and that it runs
  the same command locally.
- Acceptance: CI green on a branch; the non-ML e2e is a required check.
- Deps: P7-011. Size: S. Risk: low.

**P7-022 — Scripted Docker smoke test**
- Why: the image smoke test I ran by hand is not repeatable.
- Files: `scripts/smoke_docker.sh` (new) + a CI step or RUNBOOK entry.
- Approach: build, run detached, poll `/health` + `/health/ready`, assert
  `/api/v1/skills` lists the 3 skills, start a `prompt-engineering` demo session,
  assert it reaches an iteration, tear down. Non-zero exit on any failure.
- Acceptance: `scripts/smoke_docker.sh` passes locally and in CI.
- Deps: P7-011. Size: S-M. Risk: low.

### Wave 5 — Verify and ship

**P7-023 — Version + release notes (D2)**
- Files: `pyproject.toml`, `openapi.yaml`, `src/main.py`, `CHANGELOG.md`, tag.
- Acceptance: version consistent in all four places; notes state the breaking
  approval change and the new non-ML capability. Per D2 (§2): tag `v0.1.0`
  only after the full §6 run on a clean checkout including P7-011 + P7-022;
  any earlier artifact is pre-release-suffixed and never published as
  `latest`/final.
- Deps: P7-019. Size: S. Risk: low.

**P7-024 — Final release verification + manual publish**
- Approach: run §6 in full on a clean checkout, then manually (no automation):
  `git add` the six new files, commit, tag, push, publish image/wheel.
- Acceptance: every §6 gate green; §7 checklist fully ticked.
- Deps: all. Size: S. Risk: low.

---

## 4. Implementation order

**Critical path (B1):** P7-001 → P7-002 → P7-003 → P7-004 → P7-005 → P7-006 →
P7-007 → P7-008 → P7-011 → P7-017 → P7-019 → P7-023 → P7-024.

**Parallelisable:** P7-009/P7-010 (Wave 2) and P7-018/P7-020 (Wave 4) have no
dependency on Wave 1 and can proceed alongside it. P7-016 must run *after*
P7-004 and *after* the tree is committed clean.

```
Wave 0  P7-001                    (decisions D1-D4)
          |
Wave 1    +--> P7-002 --> P7-003 --> P7-004 --> P7-016
          |                 |          |
          |                 +--> P7-005 --> P7-007 --> P7-008
          |                                |
          +--> P7-006 ---------------------+
                                           |
Wave 2  P7-009 --> P7-010                  |
                                           v
Wave 3                                 P7-011 --> P7-014
                                         |  \--> P7-012, P7-013, P7-015
                                         v
Wave 4                       P7-017, P7-018, P7-019, P7-020, P7-021, P7-022
                                         |
Wave 5                         P7-023 --> P7-024 --> publish (manual)
```

**Recommended commit sequence** (keeps each commit reviewable and revertible):
1. Schema + builder: P7-002, P7-003, P7-004.
2. Wiring: P7-005, P7-006, P7-007, P7-008.
3. Failure semantics: P7-009, P7-010.
4. The e2e proof: P7-011, P7-012, P7-013, P7-014, P7-015.
5. Hygiene: P7-016, P7-017, P7-018, P7-019, (P7-020), P7-021, P7-022.
6. Release: P7-023, then tag.

---

## 5. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Manifest schema change breaks persisted rows | High | v3 read-compat + parity fixtures; P7-012 asserts v1/v2 round-trip |
| Non-ML promotion re-opens the just-fixed rollback hole | High | P7-007 keeps `target_descriptor` validation; re-run `tests/test_release_promotion_safety.py` explicitly |
| Relaxing `model_type` silently admits junk skills | Medium | `skill_id` required + registry lookup during start (P7-010) |
| Fabricated provenance for non-ML manifests | High | P7-003 forbids ML strings in non-ML manifests (asserted) |
| e2e uncovers further gaps (likely) | Medium | P7-011 is deliberately late in Wave 3 and may spawn new P7-025+ tasks; budget for it |
| Start API contract change (4xx instead of 201) breaks a client | Medium | D3 decision; document in CHANGELOG (P7-019) |
| Empty `model_type` collapses every non-ML skill onto `<root>/skill/…` (cross-skill overwrite) | High | D1 rule: fall back to `skill_id`, never the literal `"skill"` (`promotion_target.py:165`/`:279`); P7-014 asserts both `file_path` skills promote to distinct paths |
| A declared `path_template` aims a promotion write outside the host-configs root | High | D4 confinement (P7-007): unknown placeholders + `..` traversal rejected at skill load; relative templates rooted under `settings.host_configs_path`; rendered `subject_id`/`variant` sanitized (absolute templates allowed only via the G6 `{settings.*}` resolution — operator-controlled) |

---

## 6. Verification (run in this exact order)

Use the existing Poetry virtualenv (there is no repo-local `.venv`):

```bash
PY=/home/mike/.cache/pypoetry/virtualenvs/autoresearch-agent-w707adH2-py3.12/bin/python

# 1. Static gates
$PY -m ruff check --config pyproject.toml src tests
$PY -m mypy src --no-error-summary
$PY scripts/check_domain_coupling.py

# 2. Full suite - run in BACKGROUND: it takes ~45s and the shell tool
#    times out at 30s (a plain foreground run WILL be killed mid-suite).
nohup $PY -m pytest -q -p no:cacheprovider > /tmp/final-suite.log 2>&1 &
# then: tail -3 /tmp/final-suite.log  -> "1278 passed, 30 skipped" + new tests

# 3. Promotion safety specifically (P7-007 touches this)
$PY -m pytest -q tests/test_release_promotion_safety.py \
    tests/test_promotion_approval.py tests/test_webhook_promotion.py

# 4. Packaging (skipped unless the dist dir env var is set)
poetry build --output /tmp/dist
AUTORESEARCH_DIST_DIR=/tmp/dist $PY -m pytest -q tests/test_packaging.py

# 5. Installed-wheel smoke, OUTSIDE the checkout
python -m venv /tmp/wheel-smoke-venv
/tmp/wheel-smoke-venv/bin/python -m pip install /tmp/dist/*.whl
cd /tmp/wheel-smoke-cwd && /tmp/wheel-smoke-venv/bin/python -I -c \
  "from src.core.skill_registry import SkillRegistry; print(sorted(SkillRegistry().discover()))"

# 6. UI
cd ui
npx --no-install tsc --noEmit --types vitest/globals,@testing-library/jest-dom
npm run test:unit -- --run
npm run build

# 7. Image + a REAL session start (the check that would have caught B1)
docker build -t autoresearch-agent:verify .
docker run -d --name ar-verify -p 127.0.0.1:18030:8000 \
  -e AUTORESEARCH_DEMO=true -e AUTORESEARCH_API_TOKEN=demo-token \
  -e AUTORESEARCH_DATABASE_URL= autoresearch-agent:verify
curl -s http://127.0.0.1:18030/health
curl -s -X POST http://127.0.0.1:18030/api/v1/research/start \
  -H 'Authorization: Bearer demo-token' -H 'Content-Type: application/json' \
  -d '{"skill_id":"prompt-engineering","subject_id":"default","variant":"demo","max_iterations":2}'
# BEFORE Wave 1: 500 (manifest model_type).  AFTER Wave 1: 201 + running session.
docker rm -f ar-verify

# 8. Referenced-doc integrity (P7-018)
grep -rhoE 'docs/[A-Za-z0-9_./-]+\.md' src/ tests/ scripts/ .github/ | sort -u \
  | while read -r f; do [ -f "$f" ] || echo "MISSING: $f"; done
```

**Environment gotchas learned this session:**
- `python -I` (isolated) drops `PYTHONPATH`, so it fails in the *image* (which
  copies `src/`) but works for an *installed wheel*. Use `-I` only in step 5.
- `pytest --timeout` is not available (no `pytest-timeout` plugin installed).
- Run the full suite in the background; a foreground run is killed at 30s.

---

## 7. Manual publish checklist

- [ ] All §6 gates green on a **clean** checkout (no uncommitted edits).
- [ ] `git add` the untracked files (none of these exist in history yet):
      `src/core/promotion_approval.py`,
      `skills/prompt-engineering/eval/dataset.py`,
      `skills/prompt-engineering/README.md`,
      `tests/test_release_promotion_safety.py`,
      `tests/test_prompt_evaluator.py`, `tests/test_packaging.py`,
      `docs/adr/ARC-012-release-readiness-backlog.md`, plus new Wave-3 tests.
- [x] Resolve the staged deletion
      `D .zcode/plans/plan-sess_78a4055d…md` — **resolved 2026-09-18**
      (commit `0439d36`): finalized the deletion. The file had entered
      history incidentally via `a651939` despite `.zcode/` being gitignored
      (line 57); HEAD now matches the ignore rule and the path no longer
      appears in status snapshots (it broke a `git add`-based commit flow:
      "pathspec did not match any files").
- [ ] `poetry.lock` committed (it carries the `types-PyYAML` addition).
- [ ] Version consistent across `pyproject.toml`, `openapi.yaml`,
      `src/main.py`, `CHANGELOG.md`; tag matches.
- [ ] `AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER` set in any real deployment
      (unset = every production confirm rejected, by design).
- [ ] Release notes call out the **breaking** `hmac-sha256-v2` approval change.
- [ ] Release notes state which skills are executable and at what maturity.
- [ ] Publish image + wheel; confirm the published wheel installs and discovers
      all 3 skills from outside the checkout (§6 step 5).

---

## 8. Explicitly out of scope / deferred

- Rewriting the UI beyond the skill-session flow (P7-015 covers the gate only).
- Removing `model_type` from the DB schema (D1b) — revisit in a later release.
- Re-adding ML skills (`ml-direction` etc.). This plan assumes they stay
  uninstalled; D3 preserves their legacy *values* only for reading historical
  rows.
- Performance/scale work. Multi-worker Postgres already landed (P6); this plan
  only *verifies* it (P7-021).
- Any change to the promotion-approval v2 contract from the earlier hardening —
  treated as frozen input.
