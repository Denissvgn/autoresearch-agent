# Autoresearch Agent Runbook

## Auth

Operator API and WebSocket requests must use a bearer token. The service first
compares the token to `AUTORESEARCH_API_TOKEN` with constant-time comparison.
If it does not match and `AUTORESEARCH_IDENTITY_INTROSPECTION_URL` is set, the
token is introspected via OAuth2 Token Introspection (RFC 7666); the payload
must be active and carry `admin`, `ml_admin`, or `is_admin` roles.

Useful local checks:

```bash
curl -H "Authorization: Bearer $AUTORESEARCH_API_TOKEN" http://localhost:8030/api/v1/status
curl http://localhost:8030/info
```

Prometheus scrapers can be separated from operator tokens by setting
`AUTORESEARCH_PROMETHEUS_TOKEN`. `/metrics` is disabled when that value is
unset and requires `Authorization: Bearer <token>` when configured. A minimal
Prometheus scrape job looks like:

```yaml
scrape_configs:
  - job_name: autoresearch-agent
    metrics_path: /metrics
    static_configs:
      - targets: ["autoresearch-agent:8000"]
    authorization:
      type: Bearer
      credentials: ${AUTORESEARCH_PROMETHEUS_TOKEN}
```

## Configuration

Settings load from the process environment and a local `.env` file (no
external secret store is required). Store `ANTHROPIC_AUTH_TOKEN`,
`AUTORESEARCH_API_TOKEN`, and `AUTORESEARCH_PROMETHEUS_TOKEN` in your secret
manager of choice for shared environments; local `.env` files remain
acceptable for developer machines and are ignored by git.

Optional MLflow tracking is enabled by setting `AUTORESEARCH_MLFLOW_TRACKING_URI`
(empty = disabled).

## Metrics

`GET /metrics` uses `prometheus-client` and includes the standard
`process_*`/`python_*` runtime collectors plus autoresearch metrics such as:

- `autoresearch_sessions_total`
- `autoresearch_iteration_attempts_total`
- `autoresearch_config_promotions_total`
- `autoresearch_active_sessions`

The JSON alert endpoint remains available at
`GET /api/v1/observability/alerts`; the legacy `/api/observability/alerts`
path remains compatible.

## API Paths

`/api/v1` is the preferred API prefix and the UI default. The older `/api`
prefix remains mounted for compatibility, but it is hidden from OpenAPI and
should not be used for new clients. `/info` returns the service name, version,
docs URL, health URL, WebSocket path, and preferred API prefix.

Requests may use the canonical skill shape (`skill_id`, `subject_id`,
`variant`, `skill_params`) or the legacy aliases (`model_type`,
`instrument`, `timeframe`); responses carry both. Session starts fail fast:
an unknown skill is a 404 `skill_not_found` naming the available skills, a
legacy `model_type`-only request is translated through the alias map
(`direction` → `ml-direction`) and then skill-checked, and a skill whose
bootstrap cannot render the workspace refuses the start — a session row only
exists for sessions that actually started. A crashed background task is
persisted as `failed` with `error_message` and
`terminal_reason=background_task_crashed:<type>` within one event-loop turn
(never a zombie `running` row).

## Promotion Scopes

Development promotion writes the winning config to the skill's declared
file-path target (under `AUTORESEARCH_HOST_CONFIGS_PATH` by default). Paper
and canary promotion scopes record local audit decisions. Production-scope
promotion is fail-closed: it requires an HMAC-signed approval keyed by
`AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER` under method `hmac-sha256-v2`
(`production-approval.v2`). The signature covers stable JSON with the approved
candidate — `iteration`, `config_snapshot_sha256`, and `target_identity` from
the unsigned `promote/preview` response — plus `research_id`, canonical
`scope`, `approver`, `method`, `reason`, and `approved=true`. Confirm re-checks
that candidate against its own fresh preview and rejects a changed winner
instead of promoting it. Legacy `{research_id}:{scope}:{approver}` signatures
are rejected. `registry_api`/`webhook` promotion targets deliver the winner
to the skill's declared endpoint (idempotency key, retries, fail-closed) and
record a durable `target_descriptor` so rollback survives restarts; target
kinds the local machinery cannot execute (`artifact_store`, `git_branch`)
skip loudly with an audit trail.

## Health

`GET /health` is intentionally lightweight and is used by Docker healthchecks.

`GET /health/ready` is the Kubernetes-style readiness endpoint. It reports
internal initialization state and, when preflight is enabled, the dependency
checks declared by installed skills.

`GET /monitoring/health` returns readiness-style details, including active
session count and the same skill-declared dependency checks used before a
session can spend LLM budget. Use it for dashboards and deployment probes.

## Docker

Build from the repository root:

```bash
docker build -t autoresearch-agent .
docker run --rm -p 8030:8000 --env-file .env autoresearch-agent
```

The image copies the committed `poetry.lock`, the `src/` backend package,
the built UI, and a generic workspace venv. The runtime command is
`uvicorn src.main:app --loop uvloop`.

Smoke-test a built image end to end (health, skills list, a real demo
session reaching an iteration):

```bash
scripts/smoke_docker.sh          # builds, runs, asserts, tears down
```

The same script runs in CI against every built image. It is the check that
would have caught the "no non-ML session has ever run" release blocker.

## Clean-start reset

Use this to wipe accumulated experiment state so the next session re-baselines
on the current code with nothing stale biasing the agent (e.g. after a scoring
change). **Run it only when no session is `running`.**

1. Stop/finish running sessions (check `/api/v1/status`).

2. Remove the SQLite DB and run workspaces:

   ```bash
   rm -rf /app/workspace/db/experiments.db
   rm -rf /app/workspace/runs/*
   ```

   (Or mount-fresh volumes on container recreation.)

3. Verify clean, then launch a fresh session:

   ```bash
   python - <<'PY'
   import sqlite3; c=sqlite3.connect("/app/workspace/db/experiments.db")
   print("sessions", c.execute("SELECT count(*) FROM research_sessions").fetchone()[0],
         "iterations", c.execute("SELECT count(*) FROM iterations").fetchone()[0])
   PY
   ```

   Expect `0 0`. The next session starts at its skill's first phase with a
   freshly measured baseline.

## SQLite Schema

SQLite remains intentional for this single-writer service. Schema evolution is
handled in `ResultsStore.initialize()` with a `schema_version` table and
numbered idempotent migrations instead of Alembic. A Postgres backend
(`AUTORESEARCH_DATABASE_URL`) is available for multi-worker deployments.

## UID 1000

The container runs as UID/GID `1000` by default (`APP_UID`/`APP_GID` build
args). The entrypoint only runs as root long enough to ensure
`/app/workspace/runs` and `/app/workspace/db` are owned by the app user.

For local compose, make sure the host config promotion mount is writable by
that UID when promotions are expected:

```bash
sudo chown -R 1000:1000 configs
```

## Parity Suite

The golden-output parity suite (`pytest -m parity`) pins parser and
promotion-preview behavior against fixtures under `tests/parity/`. Regenerate
fixtures with the engine's `invoke`+`normalize` helpers after intentional
behavior changes (see `tests/parity/test_parity.py`).
