# Autoresearch Agent

[![CI](https://github.com/Denissvgn/autoresearch-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Denissvgn/autoresearch-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 18 + TypeScript](https://img.shields.io/badge/React_18-TypeScript-61DAFB.svg?logo=react&logoColor=black)](ui/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Docker Ready](https://img.shields.io/badge/Docker-3--stage_build-2496ED.svg?logo=docker&logoColor=white)](Dockerfile)

**Terraform for iterative optimization.** Describe an experiment loop in a declarative skill manifest; let an autonomous agent iterate under a default-deny command policy and enforced OS resource quotas; verify every score with cryptographic evaluator receipts; and promote winning configurations through an audited, rollback-able pipeline.

---

## About

> **GitHub Repository About Description:**
> Domain-neutral autonomous research agent and universal experiment harness powered by declarative skill manifests, enforced Linux isolation, and cryptographic promotion gates.
>
> **Topics:** `ai-agents` · `autonomous-research` · `llm` · `experiment-harness` · `prompt-engineering` · `optimization` · `fastapi` · `python` · `react` · `claude-code` · `codex`

**Autoresearch Agent** is a domain-neutral autonomous research control plane and experiment harness for engineering and platform teams tuning prompts, code paths, database parameters, and model configurations. Instead of hardcoding domain logic into an orchestrator, you package each optimization problem as a self-contained **skill** (`skills/<id>/SKILL.yaml` + primer + bootstrap + evaluator). The service provides the agent loop, harness adapters, workspace isolation, anti-forgery metric verification, comparable-context leaderboards, real-time React UI, and promotion machinery.

---

## Table of Contents

- [About](#about)
- [Key Highlights](#key-highlights)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
  - [1. Configure environment](#1-configure-environment)
  - [2. Build and run](#2-build-and-run)
  - [3. Open the UI](#3-open-the-ui)
  - [Try it with no API keys (demo mode)](#try-it-with-no-api-keys-demo-mode)
- [Installed Skills & Benchmark Packages](#installed-skills--benchmark-packages)
- [Harness Adapters & Attached-Agent Workflow](#harness-adapters--attached-agent-workflow)
- [Qualified Support](#qualified-support)
- [Using the UI](#using-the-ui)
- [Skills & Skill SDK](#skills--skill-sdk)
- [Architecture](#architecture)
- [Key API Endpoints](#key-api-endpoints)
- [Workspace, Storage & Operations](#workspace-storage--operations)
- [License](#license)

---

## Key Highlights

- **Declarative Skill Packages (`research_skill.v1`)** — Every domain decision (system prompt primer, parameter JSON Schema, allowed commands, output parser, research phase plan, preflight checks, metric schema, and promotion target) lives in `skills/<id>/SKILL.yaml`. Add a domain by adding a directory and calling `POST /api/v1/skills/reload`.
- **Wide LLM Provider & Local LLM Support** — Run any skill against **local LLMs** (`ollama`, `vllm`, `lmstudio`, `llamacpp`, `local` — keyless by default with \$0 token cost accounting) or cloud providers (`anthropic`, `openai`, `openrouter`, `openai-compatible` / LiteLLM / Together / Groq / custom proxies). Switch providers per skill in `SKILL.yaml` or globally across all skills via `AUTORESEARCH_LLM_PROVIDER` and `AUTORESEARCH_LLM_MODEL` without requiring Anthropic URLs or tokens.
- **Universal Research Kernel** — Supports single-objective maximization and minimization, multi-seed replication (mean / median / worst-case aggregation with standard-error significance gates), and multi-objective Pareto non-domination with hard metric constraints.
- **Multi-Harness Adapter Architecture** — Run experiments through the built-in Anthropic/OpenAI tool-use loop (`builtin`), OpenAI Codex (`codex exec --json`), Claude Code Agent SDK (`claude-code`), or a custom JSONL subprocess driver (`command-driver`). Every adapter shares one lifecycle, evidence-authority, and token/cost accounting contract; unsupported optional capabilities (`pause`, `resume`, `steer`) are refused explicitly with a reason, never silently substituted.
- **Attached-Agent API & CLI (`autoresearch agent`)** — External agents authenticate with run-scoped HMAC credentials (never the global operator token) to stage SHA-256 digest-verified candidates, trigger trusted evaluations, poll cursor-resumable event streams, and preview promotion eligibility with stable JSON envelopes and exit codes (`0`–`7`).
- **Evaluator-Authenticated Evidence & Enforced Isolation** — Trusted evaluators sign result receipts (`hmac-sha256-v1`) over the run ID, candidate digest, command, and metrics using a one-shot key delivered via an inherited file descriptor. Only `receipt_verified` results can become session champions or promote. Child processes run under a default-deny command policy with sanitized environments, optional Linux network namespace isolation (`unshare`), and enforced CPU, memory (`RLIMIT_AS`), file-size (`RLIMIT_FSIZE`), process (`RLIMIT_NPROC`), and workspace disk quotas.
- **Audited Promotion Pipeline** — Preview side-by-side diffs, confirm promotions across `development`, `paper`, `canary`, and `production` scopes, and roll back cleanly. Production promotions require a candidate-bound HMAC signature (`hmac-sha256-v2`) over the winning iteration, config SHA-256, and target identity. Supports local `file_path` targets and idempotent `registry_api` / `webhook` delivery with durable rollback descriptors.
- **Dual-Backend State Store** — Runs out of the box as a single-instance SQLite service (`aiosqlite`) and scales horizontally across multiple workers with PostgreSQL (`asyncpg`), distributed lease locks, and durable event-stream replay.

---

## How It Works

```
UI (React 18) / Attached CLI ──► FastAPI Control Plane ──► Harness Adapter
                                        │                  (builtin · codex · claude-code · driver)
                                        ▼                            │
                              Skill Manifest (SKILL.yaml)            ▼
                              prompt · commands · parser   Workspace-Scoped Tool / Candidate Loop
                                        │                            │
                                        ▼                            ▼
                              Trusted Evaluator Subprocess ◄── Enforced Linux Isolation
                              (one-shot FD key → HMAC receipt) (default-deny · quotas · netns)
                                        │
                                        ▼
                              Research Kernel (gates · replication · Pareto · champion)
                                        │
                                        ▼
                              SQLite / Postgres + WebSocket (/ws/events) ──► UI & Promotion Gate
```

The built-in agent receives 5 workspace-scoped tools (`bash`, `read_file`, `write_file`, `glob`, `grep`) governed by a default-deny command policy — command execution is restricted to the skill's declared allowlist and confined to the run workspace. Evaluator subprocesses execute inside the enforced Linux isolation boundary (`src/core/isolation.py`) with per-session resource limits.

The orchestrator auto-detects completed iterations by parsing the skill's declared output format (`delimited_kv` or `json_marker`) and verifying the evaluator's cryptographic receipt (`src/core/result_receipt.py`) — never relying on the LLM to self-report metrics. Every attempt records an immutable snapshot (command, config hash, artifact provenance), while sessions persist phase state, consistency reports, and reconstructable operational summaries.

Each session starts from an immutable `research_session_manifest.v3` written to the run workspace and persisted in the database. The session's **`skill_id` is authoritative**; the legacy `model_type` field is a derived, write-dead alias (empty for non-ML skills).

---

## Quick Start

### 1. Configure environment

Copy the tracked sanitized template, then edit the local `.env` file:

```bash
cp .env.example .env
```

`.env` is intentionally ignored by git. Commit changes to `.env.example` only when adding non-secret defaults or new variable names.

Choose your LLM backend (local LLM, OpenAI-compatible, or Anthropic) and set `AUTORESEARCH_API_TOKEN`:

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTORESEARCH_API_TOKEN` | Bearer token for operator/UI API calls | locally generated random value |
| `AUTORESEARCH_LLM_PROVIDER` | Optional global provider override (`ollama`, `vllm`, `lmstudio`, `llamacpp`, `local`, `openai`, `openai-compatible`, `openrouter`, `anthropic`) | `ollama` or leave empty for per-skill `SKILL.yaml` |
| `AUTORESEARCH_LLM_MODEL` | Global primary model override or default across providers | `qwen2.5-coder:32b`, `gpt-4o`, `claude-sonnet-4-20250514` |
| `AUTORESEARCH_LLM_BASE_URL` | Optional global base URL override for the active provider | `http://localhost:11434/v1` |
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` | OpenAI or OpenAI-compatible endpoint & key (`OPENAI_MODEL` for default model) | `https://api.openai.com/v1` |
| `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` | Anthropic Messages API endpoint & token (`ANTHROPIC_MODEL` for default model) | `https://api.anthropic.com` |

#### Quick configuration examples

**Option A — Local LLM with Ollama / vLLM / LM Studio / llama.cpp (no cloud API keys required):**
```dotenv
AUTORESEARCH_API_TOKEN=change-me-local-operator-token
AUTORESEARCH_LLM_PROVIDER=ollama          # or: vllm | lmstudio | llamacpp | local
AUTORESEARCH_LLM_MODEL=qwen2.5-coder:32b  # any local model supporting tool calls
OLLAMA_BASE_URL=http://localhost:11434/v1
```

**Option B — OpenAI / OpenRouter / LiteLLM / OpenAI-Compatible Proxy:**
```dotenv
AUTORESEARCH_API_TOKEN=change-me-local-operator-token
AUTORESEARCH_LLM_PROVIDER=openai          # or: openrouter | openai-compatible
AUTORESEARCH_LLM_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=<your-api-key>
```

**Option C — Anthropic (or Anthropic-compatible proxy):**
```dotenv
AUTORESEARCH_API_TOKEN=change-me-local-operator-token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_AUTH_TOKEN=<your-api-key>
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

Skills may also declare their own `llm.provider` (`anthropic`, `openai`, `openai-compatible`, `ollama`, `vllm`, `lmstudio`, `llamacpp`, `local`, `openrouter`) and `llm.primary_model` directly in `SKILL.yaml`. Optional controls — bind host/port, CORS origins, OAuth2 token introspection, Prometheus scrape auth, optional MLflow tracking, preflight flags, iteration limits, and budget limits — are documented in `.env.example`. `AUTORESEARCH_PROMETHEUS_TOKEN` is required in production; without it the `/metrics` endpoint is disabled.

Autoresearch-agent ships as a single-instance SQLite control-plane service by default. Keep Uvicorn at one worker and do not scale the container above one replica unless a Postgres backend (`AUTORESEARCH_DATABASE_URL`) is configured — the bundled `docker-compose.yml` wires one for you.

### 2. Build and run

With Docker Compose (bundles a Postgres state backend by default; clear `AUTORESEARCH_DATABASE_URL` in `.env` for SQLite):

```bash
cp .env.example .env   # fill in your LLM key + API token
docker compose up
```

With plain Docker (build context = this repository's root):

```bash
docker build -t autoresearch-agent .
docker run --rm -p 8030:8000 --env-file .env autoresearch-agent
```

Or locally with Poetry:

```bash
poetry install --no-interaction --no-root
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8030
```

Or from a built release artifact (wheel/sdist), outside the source tree:

```bash
python -m venv /opt/autoresearch/venv
/opt/autoresearch/venv/bin/pip install dist/autoresearch_agent-*.whl
/opt/autoresearch/venv/bin/python -c "import src.main"   # imports cleanly
/opt/autoresearch/venv/bin/autoresearch --help           # operator CLI responds
```

The installed package carries the service, the bundled skill packages, and the operator CLI — no repository checkout is required at runtime. Verify the install with the smoke commands in `RUNBOOK.md` (health, skills, demo session).

The Docker build consumes the tracked UI source, `package.json`, and `package-lock.json`. The `.dockerignore` excludes `.env`, `ui/node_modules/`, `ui/dist/`, and coverage outputs while keeping `.env.example`, package manifests, and source files available to Docker builds.

The service starts on **port 8030**. Skills that declare `preflight:` HTTP checks in their manifest require the target services to be reachable from the container.

### 3. Open the UI

Navigate to **http://localhost:8030** in your browser.

### Try it with no API keys (demo mode)

```bash
docker build -t autoresearch-agent .
docker run -d --name autoresearch-demo -p 127.0.0.1:8030:8000 \
  -e AUTORESEARCH_DEMO=true \
  -e AUTORESEARCH_EXECUTION_ISOLATION_MODE=trusted_local_code \
  -e AUTORESEARCH_API_TOKEN=demo-token \
  -e AUTORESEARCH_DATABASE_URL= \
  autoresearch-agent

# Wait for readiness, then check the installed skills:
curl -s http://127.0.0.1:8030/health/ready
curl -s -H "Authorization: Bearer demo-token" \
  http://127.0.0.1:8030/api/v1/skills

# Stage a tiny eval dataset and start a prompt-engineering demo session (reaches iterations, ~seconds):
docker exec autoresearch-demo sh -c \
  'printf "{\"input\":\"What is 2+2?\",\"expected\":\"4\"}\n" > /app/workspace/smoke_eval_set.jsonl'
curl -s -X POST http://127.0.0.1:8030/api/v1/research/start \
  -H "Authorization: Bearer demo-token" -H "Content-Type: application/json" \
  -d '{"skill_id":"prompt-engineering","max_iterations":1,"skill_params":{"eval_set":"/app/workspace/smoke_eval_set.jsonl"}}'

# Poll the session (use the id from the response above), then inspect it:
curl -s -H "Authorization: Bearer demo-token" \
  http://127.0.0.1:8030/api/v1/research/<id>
curl -s -H "Authorization: Bearer demo-token" \
  http://127.0.0.1:8030/api/v1/research/<id>/iterations

# Clean up:
docker rm -f autoresearch-demo
```

`AUTORESEARCH_DEMO=true` routes every LLM call to the zero-credential `MockProvider` (\$0 cost). The provider drives the skill's declared `demo_experiment_command` (offline evaluator) and relays the governed eval's `ITERATION_RESULT` marker verbatim, so the whole flow — session start, the skill's bootstrap, governed commands, marker parsing, iterations, charts, leaderboard, promotion preview — runs with no LLM keys. The provider router refuses the mock in production (fail-closed). The same flow is scripted in `scripts/smoke_docker.sh` (CI runs it against every built image).

---

## Installed Skills & Benchmark Packages

| Skill | Category | Scorer | Promotion |
|-------|----------|--------|-----------|
| `prompt-engineering` | generative | controlled scorer (live endpoint required; a scorer failure is an explicit refusal — there is no fallback chain). Offline demo scoring is a separate, labeled mode | `registry_api` (webhook delivery) |
| `code-refactor` | generative | real test/lint/type runs over candidate bundles (protected tests; a required-but-unmeasured gate rejects) | `file_path` |
| `db-config-tuning` | optimization | offline: deterministic TPS/latency bench model (simulated mode — never comparable with measured evidence) | `file_path` |

A skill is a directory under `skills/` (`SKILL.yaml` + `SKILL.md` + `bootstrap.py` + eval CLI); add one and `POST /api/v1/skills/reload` — no orchestrator or UI code changes. At session start the service runs the skill's `bootstrap.py` to render the session workspace (the evaluator's inputs); a failed bootstrap refuses the start.

The **Leaderboard** page ranks scored sessions **within comparable-context groups** (objective, units, dataset/scorer/fidelity pins, subject/variant constraints): contexts never merge into one champion table, and history without a recorded context ranks only in its own group (`GET /api/v1/skills/{id}/leaderboard`).

Skills declaring `promotion_target.kind: webhook` (or `registry_api` with an endpoint) deliver the promoted winner to their endpoint with an `Idempotency-Key` and retries, keeping a local provenance copy under `<workspace>/promotions/`; delivery failure fails the confirm (fail-closed). See `examples/prompt-registry/` for a runnable receiver.

In addition to the three `research_skill.v1` packages above, the repository includes `skills/latency-benchmark/` (`SKILL.md` + `workload.json`), which supplies the frozen workload and protocol digest used by the measured latency minimization benchmark (`src/core/latency_benchmark.py`).

---

## Harness Adapters & Attached-Agent Workflow

Autoresearch Agent supports two operating modes for agents:

1. **Managed Harnesses** — The service spawns and supervises the agent process (`builtin`, `codex`, `claude-code`, or a custom JSONL `command-driver`). Inspect registered adapters and preflight probes via `GET /api/v1/harnesses`.
2. **Attached Agents** — An external agent or CI worker connects over HTTP using a run-scoped HMAC credential (`AUTORESEARCH_AGENT_CREDENTIAL` or `--credential-file`) via the `autoresearch agent` CLI or `/api/v1/agent/runs/*` endpoints.

### Attached-Agent CLI (`autoresearch agent`)

Every `autoresearch agent` command prints a single machine-readable JSON object on stdout (`{"ok": true, "data": ...}` or `{"ok": false, "error": ...}`) and exits with a stable code (`0` success, `2` usage/validation refusal, `3` auth refused, `4` idempotency conflict, `5` size/rate limit, `6` bounded wait timeout, `7` transport failure):

```bash
export AUTORESEARCH_API_URL="http://127.0.0.1:8030"
export AUTORESEARCH_AGENT_CREDENTIAL="<run-scoped-token>"

# 1. Create or attach to the run bound to the credential
autoresearch agent run create --max-iterations 5 --max-budget-usd 5.0

# 2. Inspect run constraints (budgets, max candidate bytes, rate limits)
autoresearch agent constraints --run <run_id>

# 3. Stage a candidate artifact (SHA-256 digest verified, idempotent)
autoresearch agent submit --run <run_id> \
  --content-file candidate.json \
  --idempotency-key "cand-001"

# 4. Trigger trusted evaluation with a bounded wait
autoresearch agent evaluate --run <run_id> --wait --timeout 30

# 5. Inspect results (with recorded authority labels) & preview promotion
autoresearch agent results --run <run_id>
autoresearch agent preview --run <run_id>

# 6. Poll run events from a persisted cursor file (safe across reconnects)
autoresearch agent events --run <run_id> --cursor-file .agent-cursor.json
```

An attached agent can never declare its own results `receipt_verified` nor approve production promotion — authority labels are assigned exclusively by the server's trusted evaluation channel.

---

## Qualified Support

What "works" means here is measured, not claimed. Each combination of harness adapter, research domain, and backend is qualified by an executed candidate → evaluation → winner lifecycle; combinations without live evidence are **shipped but unclaimed**, never marked supported by fixture runs or simulations.

| Harness adapter | Real-prompt domain | Code/test domain | Latency domain | Backends |
|---|---|---|---|---|
| Built-in loop | qualified | qualified | qualified | SQLite (qualified); same-host Postgres workers (shipped, unclaimed — lifecycle cells pending in the distributed deployment lane) |
| Codex (`codex exec --json`) | shipped, unclaimed | shipped, unclaimed | shipped, unclaimed | contract-conformant; awaiting live-run evidence |
| Claude Code (Agent SDK CLI) | shipped, unclaimed | shipped, unclaimed | shipped, unclaimed | contract-conformant; awaiting live-run evidence |
| Attached API/CLI + custom drivers | contract-qualified on both stores | | | |

Unclaimed combinations still pass the shared contract suites (lifecycle, evidence authority, usage accounting, explicit capability refusals) — the gap is live external evidence, not conformance. Optional capabilities (pause, resume, steering) are advertised per adapter; an unadvertised control is refused with an explanation in the UI and API, never silently substituted. Cross-harness continuation is never presented as native transcript resume.

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
| **Max Budget (\$)** | Optional | Spending limit for LLM API calls (default: \$10, range: \$1–\$100) |
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
- **Pause** — temporarily halts the agent loop (resumes from where it left off, when advertised by the bound harness)
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

Development-scope promotion writes the winning config to the skill's declared target path. Paper and canary scopes record auditable local decisions. Production-scope promotion requires a candidate-bound HMAC-signed approval (`AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER`, method `hmac-sha256-v2`): preview first, then sign the returned `iteration`, `config_snapshot_sha256`, and `target_identity` alongside the approver identity; confirm rejects a changed winner. Promotion targets the skill declares that the local machinery cannot execute (e.g. `artifact_store`, `git_branch`) **skip loudly** with an audit trail instead of pretending. `registry_api` / `webhook` targets deliver to the skill's declared endpoint with an idempotency key and retries (fail-closed), and record a durable `target_descriptor` so rollback survives restarts.

### History

The **History** page shows:
- **Past Sessions** — all completed/stopped/failed sessions with metrics
- **Config Promotions** — log of every promotion with timestamp, source session, and target path

---

## Skills & Skill SDK

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

The manifest schema is `research_skill.v1` (see `docs/adr/skill-manifest-drafts/` for drafted examples of several domains). Highlights:

- `llm` — provider (`anthropic`, `openai`, `openai-compatible`, `ollama`, `vllm`, `lmstudio`, `llamacpp`, `local`, `openrouter`), models, primer file
- `param_schema` / `ui.form_fields` — validated skill parameters and the form the UI renders
- `metric_schema` — primary metric, direction (`maximize`/`minimize`), gates, chart series, table columns; optional `significance` block switches keep/discard to a multi-seed mean±standard-error test
- `phase_plan` — server-tracked research phases with evidence keys
- `command_policy` — allowed scripts/executables/copyable files (the base policy is default-deny)
- `output_parser` — `delimited_kv` or `json_marker`, with optional anti-forgery nonce enforcement
- `preflight` — dependency checks (`local_file`, `http_health`, `tcp`) run before a session starts
- `promotion_target` — `file_path` (writes the declared `path_template`) or `registry_api`/`webhook` (delivers to the declared endpoint)
- `prompt.demo_experiment_command` — the offline command the demo provider drives (`{session_workspace}` placeholders; validated at load)
- `command_policy.config_flag` — the CLI flag carrying the skill's per-iteration config artifact (`--config`/`--prompt`/`--target`); policy confinement and the pre-run snapshot both key on it

`POST /api/v1/skills/reload` re-discovers installed skills (non-production environments); a new skill appears with no orchestrator or UI code changes.

### Generating a skill (Skill SDK)

`autoresearch new-skill` drafts a complete package from a natural-language goal — the generator calls the LLM, validates the manifest against `research_skill.v1`, lints the emitted Python, and audits the command policy before anything is written. Drafts land in `skills/_drafts/<id>/` and are not selectable for production until promoted:

```bash
# Draft (nothing under skills/ is written in --dry-run):
poetry run autoresearch new-skill --goal "tune a Postgres config for latency" \
  --dry-run --dry-bootstrap     # + execute bootstrap.py in a preview overlay

# Generate for real, then promote after review:
poetry run autoresearch new-skill --goal "tune a Postgres config for latency"
poetry run autoresearch promote-skill --id my-skill    # confirm + git tag
```

Promotion refuses to run while the policy audit reports **critical** findings (override with `--allow-critical`), and records a `skill/<id>/<version>` git tag when the skills tree lives in a repository. The UI's **Skill Studio** page offers the same wizard through `POST /skills/generate` — set `AUTORESEARCH_SKILL_GENERATOR_ENABLED=true` to expose it (it spends LLM tokens; promotion stays a CLI/operator act).

---

## Architecture

```
autoresearch-agent/
├── src/                              # FastAPI backend & operator CLI
│   ├── main.py                       # App entry, lifespan, CORS, static files
│   ├── config.py                     # Settings (env vars → pydantic)
│   ├── cli.py                        # Operator CLI (new-skill, promote-skill, reconcile-bests)
│   ├── agent_cli.py                  # Attached-agent CLI (autoresearch agent ...)
│   ├── agent_client.py               # HTTP client for run-scoped attached agents
│   ├── core/
│   │   ├── orchestrator.py           # Domain-neutral LLM agent tool-use loop
│   │   ├── research_kernel.py        # Universal objective, replication, Pareto & promotion kernel
│   │   ├── harness_contract.py       # Universal harness contract & capability schema
│   │   ├── harness_adapter.py        # Harness registry & adapter lifecycle
│   │   ├── builtin_harness.py        # Built-in Anthropic/OpenAI tool-use adapter
│   │   ├── codex_harness.py          # OpenAI Codex CLI (codex exec --json) adapter
│   │   ├── claude_code_harness.py    # Claude Code Agent SDK CLI adapter
│   │   ├── command_driver_harness.py # Custom JSONL subprocess driver adapter
│   │   ├── isolation.py              # Enforced Linux process isolation, netns & resource quotas
│   │   ├── result_receipt.py         # HMAC-SHA256 evaluator result receipt signer/verifier
│   │   ├── scoped_credentials.py     # Run-scoped HMAC tokens for attached agents
│   │   ├── skill_runtime.py          # ManifestSkillRuntime
│   │   ├── skill_registry.py         # Skill discovery / hot reload
│   │   ├── skill_generator.py        # LLM-powered Skill SDK generator & policy auditor
│   │   ├── session_manager.py        # Asyncio session task lifecycle & distributed leases
│   │   ├── state_store.py            # SQLite StateStore (aiosqlite)
│   │   ├── postgres_state_store.py   # Multi-worker PostgreSQL StateStore (asyncpg)
│   │   ├── command_policy.py         # Default-deny governed command policy
│   │   ├── service_preflight.py      # Skill-declared dependency checks
│   │   └── config_promoter.py        # Promotion preview/confirm/rollback & webhook delivery
│   ├── api/                          # research, results, promotion, skills, subjects, harnesses, agent
│   └── ws/events.py                  # WebSocket broadcaster & durable event polling
├── ui/                               # React 18 + TypeScript + Vite + Tailwind
├── skills/                           # Installed skill packages & benchmark workloads
├── examples/prompt-registry/         # Reference webhook receiver for registry_api promotions
├── docs/adr/                         # Architecture Decision Records & skill-manifest drafts
├── Dockerfile                        # 3-stage build (UI → Python deps → runtime)
├── docker-compose.yml                # Multi-container stack with PostgreSQL backend
├── pyproject.toml                    # PEP 621 project metadata & Poetry dependencies
├── RUNBOOK.md                        # Ops: auth, metrics, health, Docker, recovery
├── CHANGELOG.md                      # Release history
└── .env.example                      # Tracked sanitized environment template
```

---

## Key API Endpoints

The documented API prefix is `/api/v1`. The legacy `/api` prefix remains available for backward compatibility but is not the UI default. Requests may use the canonical shape (`skill_id`/`subject_id`/`variant`/`skill_params`) or the legacy aliases (`model_type`/`instrument`/`timeframe`); responses carry both. Starts fail fast: an unknown `skill_id` is a 404 `skill_not_found` naming the available skills, and a legacy `model_type`-only request is first translated through the alias map (`direction` → `ml-direction`) and then faces the same installed-skill check — no 201-then-crash sessions.

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
| `GET` | `/api/v1/research/{id}/harness-context` | Get bound harness capabilities, evidence authority, and cost quality |
| `POST` | `/api/v1/research/{id}/promote/preview` | Preview promotion diff and candidate digest |
| `POST` | `/api/v1/research/{id}/promote/confirm` | Confirm promotion for the requested scope |
| `GET` | `/api/v1/promotions` | List all promotions |
| `GET` | `/api/v1/skills` | Installed skills |
| `GET` | `/api/v1/skills/{id}` | Skill descriptor + sub-resources |
| `GET` | `/api/v1/skills/{id}/leaderboard` | Comparable-context leaderboard for one skill |
| `POST` | `/api/v1/skills/reload` | Re-discover installed skills |
| `GET` | `/api/v1/harnesses` | Capability & preflight descriptors for all registered harnesses |
| `GET` | `/api/v1/harnesses/{name}` | Descriptor for a specific harness adapter |
| `POST` | `/api/v1/agent/runs` | Attached agent: create or attach to a scoped run |
| `GET` | `/api/v1/agent/runs/{id}/constraints` | Attached agent: inspect run budgets and submission limits |
| `POST` | `/api/v1/agent/runs/{id}/candidates` | Attached agent: stage an idempotent, digest-verified candidate |
| `POST` | `/api/v1/agent/runs/{id}/evaluations` | Attached agent: request trusted evaluation |
| `GET` | `/api/v1/agent/runs/{id}/results` | Attached agent: inspect results and authority labels |
| `POST` | `/api/v1/agent/runs/{id}/lifecycle` | Attached agent: pause, resume, or stop the run |
| `GET` | `/api/v1/agent/runs/{id}/promotion-preview` | Attached agent: preview promotion eligibility |
| `GET` | `/api/v1/agent/runs/{id}/events` | Attached agent: cursor-based event replay |
| `GET` | `/api/v1/subjects` | Subjects/variants a skill can run on |
| `GET` | `/api/v1/models` | Legacy alias for the skills list |
| `GET` | `/api/v1/status` | Server status and settings |
| `GET` | `/info` | Service metadata and preferred API paths |
| `GET` | `/health` | Lightweight Docker health endpoint |
| `GET` | `/health/ready` | Kubernetes-style readiness |
| `GET` | `/monitoring/health` | Dependency/preflight-style readiness |
| `GET` | `/metrics` | Prometheus metrics (disabled unless bearer-token scrape auth is configured) |
| `WS` | `/ws/events` | WebSocket for real-time events |

---

## Workspace, Storage & Operations

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

### Workspace & Runtime State

Sessions execute inside a workspace directory (default `/app/workspace`, override with `AUTORESEARCH_WORKSPACE_ROOT`). The image bundles a generic Python venv (`requirements-workspace.txt`); skills that need heavier domain dependencies (ML frameworks, GPU stacks) install their own via their bootstrap step or document them in their `SKILL.md`.

Skills declare their dependency readiness in their manifest's `preflight:` section — those checks run before each session starts and gate it on readiness (with an explicit operator override).

| Path | Volume/Mount | Purpose |
|------|--------------|---------|
| `/app/workspace/runs` | `autoresearch_runs` | Run workspaces, manifests, attempt snapshots, logs |
| `/app/workspace/db` | `autoresearch_db` | SQLite research/iteration/promotion database |
| `/host/configs` | bind mount | Optional file-path promotion target root |

SQLite schema changes are versioned by `ResultsStore.initialize()` through a single-row `schema_version` table and numbered idempotent migrations. A Postgres backend is available via `AUTORESEARCH_DATABASE_URL` for multi-worker deployments.

The container runs as UID/GID `1000` by default (`APP_UID`/`APP_GID` build args). Ensure any host-owned workspace or configs path used for promotions is writable by that identity.

### Supported LLM Backends & Local LLMs

Autoresearch Agent supports Anthropic, OpenAI, cloud OpenAI-compatible routers, and local LLM servers out of the box. You can select a provider per skill in `SKILL.yaml` (`llm.provider`) or override the provider and model globally in `.env` via `AUTORESEARCH_LLM_PROVIDER` and `AUTORESEARCH_LLM_MODEL`:

| Provider ID | Default Base URL | Auth Env Variable | Cost Accounting |
|-------------|------------------|-------------------|-----------------|
| `ollama` | `http://localhost:11434/v1` (`OLLAMA_BASE_URL`) | Optional (`AUTORESEARCH_LLM_API_KEY`) | \$0.00 local inference |
| `vllm` | `http://localhost:8000/v1` (`VLLM_BASE_URL`) | Optional (`AUTORESEARCH_LLM_API_KEY`) | \$0.00 local inference |
| `lmstudio` | `http://localhost:1234/v1` (`LMSTUDIO_BASE_URL`) | Optional (`AUTORESEARCH_LLM_API_KEY`) | \$0.00 local inference |
| `llamacpp` | `http://localhost:8080/v1` (`LLAMACPP_BASE_URL`) | Optional (`AUTORESEARCH_LLM_API_KEY`) | \$0.00 local inference |
| `local` | `http://localhost:11434/v1` (`AUTORESEARCH_LLM_BASE_URL`) | Optional (`AUTORESEARCH_LLM_API_KEY`) | \$0.00 local inference |
| `openai` | `https://api.openai.com/v1` (`OPENAI_BASE_URL`) | `OPENAI_API_KEY` | Per-model USD table |
| `openrouter` | `https://openrouter.ai/api/v1` (`OPENROUTER_BASE_URL`) | `OPENROUTER_API_KEY` | Per-model USD table |
| `openai-compatible` | `AUTORESEARCH_LLM_BASE_URL` or `OPENAI_BASE_URL` | `AUTORESEARCH_LLM_API_KEY` or `OPENAI_API_KEY` | Per-model USD table |
| `anthropic` | `https://api.anthropic.com` (`ANTHROPIC_BASE_URL`) | `ANTHROPIC_AUTH_TOKEN` | Per-model USD + cache rates |
| `mock` | In-process (`AUTORESEARCH_DEMO=true`) | None | \$0.00 (dev/CI/demo only) |

### Resource Defaults

| Setting | Default | Env Variable |
|---------|---------|--------------|
| Max iterations per session | 30 | `AUTORESEARCH_MAX_ITERATIONS` |
| Max API budget per session | \$10.00 | `AUTORESEARCH_MAX_BUDGET_USD` |
| Experiment timeout | 2 hours | `AUTORESEARCH_TIMEOUT_S` |
| Max concurrent sessions | 2 | `AUTORESEARCH_MAX_CONCURRENT` |
| Quick mode default | off | `AUTORESEARCH_DEFAULT_QUICK_MODE` |

### Operations

[`RUNBOOK.md`](RUNBOOK.md) covers service auth, metrics, health/readiness, Docker build, UID handling, budget limits, and recovery/backup operations.

---

## License

Released under the [MIT License](LICENSE).
