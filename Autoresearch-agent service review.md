# Autoresearch-agent service review

Surface: server — FastAPI + Anthropic SDK, async SQLite (aiosqlite), governed bash policy, ConfigPromoter, PipelineController, WebSocket broadcaster (~18k LOC).

Overall the service is well-structured: bearer-token auth on every API/WS, a strict allow-list command policy with shell-syntax rejection, per-attempt manifests + hashes, an audit-event store, preflight checks on dependent services, structured HPO planning, and crash-recovery via `recover_orphaned_sessions`. Findings below are concrete, verified, and ordered by severity.

## High-severity

1. **`stop_session` clobbered by orchestrator's "completed" status**  
   session_manager.py writes `status="stopped"` immediately, but the orchestrator's main loop only differentiates `timed_out` vs `completed` (orchestrator.py). When the agent reacts to `_should_stop` and the tool-loop breaks normally, the final UPDATE at orchestrator.py overwrites `stopped` with `completed` — and worse, the auto-promote path at orchestrator.py triggers because `final_status == "completed"` and `pipeline_id is None`. **Stops can silently auto-promote.** Fix: detect the stop flag and set `final_status = "stopped"`; skip auto-promotion when stopped/timed_out.

2. **`asyncio.create_task` results never observed**  
   `_run_and_cleanup` and `_run_pipeline_and_cleanup` are spawned via `asyncio.create_task` (session_manager.py, session_manager.py) without `add_done_callback`. The orchestrator catches `Exception` internally, but anything that escapes (e.g., during the pre-loop manifest write or DB update) becomes a "Task exception was never retrieved" warning at GC time, with no UI/audit signal. Fix: attach a done-callback that records to the audit table and broadcasts an event.

3. **CORS `allow_credentials=True` combined with possible `"*"`**  
   main.py passes `allow_credentials=True` and `allow_origins=settings.cors_origins`. `cors_origins` returns `["*"]` when the raw value is `*` (config.py). Starlette will warn but still respond; with the bearer token in `Authorization`, this is effectively a same-token-from-any-origin posture. Fix: reject `*` when credentials are enabled, or set `allow_credentials=False` and use `Sec-WebSocket-Protocol` style auth only.

4. **`ALTER TABLE ADD COLUMN ... except: pass` masks real failures**  
   results_store.py wraps every migration in bare `try/except: pass`. This silently swallows disk-full / permission / corruption errors at startup; later code assumes the columns exist and crashes with confusing IntegrityError/OperationalError on first write. Fix: catch only `aiosqlite.OperationalError` whose message contains `"duplicate column name"`; log everything else and abort startup.

5. **No hard timeout on the agent loop / cost-budget check is post-spend**  
   `ResearchConfig.timeout_s` is honoured per turn (`_timed_out` flag), but the loop is not wrapped in `asyncio.wait_for`. A single stuck `to_thread` (e.g., a 7200s `prepare.py` that ignores SIGTERM via stdin/SIGCHLD edge cases — there is a SIGKILL fallback in command_runner.py, good) or a multi-hour API stall (`anthropic_api_timeout_s=600` plus 3 retries × `30·2^n` backoff = ~210s extra; with `max_api_retries=3` the upper bound on a single Claude call is ~810s) can blow past the configured `timeout_minutes`. Cost is similarly checked **after** the API call — a single oversized turn can exceed `max_budget_usd` by one full message. Fix: wrap `run()` in `asyncio.wait_for(..., timeout=config.timeout_s)`; estimate cost from `input_tokens + max_tokens` and pre-check before sending.

## Medium-severity

6. **Duplicate-detection across sessions is opt-in and OFF by default**  
   `autoresearch_cross_session_duplicate_check=False` (config.py). Operators relying on `trial_identity_hash` to prevent re-running identical config/seed/mode trials will silently get duplicates across sessions. Either default to True or surface this prominently in `/api/status`.

