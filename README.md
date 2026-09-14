# Autoresearch Agent

Universal autonomous research agent. An LLM agent iteratively runs experiments,
adjusts parameters, and promotes winning configurations — for any domain you
can describe as a **skill** (a manifest + primer + experiment command).

The service is domain-neutral: every domain-specific decision — the system
prompt, allowed commands, output format, phase plan, preflight checks, metric
schema, and promotion target — is declared by an installed skill package
(`skills/<id>/SKILL.yaml`). Adding a domain means adding a directory, not
changing orchestrator or UI code. The bundled `prompt-engineering` skill is
the reference example.

## How It Works

```
UI (React) → FastAPI backend → LLM agent loop (Anthropic / OpenAI)
                                  ↓
                        Skill manifest (SKILL.yaml):
                          prompt · commands · parser · phases
                                  ↓
                            Tool-use calls:
                              bash → the skill's experiment command
                              read_file / write_file → edit configs
                                  ↓
                            Iteration auto-detected from stdout
                            + server-owned attempt snapshots
                                  ↓
                            Results → SQLite + WebSocket → UI
```

The agent gets 5 sandboxed tools (`bash`, `read_file`, `write_file`, `glob`,
`grep`) and a directive prompt assembled from the skill's manifest. The
orchestrator auto-detects completed iterations by parsing the skill's declared
output format — no reliance on the LLM to report results. Every training
attempt records an immutable snapshot (command, config hash, artifact
provenance); sessions persist phase state, consistency reports, and
reconstructable operational summaries.

Each session starts from an immutable `research_session_manifest.v2` written
to the run workspace and persisted in SQLite.

## Quick Start

### 1. Configure environment

Copy the tracked sanitized template, then edit the local `.env` file:

```bash
cp .env.example .env
```

`.env` is intentionally ignored by git. Commit changes to `.env.example` only
when adding non-secret defaults or new variable names.

Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_BASE_URL` | API endpoint for Anthropic or a compatible proxy | provider URL |
| `ANTHROPIC_AUTH_TOKEN` | LLM provider token | local secret, never committed |
| `ANTHROPIC_MODEL` | Model name supported by that backend | provider model name |
| `AUTORESEARCH_API_TOKEN` | Bearer token for operator/UI API calls | locally generated random value |

Skills may declare `llm.provider: openai`; set `OPENAI_BASE_URL` /
`OPENAI_API_KEY` for those. Optional controls — bind host/port, CORS origins,
OAuth2 token introspection, Prometheus scrape auth, optional MLflow tracking,
preflight flags, iteration limits, and budget limits — are documented in
`.env.example`. `AUTORESEARCH_PROMETHEUS_TOKEN` is required in production;
without it the `/metrics` endpoint is disabled.

Autoresearch-agent is intentionally deployed as a single-instance SQLite
control-plane service. Keep Uvicorn at one worker and do not scale the
container above one replica unless a Postgres backend
(`AUTORESEARCH_DATABASE_URL`) is configured.

### 2. Build and run

With Docker (build context = this repository's root):

```bash
docker build -t autoresearch-agent .
docker run --rm -p 8030:8000 --env-file .env autoresearch-agent
```

Or locally with Poetry:

```bash
poetry install --no-interaction --no-root
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8030
```

The Docker build consumes the tracked UI source, `package.json`, and
`package-lock.json`. The `.dockerignore` excludes `.env`, `ui/node_modules/`,
`ui/dist/`, and coverage outputs while keeping `.env.example`, package
manifests, and source files available to Docker builds.

The service starts on **port 8030**. Skills that declare `preflight:` HTTP
checks in their manifest require the target services to be reachable from the
container.

### 3. Open the UI

Navigate to **http://localhost:8030** in your browser.

### Try it with no API keys (demo mode)

```bash
docker run --rm -p 8030:8000 \
  -e AUTORESEARCH_DEMO=true \
  -e AUTORESEARCH_API_TOKEN=demo-token \
  autoresearch-agent
