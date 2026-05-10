# =================================================================
# Multi-stage build for autoresearch-agent container
#
# Stage 1 (ui-builder): Build the React/Vite frontend
# Stage 2 (python-builder): Install server + workspace Python deps
# Stage 3 (runtime): Minimal production image
#
# Multi-Architecture Support: linux/amd64, linux/arm64
# =================================================================

# -----------------------------------------------------------------
# Stage 1: Build React UI
# -----------------------------------------------------------------
FROM node:20-alpine AS ui-builder

WORKDIR /app/ui

# Copy UI source and install deps
COPY services/autoresearch-agent/ui/package.json services/autoresearch-agent/ui/package-lock.json* ./
RUN npm ci --ignore-scripts

COPY services/autoresearch-agent/ui/ ./
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
COPY libs/vdmc_core /libs/vdmc_core
COPY libs/config /libs/config
COPY libs/data_clients /libs/data_clients
COPY libs/feature_engineering /libs/feature_engineering
COPY libs/identity_client /libs/identity_client
COPY libs/observability /libs/observability
COPY libs/ml_artifacts /libs/ml_artifacts
COPY libs/resilience /libs/resilience
COPY libs/__init__.py /libs/__init__.py
COPY traid_training_sdk /traid_training_sdk
COPY services/autoresearch-agent/pyproject.toml ./
COPY services/autoresearch-agent/poetry.lock* ./

ENV POETRY_HTTP_TIMEOUT=300
ENV PIP_DEFAULT_TIMEOUT=300

RUN poetry export --without dev --format requirements.txt --output server-requirements.txt --without-hashes && \
    python -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir --timeout 300 -r server-requirements.txt

# --- Workspace venv (ML deps for prepare.py) ---
COPY services/autoresearch-agent/requirements-workspace.txt /tmp/requirements-workspace.txt
RUN python -m venv /app/workspace/.venv && \
    /app/workspace/.venv/bin/pip install --no-cache-dir --timeout 300 --retries 5 \
    -r /tmp/requirements-workspace.txt

# --- Copy workspace content (baked into image) ---
# Autotuner scripts (prepare.py, setup.py, promote.py, train.yaml templates)
COPY scripts/autotuner/ /app/workspace/scripts/autotuner/

# Training scripts invoked by prepare.py
COPY scripts/training/ /app/workspace/scripts/training/

# Ensemble-trainer source (required by training scripts for DirectionModelConfig, etc.)
COPY services/ml/ensemble-trainer/src/ /app/workspace/services/ml/ensemble-trainer/src/

# RL-trainer source (required by RL training scripts for RLTrainingConfig, etc.)
COPY services/ml/rl-trainer/src/ /app/workspace/services/ml/rl-trainer/src/

# SKILL.md files the agent follows
COPY .github/skills/direction-autotuner/ /app/workspace/.github/skills/direction-autotuner/
COPY .github/skills/volatility-autotuner/ /app/workspace/.github/skills/volatility-autotuner/
COPY .github/skills/rl-autotuner/ /app/workspace/.github/skills/rl-autotuner/

# Production configs (baseline for promotion)
COPY configs/ /app/workspace/configs/

# Promotion gate bundles consumed by ConfigPromoter.
COPY reports/direction-tuning/promotion/ /app/workspace/reports/direction-tuning/promotion/

# Shared Python libraries used by training scripts
COPY libs/ /app/workspace/libs/

# Training SDK
COPY traid_training_sdk/ /app/workspace/traid_training_sdk/

# Install libs and SDK into the workspace venv (editable)
RUN cd /app/workspace && \
    .venv/bin/pip install --no-cache-dir \
    -e ./libs/vdmc_core \
    -e ./libs/config \
    -e ./libs/data_clients \
    -e ./libs/feature_engineering \
    -e ./libs/identity_client \
    -e ./libs/observability \
    -e ./libs/ml_artifacts \
    -e ./libs/resilience \
    -e ./traid_training_sdk

# CLAUDE.md — agent workspace context
COPY services/autoresearch-agent/CLAUDE.md /app/workspace/CLAUDE.md

# -----------------------------------------------------------------
# Stage 3: Production runtime
# -----------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Runtime system deps (curl for healthcheck, libgomp for lightgbm)
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libgomp1 \
    curl \
    ca-certificates \
    grep \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Non-root user aligned with the ML services.
RUN groupadd -g 1001 appuser && useradd -u 1001 -g appuser -m appuser

# Copy server venv from builder
COPY --from=python-builder /app/.venv /app/.venv

# Copy editable path dependencies used by the server venv.
COPY --from=python-builder --chown=appuser:appuser /libs /libs
COPY --from=python-builder --chown=appuser:appuser /traid_training_sdk /traid_training_sdk

# Copy workspace (including .venv) from builder
COPY --from=python-builder --chown=appuser:appuser /app/workspace /app/workspace

# Copy built UI from ui-builder
COPY --from=ui-builder /app/ui/dist /app/ui/dist

# Copy shared service helpers and server source code
COPY --chown=appuser:appuser services/__init__.py /app/services/__init__.py
COPY --chown=appuser:appuser services/shared /app/services/shared
COPY --chown=appuser:appuser services/autoresearch-agent/src/ /app/src/

# Create runtime directories
RUN mkdir -p /app/workspace/runs /app/workspace/db && \
    chown -R appuser:appuser /app/workspace/runs /app/workspace/db

# Entrypoint script (fixes volume ownership, then drops to appuser)
COPY services/autoresearch-agent/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /app

# Environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:/" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

# Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop"]
