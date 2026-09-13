# Autoresearch Agent Consistency Review Against MLflow Service

Review date: 2026-05-08

Scope: static consistency review of `services/autoresearch-agent` against the API, lifecycle, auth, observability, deployment, and documentation patterns in `services/mlflow-service`.

## Executive Summary

`autoresearch-agent` is already aligned with `mlflow-service` on several platform basics: both are FastAPI services, both use shared platform headers and telemetry lifecycle hooks, both use Pydantic settings with Vault support, both run Uvicorn with one worker in compose, both expose Prometheus metrics, and both have CORS wildcard hardening.

The main consistency risks are around production model lifecycle ownership and contract discipline. `mlflow-service` is the system of record for composite promotion status, lifecycle audit, Redis/NATS model events, `/api/v1` APIs, and an explicit OpenAPI artifact. `autoresearch-agent` records strong local promotion evidence, but scoped production promotions remain local metadata unless the separate mlflow-service promotion API is invoked. It also exposes unversioned `/api` routes and lacks a checked-in OpenAPI contract comparable to `mlflow-service`.

## Positive Alignment

- Both services install platform headers and telemetry hooks: `services/autoresearch-agent/src/main.py:23-28`, `services/autoresearch-agent/src/main.py:84-106`, `services/mlflow-service/src/main.py:16-21`, and `services/mlflow-service/src/main.py:180-190`.
- Both services disable credentialed CORS for wildcard origins: `services/autoresearch-agent/src/main.py:139-163` and `services/mlflow-service/src/main.py:86-92`.
- Both services expose lightweight liveness and deeper dependency health surfaces: `services/autoresearch-agent/src/main.py:176-260` and `services/mlflow-service/src/api/v1/routes/health_routes.py:250-364`.
- Both services use Vault-aware settings and environment precedence: `services/autoresearch-agent/src/config.py:17-95` and `services/mlflow-service/src/config.py:27-89`.
- Both services run single-worker Uvicorn in their runtime images: `services/autoresearch-agent/Dockerfile:177` and `services/mlflow-service/Dockerfile:99`.
- Both services use read-only compose hardening with tmpfs scratch space: `compose/autoresearch.yml:107-111` and `compose/ml.yml:101-104`.

## Findings

### 1. High - Scoped production promotion in autoresearch does not execute the mlflow-service lifecycle promotion

`mlflow-service` owns composite promotion state and publishes lifecycle side effects from its authenticated promotion endpoint:

- `services/mlflow-service/src/api/v1/routes/composite_routes.py:1056-1061`
- `services/mlflow-service/src/api/v1/routes/composite_routes.py:1070-1109`
- `services/mlflow-service/src/services/model_lifecycle_publisher.py:72-73`
- `services/mlflow-service/src/services/model_lifecycle_publisher.py:216`

`autoresearch-agent` enforces signed approval for `production` scope, but the scoped confirmation path only writes local promotion metadata through its SQLite store:

- `services/autoresearch-agent/src/api/promotion.py:75-86`
- `services/autoresearch-agent/src/api/promotion.py:144`
- `services/autoresearch-agent/src/core/config_promoter.py:523-580`

Its development promotion path can patch component model versions in `mlflow-service`, but that is a version-reference update, not the lifecycle promotion endpoint that records actor-backed promotion status and emits model events:

- `services/autoresearch-agent/src/core/config_promoter.py:513-515`
- `services/autoresearch-agent/src/core/config_promoter.py:2100-2148`

Impact: an autoresearch "production" promotion can appear approved locally without updating the mlflow-service composite lifecycle state, promotion audit/event stream, or NATS/domain event consumers. Downstream services that treat `mlflow-service` as the source of truth can miss the decision.

Recommendation: make non-development promotion confirmation call the authenticated `mlflow-service` composite promotion API, or rename the current scoped record to "promotion approval" until it actually drives the mlflow-service lifecycle transition. Persist both the local autoresearch evidence and the returned mlflow-service promotion/audit identifiers.

### 2. High - Docker build context can include local autoresearch secrets and heavy UI artifacts

The compose build for `autoresearch-agent` uses the project root as context:

- `compose/autoresearch.yml:10-12`

The service README instructs developers to create a local `.env` containing API credentials:

- `services/autoresearch-agent/README.md:38-45`
- `services/autoresearch-agent/README.md:199-200`

The root `.dockerignore` ignores `.env.local`, `.env.development`, and `.env.test`, but not plain `.env`. Its UI artifact patterns target top-level `ui/**`, not `services/autoresearch-agent/ui/**`:

- `.dockerignore:22-24`
- `.dockerignore:85-88`
- `services/autoresearch-agent/README.md:89`

Impact: local builds can send `services/autoresearch-agent/.env`, `ui/node_modules`, and `ui/dist` to the Docker daemon/build cache even though the Dockerfile does not intentionally copy them. This is a security and build-performance inconsistency with the minimal-context posture expected for ML service images.

Recommendation: update the root `.dockerignore` for `services/**/.env`, `services/**/ui/node_modules/`, `services/**/ui/dist/`, coverage directories, and other generated service artifacts. Keep the explicit Dockerfile `COPY` allow-list as the runtime boundary, but prevent secrets and large local files from entering the build context at all.

