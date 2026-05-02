# Autoresearch-Agent Service — Code Review

**Date:** 2026-05-02
**Scope:** `services/autoresearch-agent/` (src, Dockerfile, entrypoint, config)
**Method:** Read-only review of `src/main.py`, `src/config.py`, `src/api/`, `src/core/`, `src/ws/`, container build/runtime, and test layout.

---

## Summary Table

| # | Issue | Severity | File | Category | Fix Effort |
|---|-------|----------|------|----------|------------|
| 1 | Race in concurrent session limit / dup detection | Critical | `src/core/session_manager.py` | Race | Medium |
| 2 | DB connection lifecycle / leaks | High | `src/core/results_store.py` | Resource | Medium |
| 3 | WebSocket heartbeat failure swallowed | High | `src/main.py` | Resource | Medium |
| 4 | Auth rejection silently un-audited | High | `src/api/auth.py` | Audit/Security | Low |
| 5 | Process group timeout race | High | `src/core/command_runner.py` | Race | Medium |
| 6 | Unbounded message-log growth | High | `src/core/orchestrator.py` | Memory | Medium |
| 7 | Broadcaster send-failure silent | High | `src/ws/events.py` | Logging | Low |
| 8 | Vault load may log secrets / silent `{}` | High | `src/config.py` | Security | Low |
| 9 | Continue/resume not idempotent | High | `src/core/session_manager.py` | Data consistency | High |
| 10 | Pipeline promotion-blocked state can be lost | High | `src/core/pipeline_controller.py` | Data consistency | Medium |
| 11 | 600s hard-timeout grace too generous | Medium | `src/core/session_manager.py` | Config | Low |
| 12 | Prometheus token / metrics endpoint policy | Medium | `src/config.py`, `src/main.py` | Security | Low |
| 13 | Symlink-based command-policy bypass | Medium | `src/core/command_policy.py` | Security | Medium |
| 14 | Phase budgets unvalidated | Medium | `src/core/pipeline_controller.py` | Input validation | Low |
| 15 | No distributed locking for multi-instance | Medium | `src/core/session_manager.py` | Architecture | High |
| 16 | Bare `except Exception` swallows errors | Low | `src/core/orchestrator.py` | Code quality | Low |
| 17 | No DB schema migration path | Low | `src/core/results_store.py` | Upgrade | Medium |
| 18 | `/metrics` unauthenticated when token unset | Low | `src/main.py` | Security | Low |
| 19 | Broadcaster has no max-client cap | Low | `src/ws/events.py` | DoS | Low |
| 20 | Missing composite audit-log indexes | Low | `src/core/results_store.py` | Performance | Low |
| 21 | Orphaned workspace dir on start failure | Low | `src/core/session_manager.py` | Resource | Low |
| 22 | Stop/cancel doesn't evict from `_active` | Low | `src/core/session_manager.py` | Resource | Low |

---

## Critical