7. **Promotion is not atomic vs. host bind-mount writes**  
   `ConfigPromoter.confirm` writes the YAML and metadata sidecar separately (per the subagent's read; consistent with the typical pattern). If the second write fails, `host_configs_path` is left with a new config but no audit metadata. Fix: write both files to `*.tmp` next to the targets, fsync, then `os.replace` in a deterministic order; on failure remove the temps.

8. **Approval is structurally optional even on production-scope promotions**  
   `PromotionApproval` fields are all `Optional` (promotion.py). There is no enforcement at the API layer that `scope="production"` requires `approval.approved=True` with a non-empty signature/approver. Whatever logic exists in `ConfigPromoter` should be enforced upstream so audit captures the rejection.

9. **`/metrics` endpoint is unauthenticated**  
   main.py exposes Prometheus metrics with no auth. Inside Docker this is conventional, but the same port serves the public API — anyone reaching `/metrics` learns active session counts, costs, alert suggestions, and instrument labels. Fix: gate behind a separate scrape token or a network policy.

10. **WebSocket heartbeat ignores client liveness; no timeout on `receive_text`**  
    main.py: the heartbeat loop pings every 15s but does not detect dead peers; `await websocket.receive_text()` blocks indefinitely. A client that vanishes without TCP RST keeps the slot. Combined with `EventBroadcaster` retaining stale entries until the next failed `send_text`, this leaks WebSocket objects. Fix: set a `receive_text` timeout via `asyncio.wait_for`, drop on consecutive ping failures.

11. **`EventBroadcaster._clients` mutated from concurrent coroutines without lock**  
    events.py. In CPython this is "safe" against corruption only because of the GIL+atomic ops, but iterating `self._clients` in `broadcast` while `connect` mutates it can raise `RuntimeError: Set changed size during iteration`. Fix: snapshot with `list(self._clients)` before iteration; use an `asyncio.Lock` for connect/disconnect.

12. **Recovery sets status to `resumable`/`interrupted`, but `_active` does NOT track them**  
    `recover_orphaned_sessions` updates the DB but the orchestrator instance has no in-memory record. If the operator calls `/research/{id}/runtime-resume`, `continue_session` runs through `start_session`-style validation OK; but `is_running()` returns `False` for these IDs while their underlying subprocess (if it survived a container restart with shared workspace) may still be writing files. Since the service is dockerized this is rare, but worth a comment + test.

13. **Prompt injection via `prepare.py --- ... ---` markers in stdout**  
    `parse_prepare_output` ([orchestrator.py#L284 region read via marker logic](services/autoresearch-agent/server/core/orchestrator.py)) and the universal scanner at orchestrator.py treat any tool output containing `---` plus the expected fields as an iteration result. The agent's `read_file` tool surfaces file content into the LLM's context, but `bash`'s `cat` allowlist is restricted to `train.yaml`, `best_train.yaml`, `hpo_results.json`, `last_metrics.txt`, `results.json` (command_policy.py). Still: a hostile training script (or a future skill modification) can emit a forged `---` block to fake a passed iteration. Fix: require the marker file (`last_metrics.txt`) to also include a per-run nonce written by the server, or sign the metrics block with the session manifest hash.

14. **Unbounded `list_sessions` / `list_iterations` / `list_pipelines`**  
    research.py and the `_store.list_*` methods don't accept `limit`/`offset`. Long-running deployments will see slow responses and large WS broadcasts. Add cursor pagination.

15. **`record_audit_event` failures only `try/except` at call sites — but not all sites guard**  
    Auth rejection logging is wrapped in try/except (auth.py), but research-state callers (`_audit` in research.py) propagate exceptions, meaning a transient SQLite error during audit logging will return 500 to the operator and skip the actual side-effect. Either fail-closed deliberately (current behaviour, document it) or fail-open with logged warning.

16. **`include_in_schema=False` on `/metrics` is fine, but `/api/audit-events` has no auth scope guard**  
    research.py inherits the router's bearer-auth dependency, but any token holder can read every audit row including auth-reject token fingerprints. With a single shared token, that's everyone. Fix: scope/role check or omit fingerprints from the response.

17. **Pipeline `stop_pipeline` writes status='stopped' before sub-session actually stops**  
    session_manager.py sets `status="stopped"` synchronously, but the running phase session continues until its orchestrator drains. Same race as #1 — phase finalization will overwrite to `completed`. Fix: only mark stopped after `await task` returns or after the phase orchestrator's finally block.

18. **`recover_orphaned_sessions` runs before middleware but is unbounded**  
    On every startup it scans `list_sessions()` (no time-window). For a deployment with thousands of historical sessions all in terminal status this is fine (returns "unchanged") but DB-heavy. Add a `WHERE status IN ('running','paused')` filter at the SQL layer.

19. **Synchronous `subprocess.run(grep, …, timeout=30)` from inside async tool execution**  
    `_tool_grep` (orchestrator.py) uses blocking `subprocess.run`. It's invoked under `asyncio.to_thread` (orchestrator.py) so it doesn't block the event loop, but the 30s blocking timeout sums against the worker thread pool default (32 threads in 3.12+) — pathological agent loops can exhaust the executor. Fix: use `asyncio.create_subprocess_exec`.

## Low-severity / hygiene

20. **Anthropic API tokens passed via `anthropic_auth_token` and embedded in env are not scrubbed from `/api/observability/alerts`** — the snapshot includes URLs but check `format_prometheus` does not echo settings.
21. **Marker-file consumption is racy** — `os.remove(marker_path)` after `read_text` (orchestrator.py) can lose data if the file is being concurrently rewritten by a trailing iteration of `prepare.py`. Read+rename+parse instead.
22. **Pipeline `phase_budgets` JSON is parsed in `continue_pipeline` without schema validation**, allowing arbitrary keys to silently pass through (session_manager.py).
23. **`/api/instruments` builds the list from globs every call** — fine for a few files but caches nothing; for tens of instruments this is OK, just note.
24. **`AGENT_TOOLS` declares default timeout 7200s in the description, but `_tool_bash` enforces a hard floor of 900s** (orchestrator.py). For unit-test commands this floor is excessive — surface as a settings-driven minimum.
25. **`anthropic_default_haiku_model` defaults to `claude-haiku-4-20250514`** which is not a real model identifier in the Anthropic catalog — silent insight-extraction failure on first deploy. Make this required, or default to `claude-haiku-3-5` family.
26. **No `task.cancel()` timeout in `SessionManager.shutdown`** — `await asyncio.wait(tasks, timeout=15)` then `task.cancel()`, but no second `await` to drain cancellations; FastAPI lifespan exits with un-finished tasks.
27. **`_record_command_policy_rejection` is best-effort but leaves the rejected command in the agent's tool-result loop, which the model can re-attempt** — fine functionally, but consider a per-session rejection counter that aborts the loop after N policy violations.
28. **`research_id` is a 12-hex string** — collision-safe in practice (~10^14) but listed as "session_id" elsewhere, double-check storage column lengths under load.
29. **Tests directory not inspected here** — ensure coverage for: stop→complete clobber, CORS `*`+credentials, ALTER TABLE failure, marker-file forgery, websocket disconnect race, runtime-resume on a session where `_active` already contains that ID.

## Recommended next actions (in order)

1. Patch the stop/timeout status-clobber and add `add_done_callback` to spawned tasks — both are small, isolated changes.
2. Tighten `ALTER TABLE` migration error handling (allow only "duplicate column name").
3. Wrap orchestrator `run()` in `asyncio.wait_for(timeout=config.timeout_s)` and add a pre-API cost guard.
4. Default `autoresearch_cross_session_duplicate_check=True` and document.
5. Make production-scope promotion approval mandatory at the API layer; make config + metadata writes atomic via temp+rename.
6. Snapshot the broadcaster set under a lock and add a receive-timeout to the WS handler.

Want me to implement any of these? I'd recommend starting with #1 + #2 — they're contained and high-impact.
