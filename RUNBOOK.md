# Autoresearch Agent Runbook

## Auth

Operator API and WebSocket requests must use a bearer token. The service first
compares the token to `AUTORESEARCH_API_TOKEN` with constant-time comparison.
If it does not match, the token is introspected through
`AUTORESEARCH_IDENTITY_SERVICE_URL` or `IDENTITY_SERVICE_URL`; the token must be active and carry
`admin`, `ml_admin`, or `is_admin`.

Useful local checks:

```bash
curl -H "Authorization: Bearer $AUTORESEARCH_API_TOKEN" http://localhost:8030/api/status
```

Prometheus scrapers can be separated from operator tokens by setting
`AUTORESEARCH_PROMETHEUS_TOKEN`. When that value is set, `/metrics` requires
`Authorization: Bearer <token>`.

## Configuration and Vault

Autoresearch uses the platform Vault loader with environment precedence:
process environment and `.env` values win, Vault provides service defaults from
`secret/config/autoresearch-agent/<env>`, and code defaults fill the rest.

Store `ANTHROPIC_AUTH_TOKEN`, `AUTORESEARCH_API_TOKEN`, and
`AUTORESEARCH_PROMETHEUS_TOKEN` in Vault for shared environments. Local `.env`
files remain acceptable for developer machines and are ignored by git.

## Metrics

`GET /metrics` uses `prometheus-client` and includes the standard
`process_*`/`python_*` runtime collectors plus autoresearch metrics such as:

- `autoresearch_sessions_total`
- `autoresearch_pipeline_runs_total`
- `autoresearch_iteration_attempts_total`
- `autoresearch_config_promotions_total`
- `autoresearch_active_sessions`

The JSON alert endpoint remains available at
`GET /api/observability/alerts`.

## Health

`GET /health` is intentionally lightweight and is used by Docker healthchecks.
It should not call downstream ML services.

`GET /health/ready` is the Kubernetes-style readiness endpoint. It reports
internal initialization state and, when preflight is enabled, the same required
dependency checks used before a session can spend LLM budget.

`GET /monitoring/health` returns readiness-style details, including active
session count and the same dependency/preflight checks used before a session can
spend LLM budget. Use it for dashboards and deployment probes that need to know
whether data ingest, feature service, trainers, MLflow, and artifact storage are
ready.

## Docker

Build from the repository root so Poetry path dependencies resolve from their
real repo-relative locations:

```bash
docker compose -f compose/base.yml -f compose/infra.yml -f compose/ml.yml -f compose/autoresearch.yml build autoresearch-agent
```

The image copies `services/shared`, shared `libs/`, `traid_training_sdk`, the
committed `poetry.lock`, and the `src/` backend package. The runtime command is
`uvicorn src.main:app --loop uvloop`.

## SQLite Schema

SQLite remains intentional for this single-writer service. Schema evolution is
handled in `ResultsStore.initialize()` with a `schema_version` table and
numbered idempotent migrations instead of Alembic.

## Intentional Non-Integrations

The service does not publish NATS events or use `libs.model_naming` today.
Session lifecycle events and shared naming should be revisited when the agent
starts emitting platform domain events.

## UID 1001

The container runs as UID/GID `1001`, matching the ML service images. The
entrypoint only runs as root long enough to ensure `/app/workspace/runs` and
`/app/workspace/db` are owned by `1001:1001`.

For local compose, make sure the host config promotion mount is writable by UID
`1001` when promotions are expected:

```bash
sudo chown -R 1001:1001 configs
```

## Workspace Dependency Parity

The autoresearch workspace venv runs the training scripts that interact with
the ML services, so its critical modelling packages must stay aligned with the
locked ML services. Run the parity check from the repo root:

```bash
python scripts/ci/check_ml_dep_parity.py
```

When all ML service locks agree on a version, autoresearch must pin the exact
same version in `requirements-workspace.txt`. When the locked ML services still
differ, autoresearch may use a range only if it accepts every locked version.
