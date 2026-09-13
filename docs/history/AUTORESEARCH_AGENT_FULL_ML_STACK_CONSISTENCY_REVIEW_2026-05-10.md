# Autoresearch Agent Full ML Stack Consistency Review - 2026-05-10

## Scope

Reviewed `services/autoresearch-agent` for consistency with the current full ML stack, including:

- `compose/autoresearch.yml`
- `services/autoresearch-agent/src`
- `scripts/autotuner/*`
- `scripts/training/*` paths baked into the autoresearch workspace image
- `services/ml/ensemble-trainer`
- `services/ml/rl-trainer`
- `services/ml/inference-service`
- active generated ensemble configs used by the recent DOGEUSDT 15m E2E flow

## Verification Run

Focused autoresearch deployment and preflight tests pass:

```bash
.venv/bin/pytest --no-cov services/autoresearch-agent/tests/test_service_preflight.py services/autoresearch-agent/tests/test_deployment_inputs.py
```

Result: `12 passed, 1 warning`.

No runtime stack was rebuilt or restarted for this review.

## Executive Summary

`services/autoresearch-agent` is substantially aligned with the ML stack at the service-wiring level. It has Docker DNS URLs for MLflow, mlflow-service, data-ingest, ensemble-trainer, rl-trainer, feature-service, and vdmc-indicator; it exposes `/api/v1`; it has OpenAPI and deployment input tests; and its promotion path now calls the central `mlflow-service` instead of writing production composite state directly.

The remaining inconsistencies are production-path contract drift rather than missing plumbing. The highest-risk issues are:

1. Autoresearch predictive tuning still pins and searches stale feature-library versions `2.1.0`/`2.2.0`, while active ensemble configs and defaults use `2.3.0`.
2. Autoresearch promotion propagates base model registry versions instead of ensemble registry versions for stacking runs, while ensemble-trainer's admin tuning flow prefers `ensemble_model_version`.
3. RL GPU delegation to `rl-trainer` does not send the bearer service token required by the rl-trainer internal training API.
4. Preflight does not verify inference-service/admin-service/NATS readiness, although production replay, promotion, and full E2E validation depend on those paths.
5. The baked production replay helper calls an inference replay endpoint path and payload shape that do not match inference-service.

## Consistent Areas

- Compose wiring covers the main ML services. `compose/autoresearch.yml` sets `MLFLOW_SERVICE_URL` at line 25, `ADMIN_SERVICE_URL` at line 33, and declares service dependencies starting at line 79.
- Service preflight covers most model-training dependencies: mlflow-service, data-ingest, ensemble-trainer, rl-trainer, feature-service, vdmc-indicator, and optional artifact store are listed in `services/autoresearch-agent/src/core/service_preflight.py:69-97`.
- Autoresearch has deployment contract tests: `services/autoresearch-agent/tests/test_service_preflight.py` and `services/autoresearch-agent/tests/test_deployment_inputs.py`.
- The autoresearch image includes shared libraries needed by the training workspace, including `libs/ml_artifacts`, `libs/resilience`, and `traid_training_sdk` in `services/autoresearch-agent/Dockerfile:54-57`.
- The autoresearch workspace includes the production training scripts via `services/autoresearch-agent/Dockerfile:79`, which means the service has access to the same training entrypoints used elsewhere in the stack.

## Findings

### 1. High - Predictive autotuner still uses stale feature-library versions

Autoresearch predictive tuning is not aligned with the current feature library version used by the full ML stack.

Evidence:

- Active ensemble trainer defaults use `2.3.0`: `services/ml/ensemble-trainer/src/config/training_config.py:1112`.
- Ensemble trainer tests assert `2.3.0`: `services/ml/ensemble-trainer/tests/config/test_training_config.py:172` and `services/ml/ensemble-trainer/tests/config/test_training_config.py:212`.
- Active DOGEUSDT generated configs use `2.3.0`, for example:
  - `configs/ensemble/generated/DOGE_USDT_15m/doge_deadzone_010.yaml:25`
  - `configs/ensemble/generated/DOGE_USDT_15m/doge_deadzone_012.yaml:25`
  - `configs/ensemble/generated/DOGE_USDT_15m/doge_deadzone_020.yaml:32`
  - `configs/ensemble/generated/DOGE_USDT_15m/doge_deadzone_025.yaml:32`
- Autoresearch direction template still pins `2.1.0`: `scripts/autotuner/direction/train.yaml:99`.
- Autoresearch volatility template still pins `2.1.0`: `scripts/autotuner/volatility/train.yaml:102`.
- Direction prepare fallback still defaults to `2.1.0`: `scripts/autotuner/direction/prepare.py:63`.
- Volatility prepare fallback still defaults to `2.1.0`: `scripts/autotuner/volatility/prepare.py:60`.
- Structured HPO search space only allows `2.1.0` and `2.2.0`: `services/autoresearch-agent/src/core/structured_hpo.py:60` and `services/autoresearch-agent/src/core/structured_hpo.py:81`.

Impact:

