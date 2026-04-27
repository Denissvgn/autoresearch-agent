# Autoresearch Agent

Autonomous ML model tuning service. An LLM agent iteratively runs training experiments, adjusts hyperparameters, and promotes winning configurations — without human intervention.

## How It Works

```
UI (React) → FastAPI backend → LLM agent loop (Anthropic SDK)
                                  ↓
                            Tool-use calls:
                              bash → prepare.py → real ML services
                              read_file / write_file → edit configs
                                  ↓
                            Iteration auto-detected from stdout
                            + server-owned attempt snapshots
                                  ↓
                            Results → SQLite + WebSocket → UI
```

The agent gets 5 sandboxed tools (`bash`, `read_file`, `write_file`, `glob`, `grep`) and a directive prompt with exact commands. It runs `setup.py` to create a workspace, reads the tuning strategy from the model-specific SKILL.md, then loops: edit `train.yaml` → run `prepare.py` → check metrics → keep or revert. The orchestrator auto-detects completed iterations by parsing `prepare.py` stdout — no reliance on the LLM to report results.

Each session now starts from an immutable `research_session_manifest.v1` written
to the run workspace and persisted in SQLite. Each training attempt records an
`autoresearch_iteration_attempt.v1` snapshot with the command/API request,
config hash, environment metadata, and artifact/provenance hashes when present;
failed, timed-out, and pruned attempts remain visible even when no metric is
produced.

M8 also makes the server the operational source of truth for autonomous
direction research: sessions persist `autoresearch_phase_state.v1`, structured
HPO plans, cross-service consistency reports, and reconstructable
`autoresearch_state.v1` summaries for API/UI clients.

## Quick Start

### 1. Configure environment

Copy and edit the `.env` file:

```bash
cd services/autoresearch-agent
cp .env.example .env   # or edit .env directly
```

Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_BASE_URL` | API endpoint (Anthropic or proxy) | `https://api.anthropic.com` |
| `ANTHROPIC_AUTH_TOKEN` | API key | `sk-ant-...` |
| `ANTHROPIC_MODEL` | Model name | `claude-sonnet-4-20250514` or `qwen3.5-plus` |

### 2. Build and run

```bash
# From project root:
docker compose -f compose/base.yml -f compose/infra.yml -f compose/ml.yml -f compose/autoresearch.yml build autoresearch-agent
docker compose -f compose/base.yml -f compose/infra.yml -f compose/ml.yml -f compose/autoresearch.yml up -d autoresearch-agent
```

The service starts on **port 8030**. The ML platform services must already be running on the same Docker network (`traid-network`).

### 3. Open the UI

Navigate to **http://localhost:8030** in your browser.

---

## Using the UI

### Dashboard

The landing page shows:
- **Status bar** — active session count and server settings
- **Active Sessions** — cards for currently running research with live iteration count, best metric, and cost
- **Recent Sessions** — table of past sessions with status badges

### Starting a New Research Session

Click **"New Research"** in the navigation bar (or the button on the Dashboard).

Fill in the form:

| Field | Required | Description |
|-------|----------|-------------|
| **Instrument** | Yes | Trading pair to tune for (e.g. `DOGE_USDT`, `BTC_USDT`). Dropdown shows available instruments from existing configs. |
| **Timeframe** | Yes | Candle timeframe: `5m`, `15m`, `1h`, or `4h` |
| **Model Type** | Yes | Which model to tune: `direction` (price direction prediction), `volatility` (breakout detection), or `rl` (PPO trading agent) |
| **Tag** | Optional | Label for this session (e.g. `doge-apr01`, `btc-horizon-sweep`) |
| **Focus Hint** | Optional | Free-text guidance for the agent (e.g. "try increasing deadzone_width" or "sweep learning rates") |
| **Max Iterations** | Optional | Cap on training iterations (default: 30, range: 1–100) |
| **Max Budget ($)** | Optional | Spending limit for LLM API calls (default: $10, range: $1–$100) |
| **Quick Mode** | Optional | Checkbox — uses reduced dataset and fewer folds for faster but less precise results |

Click **"Start Research"**. You'll be redirected to the session detail page.

### Monitoring a Running Session

The detail page shows real-time progress:

- **Stats row** — current iteration number, best metric value, best iteration number, cumulative API cost, mode (quick/standard)
- **State** tab — current phase, next action, phase table, top candidates, failed/pruned configs, HPO study IDs, budget usage, rollback target, and smoke status
- **Metrics Chart** tab — line chart of the primary metric across iterations. Green dots = all quality gates passed; red dots = gates failed
- **Iterations** tab — table with columns: iteration number, metric name, value, gates (✓/✗), decision (keep/discard), training time, attempt snapshots, artifact hashes, and consistency reports
- **Agent Log** tab — raw LLM conversation transcript (tool calls and responses)

**Controls while running:**
- **Pause** — temporarily halts the agent loop (resumes from where it left off)
- **Resume** — continues a paused session
- **Stop** — permanently ends the session

### Promoting a Config

After a session completes (or is stopped), if it has a best iteration:

1. Click **"Promote Config"** on the session detail page
2. A modal opens showing:
   - Target path where the config will be written (e.g. `configs/instrument_configs/DOGE_USDT_15m.yaml`)
   - The winning iteration number
   - Side-by-side diff: current production config vs. proposed new config
3. Review the diff, then click **"Confirm Promotion"**

This writes the best config to `configs/instrument_configs/` so future training and inference use it as the new baseline.

### History

The **History** page shows:
- **Past Sessions** — all completed/stopped/failed sessions with metrics
- **Config Promotions** — log of every config promotion with timestamp, source session, and target path

---

## Architecture