### 1. Race in concurrent session limit & duplicate detection
**File:** [services/autoresearch-agent/src/core/session_manager.py](services/autoresearch-agent/src/core/session_manager.py#L212-L229) (lines 212–229; also `start_pipeline` ~553–565)

`start_session` reads `self.active_count`, scans `self._active` for duplicates, then later assigns `self._active[research_id] = ...`. There is no lock around the read–check–write, so two concurrent API calls can both pass the gate and both spawn, exceeding `max_concurrent_sessions` or producing duplicate (instrument, timeframe, model_type) sessions.

**Fix:** Wrap the spawn path in a single `asyncio.Lock` (e.g. `self._session_spawn_lock`); acquire it before the count/dup check and release after `self._active[...] = ActiveSession(...)`.

---

## High

### 2. Database connection lifecycle
**File:** [services/autoresearch-agent/src/core/results_store.py](services/autoresearch-agent/src/core/results_store.py#L340-L380)

`initialize()` opens `aiosqlite.connect(...)` inside `async with`, which closes immediately. Subsequent operations rely on `self._conn` whose lifecycle / shutdown is unclear; on `SIGTERM` writes may not flush. Cursor exception paths can leak.

**Fix:** Hold a single long-lived connection, close it in FastAPI shutdown hook, and wrap every cursor in `async with conn.cursor() as cur`. Add a readiness probe DB check.

### 3. WebSocket heartbeat failure swallowed
**File:** [services/autoresearch-agent/src/main.py](services/autoresearch-agent/src/main.py#L257-L310)

The heartbeat coroutine `except Exception: pass`. If `send_json({"type":"ping"})` fails on a half-open socket, the receive loop can stall on `receive_text()` forever.

**Fix:** Use a shared `asyncio.Event` set on heartbeat failure; race `receive_text()` against the event using `asyncio.wait(..., return_when=FIRST_COMPLETED)` and break on event set.

### 4. Auth rejection silently un-audited
**File:** [services/autoresearch-agent/src/api/auth.py](services/autoresearch-agent/src/api/auth.py#L235-L250)

`_record_auth_rejection` returns silently when `store is None`. Authentication failures during the early startup window or due to misconfig are never logged.

**Fix:** Emit `logger.warning(...)` before returning, including mechanism and status code. Consider failing startup if the audit store is required.

### 5. Process-group termination race
**File:** [services/autoresearch-agent/src/core/command_runner.py](services/autoresearch-agent/src/core/command_runner.py#L56-L80)

`_terminate_process_group` `killpg`s the original PID's group, but child processes may have started new sessions/groups. Calling `proc.communicate()` after `SIGKILL` is also racy.

**Fix:** Use `psutil.Process(pid).children(recursive=True)` to enumerate descendants, send `SIGTERM` then `SIGKILL`, and verify exit via `proc.wait(timeout=...)`.

### 6. Unbounded message log in orchestrator
**File:** [services/autoresearch-agent/src/core/orchestrator.py](services/autoresearch-agent/src/core/orchestrator.py#L1585-L1750)

Per-turn `messages` list grows for the lifetime of the agent loop (max_iterations 500). Compaction touches tool-result content but not the list length.

**Fix:** Cap retained messages with a rolling window (e.g. keep system + last N turns + critical pinned messages); compact older user/assistant pairs into summaries.

### 7. Broadcaster silently drops send errors
**File:** [services/autoresearch-agent/src/ws/events.py](services/autoresearch-agent/src/ws/events.py#L43-L52)

`except Exception: dead.append(ws)` — no log, hard to diagnose disconnects.

**Fix:** `logger.debug("ws send failed: %s", exc)` before appending.

### 8. Vault load: silent `{}` fallback + exception text logged
**File:** [services/autoresearch-agent/src/config.py](services/autoresearch-agent/src/config.py#L48-L52)

Catches all exceptions, logs raw exception message (may contain secrets/paths), and returns `{}` so missing critical secrets aren't surfaced.

**Fix:** Log only `type(exc).__name__` + sanitized context. Add an explicit preflight that fails startup when required secrets (e.g. `anthropic_auth_token`) are absent.

### 9. Continue/resume endpoints lack idempotency
**File:** [services/autoresearch-agent/src/core/session_manager.py](services/autoresearch-agent/src/core/session_manager.py#L440-L520)

A retried `POST /research/{id}/continue` (network blip) can spawn a second orchestrator for the same research_id, producing concurrent state writes.

**Fix:** Require/accept `Idempotency-Key`; persist seen keys and short-circuit on replays. At minimum, reject continue/resume if a task for that research_id is already active in `_active`.

### 10. Pipeline promotion-blocked state can be lost
**File:** [services/autoresearch-agent/src/core/pipeline_controller.py](services/autoresearch-agent/src/core/pipeline_controller.py#L270-L290)

If `_mark_promotion_blocked` itself raises after `PipelinePromotionBlocked`, pipeline status is left mid-state.

**Fix:** Wrap the mark call in try/except; on failure, log and force-update to `phase_promotion_failed` with reason="persistence_failed".

---

## Medium

### 11. 10-minute hard-timeout grace too large
**File:** [services/autoresearch-agent/src/core/session_manager.py](services/autoresearch-agent/src/core/session_manager.py#L29-L33)

`_HARD_TIMEOUT_GRACE_S = 600` allows an extra 10 min beyond soft timeout. With long sessions this overshoots the budget.

**Fix:** Reduce to ~300s, or make it `min(600, max(180, soft_timeout * 0.05))`.

### 12. Prometheus scrape token policy
**File:** [services/autoresearch-agent/src/config.py](services/autoresearch-agent/src/config.py#L129-L139), [services/autoresearch-agent/src/main.py](services/autoresearch-agent/src/main.py#L268-L280)

Token comparison uses `compare_digest` (good) but the token is optional. Where unset, `/metrics` is open.

**Fix:** Require token in production (env-validated); when absent, return 404 from `/metrics` instead of serving it.

### 13. Symlink-based command-policy bypass
**File:** [services/autoresearch-agent/src/core/command_policy.py](services/autoresearch-agent/src/core/command_policy.py#L185-L210)

`os.path.realpath` resolves symlinks at check-time. An agent that creates `ln -s` to outside the workspace passes the check whenever the link resolves inside, but a TOCTOU swap is possible. Also `_is_within` matches by prefix.

**Fix:** Disallow `ln`/`ln -s` in `_DISALLOWED_EXECUTABLES`; verify both target and parent stay inside workspace; consider `Path.resolve(strict=True)` and reject any symlink whose resolved target leaves the sandbox; clean residual symlinks at session start.

### 14. `phase_budgets` unvalidated
**File:** [services/autoresearch-agent/src/core/pipeline_controller.py](services/autoresearch-agent/src/core/pipeline_controller.py#L160-L170)

Negative or zero budgets accepted from API.

**Fix:** Add Pydantic `field_validator` requiring `int >= 1` per phase; reject unknown phase names.

### 15. No distributed lock for multi-instance
**File:** [services/autoresearch-agent/src/core/session_manager.py](services/autoresearch-agent/src/core/session_manager.py#L212-L240)

`_active` is in-process only. With >1 replica the global concurrent-session limit and dup-session check break.

**Fix:** Either document single-instance constraint and enforce in deployment, or move state to Redis with a shared lock.

---

## Low / Code Quality

### 16. Bare `except Exception` swallowing
**File:** [services/autoresearch-agent/src/core/orchestrator.py](services/autoresearch-agent/src/core/orchestrator.py#L1194) (also ~L1416, ~L684)
Replace with specific types or `logger.exception(...)`.

### 17. No DB schema migration path
**File:** [services/autoresearch-agent/src/core/results_store.py](services/autoresearch-agent/src/core/results_store.py#L310-L380)
Schema version is checked but no upgrade is performed — old DBs require manual intervention.

### 18. `/metrics` unauthenticated when token absent
**File:** [services/autoresearch-agent/src/main.py](services/autoresearch-agent/src/main.py#L268-L280)
Disable endpoint entirely when token is `None`, or fail startup.

### 19. Broadcaster has no max-client cap
**File:** [services/autoresearch-agent/src/ws/events.py](services/autoresearch-agent/src/ws/events.py)
Add a configurable cap; reject excess connections with 1013 (try again later).

### 20. Missing composite audit-log indexes
**File:** [services/autoresearch-agent/src/core/results_store.py](services/autoresearch-agent/src/core/results_store.py#L200-L210)
Add `(actor_id, timestamp DESC)` and `(research_id, timestamp DESC)` covering indexes.

### 21. Orphaned workspace dir on start failure
**File:** [services/autoresearch-agent/src/core/session_manager.py](services/autoresearch-agent/src/core/session_manager.py#L257-L290)
Wrap manifest+task spawn in try/except; clean workspace on error.

### 22. Stop/cancel does not immediately evict from `_active`
**File:** [services/autoresearch-agent/src/core/session_manager.py](services/autoresearch-agent/src/core/session_manager.py#L48-L85)
Cancelled task may be stuck on a network call; `_active` slot remains occupied.
**Fix:** After `task.cancel()`, `await asyncio.wait_for(task, 5)`; pop on timeout regardless.

---

## Architectural Observations

- **Audit trail design is solid** — JSON payloads, event categorization. The auth-rejection silent-fail (#4) is the main gap.
- **Command-policy sandbox is reasonable** but symlink semantics and TOCTOU on realpath need hardening.
- **SQLite as single source of truth** is fine for single-instance deployment; lock contention and writer starvation become risks under load. Consider WAL mode + busy_timeout if not already enabled.
- **Concurrency model under-uses locks.** Several mutable structures (`_active`, broadcaster client set, pipeline state) need explicit `asyncio.Lock`s. Several issues above (#1, #15, #22) collapse into this.
- **No circuit breaker for downstream services.** Preflight allows `allow_unready_services=true`, which can mask cascading failures of ensemble-trainer / feature-service. Add per-dependency breakers with cooldown.
- **Testing gaps (high level).** `tests/` has good unit coverage of orchestrator and policy paths but appears thin on:
  - WebSocket disconnect / heartbeat-failure scenarios
  - Pipeline promotion-blocked persistence failures
  - Concurrent session-start race
  - Symlink/command-policy edge cases
  - DB connection failure / reconnection behavior

---

## Recommended Priority Order

1. (#1) Add `_session_spawn_lock` — small change, prevents over-quota / dup spawn.
2. (#4) Log auth rejection when audit store missing — low effort, security-relevant.
3. (#9, #22) Idempotency + immediate eviction on stop/cancel — protects state integrity.
4. (#3) WebSocket heartbeat propagation — prevents stuck connections.
5. (#6) Bound orchestrator message history — prevents long-running OOM.
6. (#13, #18) Tighten command-policy symlink handling and `/metrics` exposure.
7. Remaining medium/low items as opportunistic cleanup.