Autoresearch can generate configs or HPO candidates that differ from the currently validated ensemble-trainer/inference path. In a strict run, this can trigger feature-library version mismatch failures. In a permissive run, it can train and promote artifacts whose feature contract is older than the active serving stack.

Recommendation:

- Update active autotuner direction and volatility templates to `2.3.0`.
- Update prepare fallbacks to `2.3.0`.
- Update structured HPO search spaces to include or default to `2.3.0`.
- Prefer deriving the default from ensemble-trainer's `TrainingConfig` or a shared config constant to avoid future drift.
- Add tests that the default autoresearch-generated direction and volatility configs request feature library `2.3.0`.

### 2. High - Autoresearch promotion uses base model versions instead of ensemble versions

Autoresearch promotion does not mirror ensemble-trainer's model-version selection when stacking is enabled.

Evidence:

- Direction training summary includes base model fields at `scripts/training/run_phase1c_direction.py:513-514`.
- Direction training summary separately includes `ensemble_model_version` at `scripts/training/run_phase1c_direction.py:610`.
- Volatility training summary includes base model fields at `scripts/training/run_phase1c_volatility.py:530-531`.
- Volatility training summary separately includes `ensemble_model_version` at `scripts/training/run_phase1c_volatility.py:564`.
- Autoresearch direction prepare extracts only `model_version` and `model_registry_name`: `scripts/autotuner/direction/prepare.py:161-162`.
- Autoresearch volatility prepare extracts only `model_version` and `model_registry_name`: `scripts/autotuner/volatility/prepare.py:130-131`.
- Autoresearch composite patching builds a version tag from `model_registry_name:model_version`: `services/autoresearch-agent/src/core/config_promoter.py:514-517`.
- The central model-version helper also requires `model_registry_name` and `model_version`: `services/autoresearch-agent/src/core/config_promoter.py:629-643`.
- Ensemble-trainer's admin tuning path explicitly prefers ensemble versions: `services/ml/ensemble-trainer/src/api/admin_tuning.py:1445-1457`.
- Ensemble-trainer patches the composite with the selected direction and volatility version tags at `services/ml/ensemble-trainer/src/api/admin_tuning.py:1495-1497`.

Impact:

For stacking runs, autoresearch can update the production composite with a base model registry/version while the full ML stack's canonical admin tuning flow would use the ensemble registry/version. This can produce production composites that point at artifacts inconsistent with inference-service loading expectations and with the validated E2E path.

Recommendation:

- Propagate `ensemble_model_version` from direction and volatility prepare outputs.
- Derive the ensemble registry name when stacking is enabled, matching ensemble-trainer's naming convention.
- Change `ConfigPromoter` to prefer ensemble version tags when present and fall back to base model tags only for non-stacking runs.
- Add regression tests for stacked and non-stacked promotion payloads.

### 3. High - RL GPU delegation omits required rl-trainer service-token auth

The rl-trainer internal training API requires a bearer service token, but the autoresearch RL GPU delegation code does not consistently send one.

Evidence:

- `rl-trainer` protects the train router with `require_service_token`: `services/ml/rl-trainer/src/api/train.py:144-147`.
- The dependency is implemented in `services/ml/rl-trainer/src/auth/dependencies.py:238`.
- Autoresearch compose provides `ML_ADMIN_TOKEN`: `compose/autoresearch.yml:44`.
- Autoresearch RL prepare has internal trainer calls for cancel/list/submit/status:
  - cancel active job URL: `scripts/autotuner/rl/prepare.py:52`
  - list jobs URL: `scripts/autotuner/rl/prepare.py:1328`
  - cancel stale job URL: `scripts/autotuner/rl/prepare.py:1340`
  - submit base URL: `scripts/autotuner/rl/prepare.py:1367`
  - cancel on polling timeout/failure: `scripts/autotuner/rl/prepare.py:1435`
- The only `Authorization` header occurrences in `scripts/autotuner/rl/prepare.py` are on later admin HPO calls at lines 1874 and 2052, not on the normal rl-trainer submit/status/list/cancel path.

Impact:

The normal GPU mode can fail with `401 Unauthorized` against `rl-trainer` and then fall back to local CPU execution depending on mode. That local path uses a different runtime and dependency profile from the GPU ML stack, so it weakens full-stack consistency and can hide service-auth problems.

Recommendation:

- Add a shared helper for rl-trainer service headers using `ML_ADMIN_TOKEN` or a dedicated `RL_TRAINER_SERVICE_TOKEN`.
- Use that helper for submit, status, list, and cancel calls.
- Treat `401`/`403` from rl-trainer as hard configuration failures in production modes instead of silently falling back to local CPU.
- Add tests that rl-trainer calls include `Authorization: Bearer ...`.

### 4. Medium - Preflight does not cover inference-service, admin-service, or NATS/model events

Autoresearch preflight covers training dependencies but not the full inference and control-plane dependencies exercised by full E2E validation.

Evidence:

