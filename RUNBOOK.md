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

## Install & Isolation Requirements

Install from a built wheel or sdist into a dedicated virtual environment (see
README → Quick Start). Runtime requirements: Python 3.12+, a writable
workspace directory (`AUTORESEARCH_WORKSPACE_ROOT` or `workspace/`), and
network access to your LLM provider and any skill-declared preflight targets.

The command policy is **default-deny** and workspace-scoped, but it is not an
OS sandbox — skill packages execute code with the service's privileges.
Isolate accordingly: run in a container or on a dedicated host, mount only the
workspace and config paths, and do not run untrusted skill packages on a
privileged host. The UI ships prebuilt; no Node.js is required at runtime.

## Credential Roles

| Role | Credential | Grants |
|------|-----------|--------|
| Operator / admin | `AUTORESEARCH_API_TOKEN` (or OAuth2 introspection with `admin`/`ml_admin`/`is_admin`) | full API + UI + promotion confirm |
| Attached agent | short-lived scoped credential (run/tenant-bound, revocable) | `read`, `submit`, `evaluate`, `lifecycle` only |
| Metrics scraper | `AUTORESEARCH_PROMETHEUS_TOKEN` | `/metrics` only |
| LLM providers | `ANTHROPIC_AUTH_TOKEN` / `OPENAI_API_KEY` | model calls |
| Live harness CLIs | provider credentials for `codex` / `claude` | external harness runs (opt-in) |

Scoped attached-agent credentials **cannot** carry operator, settings,
evidence-declaration, or promotion-approval permissions — those refusals are
enforced server-side, and the UI disables the corresponding controls with the
reason shown. Promotion approval always requires an operator credential.

## Budget Limits

Every session carries a money cap (`max_budget_usd`) enforced with usage
reservations — work is admitted only when budget and concurrency capacity are
reserved, so caps hold under concurrent workers. Unknown-cost usage events are
reported as unknown (never summed as zero). External benchmark and live
qualification jobs take their own explicit budget caps
(`AUTORESEARCH_LIVE_BUDGET_USD`); a required-but-unmeasured cost or
performance gate is a rejection, not a pass.

## Recovery & Restart

Sessions persist full operational state (phase state, attempt snapshots,
event outbox). On restart, interrupted runs are assessed for recovery from
their pinned run spec and receipts: resumable sessions report `resumable`,
unresumable ones report the reason; in-flight work without a receipt is
`interrupted`, never silently completed. Stale owners cannot write after a
worker restart (lease epochs fence them). Terminal state persistence retries
transient store failures before falling back to a broadcast.

## Backup & Restore

SQLite: use the online backup API (or `sqlite3 .backup`) while the service is
running — a plain file copy of a live database is not a backup. A restore
recovers sessions, events, usage, and reservations together. Postgres: use
your standard `pg_dump`/`pg_restore` procedure. Back up the workspace
directory alongside the database: attempt snapshots and manifests carry the
digest-pinned provenance the recovery assessment verifies.

## Migrations

Schema evolution runs automatically at startup: `schema_version` plus numbered,
idempotent migrations (no manual steps on upgrade). Take a backup before
upgrading across versions. A Postgres backend
(`AUTORESEARCH_DATABASE_URL=postgresql://…`) supports multi-worker
deployments with lease-fenced writes and serialized cross-worker stop.

## Plugin & Skill Trust Modes

Skill packages are code. Two trust modes:

1. **Repo-vendored** (default): the bundled `skills/` directory, shipped and
   versioned with the service.
2. **Operator-installed**: a package added under `skills/` and loaded with
   `POST /api/v1/skills/reload`. The operator is responsible for auditing the
   package — its `bootstrap.py` runs with service privileges at session start.

In both modes the manifest's command policy is default-deny and the evaluator
entrypoints and test files of a domain are protected from candidate mutation.
External documentation sources are evidence-only: they never grant execution
authority.

## Verifying an Installation

Smoke the installed service (health → skills → one demo session):

```bash
curl -sf http://localhost:8030/health | head -1
curl -H "Authorization: Bearer $AUTORESEARCH_API_TOKEN" \
  http://localhost:8030/api/v1/skills
AUTORESEARCH_DEMO=true curl -sf -X POST http://localhost:8030/api/v1/research/start \
  -H "Authorization: Bearer $AUTORESEARCH_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"skill_id": "prompt-engineering", "max_iterations": 1}'
```

The package also ships golden-output fixtures for parser and
promotion-preview behavior (the parity fixtures). Regenerating them is an
intentional-engineering procedure described in the implementation handoff
record, not an operator task.
