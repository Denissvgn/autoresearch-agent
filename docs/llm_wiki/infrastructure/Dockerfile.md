# Dockerfile

**Path:** `Dockerfile`
**Base Image(s):** `node:20-alpine`, `python:3.12-slim`, `python:3.12-slim`

## Build Stages

| Stage | Base Image |
|-------|-----------|
| `ui-builder` | `node:20-alpine` |
| `python-builder` | `python:3.12-slim` |
| `runtime` | `python:3.12-slim` |

## Exposed Ports

- `8000`

## Build Arguments

| Argument | Default |
|----------|---------|
| `TARGETARCH` | — |

## Environment Variables

| Variable | Default |
|----------|---------|
| `PATH` | `/root/.local/bin:$PATH` |
| `POETRY_HTTP_TIMEOUT` | `300` |
| `PIP_DEFAULT_TIMEOUT` | `300` |
| `PATH` | `/app/.venv/bin:$PATH` |
| `PYTHONPATH` | `/app:/` |
| `PYTHONUNBUFFERED` | `1` |
| `PYTHONDONTWRITEBYTECODE` | `1` |

**Working Directory:** `/app`

## Entry Point

**ENTRYPOINT:** `["/app/entrypoint.sh"]`
**CMD:** `["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop"]`

## File Copies

| Instruction | Source | Destination | From Stage |
|-------------|--------|-------------|------------|
| `COPY` | `services/autoresearch-agent/ui/package.json`, `services/autoresearch-agent/ui/package-lock.json*` | `./` | — |
| `COPY` | `services/autoresearch-agent/ui/` | `./` | — |
| `COPY` | `libs/vdmc_core` | `/libs/vdmc_core` | — |
| `COPY` | `libs/config` | `/libs/config` | — |
| `COPY` | `libs/data_clients` | `/libs/data_clients` | — |
| `COPY` | `libs/feature_engineering` | `/libs/feature_engineering` | — |
| `COPY` | `libs/identity_client` | `/libs/identity_client` | — |
| `COPY` | `libs/observability` | `/libs/observability` | — |
| `COPY` | `libs/ml_artifacts` | `/libs/ml_artifacts` | — |
| `COPY` | `libs/resilience` | `/libs/resilience` | — |
| `COPY` | `libs/__init__.py` | `/libs/__init__.py` | — |
| `COPY` | `traid_training_sdk` | `/traid_training_sdk` | — |
| `COPY` | `services/autoresearch-agent/pyproject.toml` | `./` | — |
| `COPY` | `services/autoresearch-agent/poetry.lock*` | `./` | — |
| `COPY` | `services/autoresearch-agent/requirements-workspace.txt` | `/tmp/requirements-workspace.txt` | — |
| `COPY` | `scripts/autotuner/` | `/app/workspace/scripts/autotuner/` | — |
| `COPY` | `scripts/training/` | `/app/workspace/scripts/training/` | — |
| `COPY` | `services/ml/ensemble-trainer/src/` | `/app/workspace/services/ml/ensemble-trainer/src/` | — |
| `COPY` | `services/ml/rl-trainer/src/` | `/app/workspace/services/ml/rl-trainer/src/` | — |
| `COPY` | `.github/skills/direction-autotuner/` | `/app/workspace/.github/skills/direction-autotuner/` | — |
| `COPY` | `.github/skills/volatility-autotuner/` | `/app/workspace/.github/skills/volatility-autotuner/` | — |
| `COPY` | `.github/skills/rl-autotuner/` | `/app/workspace/.github/skills/rl-autotuner/` | — |
| `COPY` | `configs/` | `/app/workspace/configs/` | — |
| `COPY` | `reports/direction-tuning/promotion/` | `/app/workspace/reports/direction-tuning/promotion/` | — |
| `COPY` | `libs/` | `/app/workspace/libs/` | — |
| `COPY` | `traid_training_sdk/` | `/app/workspace/traid_training_sdk/` | — |
| `COPY` | `services/autoresearch-agent/CLAUDE.md` | `/app/workspace/CLAUDE.md` | — |
| `COPY` | `/app/.venv` | `/app/.venv` | `python-builder` |
| `COPY` | `/libs` | `/libs` | `python-builder` |
| `COPY` | `/traid_training_sdk` | `/traid_training_sdk` | `python-builder` |
| `COPY` | `/app/workspace` | `/app/workspace` | `python-builder` |
| `COPY` | `/app/ui/dist` | `/app/ui/dist` | `ui-builder` |
| `COPY` | `services/__init__.py` | `/app/services/__init__.py` | — |
| `COPY` | `services/shared` | `/app/services/shared` | — |
| `COPY` | `services/autoresearch-agent/src/` | `/app/src/` | — |
| `COPY` | `services/autoresearch-agent/entrypoint.sh` | `/app/entrypoint.sh` | — |

**Healthcheck:** `--interval=30s --timeout=10s --retries=3 --start-period=15s      CMD curl -sf http://localhost:8000/health || exit 1`
