# Autoresearch Agent Runbook

## Auth

Operator API and WebSocket requests must use a bearer token. The service first
compares the token to `AUTORESEARCH_API_TOKEN` with constant-time comparison.
If it does not match, the token is introspected through
`AUTORESEARCH_IDENTITY_SERVICE_URL` or `IDENTITY_SERVICE_URL`; the token must be active and carry
`admin`, `ml_admin`, or `is_admin`.

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

## Configuration and Vault

Autoresearch uses the platform Vault loader with environment precedence:
process environment and `.env` values win, Vault provides service defaults from
`secret/config/autoresearch-agent/<env>`, and code defaults fill the rest.

Store `ANTHROPIC_AUTH_TOKEN`, `AUTORESEARCH_API_TOKEN`, and
`AUTORESEARCH_PROMETHEUS_TOKEN` in Vault for shared environments. Store
`AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN` there too when production promotion is
enabled. Local `.env` files remain acceptable for developer machines and are
ignored by git.

Use `AUTORESEARCH_VDMC_INDICATOR_URL` or its compose-compatible alias
`VDMC_SERVICE_URL` to override the VDMC indicator dependency. VDMC readiness is
required for `rl`, `pipeline`, and service-wide `all` preflight checks; it is
recorded but non-blocking for `direction` and `volatility` sessions.

## Metrics

`GET /metrics` uses `prometheus-client` and includes the standard
`process_*`/`python_*` runtime collectors plus autoresearch metrics such as:

- `autoresearch_sessions_total`
- `autoresearch_pipeline_runs_total`
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

## Production Promotion

Development promotion remains local to the host config mount. Paper and canary
promotion scopes record local audit decisions. Production-scope promotion
requires `AUTORESEARCH_MLFLOW_SERVICE_AUTH_TOKEN` and calls mlflow-service as
`X-Service-Name: autoresearch-agent`.

The service lists `/api/v1/composites?instrument=<instrument>&page_size=100`,
selects the single non-retired composite whose relevant component version
matches the winning `model_registry_name:model_version`, and then calls
`POST /api/v1/composites/{composite_id}/promote`. If mlflow-service returns an
error, no local production promotion record is created.

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
ready. For RL/pipeline sessions, the same dependency set also includes
vdmc-indicator readiness.

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
.venv/bin/python scripts/ci/check_ml_dep_parity.py
```

When all ML service locks agree on a version, autoresearch must pin the exact
same version in `requirements-workspace.txt`. When the locked ML services still
differ, autoresearch may use a range only if it accepts every locked version.
