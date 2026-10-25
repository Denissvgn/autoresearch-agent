# Dockerfile

**Path:** `Dockerfile`
**Base Image(s):** `node:24-alpine`, `python:3.12-slim`, `python:3.12-slim`

## Build Stages

| Stage | Base Image |
|-------|-----------|
| `ui-builder` | `node:24-alpine` |
| `python-builder` | `python:3.12-slim` |
| `runtime` | `python:3.12-slim` |

## Exposed Ports

- `8000`

## Build Arguments

| Argument | Default |
|----------|---------|
| `TARGETARCH` | — |
| `APP_UID` | `1000` |
| `APP_GID` | `1000` |

## Environment Variables

| Variable | Default |
|----------|---------|
| `PATH` | `/root/.local/bin:$PATH` |
| `POETRY_HTTP_TIMEOUT` | `300` |
| `PIP_DEFAULT_TIMEOUT` | `300` |
| `PATH` | `/app/.venv/bin:$PATH` |
| `PYTHONPATH` | `/app` |
| `PYTHONUNBUFFERED` | `1` |
| `PYTHONDONTWRITEBYTECODE` | `1` |

**Working Directory:** `/app`

## Entry Point

**ENTRYPOINT:** `["/app/entrypoint.sh"]`
**CMD:** `["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop"]`

## File Copies

| Instruction | Source | Destination | From Stage |
|-------------|--------|-------------|------------|
| `COPY` | `ui/package.json`, `ui/package-lock.json*` | `./` | — |
| `COPY` | `ui/` | `./` | — |
| `COPY` | `pyproject.toml`, `poetry.lock*` | `./` | — |
| `COPY` | `requirements-workspace.txt` | `/tmp/requirements-workspace.txt` | — |
| `COPY` | `CLAUDE.md` | `/app/workspace/CLAUDE.md` | — |
| `COPY` | `/app/.venv` | `/app/.venv` | `python-builder` |
| `COPY` | `/app/workspace` | `/app/workspace` | `python-builder` |
| `COPY` | `/app/ui/dist` | `/app/ui/dist` | `ui-builder` |
| `COPY` | `src/` | `/app/src/` | — |
| `COPY` | `skills/` | `/app/skills/` | — |
| `COPY` | `entrypoint.sh` | `/app/entrypoint.sh` | — |

## Unsupported Copied Sources

Shell extraction is not yet supported; these copied deployment scripts are reported as unsupported-source coverage notices.

| COPY Source | Resolved Source | Language |
|-------------|-----------------|----------|
| `entrypoint.sh` | `entrypoint.sh` | Shell |

**Healthcheck:** `--interval=30s --timeout=10s --retries=3 --start-period=15s      CMD curl -sf http://localhost:8000/health || exit 1`

## Notes

_Add reviewed operational context here; generated sections are replaced from source observations._
