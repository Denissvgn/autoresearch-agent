# =================================================================
# Multi-stage build for the standalone autoresearch-agent container
#
# Stage 1 (ui-builder): Build the React/Vite frontend
# Stage 2 (python-builder): Install server + workspace Python deps
# Stage 3 (runtime): Minimal production image
#
# Build context: repository root of this project.
# Multi-Architecture Support: linux/amd64, linux/arm64
#
# NOTE: this image is standalone — it bundles the agent service, the
# UI, and a generic workspace Python venv. Domain skill assets
# (experiment scripts, training harnesses, production configs) are NOT
# baked in; install them as skills/ packages or mount them into
# /app/workspace when running against an external stack.
# =================================================================

# -----------------------------------------------------------------
# Stage 1: Build React UI
# -----------------------------------------------------------------
FROM node:20-alpine AS ui-builder

WORKDIR /app/ui

# Copy UI source and install deps
COPY ui/package.json ui/package-lock.json* ./
RUN npm ci --ignore-scripts

COPY ui/ ./
RUN npx vite build

# -----------------------------------------------------------------
# Stage 2: Python builder — install server deps + workspace venv
# -----------------------------------------------------------------
FROM python:3.12-slim AS python-builder

ARG TARGETARCH

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    build-essential \
    git \
    curl \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
RUN poetry self add poetry-plugin-export

WORKDIR /app

# --- Server venv (FastAPI + Anthropic SDK) ---
COPY pyproject.toml poetry.lock* ./

ENV POETRY_HTTP_TIMEOUT=300
ENV PIP_DEFAULT_TIMEOUT=300

RUN poetry export --without dev --format requirements.txt --output server-requirements.txt --without-hashes && \
    python -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir --timeout 300 -r server-requirements.txt

# --- Workspace venv (ML deps for prepare.py) ---
COPY requirements-workspace.txt /tmp/requirements-workspace.txt
RUN python -m venv /app/workspace/.venv && \
    /app/workspace/.venv/bin/pip install --no-cache-dir --timeout 300 --retries 5 \
    -r /tmp/requirements-workspace.txt

# --- Workspace skeleton ---

# CLAUDE.md — agent workspace context
COPY CLAUDE.md /app/workspace/CLAUDE.md

# -----------------------------------------------------------------
# Stage 3: Production runtime
# -----------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Runtime system deps (curl for healthcheck, libgomp for lightgbm, bubblewrap for sandbox)
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libgomp1 \
    curl \
    ca-certificates \
    grep \
    bubblewrap \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Non-root user. UID/GID 1000 matches a typical host user that owns
# bind-mounted workspace content, so promotion can write atomic
# temp/rollback files there. Overridable via build args if a deploy
# needs a different host UID.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -g ${APP_GID} appuser && useradd -u ${APP_UID} -g appuser -m appuser

# Copy server venv from builder
COPY --from=python-builder /app/.venv /app/.venv

# Copy workspace (including .venv) from builder
COPY --from=python-builder --chown=appuser:appuser /app/workspace /app/workspace

# Copy built UI from ui-builder
COPY --from=ui-builder /app/ui/dist /app/ui/dist

# Copy server source code
COPY --chown=appuser:appuser src/ /app/src/

# Copy bundled skill packages (prompt-engineering, code-refactor, db-config-tuning)
COPY --chown=appuser:appuser skills/ /app/skills/

# Create runtime directories
RUN mkdir -p /app/workspace/runs /app/workspace/db && \
    chown -R appuser:appuser /app/workspace/runs /app/workspace/db

# Entrypoint script (fixes volume ownership, then drops to appuser)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /app

# Environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

# Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop"]