### 3. Medium - Autoresearch API routes are unversioned while mlflow-service standardizes on `/api/v1`

`mlflow-service` centralizes API versioning through `settings.api_v1_prefix` and exposes service metadata through `/info`:

- `services/mlflow-service/src/main.py:71`
- `services/mlflow-service/src/main.py:228-252`
- `services/mlflow-service/src/main.py:257-293`

`autoresearch-agent` hardcodes its API routers under `/api`:

- `services/autoresearch-agent/src/api/research.py:20`
- `services/autoresearch-agent/src/api/results.py:21`
- `services/autoresearch-agent/src/api/promotion.py:11`

Impact: client generation, gateway routing, monitoring conventions, and cross-service docs need special-case handling for autoresearch. The SPA catch-all at `services/autoresearch-agent/src/main.py:396` also means mistyped future API paths can render the UI instead of failing like a service API.

Recommendation: introduce a configurable `api_v1_prefix` setting and mount `/api/v1` aliases before the existing `/api` routes. Keep `/api` as a backward-compatible alias until the UI and operator docs migrate. Add a lightweight `/info` endpoint with service name, version, docs URL, health URL, and API prefix.

### 4. Medium - Autoresearch lacks a checked-in OpenAPI contract comparable to mlflow-service

`mlflow-service` documents `openapi.yaml` as the schema source of truth and has tests that load the checked-in spec:

- `services/mlflow-service/README.md:36`
- `services/mlflow-service/README.md:76`
- `services/mlflow-service/tests/test_openapi_schema.py:13-14`

No equivalent `services/autoresearch-agent/openapi.yaml` exists, and the README lists endpoints manually instead:

- `services/autoresearch-agent/README.md:211-229`

Impact: the React client and external operators depend on implicit FastAPI runtime docs/manual tables rather than a reviewed API artifact. This makes versioning, compatibility checks, and generated clients less consistent with the mlflow-service workflow.

Recommendation: generate and commit an autoresearch OpenAPI artifact, then add a focused schema test for the high-risk contracts: auth-protected research controls, idempotent continue/runtime-resume headers, promotion approval payloads, WebSocket docs, health, metrics, and observability alerts.

### 5. Medium - Cross-service composite version writes are not prepared for authenticated mlflow-service internals

`mlflow-service` mostly protects state-changing composite operations with admin JWT dependencies, including the lifecycle promotion path:

- `services/mlflow-service/src/api/v1/routes/composite_routes.py:1056-1061`
- `services/mlflow-service/src/api/deps.py:147-189`

But the component-version PATCH endpoints are explicitly unauthenticated internal routes:

- `services/mlflow-service/src/api/v1/routes/composite_routes.py:1149-1160`
- `services/mlflow-service/src/api/v1/routes/composite_routes.py:1186-1200`

`autoresearch-agent` depends on that unauthenticated behavior when patching component versions:

- `services/autoresearch-agent/src/core/config_promoter.py:2119-2129`

Impact: this matches the current mlflow-service endpoint contract, but it is inconsistent with the broader platform auth pattern and with `compose/ml.yml:84`, which already defines a service-to-service token for ML services. When mlflow-service hardens these internal endpoints, autoresearch will need a coordinated client update.

Recommendation: add an autoresearch setting for the ML service token and send it on composite version PATCH calls. In parallel, harden the mlflow-service internal PATCH endpoints to accept service-token or admin JWT auth and record the caller in promotion/version audit metadata.

### 6. Low - Prometheus scrape behavior is stricter than mlflow-service and needs explicit monitoring configuration

`mlflow-service` leaves `/metrics` open when no scrape token is configured:

- `services/mlflow-service/src/main.py:94-102`
- `services/mlflow-service/src/main.py:300-303`

`autoresearch-agent` requires a scrape token in production and returns 404 when the token is unset:

- `services/autoresearch-agent/src/main.py:63`
- `services/autoresearch-agent/src/main.py:273-283`
- `services/autoresearch-agent/tests/test_main_operational_endpoints.py:37-53`

Impact: this is a safer default, but it is not plug-compatible with mlflow-service scrape assumptions. A Prometheus job copied from mlflow-service can silently lose autoresearch metrics unless `AUTORESEARCH_PROMETHEUS_TOKEN` and the bearer header are configured.

Recommendation: keep the fail-closed behavior, but document the monitoring scrape config next to the compose/Prometheus setup and avoid copying mlflow-service's optional-token behavior into autoresearch.

## Suggested Fix Order

1. Decide whether autoresearch scoped production promotion should call `mlflow-service` promotion now; if yes, wire the authenticated call and persist returned lifecycle/audit IDs.
2. Update root `.dockerignore` to exclude service `.env` files and nested UI/generated artifacts before the next image build.
3. Add `/api/v1` aliases and `/info` while retaining `/api` compatibility.
4. Generate and test an autoresearch OpenAPI contract.
5. Add service-token support for autoresearch composite version updates and coordinate mlflow-service hardening of internal PATCH routes.
6. Update monitoring docs/config to make the stricter autoresearch `/metrics` behavior explicit.

## Verification Notes

This was a static source review only. No tests were run because no runtime behavior was changed. The only repository change made by this review is this Markdown report.