```

`AUTORESEARCH_DEMO=true` routes every LLM call to the zero-credential
`MockProvider` (a scripted edit-run-keep loop, $0 cost) so the whole flow —
session start, governed commands, `ITERATION_RESULT` parsing, iterations,
charts, leaderboard, promotion preview — runs with no LLM keys. The provider
router refuses the mock in production (fail-closed).

### Installed skills

| Skill | Category | Scorer | Promotion |
|-------|----------|--------|-----------|
| `prompt-engineering` | generative | remote scorer → OpenAI judge → offline fallback | `registry_api` (webhook delivery) |
| `code-refactor` | generative | offline: syntax + lint + JSONL test ledger | `file_path` |
| `db-config-tuning` | optimization | offline: deterministic TPS/latency bench model | `file_path` |

A skill is a directory under `skills/` (`SKILL.yaml` + `SKILL.md` +
`bootstrap.py` + eval CLI); add one and `POST /api/v1/skills/reload` — no
orchestrator or UI code changes. The **Leaderboard** page ranks every scored
session per skill by the skill's declared metric direction
(`GET /api/v1/skills/{id}/leaderboard`).

Skills declaring `promotion_target.kind: webhook` (or `registry_api` with an
endpoint) deliver the promoted winner to their endpoint with an
`Idempotency-Key` and retries, keeping a local provenance copy under
`<workspace>/promotions/`; delivery failure fails the confirm (fail-closed).
See `examples/prompt-registry/` for a runnable receiver.

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
| **Skill** | Yes | The installed skill to run (from `GET /skills`) |
| **Skill parameters** | Varies | Rendered from the skill's `ui.form_fields` (e.g. an eval-set path) |
| **Subject / Variant** | Yes* | The entity and variant this research operates on (*when the skill declares no form fields) |
| **Tag** | Optional | Label for this session (e.g. `sweep-lr`) |
| **Focus Hint** | Optional | Free-text guidance for the agent (e.g. "improve robustness without inflating cost") |
| **Max Iterations** | Optional | Cap on experiment iterations (default: 30, range: 1–100) |
| **Max Budget ($)** | Optional | Spending limit for LLM API calls (default: $10, range: $1–$100) |
| **Quick Mode** | Optional | Checkbox — reduced sample sizes for faster but less precise results |

Click **"Start Research"**. You'll be redirected to the session detail page.

### Monitoring a Running Session

The detail page shows real-time progress:

- **Stats row** — current iteration number, best metric value, best iteration number, cumulative API cost, mode (quick/standard)
- **State** tab — current phase, next action, phase table, top candidates, failed/pruned attempts, budget usage, and rollback target
- **Metrics Chart** tab — line chart of the primary metric across iterations, with the skill's declared series as overlays. Green dots = all quality gates passed; red dots = gates failed
- **Iterations** tab — per-iteration metrics (columns from the skill's `metric_schema`), decisions (keep/discard), attempt snapshots, and consistency reports
- **Agent Log** tab — raw LLM conversation transcript (tool calls and responses)

**Controls while running:**
- **Pause** — temporarily halts the agent loop (resumes from where it left off)
- **Resume** — continues a paused session
- **Stop** — permanently ends the session

### Promoting a Result

After a session completes (or is stopped), if it has a best iteration:

1. Click **"Promote Config"** on the session detail page
2. A modal opens showing:
   - The promotion target declared by the skill (file path, or a registry API for supported kinds)
   - The winning iteration number
   - Side-by-side diff: current production config vs. proposed new config
3. Review the diff, then click **"Confirm Promotion"**

Development-scope promotion writes the winning config to the skill's declared
target path. Paper and canary scopes record auditable local decisions.
Production-scope promotion requires an HMAC-signed approval
(`AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER`); promotion targets the skill
declares that the local machinery cannot execute (e.g. `registry_api`)
**skip loudly** with an audit trail instead of pretending.

### History

The **History** page shows:
- **Past Sessions** — all completed/stopped/failed sessions with metrics
- **Config Promotions** — log of every promotion with timestamp, source session, and target path

---

## Skills

A skill is a directory under `skills/`:

```
skills/<skill-id>/
├── SKILL.yaml     # Manifest: llm, params, metrics, phases, command policy,
│                  #   output parser, preflight, promotion target, UI hints
├── SKILL.md       # Primer — the agent's domain instructions
├── bootstrap.py   # Optional: workspace initialization plugin
├── eval/          # Skill-owned experiment scripts (e.g. eval/run.py)
└── knowledge/     # Optional: reference material for the agent
```

The manifest schema is `research_skill.v1` (see
`docs/adr/arc-011-manifest-spike/` for drafted examples of several domains).
Highlights:

- `llm` — provider (`anthropic`/`openai`), models, primer file
- `param_schema` / `ui.form_fields` — validated skill parameters and the form the UI renders
- `metric_schema` — primary metric, gates, chart series, table columns
- `phase_plan` — server-tracked research phases with evidence keys
- `command_policy` — allowed scripts/executables/copyable files (the base policy is default-deny)
- `output_parser` — `delimited_kv` or `json_marker`, with optional anti-forgery nonce enforcement
- `preflight` — dependency checks (`local_file`, `http_health`, `tcp`) run before a session starts
- `promotion_target` — `file_path` (wired) or `registry_api` (loud skip until a target implementation is registered)

`POST /api/v1/skills/reload` re-discovers installed skills (non-production
environments); a new skill appears with no orchestrator or UI code changes.

## Architecture

```
autoresearch-agent/
├── src/                        # FastAPI backend
│   ├── main.py                 # App entry, lifespan, CORS, static files
│   ├── config.py               # Settings (env vars → pydantic)
│   ├── core/
│   │   ├── orchestrator.py     # Domain-neutral LLM agent tool-use loop
│   │   ├── skill_runtime.py    # ManifestSkillRuntime (the only runtime)
│   │   ├── skill_registry.py   # Skill discovery / hot reload
│   │   ├── session_manager.py  # asyncio task lifecycle
│   │   ├── results_store.py    # SQLite persistence (aiosqlite; Postgres optional)
│   │   ├── command_policy.py   # Default-deny governed command policy
│   │   ├── service_preflight.py# Skill-declared dependency checks
│   │   └── config_promoter.py  # Promotion preview/confirm/rollback
│   ├── api/                    # research, results, promotion, skills, subjects, audit, auth
│   └── ws/events.py            # WebSocket broadcaster
├── ui/                         # React 18 + TypeScript + Vite + Tailwind
├── skills/                     # Installed skill packages
├── docs/adr/                   # Skill-manifest drafts and ADRs
├── Dockerfile                  # 3-stage build (UI → Python deps → runtime)
├── CLAUDE.md                   # Agent workspace context
├── pyproject.toml              # Server Python dependencies
├── RUNBOOK.md                  # Ops: auth, metrics, health, Docker, parity
├── CHANGELOG.md
├── .env.example                # Tracked sanitized environment template
└── .env                        # Local ignored API credentials
```

### Key API Endpoints

The documented API prefix is `/api/v1`. The legacy `/api` prefix remains
available for backward compatibility but is not the UI default. Requests may
use the canonical shape (`skill_id`/`subject_id`/`variant`/`skill_params`) or
the legacy aliases (`model_type`/`instrument`/`timeframe`); responses carry
both.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/research/start` | Start a new research session |
| `GET` | `/api/v1/research` | List all sessions (filterable) |
| `GET` | `/api/v1/research/{id}` | Get session details |
| `POST` | `/api/v1/research/{id}/stop` | Stop a running session |
| `POST` | `/api/v1/research/{id}/pause` | Pause a running session |
| `POST` | `/api/v1/research/{id}/resume` | Resume a paused session |
| `DELETE` | `/api/v1/research/{id}` | Delete a session (not while running) |
| `GET` | `/api/v1/research/{id}/iterations` | Get all iterations |
| `GET` | `/api/v1/research/{id}/state` | Get reconstructable operational session state |
| `GET` | `/api/v1/research/{id}/best` | Get best iteration |
| `GET` | `/api/v1/research/{id}/agent-log` | Get agent conversation log |
| `POST` | `/api/v1/research/{id}/promote/preview` | Preview promotion |
| `POST` | `/api/v1/research/{id}/promote/confirm` | Confirm promotion for the requested scope |
| `GET` | `/api/v1/promotions` | List all promotions |
| `GET` | `/api/v1/skills` | Installed skills |
| `GET` | `/api/v1/skills/{id}` | Skill descriptor + sub-resources |
| `GET` | `/api/v1/skills/{id}/leaderboard` | Cross-session leaderboard for one skill |
| `POST` | `/api/v1/skills/reload` | Re-discover installed skills |
| `GET` | `/api/v1/subjects` | Subjects/variants a skill can run on |
| `GET` | `/api/v1/models` | Legacy alias for the skills list |
| `GET` | `/api/v1/status` | Server status and settings |
| `GET` | `/info` | Service metadata and preferred API paths |
| `GET` | `/health` | Lightweight Docker health endpoint |
| `GET` | `/health/ready` | Kubernetes-style readiness |
| `GET` | `/monitoring/health` | Dependency/preflight-style readiness |
| `GET` | `/metrics` | Prometheus metrics (disabled unless bearer-token scrape auth is configured) |
| `WS` | `/ws/events` | WebSocket for real-time events |