- `compose/autoresearch.yml` provides `ADMIN_SERVICE_URL`: line 33.
- Current preflight targets include mlflow-service, data-ingest, ensemble-trainer, rl-trainer, feature-service, vdmc-indicator, and optional artifact store: `services/autoresearch-agent/src/core/service_preflight.py:69-97`.
- No `INFERENCE_SERVICE_URL` target is present in `compose/autoresearch.yml` or `service_preflight.py`.
- Inference-service exposes the routed API under `/api/v1`: `services/ml/inference-service/src/main.py:698-703`.
- The full E2E flow validates inference behavior after composite training, so inference-service readiness is part of the effective ML-stack contract.

Impact:

Autoresearch can start and pass preflight while inference-service, admin-service, or model-event dependencies are unavailable. This creates a gap between autoresearch "ready" state and the actual full-stack E2E readiness needed for promotion, reload, replay, and prediction checks.

Recommendation:

- Add `INFERENCE_SERVICE_URL` to autoresearch settings and compose.
- Add inference-service health to preflight, using `/api/v1/health` or the stack's canonical readiness endpoint.
- Add admin-service health when promotion or admin orchestration is enabled.
- Add a NATS/model-event check if autoresearch is expected to validate propagation from composite updates to serving reload behavior.
- Keep optional dependencies configurable, but make the production/full-stack profile strict.

### 5. Medium - Baked production replay helper does not match inference-service replay contract

The production training helper copied into the autoresearch workspace has replay logic that does not match the inference-service router mount or request schema.

Evidence:

- The autoresearch image copies `scripts/training/` into the workspace: `services/autoresearch-agent/Dockerfile:79`.
- The helper checks inference health under `/api/v1/health`: `scripts/training/run_production_training.py:915`.
- The replay POST uses `f"{inference_url}/replay/run"` without `/api/v1`: `scripts/training/run_production_training.py:923`.
- Inference-service mounts replay routes under `/api/v1`: `services/ml/inference-service/src/main.py:702`.
- The replay router path is `/replay/run`: `services/ml/inference-service/src/api/replay.py:179`.
- The replay request requires `sample_path`: `services/ml/inference-service/src/api/replay.py:126`.

Impact:

If operators use this helper from the autoresearch workspace, the replay gate can call the wrong URL and/or omit the required replay sample path. That produces inconsistent promotion evidence relative to inference-service's current deterministic replay contract.

Recommendation:

- Change the helper to call `/api/v1/replay/run`.
- Provide a valid `sample_path` under inference-service's allowed replay sample directory.
- Add a contract test that validates the helper payload against `ReplayRequest`.
- Consider replacing script-local replay construction with a small shared inference client to avoid future route drift.

### 6. Medium - Local RL fallback diverges from the GPU ML runtime

Autoresearch includes a local workspace fallback for RL that is not equivalent to the GPU `rl-trainer` image.

Evidence:

- Autoresearch workspace requirements rely on PyPI `stable-baselines3>=2.2.0`: `services/autoresearch-agent/requirements-workspace.txt:37`.
- The same file notes that PyPI torch installs CPU-only on aarch64: `services/autoresearch-agent/requirements-workspace.txt:35-36`.
- The GPU rl-trainer image is based on NVIDIA PyTorch: `services/ml/rl-trainer/Dockerfile:165`.

Impact:

When the service path fails and fallback is allowed, autoresearch can produce RL training results from a different runtime than the stack being validated. That is acceptable for local development, but it should not be considered equivalent to full-stack GPU validation.

Recommendation:

- Keep local fallback explicitly development-only.
- In production/full-stack modes, fail closed when rl-trainer auth, health, or submission fails.
- Include the execution backend in RL metrics and promotion evidence.

## Recommended Fix Order

1. Align feature-library versions in autoresearch templates, prepare fallbacks, and structured HPO search spaces.
2. Fix stacked model promotion by propagating and preferring `ensemble_model_version`.
3. Add service-token auth to all rl-trainer calls and fail closed on auth errors in production modes.
4. Extend preflight to inference-service and admin-service, then decide whether NATS/model-event readiness is required for the strict profile.
5. Fix the production replay helper URL and payload contract.
6. Restrict local RL fallback semantics to development evidence only.

## Suggested Regression Tests

- Autoresearch-generated default direction config uses feature library `2.3.0`.
- Autoresearch-generated default volatility config uses feature library `2.3.0`.
- Structured HPO can produce `feature_library_version=2.3.0`.
- Stacking promotion payload prefers `ensemble_model_version` and ensemble registry names.
- Non-stacking promotion payload still uses base `model_version`.
- RL trainer submit/status/list/cancel calls include bearer auth.
- `401`/`403` from rl-trainer does not fall back to local CPU in production/full-stack mode.
- Preflight fails strict mode when inference-service is unavailable.
- Production replay helper posts to `/api/v1/replay/run` with a valid `sample_path`.

## Conclusion

The autoresearch agent is close to stack-consistent at the deployment level, but it still has several stale internal contracts. The most important fixes are to align feature-library versioning with `2.3.0`, match ensemble-trainer's ensemble-version promotion semantics, and authenticate all rl-trainer service calls. Those changes would remove the main ways autoresearch can produce artifacts or readiness evidence that differ from the full ML stack.