```
services/autoresearch-agent/
├── server/                     # FastAPI backend
│   ├── main.py                 # App entry, lifespan, CORS, static files
│   ├── config.py               # Settings (env vars → pydantic)
│   ├── core/
│   │   ├── orchestrator.py     # LLM agent tool-use loop
│   │   ├── session_manager.py  # asyncio task lifecycle
│   │   ├── results_store.py    # SQLite persistence (aiosqlite)
│   │   ├── research_phase_plan.py # Direction phase state derivation
│   │   ├── structured_hpo.py   # Bounded HPO plan metadata
│   │   ├── consistency_validator.py # Cross-service candidate gate reports
│   │   ├── research_state.py   # API/UI session-state summaries
│   │   ├── experiment_parser.py# Parse prepare.py output + ITERATION_RESULT markers
│   │   └── config_promoter.py  # Write winning configs to production path
│   ├── api/
│   │   ├── research.py         # Session CRUD + control endpoints
│   │   ├── results.py          # Iterations, best, agent log
│   │   └── promotion.py        # Preview + confirm promotion
│   └── ws/
│       └── events.py           # WebSocket broadcaster
├── ui/                         # React 18 + TypeScript + Vite + Tailwind
│   └── src/
│       ├── pages/              # Dashboard, NewResearch, ResearchDetail, History
│       ├── components/         # MetricsChart, IterationsTable, AgentLog, etc.
│       ├── hooks/              # React Query hooks with auto-refetch
│       └── api/client.ts       # API client + TypeScript types
├── Dockerfile                  # 3-stage build (UI → Python deps → runtime)
├── CLAUDE.md                   # Agent system prompt ("Act, Don't Explore")
├── pyproject.toml              # Server Python dependencies
└── .env                        # API credentials
```

### Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/research/start` | Start a new research session |
| `GET` | `/api/research` | List all sessions (filterable) |
| `GET` | `/api/research/{id}` | Get session details |
| `POST` | `/api/research/{id}/stop` | Stop a running session |
| `POST` | `/api/research/{id}/pause` | Pause a running session |
| `POST` | `/api/research/{id}/resume` | Resume a paused session |
| `DELETE` | `/api/research/{id}` | Delete a session (not while running) |
| `GET` | `/api/research/{id}/iterations` | Get all iterations |
| `GET` | `/api/research/{id}/hpo-studies` | Get structured HPO plans/results |
| `GET` | `/api/research/{id}/state` | Get reconstructable operational session state |
| `GET` | `/api/research/{id}/best` | Get best iteration |
| `GET` | `/api/research/{id}/agent-log` | Get agent conversation log |
| `POST` | `/api/research/{id}/promote/preview` | Preview config promotion |
| `POST` | `/api/research/{id}/promote/confirm` | Confirm and write promoted config |
| `GET` | `/api/promotions` | List all promotions |
| `GET` | `/api/instruments` | Available instruments |
| `GET` | `/api/models` | Available model types |
| `GET` | `/api/status` | Server status and settings |
| `WS` | `/ws` | WebSocket for real-time events |

### Docker Compose

```yaml
# compose/autoresearch.yml
services:
  autoresearch-agent:
    container_name: traid_autoresearch_agent
    ports: ["8030:8000"]
    networks: [traid-network]
    volumes:
      - autoresearch_runs:/app/workspace/runs    # Experiment artifacts
      - autoresearch_db:/app/workspace/db         # SQLite database
      - ../configs:/host/configs                  # Config promotion target
    deploy:
      resources:
        limits: { memory: 2G, cpus: "2.0" }
```

### Required Platform Services

The agent calls these services over Docker DNS during training:

| Service | URL (inside Docker) | Purpose |
|---------|---------------------|---------|
| Data Ingest | `data-ingest:8000` | Market OHLCV data |
| Feature Service | `feature-service:8000` | Technical indicators |
| Ensemble Trainer | `ensemble-trainer:8000` | Walk-forward model training |
| RL Trainer | `rl-trainer:8000` | PPO agent training |
| MLflow | `mlflow:5000` | Experiment tracking |
| MLflow Service | `mlflow-service:8000` | Promotion/composite API |
| Admin Service | `admin-service:8000` | Admin API discovery/status |
| MinIO | `minio:9000` | Model artifact storage |

### Runtime State

The compose stack persists autoresearch state across restarts:

| Path | Volume/Mount | Purpose |
|------|--------------|---------|
| `/app/workspace/runs` | `autoresearch_runs` | Run workspaces, manifests, attempt snapshots, logs |
| `/app/workspace/db` | `autoresearch_db` | SQLite research/iteration/promotion database |
| `/host/configs` | `../configs` bind mount | Development config promotion target |

`GET /api/status` exposes the Docker DNS service URLs, browser MLflow URL,
and persistence paths currently used by the server. The same URL set is copied
into each session manifest for reproducibility.

### Supported LLM Backends

Any API compatible with the Anthropic Messages format:

| Backend | `ANTHROPIC_BASE_URL` | `ANTHROPIC_MODEL` |
|---------|---------------------|-------------------|
| Anthropic | `https://api.anthropic.com` | `claude-sonnet-4-20250514` |
| DashScope proxy | `https://coding-intl.dashscope.aliyuncs.com/apps/anthropic` | `qwen3.5-plus` |
| Any Anthropic-compatible proxy | Custom URL | Model name supported by proxy |

### Resource Defaults

| Setting | Default | Env Variable |
|---------|---------|-------------|
| Max iterations per session | 30 | `MAX_ITERATIONS` |
| Max API budget per session | $10.00 | `MAX_BUDGET_USD` |
| Experiment timeout | 2 hours | `EXPERIMENT_TIMEOUT_S` |
| Max concurrent sessions | 2 | `MAX_CONCURRENT_SESSIONS` |
| Quick mode default | off | `DEFAULT_QUICK_MODE` |