### Docker Compose (example)

```yaml
services:
  autoresearch-agent:
    container_name: autoresearch_agent
    ports: ["127.0.0.1:8030:8000"]
    env_file: .env
    volumes:
      - autoresearch_runs:/app/workspace/runs    # Experiment artifacts
      - autoresearch_db:/app/workspace/db         # SQLite database
      - ./workspace:/app/workspace                # Skill experiment workspaces
    deploy:
      resources:
        limits: { memory: 2G, cpus: "2.0" }
```

## Workspace

Sessions execute inside a workspace directory (default `/app/workspace`,
override with `AUTORESEARCH_WORKSPACE_ROOT`). The image bundles a generic
Python venv (`requirements-workspace.txt`); skills that need heavier domain
dependencies (ML frameworks, GPU stacks) install their own via their
bootstrap step or document them in their SKILL.md.

Skills declare their dependency readiness in their manifest's `preflight:`
section — those checks run before each session starts and gate it on
readiness (with an explicit operator override).

### Runtime State

| Path | Volume/Mount | Purpose |
|------|--------------|---------|
| `/app/workspace/runs` | `autoresearch_runs` | Run workspaces, manifests, attempt snapshots, logs |
| `/app/workspace/db` | `autoresearch_db` | SQLite research/iteration/promotion database |
| `/host/configs` | bind mount | Optional file-path promotion target root |

