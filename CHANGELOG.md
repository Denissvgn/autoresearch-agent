# Changelog

## Unreleased

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