SQLite schema changes are versioned by `ResultsStore.initialize()` through a
single-row `schema_version` table and numbered idempotent migrations. A
Postgres backend is available via `AUTORESEARCH_DATABASE_URL` for
multi-worker deployments.

The container runs as UID/GID `1000` by default (`APP_UID`/`APP_GID` build
args). Ensure any host-owned workspace or configs path used for promotions is
writable by that identity.

### Supported LLM Backends

Any API compatible with the Anthropic Messages format, plus OpenAI:

| Backend | Setting | Example |
|---------|---------|---------|
| Anthropic | `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL` | `https://api.anthropic.com`, `claude-sonnet-4-20250514` |
| OpenAI (per-skill) | `OPENAI_BASE_URL` / `OPENAI_API_KEY` | `https://api.openai.com/v1`, `gpt-4o` |
| Any compatible proxy | custom URL | model name supported by proxy |

### Resource Defaults

| Setting | Default | Env Variable |
|---------|---------|--------------|
| Max iterations per session | 30 | `AUTORESEARCH_MAX_ITERATIONS` |
| Max API budget per session | $10.00 | `AUTORESEARCH_MAX_BUDGET_USD` |
| Experiment timeout | 2 hours | `AUTORESEARCH_TIMEOUT_S` |
| Max concurrent sessions | 2 | `AUTORESEARCH_MAX_CONCURRENT` |
| Quick mode default | off | `AUTORESEARCH_DEFAULT_QUICK_MODE` |

### Operations

`RUNBOOK.md` covers service auth, metrics, health/readiness, Docker build,
UID handling, and parity-suite operations.

---

## License

Released under the [MIT License](LICENSE).
