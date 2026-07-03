# Universal Research Agent — Generalization Analysis

**Status:** Planning / for further analysis
**Date:** 2026-06-28
**Author:** LLM analysis pass
**Scope:** Generalize `services/autoresearch-agent` into a domain-agnostic
"universal research agent" that can run any LLM-driven iterative research
workflow, not just ML model tuning for trading.

---

## 1. Executive summary

`autoresearch-agent` is a mature, production-grade implementation of an
**LLM tool-use loop with server-authoritative state**. Its reusable core is
strong: governed command execution, budget/timeout guards, server-parsed
iteration detection, audit/manifest provenance, phase contracts, structured
search plans, cross-session dedup, live UI, and a promotion handoff. These
primitives are **not** specific to ML or trading — they are the generic
building blocks of any "autonomous agent that iterates, measures, and
promotes a winner". Trading-model tuning is simply the first instance that
was built; it should not remain the spine of the architecture.

The goal of this document is to turn the service into a **universal research
agent**: one runtime that hosts any number of research domains — ML tuning,
prompt engineering, code refactoring, literature review, system
configuration optimization, security research, scientific sweeps — as peers,
each installed as a self-contained **domain skill** that the agent loads on
demand.

**The proposal has two layers:**

1. **A domain-neutral runtime** (the orchestrator, command policy, loop
   guards, storage protocol, API, UI). It contains zero domain knowledge.
   Every domain-specific decision is delegated to a loaded skill through a
   typed `SkillRuntime` protocol.

2. **Domain skills** — self-contained, installable packages
   (`skills/<id>/`) that do two jobs a manifest alone cannot:
   - **Auto-initialize** the agent for their domain at session start: render
     a workspace scaffold, inject domain expertise into the system prompt,
     configure the tool allow-list, seed the search space, and wire up the
     evaluation harness. Selecting a domain makes the agent domain-ready in
     one step.
   - **Govern** the loop declaratively via `SKILL.yaml` (param schema,
     metric schema, phase plan, parser, preflight, promotion target).

A new research domain is added by dropping a skill directory — no
orchestrator or UI code changes. Domains can even be **drafted
automatically**: an LLM-assisted skill generator takes a natural-language
domain description and produces a reviewable draft skill (§8.6), so a
domain expert never has to write YAML or Python to add a research capability.

The same refactor fixes several operational weaknesses "for free" by making
them explicit extension points: LLM-provider lock-in becomes a pluggable
provider; single-instance SQLite becomes a storage protocol; the `---`
forgery surface becomes a signed-metrics contract; race-prone ad-hoc status
updates become an explicit state machine.

**Interface consequence (Section 7):** because every variant must be
supported *natively* rather than via shim, the public surface —
`ResearchConfig`, the HTTP API, WebSocket payloads, persisted artifacts,
and the React UI — is generalized once around a small set of canonical
fields (`skill_id`, `subject_id`, `variant`, `skill_params`) plus a typed
`SkillRuntime` protocol the orchestrator calls into. The existing trading
client shape (`{instrument, timeframe, model_type}`) is preserved as a
**dual-shape alias** — one domain among many, not the default mental model.
The operational test of "done" is concrete: a grep for `config.model_type`
in the orchestrator returns zero hits, and a new skill ships as a directory
under `skills/` with no orchestrator or UI code changes.

---

## 2. Current state (architecture recap)

```
UI (React) ──► FastAPI (/api/v1) ──► SessionManager ──► AgentOrchestrator
                     │                       │                   │
                     │                       │                   ├── Anthropic SDK
                     │                       │                   │   (messages.create + tools)
                     │                       │                   │
                     │                       │                   └── Tool execution:
                     │                       │                       bash → GovernedCommandRunner
                     │                       │                            (command_policy allow-list)
                     │                       │                       read_file / write_file
                     │                       │                       glob / grep
                     │                       │
                     │                       └── PipelineController (multi-phase pipelines)
                     │
                     ├── ResultsStore (aiosqlite)
                     │     research_sessions, iterations, promotions,
                     │     audit_events, runtime_commands, planned_trials,
                     │     hpo_studies, schema_version
                     │
                     ├── ConfigPromoter (preview/confirm, atomic write to host configs)
                     │
                     ├── WebSocket broadcaster (live UI events)
                     │
                     └── Service preflight (data-ingest, feature-service,
                                            ensemble-trainer, rl-trainer,
                                            mlflow, inference, vdmc, admin)
```

**Loop shape** (`src/core/orchestrator.py:2562` `AgentOrchestrator.run`):

1. Load `CLAUDE.md` + per-`model_type` `SKILL.md` as system prompt.
2. Build a directive user prompt with exact setup/train commands.
3. For each turn (bounded by `max_turns = max_iterations × 10`):
   - Check stop / pause / timeout / pre-spend budget gate.
   - Compact context if over threshold.
   - Call Claude (retry + backoff on transient errors).
   - For each `tool_use` block: structured-HPO guard → duplicate guard →
     pre-snapshot `train.yaml` → record `runtime_command` → execute via
     `asyncio.to_thread(_execute_tool, …)`.
   - Digest large bash outputs before they re-enter the LLM context.
   - **Server-side iteration detection**: scan bash output for the
     `---` delimited metrics block (`parse_prepare_output`) **and** the
     `ITERATION_RESULT:` JSON marker (`parse_iteration_marker`). Also
     fall back to reading `last_metrics.txt` / `results.json`.
   - Record iteration with attempt snapshot, trial identity hash, config
     hash, consistency report, MLflow run id.
   - Inject an iteration-context digest into the next turn's tool results.
4. On exit: extract insights (Haiku), update `research_resume.md`,
   auto-promote if conditions met, broadcast final event.

**Domain anchors (the parts that need to become pluggable):**

| Anchor | Location | What's hardcoded |
|---|---|---|
| `model_type` enum | `ResearchConfig`, `config.py`, UI | `direction`, `volatility`, `rl` |
| Skill loader | `orchestrator.py:831` `_load_skill` | map `{direction, volatility, rl} → SKILL.md` |
| Allowed scripts | `command_policy.py:12` `_ALLOWED_SCRIPTS` | `scripts/autotuner/{setup,prepare,enrich_rl_dataset,resume}.py` |
| Output parser | `experiment_parser.py` | `---` KV block, `ITERATION_RESULT:` marker, gate field names |
| Phase plan | `research_phase_plan.py` | `DIRECTION_PHASES`, `VOLATILITY_PHASES`, `RL_PHASES` |
| Preflight deps | `service_preflight.py` | data-ingest, feature-service, ensemble-trainer, rl-trainer, mlflow, vdmc |
| Promotion target | `config_promoter.py` | `configs/instrument_configs/{instrument}_{timeframe}.yaml` |
| Metric taxonomy | `blocker_classifier.py`, `development_gate_bundle.py` | `signal_saturation`, `weak_calibration`, composite score formulas |
| Insights prompt | `orchestrator.py:1561` | ML-specific ("which params improved/degraded the metric") |
| Prompt builders | `orchestrator.py:1108 _build_prompt` etc. | setup.py / enrich / prepare.py command templates |

---

## 3. Strengths (what to preserve and reuse)

### 3.1 Server-authoritative iteration detection
The orchestrator does **not** trust the LLM to report results. It parses
the deterministic stdout of the experiment script (`parse_prepare_output`)
and consumes a marker file (`last_metrics.txt`) via atomic rename
(`orchestrator.py:849 _read_marker_file`). This is the single most
important pattern for any autonomous agent: **the thing being measured
must be measured by the server, not self-reported by the agent**.

**Reuse value:** universal. Any research workflow that runs an
evaluable script gets correct iteration accounting for free.

### 3.2 Strict, declarative command policy
`command_policy.py` rejects shell pipes, redirection, substitution,
chaining, secret-bearing tokens, and any executable outside an
allow-list. Decisions are dataclass values with a `reason` that flows
back to the agent as a tool error and to the audit log.

**Reuse value:** universal. The allow-list contents are domain-specific;
the policy engine is not.

### 3.3 Defense-in-depth budget / timeout / iteration guards
- Pre-spend cost gate projecting next-turn cost from rolling input-token
  count (`orchestrator.py:2662`).
- Per-session wall-clock timeout with budget-aware retry backoff
  (`_call_claude_with_retry` skips a retry whose backoff would blow the
  remaining budget).
- Hard iteration cap, hard turn cap (`max_iterations × 10`).
- Max concurrent sessions + per-`(instrument, timeframe, model_type)`
  uniqueness lock.
- Policy-rejection counter that aborts the loop after 5 consecutive
  rejected commands (`_MAX_CONSECUTIVE_POLICY_REJECTIONS`).

**Reuse value:** universal. These are properties of the loop, not the
domain.

### 3.4 Auditability and provenance
- `research_session_manifest.v1` written to workspace + SQLite at session
  start, with content hash.
- `autoresearch_iteration_attempt.v1` snapshots per attempt: command,
  config hash, environment metadata, artifact hashes.
- `audit_events` table for every meaningful operator/agent action.
- `runtime_commands` table tracking every bash invocation with status,
  returncode, timed_out, output_preview.
- `agent_log.jsonl` per session with full transcript.
- Schema migrations versioned via single-row `schema_version` table.

**Reuse value:** universal. Provenance is what makes an autonomous
agent trustworthy.

### 3.5 Phase contract mechanism
The 9-phase direction plan (`research_phase_plan.py`) is more than a
domain artifact: it is a **generic mechanism** for telling an LLM "you
may not terminate until these evidence keys appear in your iteration
metrics, and you may not dwell in one phase beyond `max_iterations`".
The orchestrator enforces this server-side by injecting continuation
messages when the agent tries to `end_turn` early.

**Reuse value:** the mechanism is universal; only the phase
definitions are domain-specific. Any multi-stage research workflow
(literature review → synthesis → validation; hypothesis → experiment →
analysis; etc.) maps cleanly onto this.

### 3.6 Structured HPO / planned-trial enforcement
When enabled, the server materializes a bounded set of planned trials
(`planned_trials/<trial_id>/train.yaml` + `server_hpo_plan.json`) and
the orchestrator **rejects** any off-plan training command, routing
the agent's alternatives to a `manual_review` queue. This converts the
LLM from "free explorer" to "trusted executor of a server-validated
search plan" — exactly the right trust split for expensive operations.

**Reuse value:** universal for any research where the search space
can be pre-enumerated (config sweeps, prompt variants, A/B test
designs, etc.).

### 3.7 Cross-session memory and dedup
- `trial_identity_hash` over (instrument, timeframe, model_type,
  canonical_config_hash, quick_mode, data_split_id, source_model_ids)
  with `find_duplicate_trial_identity` rejecting re-runs.
- `research_resume.md` per (instrument, timeframe) summarizing prior
  sessions, loaded into every new session's prompt.
- Haiku-extracted `insights` (≤500 chars) stored on the session row.
- Cross-session iteration summary fed into the iteration-context digest
  so the agent sees what neighboring sessions already explored.

**Reuse value:** universal. "Don't repeat prior work" is a property
of every long-running research program.

### 3.8 Promotion handoff
The agent cannot self-promote. It produces a best candidate; the server
runs `ConfigPromoter.preview` (with optional `PromotionEvidenceCollector`
for infra-side gates) and surfaces a diff; a human or downstream service
confirms. Atomic temp+rename writes, scope-aware approval rules
(development/paper/canary/production), and delegation to mlflow-service
for production composites.

**Reuse value:** universal. "Promote a winning artifact through
environments with audit and approval" is a generic deployment pattern.

### 3.9 Resilience primitives
- Transient-error retry with bounded backoff (`_TRANSIENT_EXCEPTIONS`,
  HTTP 429/502/503/529).
- Context compaction bounding retained history
  (`_compact_messages`, `context_compaction_threshold`).
- Crash recovery on startup: `recover_orphaned_sessions` classifies
  interrupted sessions as `resumable` / `interrupted` based on
  workspace/manifest presence, and interrupts dangling
  `runtime_commands`.
- Process-tree termination via `psutil` with SIGKILL fallback
  (`command_runner.py:220`).
- Stale-marker-file detection via `min_mtime` so a leftover file from
  a prior session can't be mistaken for a fresh result.

**Reuse value:** universal. These are operational properties of any
long-running agent service.

### 3.10 Live UI + WebSocket
Dashboard, NewResearch form, session detail with State / Metrics Chart
/ Iterations / Agent Log tabs, History, promotion modal with side-by-side
diff. WebSocket with heartbeat + idle-window timeout.

**Reuse value:** mostly universal. The session/iteration/chart
visualization is generic; the "instrument/timeframe/model_type" form
fields are not.

### 3.11 Anti-waste rules baked into the directive prompt
"Never re-run identical config+seed", "never change only the seed",
"make meaningful changes (≥2× or 0.5×)", "diversify search dimensions
after 3+ same-axis iterations", "quick-mode winners fail in full mode".
These are encoded in `CLAUDE.md`.

**Reuse value:** the *form* of these rules is universal ("don't burn
budget on inert changes"); the *content* is domain-specific.

---

## 4. Weaknesses (and how each constrains generalization)

Grouped by whether they block generalization or are merely operational
debt.

### 4.1 Blocking generalization

**W1. Domain-coupled `ResearchConfig` and prompt builders.**
`ResearchConfig` carries `instrument`, `timeframe`, `model_type`,
`trading_mode`, `agent_strategy`, `initial_balance`. The prompt builders
`_build_prompt` / `_build_resume_prompt` / `_build_prompt_rl_hpo`
hardcode `setup.py`, `enrich_rl_dataset.py`, and `prepare.py` command
templates. A non-ML research workflow cannot be expressed without
forking the orchestrator.

**W2. Hardcoded command allow-list.**
`command_policy.py:_ALLOWED_SCRIPTS` enumerates four exact script paths.
A new research domain with different scripts is rejected by policy.

**W3. Hardcoded output parser contract.**
`experiment_parser.py` knows the `---` delimiter, the specific field
names (`primary_metric`, `metric_name`, `training_gates_passed`,
`all_gates_passed`), and the failure-status set. Any workflow using a
different output convention (JSON, structured logs, exit code only)
needs a new parser.

**W4. Hardcoded phase plans and metric taxonomy.**
`research_phase_plan.py` ships `DIRECTION_PHASES`, `VOLATILITY_PHASES`,
`RL_PHASES` as module-level constants. `_AGENT_ACTIONABLE_BLOCKERS` and
`_PHASE_SPECIFIC_AGENT_KEYS` are direction/RL-specific. The
`blocker_classifier` and `development_gate_bundle` encode trading model
gates.

**W5. Hardcoded preflight dependencies.**
`service_preflight.py` knows the trading platform's service mesh. A
research workflow with different dependencies (a code repo, a database,
a browser, an external API) cannot declare its own.

**W6. Hardcoded promotion target.**
`config_promoter.py` writes to `configs/instrument_configs/`. A research
workflow whose "winning artifact" is a prompt, a docker image, a
config file in a different layout, or a registry API call has no path.

**W7. Single LLM provider.**
The orchestrator constructs `anthropic.AsyncAnthropic` directly and the
loop is shaped around the Anthropic Messages tool-use protocol. There
is no `LLMProvider` abstraction. OpenAI / Gemini / local backends are
not first-class.

### 4.2 Operational debt (also worth fixing during the refactor)

**W8. Stop-status clobber race.** `session_manager.stop_session` writes
`status="stopped"` immediately, but the orchestrator's exit path can
overwrite it with `completed` and trigger spurious auto-promotion.
(Noted in the existing service review, item #1.)

**W9. No hard wall-clock wrapper on `run()`.** Per-turn checks rely on
the loop reaching the top; a stuck `to_thread` can exceed the configured
timeout.

**W10. `ALTER TABLE … except: pass` masks real failures** in
`results_store` migrations.

**W11. `---` block forgery surface.** A hostile (or merely buggy)
experiment script can emit a forged `---` block and fake a passed
iteration. There is no per-session nonce or signature binding the
metrics block to the server-issued manifest.

**W12. Promotion write is not atomic vs. host bind-mount.** Config and
metadata sidecar are separate writes.

**W13. `EventBroadcaster._clients` mutated without a lock.**
`RuntimeError: Set changed size during iteration` is possible.

**W14. Single-instance SQLite ceiling.** Explicit guard rejects
`WEB_CONCURRENCY > 1`. Cannot scale horizontally without moving session
state and idempotency locks to a distributed store.

**W15. Unbounded list endpoints.** `list_sessions`, `list_iterations`,
`list_pipelines` have no pagination.

**W16. Synchronous `subprocess.run(grep, …)` inside async tool path.**
Bounded by `asyncio.to_thread` but contributes to thread-pool pressure.

**W17. CORS `*` + credentials posture** (partially mitigated already;
document the remaining policy explicitly).

**W18. Production-scope promotion approval is structurally optional**
at the API layer (`PromotionApproval` fields all `Optional`).

---

## 5. Generalization strategy: turn weaknesses into advantages

The recurring move is: **take a hardcoded domain coupling, lift it into
a declarative skill descriptor, and the weakness becomes an extension
point.**

| Weakness | Refactor | Becomes advantage |
|---|---|---|
| W1 domain-coupled config/prompt | `ResearchConfig` becomes generic (`subject_id`, `variant`, `skill_id`); prompt is rendered from the skill manifest | New research types added without orchestrator changes |
| W2 hardcoded allow-list | Allow-list is a section of the skill manifest | Per-skill least-privilege policy; auditable |
| W3 hardcoded parser | Parser is selected by manifest (`format: delimited_kv \| json_marker \| structured \| exit_code`), with a field map | Any output convention is supported |
| W4 hardcoded phases | Phase plan is a manifest section | Any multi-stage workflow reuses the same enforcement machinery |
| W5 hardcoded preflight | Preflight deps declared in manifest | Any dependency topology (HTTP services, local files, git remotes, browser CDP) |
| W6 hardcoded promotion | Promotion target descriptor in manifest (`file_path \| registry_api \| webhook \| composite_api`) | Any artifact type can be promoted |
| W7 single LLM provider | `LLMProvider` protocol + per-tier router | Price/quality arbitrage, fallback, local models for sensitive data |
| W8 status clobber | Explicit `SessionStateMachine` with transition guards and an authoritative `transition()` entry point | Auditable, testable, race-free lifecycle |
| W9 no hard timeout | Wrap `run()` in `asyncio.wait_for` | Predictable wall-clock bound |
| W10 migration error masking | Catch only `OperationalError("duplicate column name")` | Fail-fast on real DB problems |
| W11 `---` forgery | Server writes a per-session nonce; experiment script must echo it in the metrics block; signature validated on parse | Cryptographically verifiable results |
| W12 non-atomic promotion | Temp + `os.replace` in deterministic order | Crash-safe promotion |
| W13 broadcaster race | `asyncio.Lock` + snapshot before iteration | Concurrency-correct fan-out |
| W14 SQLite ceiling | `StateStore` protocol; SQLite default, Postgres/Redis optional | Right-sized storage per deployment |
| W15 unbounded lists | Cursor pagination on all list endpoints | Stable performance at scale |
| W16 sync subprocess in async | `asyncio.create_subprocess_exec` for grep/glob | Frees worker threads |
| W18 optional approval | API-layer enforcement: `scope=production` requires `approval.approved=True` + signature | Mandatory audit trail for prod |

The weaknesses don't disappear — they become **named, typed extension
points** with explicit contracts. That is what "turning weaknesses into
advantages" means here: the same property that was a coupling (a
hardcoded list of phases, a hardcoded parser, a hardcoded promotion
target) becomes a *slot* the operator fills per research type.

---

## 6. Proposed universal architecture

### 6.1 Layered design

```
┌──────────────────────────────────────────────────────────────────┐
│  API layer (FastAPI): /research, /skills, /results, /promotion    │
├──────────────────────────────────────────────────────────────────┤
│  Session management + state machine + WebSocket                   │
├──────────────────────────────────────────────────────────────────┤
│  Orchestrator (domain-agnostic tool-use loop)                     │
│   ├── LLM provider router (anthropic | openai | gemini | local)   │
│   ├── Tool registry (bash, read_file, write_file, glob, grep,     │
│   │                   + skill-declared custom tools)              │
│   ├── Budget / timeout / iteration guards                         │
│   ├── Context compaction                                          │
│   ├── Iteration detection (delegates to skill's parser)           │
│   ├── Phase contract enforcement (delegates to skill's phases)    │
│   ├── Duplicate-trial guard (delegates to skill's identity fn)    │
│   └── Insights extraction (delegates to skill's insights prompt)  │
├──────────────────────────────────────────────────────────────────┤
│  Skill runtime (loaded per session from ResearchSkillManifest)    │
│   ├── Command policy extension (allowed scripts/executables)      │
│   ├── Output parser instance                                      │
│   ├── Phase plan instance                                         │
│   ├── Preflight dependency list                                   │
│   ├── Promotion target descriptor                                 │
│   └── Metric schema + gate rules                                  │
├──────────────────────────────────────────────────────────────────┤
│  Storage protocol (SQLite default; Postgres optional)             │
│  Observability (Prometheus / audit / agent_log.jsonl)             │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Key abstractions

**`ResearchSkillManifest`** — declarative description of one research type.
Loaded from `skills/<skill_id>/SKILL.yaml` (+ optional `SKILL.md`,
scripts, parser plugin). Versioned, auditable, hot-loadable.

**`OutputParser` Protocol** — `parse(raw_output: str, *, session_nonce: bytes)
→ IterationResult | None`. Implementations: `DelimitedKVParser`,
`JSONMarkerParser`, `StructuredLogParser`, `ExitCodeOnlyParser`,
skill-supplied custom parser.

**`PhasePlan`** — `list[Phase]` with `id`, `min_iterations`,
`max_iterations`, `evidence_keys`, `next_action`. The orchestrator's
phase-enforcement logic stays; the phase *content* comes from the skill.

**`TrialIdentityFn`** — skill-supplied function (or declarative field
list) that produces the hash inputs for duplicate detection. Default:
hash of (skill_id, subject_id, variant, canonical_config_hash).

**`PromotionTarget`** Protocol — `preview(iteration) → Diff`,
`confirm(iteration, scope, approval) → Result`. Implementations:
`FilePathTarget`, `RegistryAPITarget`, `WebhookTarget`,
`CompositeAPITarget` (the existing mlflow-service path).

**`PreflightCheck`** Protocol — `name`, `run() → CheckResult`.
Implementations: `HTTPHealthCheck`, `LocalFileCheck`,
`GitRemoteCheck`, `BrowserCDPCheck`.

**`LLMProvider`** Protocol — `messages_create(system, messages, tools,
model, max_tokens) → Response` with cost accounting. Implementations:
`AnthropicProvider` (existing), `OpenAIProvider`, `GeminiProvider`,
`LocalProvider` (e.g. llama.cpp / vLLM).

**`SessionStateMachine`** — explicit transitions:
`pending → running ⇄ paused → stopping → stopped`,
`running → completing → completed`,
`running → timing_out → timed_out`,
`running → failing → failed`.
Single authoritative `transition(session_id, event)` entry point that
writes status, emits audit, and broadcasts. Race-free by construction.

**`StateStore`** Protocol — `create_session`, `record_iteration`,
`find_duplicate_trial_identity`, `record_audit_event`, etc.
SQLite implementation today; Postgres/Redis for distributed later.

### 6.3 Session start contract

`POST /api/v1/research/start` becomes:

```json
{
  "skill_id": "ml-direction",
  "skill_version": "1.0.0",
  "subject_id": "DOGE_USDT",
  "variant": "15m",
  "tag": "doge-apr01",
  "focus_hint": "try increasing deadzone_width",
  "max_iterations": 30,
  "max_budget_usd": 10.0,
  "timeout_minutes": 120,
  "quick_mode": false,
  "skill_params": {
    "trading_mode": "margin",
    "agent_strategy": "AGGR",
    "enable_hpo": true,
    "hpo_trials": 20
  }
}
```

`skill_id` replaces `model_type`. `subject_id` + `variant` replace
`instrument` + `timeframe`. `skill_params` is an opaque bag validated
against the skill's declared `param_schema`. The full request/response
contract, legacy-field adapter, and dual-shape responses are specified
in **Section 7**.

### 6.4 Skill discovery

`GET /api/v1/skills` lists installed skills with manifest summaries.
`GET /api/v1/skills/{id}` returns the full manifest. Skills live under
`skills/<id>/` and are discovered at startup (and re-scanned on
`POST /api/v1/skills/reload` in dev). Each skill is a self-contained
directory: `SKILL.yaml`, `SKILL.md`, `scripts/`, optional
`parser.py` / `phases.yaml` / `preflight.yaml`. The complete skill
endpoint surface, form-field descriptor, and UI rendering contract are
specified in **Section 7**.

---

## 7. Universal interface design

This section specifies the concrete interface contracts required so that
**any** research variant is supported natively — not via an adapter shim
running on top of an ML-shaped core, but as a first-class citizen whose
parameters, metrics, phases, and promotion targets are all treated
uniformly by the orchestrator, the API, the persistence layer, and the UI.

The design preserves consistency with existing conventions: `res_<12hex>`
IDs, the `/api/v1` prefix, the `schema_version` pattern, the
`audit_events` action vocabulary, the `ITERATION_RESULT:` marker, the
governed command runner, the manifest+hash provenance pattern, and the
`AgentLogWriter` JSONL format. Nothing here is a greenfield rewrite; it
is a generalization of shapes the service already emits.

### 7.1 Design principles

1. **One session model, many skills.** Every session — ML tuning, prompt
   engineering, code refactor, literature review — is the same row in
   `research_sessions` with the same lifecycle. The skill determines
   *content*, never *shape*. There is no `ml_session` vs `code_session`
   table; there is one `research_sessions` table whose rows are
   parameterized by `skill_id`.

2. **Skill as a typed contract.** A skill is not just a prompt; it
   declares its parameter schema, metric schema, decision vocabulary,
   phase plan, command policy, parser, preflight, and promotion target.
   The orchestrator validates session inputs against the skill's
   contract **before the first turn**, so malformed sessions fail at
   `POST /research/start`, not 10 minutes into a run.

3. **Backward compatibility as aliases, not branches.** Legacy
   `{instrument, timeframe, model_type}` fields are aliased onto
   `{subject_id, variant, skill_id}`. The response payload populates
   **both** shapes so existing clients keep working without code
   changes. There is no `/api/v2` and no parallel handler tree.

4. **Extension via declaration, escape via plugin.** Skills declare
   everything they can in YAML (phases, command policy, parser config,
   preflight). When declaration is insufficient, a small Python plugin
   (`parser.py`, `preflight.py`, `resolve_identity.py`) runs server-side
   under the operator's trust boundary — never inside the agent's
   sandbox. This keeps the agent's attack surface unchanged while
   removing the orchestrator's domain coupling.

5. **Stable schema versioning.** Every persisted artifact carries a
   `schema_version` (`research_session_manifest.v2`,
   `autoresearch_iteration_attempt.v2`, `research_skill.v1`). The
   orchestrator negotiates per-skill version compatibility at session
   start and migrates old rows forward on read.

6. **UI discovers, doesn't hardcode.** The React app never imports a
   skill list and never branches on `model_type`. It calls
   `GET /api/v1/skills` and renders the new-session form from the
   skill's `form_fields`. Skill-specific metrics renderers load lazily
   by `skill_id`, falling back to a generic renderer when absent.

7. **Symmetric request and response shapes.** Every field the client
   can send in `POST /research/start` can appear in the
   `GET /research/{id}` response. There are no write-only or
   read-only surprises except true aliases (legacy fields are
   read-only derivations of canonical fields).

### 7.2 Interface layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  HTTP API (/api/v1)         WebSocket (/ws/events)    UI (React)    │
├─────────────────────────────────────────────────────────────────────┤
│  Skill contract (manifest: param_schema, metric_schema,            │
│  phase_plan, decision_vocabulary, command_policy, parser,          │
│  preflight, promotion_target, insights_prompt, form_fields)        │
├─────────────────────────────────────────────────────────────────────┤
│  Orchestrator ⇄ SkillRuntime protocol (Python Protocol)            │
├─────────────────────────────────────────────────────────────────────┤
│  Persisted artifacts                                                │
│    research_sessions, iterations, audit_events,                     │
│    runtime_commands, planned_trials, promotions,                    │
│    research_session_manifest.vN (workspace + DB),                   │
│    autoresearch_iteration_attempt.vN (workspace + DB)               │
└─────────────────────────────────────────────────────────────────────┘
```

Each layer is specified below.

### 7.3 Session identity and parameter contract

**Canonical fields** (skill-agnostic, owned by the orchestrator):

| Field | Type | Replaces (legacy) | Owner | Notes |
|---|---|---|---|---|
| `id` | str | — | orchestrator | `res_<12hex>`, unchanged |
| `skill_id` | str | `model_type` | skill contract | references an installed skill |
| `skill_version` | str | — | skill contract | semver; default = latest installed |
| `subject_id` | str | `instrument` | skill enumerator | the thing being researched |
| `variant` | str | `timeframe` | skill enumerator | sub-dimension of the subject |
| `tag` | str | `tag` | caller | unchanged |
| `focus_hint` | str? | `focus_hint` | caller | unchanged |
| `quick_mode` | bool | `quick_mode` | caller | loop-level, skill-agnostic |
| `max_iterations` | int | `max_iterations` | caller | loop-level |
| `max_budget_usd` | float | `max_budget_usd` | caller | loop-level |
| `timeout_minutes` | int | `timeout_minutes` | caller | loop-level |
| `skill_params` | object | `trading_mode`, `agent_strategy`, `initial_balance`, `enable_hpo`, `hpo_trials`, `hpo_timesteps` | caller (validated by `skill.param_schema`) | opaque bag; skill owns its schema |
| `resumed_from` | str? | `resumed_from` | caller | unchanged |
| `pipeline_id` | str? | `pipeline_id` | orchestrator | unchanged |
| `workspace_path` | str | `workspace_path` | orchestrator | rendered from skill template |

**`ResearchConfig` (Python) — generalized:**

```python
@dataclass
class ResearchConfig:
    id: str
    skill_id: str
    skill_version: str
    subject_id: str
    variant: str
    tag: str = ""
    quick_mode: bool = False
    max_iterations: int = 30
    max_budget_usd: float = 10.0
    timeout_s: int = 0
    focus_hint: Optional[str] = None
    workspace_path: str = ""
    skill_params: Dict[str, Any] = field(default_factory=dict)
    resumed_from: Optional[str] = None
    pipeline_id: Optional[str] = None

    # ── Legacy aliases (read-only, for backward compatibility) ──────
    @property
    def model_type(self) -> str:
        return _legacy_model_type_for_skill(self.skill_id)

    @property
    def instrument(self) -> str:
        return self.subject_id

    @property
    def timeframe(self) -> str:
        return self.variant
```

The ML-specific flat fields are removed from the dataclass and live
exclusively in `skill_params`. Existing code paths that read
`config.trading_mode` migrate mechanically to
`config.skill_params["trading_mode"]`. The orchestrator never reads
`skill_params` directly — it hands the whole bag to the loaded
`SkillRuntime`, which is the only consumer of skill-specific fields.

### 7.4 Skill manifest as interface contract

The manifest (full reference in Section 8) carries five sections that
are, in effect, the interface between skill authors and the rest of the
system:

**`param_schema`** — JSON Schema validating `skill_params` at session
start. Validated before any workspace is created, so a bad request
fails fast with a 422 and a pointer to the offending field.

```yaml
param_schema:
  type: object
  additionalProperties: false
  properties:
    trading_mode:        { type: string, enum: [stock, margin], default: margin }
    agent_strategy:      { type: string, enum: [AGGR, CONS, BALA, SCAL] }
    initial_balance:     { type: number, minimum: 0 }
    enable_hpo:          { type: boolean, default: false }
    hpo_trials:          { type: integer, minimum: 1, maximum: 100, default: 20 }
    hpo_timesteps:       { type: integer, minimum: 1000, default: 50000 }
  required: []
```

**`metric_schema`** — declares what `metrics_json` should contain and
how to chart it. This is what makes the UI skill-aware without
hardcoding.

```yaml
metric_schema:
  primary:
    field: primary_metric
    label: "Walkforward Mean AUC"
    direction: higher_is_better
    format: ".4f"
  gates:
    - { field: all_gates_passed, label: "All Gates", kind: boolean_badge }
  chart_series:
    - { field: walkforward_mean_auc, label: "OOS AUC" }
    - { field: sharpe,                label: "Sharpe", axis: right }
  iteration_table_columns:
    - { field: primary_metric,   label: "Metric" }
    - { field: all_gates_passed, label: "Gates", kind: icon }
    - { field: folds_passed,     label: "Folds" }
    - { field: training_time_s,  label: "Time", format: duration_seconds }
```

**`decision_vocabulary`** — closed set of allowed `decision` values.
The orchestrator rejects unknown values; skills may extend the base
set in their manifest.

```yaml
decision_vocabulary:
  base: [keep, discard, duplicate_rejected, baseline_linked,
         evidence_replayed, manual_review]
  extensions: [hpo_screening]   # skill-specific additions
```

**`phase_plan` with `evidence_keys` and `advancement_rule`** — the
contract for when a phase is complete. Already present in the existing
direction plan; made explicit and declarative.

```yaml
phase_plan:
  - id: tabular_sweeps
    min_iterations: 6
    max_iterations: 40
    evidence_keys: [tabular_sweep_variant]
    advancement_rule: any       # any listed key present → phase complete
    stagnation_exempt: false
```

**`form_fields`** — UI hint for rendering the new-session form. Pure
presentation; the source of truth for validation is `param_schema`.

```yaml
form_fields:
  - name: trading_mode
    type: enum
    label: "Trading Mode"
    options: [stock, margin]
    default: margin
    group: "RL Settings"
    visible_when: { skill_id: ml-rl }
```

### 7.5 Orchestrator ⇄ SkillRuntime protocol (Python)

At session start the manifest is materialized into a `SkillRuntime`
instance. This is the single contract between skill author and
orchestrator — every domain-specific decision the orchestrator used to
make via `if config.model_type == ...` is moved into a method on this
protocol.

```python
class SkillRuntime(Protocol):
    """Contract every research skill implements.

    Materialized once per session from ResearchSkillManifest. All
    methods are deterministic and side-effect-free unless documented
    otherwise; the orchestrator owns persistence, audit, and execution.
    """

    # ── Identity ──────────────────────────────────────────────────
    @property
    def skill_id(self) -> str: ...
    @property
    def skill_version(self) -> str: ...

    # ── Prompt construction ───────────────────────────────────────
    def system_prompt(self) -> str: ...
    def directive_prompt(self, config: ResearchConfig) -> str: ...
    def resume_prompt(
        self, config: ResearchConfig, parent: SessionRecord,
        parent_iterations: list[IterationRecord],
    ) -> str: ...

    # ── Command policy ────────────────────────────────────────────
    def command_policy_extension(self) -> CommandPolicyExtension:
        """Allowed scripts/executables/copyable-files/readable-files
        that extend the orchestrator's base policy."""

    # ── Iteration detection ───────────────────────────────────────
    def parse_iteration(
        self, raw_output: str, *,
        session_nonce: bytes,
        config_snapshot: Optional[str],
    ) -> Optional[IterationResult]:
        """Parse experiment output into a structured result.
        Validates session_nonce to reject forged metrics blocks."""

    def marker_file_paths(self, config: ResearchConfig) -> list[Path]:
        """Fallback iteration sources (last_metrics.txt, results.json)."""

    # ── Phase contract ────────────────────────────────────────────
    def phase_plan(self) -> list[Phase]: ...
    def phase_advancement_rule(self, phase_id: str) -> AdvancementRule: ...

    # ── Trial identity (dedup) ────────────────────────────────────
    def trial_identity(
        self, config: ResearchConfig, *,
        command: str,
        config_snapshot: Optional[str],
        planned_trial: Optional[dict] = None,
    ) -> dict: ...

    # ── Preflight ─────────────────────────────────────────────────
    def preflight_checks(self) -> list[PreflightCheck]: ...

    # ── Promotion ─────────────────────────────────────────────────
    def promotion_target(self) -> PromotionTarget: ...

    # ── Insights ──────────────────────────────────────────────────
    def insights_prompt(
        self, session: SessionRecord,
        iterations: list[IterationRecord],
    ) -> str: ...

    # ── Cross-session memory ──────────────────────────────────────
    def research_resume_path(self, config: ResearchConfig) -> Path: ...
    def generate_research_resume(
        self, config: ResearchConfig, store: StateStore,
    ) -> str: ...

    # ── Structured HPO (optional) ─────────────────────────────────
    def structured_hpo_plan(
        self, config: ResearchConfig,
    ) -> Optional[StructuredHPOPlan]: ...

    # ── Subjects / variants enumeration ───────────────────────────
    def list_subjects(self) -> list[SubjectDescriptor]: ...
    def list_variants(self, subject_id: str) -> list[VariantDescriptor]: ...
```

The orchestrator's main loop becomes structurally flat — every
domain-specific branch moves into a `skill.*` call:

```python
skill = self._skill_loader.load(config.skill_id, config.skill_version)
system_prompt = skill.system_prompt()
user_prompt   = skill.directive_prompt(config)

for turn in range(max_turns):
    # ... budget / timeout / pause / stop guards (skill-agnostic) ...
    response = await self._llm.messages_create(
        system=system_prompt, messages=messages,
        tools=self._tools_for(skill),
    )
    for block in response.tool_use_blocks:
        result = await self._execute_tool(
            block, skill=skill, config=config,
            policy=skill.command_policy_extension(),
        )
        iteration = skill.parse_iteration(
            result.content,
            session_nonce=session.nonce,
            config_snapshot=pending_snapshot,
        )
        if iteration:
            self._record_iteration(
                config, iteration,
                phase_plan=skill.phase_plan(),
                identity=skill.trial_identity(config, ...),
            )
```

A grep for `config.model_type ==` in the orchestrator should return
zero hits after the refactor. That is the operational definition of
"domain-agnostic".

### 7.6 HTTP API surface

**New endpoints (additive):**

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/skills` | List installed skills (`id`, `version`, `display_name`, `category`, `latest`) |
| `GET` | `/api/v1/skills/{id}` | Full manifest with defaults applied |
| `GET` | `/api/v1/skills/{id}/param-schema` | JSON Schema for `skill_params` |
| `GET` | `/api/v1/skills/{id}/form-fields` | UI form descriptor |
| `GET` | `/api/v1/skills/{id}/metric-schema` | Metric/chart descriptor |
| `GET` | `/api/v1/skills/{id}/versions` | Installed versions |
| `GET` | `/api/v1/skills/{id}/changelog` | Version-to-version change notes |
| `POST` | `/api/v1/skills/reload` | Dev-mode hot reload (auth-gated) |
| `GET` | `/api/v1/subjects?skill_id=…` | Subject universe for a skill (legacy alias `/api/v1/instruments`) |
| `GET` | `/api/v1/subjects/{id}/variants?skill_id=…` | Variants for a subject |

**Adapted existing endpoints (extended, not broken):**

| Method | Path | Change |
|---|---|---|
| `POST` | `/api/v1/research/start` | Accepts the new canonical shape; the legacy shape is auto-detected by presence of `model_type` and translated. Response carries **both** shapes. |
| `GET` | `/api/v1/research` | Adds `?skill_id=`, `?subject_id=`, `?variant=` filters alongside the legacy `?model_type=`, `?instrument=`, `?timeframe=`. Adds cursor pagination. |
| `GET` | `/api/v1/research/{id}` | Response carries `skill_id`, `skill_version`, `subject_id`, `variant`, `skill_params`, plus legacy aliases derived from them. |
| `GET` | `/api/v1/research/{id}/iterations` | Same row shape; `metrics_json` content is skill-declared. Adds top-level `evidence_keys: list[str]` and `skill_phase: str` so clients don't have to dig into `metrics_json`. |
| `GET` | `/api/v1/research/{id}/state` | `phase_state` is skill-driven; adds a `skill_phase_plan` mirror so clients can render the active plan without a separate fetch. |
| `POST` | `/api/v1/research/{id}/promote/preview` | Response `target_kind` discriminator (`file_path` / `registry_api` / `webhook` / `git_branch`) selects the diff format. |
| `POST` | `/api/v1/research/{id}/promote/confirm` | Same request shape; delegation target chosen by skill's promotion config. |
| `GET` | `/api/v1/models` | Legacy alias for `GET /api/v1/skills` (kept indefinitely). |
| `GET` | `/api/v1/instruments` | Legacy alias for `GET /api/v1/subjects` (kept indefinitely). |

No URL is removed; no event name is renamed.

### 7.7 Request and response schemas

**`POST /api/v1/research/start` — canonical request:**

```json
{
  "skill_id": "ml-direction",
  "skill_version": "1.0.0",
  "subject_id": "DOGE_USDT",
  "variant": "15m",
  "tag": "doge-apr01",
  "focus_hint": "try increasing deadzone_width",
  "max_iterations": 30,
  "max_budget_usd": 10.0,
  "timeout_minutes": 120,
  "quick_mode": false,
  "skill_params": {
    "trading_mode": "margin",
    "agent_strategy": "AGGR",
    "enable_hpo": true,
    "hpo_trials": 20
  },
  "resumed_from": null,
  "pipeline": null
}
```

**`POST /api/v1/research/start` — legacy request (auto-translated):**

```json
{
  "instrument": "DOGE_USDT",
  "timeframe": "15m",
  "model_type": "direction",
  "trading_mode": "margin",
  "agent_strategy": "AGGR",
  "enable_hpo": true
}
```

Server-side translation table (applied at the API boundary, before the
orchestrator sees the request):

| Legacy field | Canonical field | Notes |
|---|---|---|
| `model_type: direction\|volatility\|rl` | `skill_id: ml-direction\|ml-volatility\|ml-rl` | 1:1 map in a legacy-alias registry |
| `instrument` | `subject_id` | verbatim |
| `timeframe` | `variant` | verbatim |
| `trading_mode`, `agent_strategy`, `initial_balance` | `skill_params.{name}` | lifted into the opaque bag |
| `enable_hpo`, `hpo_trials`, `hpo_timesteps` | `skill_params.{name}` | lifted |
| `max_iterations`, `max_budget_usd`, `timeout_minutes`, `quick_mode`, `tag`, `focus_hint` | unchanged | verbatim |

**Response (201 Created) — carries both shapes:**

```json
{
  "id": "res_a1b2c3d4e5f6",
  "skill_id": "ml-direction",
  "skill_version": "1.0.0",
  "subject_id": "DOGE_USDT",
  "variant": "15m",
  "instrument": "DOGE_USDT",
  "timeframe": "15m",
  "model_type": "direction",
  "tag": "doge-apr01",
  "status": "running",
  "quick_mode": false,
  "max_iterations": 30,
  "max_budget_usd": 10.0,
  "workspace_path": "runs/ml-direction/DOGE_USDT/15m",
  "manifest_path": "runs/.../research_session_manifest.v2.json",
  "manifest_hash": "sha256:abc123...",
  "started_at": "2026-06-28T12:00:00Z",
  "skill_params": { "trading_mode": "margin", "enable_hpo": true },
  "preflight": { "schema_version": "research_preflight.v1", "status": "ready" },
  "links": {
    "self":            "/api/v1/research/res_a1b2c3d4e5f6",
    "iterations":      "/api/v1/research/res_a1b2c3d4e5f6/iterations",
    "state":           "/api/v1/research/res_a1b2c3d4e5f6/state",
    "agent_log":       "/api/v1/research/res_a1b2c3d4e5f6/agent-log",
    "promote_preview": "/api/v1/research/res_a1b2c3d4e5f6/promote/preview",
    "ws":              "/ws/events"
  }
}
```

Legacy clients read `instrument`/`timeframe`/`model_type`; new clients
read `skill_id`/`subject_id`/`variant`. Both are always populated.

**`GET /api/v1/skills` response:**

```json
{
  "skills": [
    {
      "id": "ml-direction",
      "version": "1.0.0",
      "display_name": "ML Direction Model Tuning",
      "description": "Tune price-direction prediction models via walk-forward training.",
      "category": "ml/trading",
      "tags": ["ml", "trading", "direction"],
      "latest": true,
      "installed_at": "2026-06-28T10:00:00Z",
      "llm_provider": "anthropic",
      "promotion_target_kind": "file_path",
      "links": { "self": "/api/v1/skills/ml-direction" }
    },
    {
      "id": "prompt-engineering",
      "version": "0.3.0",
      "display_name": "Prompt Engineering Research",
      "category": "nl/eval",
      "latest": true,
      "promotion_target_kind": "registry_api",
      "links": { "self": "/api/v1/skills/prompt-engineering" }
    }
  ]
}
```

**`GET /api/v1/skills/{id}/form-fields` response** (drives the
new-session form dynamically):

```json
{
  "skill_id": "ml-direction",
  "skill_version": "1.0.0",
  "fields": [
    { "name": "subject_id", "type": "enum_dynamic",
      "label": "Instrument", "required": true,
      "options_url": "/api/v1/subjects?skill_id=ml-direction" },
    { "name": "variant", "type": "enum",
      "label": "Timeframe", "required": true,
      "options": ["5m", "15m", "1h", "4h"] },
    { "name": "tag", "type": "string", "required": false },
    { "name": "focus_hint", "type": "text", "required": false },
    { "name": "max_iterations", "type": "integer",
      "default": 30, "min": 1, "max": 100 },
    { "name": "max_budget_usd", "type": "number",
      "default": 10.0, "min": 1, "max": 100 },
    { "name": "quick_mode", "type": "boolean", "default": false },
    { "name": "enable_hpo", "type": "boolean",
      "default": false, "group": "Advanced" },
    { "name": "trading_mode", "type": "enum",
      "options": ["stock", "margin"], "default": "margin",
      "visible_when": { "skill_id": "ml-rl" } }
  ]
}
```

**`GET /api/v1/research/{id}/iterations` — extended row shape:**

```json
{
  "iterations": [
    {
      "iteration": 7,
      "skill_phase": "tabular_sweeps",
      "evidence_keys": ["tabular_sweep_variant"],
      "primary_metric": 0.5868,
      "metric_name": "walkforward_mean_auc",
      "direction": "higher_is_better",
      "all_gates_passed": true,
      "decision": "keep",
      "description": "Increased deadzone_width 0.02 → 0.04",
      "training_time_s": 342.1,
      "api_cost_usd": 0.21,
      "config_snapshot": "...",
      "canonical_config_hash": "sha256:...",
      "trial_identity_hash": "sha256:...",
      "attempt_snapshot_path": "...",
      "attempt_snapshot_hash": "sha256:...",
      "consistency_report": { "schema_version": "autoresearch_consistency.v1", "blockers": [] },
      "metrics": { "walkforward_mean_auc": 0.5868, "folds_passed": "5/5", "sharpe_cv": 0.18 },
      "created_at": "2026-06-28T12:14:32Z"
    }
  ],
  "next_cursor": null
}
```

The new top-level `skill_phase` and `evidence_keys` are projections of
fields previously buried in `metrics_json` — surfaced so the UI and
API clients don't need skill-specific parsing to render phase progress.
The `metrics` object's inner shape is declared by the skill's
`metric_schema`.

**`POST /api/v1/research/{id}/promote/preview` — multi-kind response:**

```json
// target_kind = file_path
{
  "target_kind": "file_path",
  "scope": "development",
  "iteration": 7,
  "target_path": "configs/subject_configs/DOGE_USDT_15m.yaml",
  "diff_format": "unified_text",
  "diff": "--- a/configs/...\n+++ b/configs/...\n@@ ...",
  "approval_required": false,
  "evidence": { "consistency_report": {}, "gate_results": {} }
}

// target_kind = registry_api  (e.g. mlflow composite)
{
  "target_kind": "registry_api",
  "scope": "production",
  "iteration": 7,
  "registry": "mlflow-service",
  "composite_id": "42",
  "model_registry_name": "direction_doge_usdt_15m",
  "from_version": "5",
  "to_version": "6",
  "diff_format": "registry_version_bump",
  "diff": { "added_params": {}, "removed_params": [], "metric_delta": {} },
  "approval_required": true,
  "delegate_url": "http://mlflow-service:8000/api/v1/composites/42/promote"
}

// target_kind = git_branch  (e.g. code-refactor skill)
{
  "target_kind": "git_branch",
  "scope": "development",
  "iteration": 12,
  "repository": "internal/traid-platform",
  "base_branch": "main",
  "proposed_branch": "research/res_.../refactor-iter-12",
  "diff_format": "unified_text",
  "diff": "...",
  "approval_required": false,
  "pr_template": { "title": "...", "body": "..." }
}
```

### 7.8 WebSocket event contract

Events stay on `/ws/events` with the existing name vocabulary
(`research_started`, `iteration_recorded`, `research_completed`,
`research_failed`, `runtime_command_*`, `broadcaster.ping`). Every
event payload gains three top-level fields so clients can dispatch
rendering without a separate fetch:

```json
{
  "event": "iteration_recorded",
  "research_id": "res_...",
  "skill_id": "ml-direction",
  "skill_version": "1.0.0",
  "skill_phase": "tabular_sweeps",
  "iteration": 7,
  "primary_metric": 0.5868,
  "metric_name": "walkforward_mean_auc",
  "direction": "higher_is_better",
  "all_gates_passed": true,
  "decision": "keep",
  "evidence_keys": ["tabular_sweep_variant"],
  "training_time_s": 342.1,
  "total_api_cost_usd": 2.34,
  "metrics": { },
  "timestamp": "2026-06-28T12:14:32Z"
}
```

`metrics` is an instance of the skill's `metric_schema`. The UI uses
`skill_id` to look up the renderer. Skills that want custom events
(e.g. `hpo_study_completed`) declare them in the manifest under
`custom_events` and the broadcaster passes them through unchanged.

### 7.9 UI contract (dynamic, skill-aware)

The React app becomes skill-aware without hardcoding skills:

1. **Dashboard** — session cards group/filter by `skill_id`. Each skill
   gets a color and icon from the manifest's `ui.appearance` block.
2. **NewResearch** — fully dynamic. On mount: `GET /api/v1/skills`,
   render a skill picker. On skill select:
   `GET /api/v1/skills/{id}/form-fields`, render the form. Conditional
   fields (`visible_when`) and dynamic option URLs (`options_url`) are
   honored. The submitted JSON is the canonical session-start request.
3. **ResearchDetail** — the four tabs (State / Metrics Chart /
   Iterations / Agent Log) stay. Each tab fetches the skill manifest
   once and uses `metric_schema` to configure chart series, iteration
   table columns, and the gates badge.
4. **MetricsChart** — `chart_series` from `metric_schema` drives the
   lines and axes. The `primary` field is the headline metric.
5. **IterationsTable** — `iteration_table_columns` drives columns.
   Unknown metric fields collapse into an expandable "details" row.
6. **Promotion modal** — branches on `target_kind` from the preview
   response. A small renderer registry maps each kind to a component
   (`FilePathDiff`, `RegistryVersionBump`, `GitDiff`, `WebhookJson`).
7. **History** — filter by skill; columns adapt the same way as
   IterationsTable.

Skill-specific renderers (e.g. a fold-stability heatmap for ML skills)
load lazily by `skill_id` from a `ui/skill-plugins/<skill_id>/`
directory, falling back to the generic renderer when absent. This
keeps the core UI domain-agnostic while allowing rich skill-specific
visualizations where they earn their complexity.

### 7.10 Promotion interface (per target kind)

Each target implements a two-method protocol declared by the skill:

```python
class PromotionTarget(Protocol):
    kind: str  # "file_path" | "registry_api" | "webhook" | "git_branch" | ...

    def preview(
        self, session: SessionRecord, iteration: IterationRecord,
        scope: str,
    ) -> PromotionPreview:
        """Compute a diff/summary without side effects."""

    def confirm(
        self, session: SessionRecord, iteration: IterationRecord,
        scope: str, approval: Optional[Approval],
    ) -> PromotionResult:
        """Execute the promotion. Approval required when
        ``scope in approval_required_scopes``."""
```

Built-in implementations cover the common cases; skills supply a
`promotion_target.plugin` for novel targets. The current
`ConfigPromoter` becomes `FilePathPromotionTarget`; the mlflow-service
delegation becomes `RegistryAPIPromotionTarget`. Atomic write
(temp + `os.replace`) lives in the `FilePathPromotionTarget`, fixing
W12 as a side effect.

### 7.11 Subject and variant enumeration

`GET /api/v1/instruments` currently globs config files. Generalized:

```yaml
# in the skill manifest
subjects:
  enumerator: scripts/list_subjects.py    # returns [{"id": "DOGE_USDT", "label": "..."}]
  cache_ttl_s: 60
variants:
  static: ["5m", "15m", "1h", "4h"]       # or scripts/list_variants.py
```

`GET /api/v1/subjects?skill_id=ml-direction` calls the enumerator.
`GET /api/v1/instruments` remains as a legacy alias returning the
union of subjects across ML skills.

### 7.12 Backward compatibility guarantees

To preserve code consistency with existing callers (UI, runbooks,
operator muscle memory, openapi consumers):

1. **No URL changes.** All existing paths remain. New paths are
   additive.
2. **No ID format changes.** `res_<12hex>` session IDs,
   `pipe_<…>` pipeline IDs, integer iteration numbers.
3. **No event name changes.** WebSocket events keep their names;
   payloads only gain fields.
4. **Dual-shape responses.** Every session and iteration response
   carries both canonical (`skill_id`/`subject_id`/`variant`) and
   legacy (`model_type`/`instrument`/`timeframe`) fields. Clients can
   read either.
5. **Legacy request acceptance.** `POST /api/v1/research/start`
   accepts both shapes; the server detects via presence of
   `model_type` vs `skill_id`.
6. **Schema version bumps, never silent rewrites.** Persisted
   artifacts that gain fields bump their `schema_version`
   (`research_session_manifest.v1` → `v2`,
   `autoresearch_iteration_attempt.v1` → `v2`). Old rows are migrated
   by `ResultsStore.initialize()`; reads of old rows synthesize
   missing fields with defaults.
7. **Audit vocabulary stable.** `audit_events.action` keeps existing
   values; new actions are additive.
8. **No new required fields on existing clients.** Any field not
   supplied defaults; the session starts with the skill's declared
   defaults applied.

### 7.13 Versioning policy

- **Skill manifest schema version** (`research_skill.v1`): bumps when
  the manifest schema changes. The loader supports `N` and `N−1`.
- **Skill content version** (`version: 1.0.0` in the manifest):
  semver, operator-controlled. Multiple versions of the same
  `skill_id` can coexist; sessions pin to a specific version.
- **Persisted artifact versions** (`research_session_manifest.v2`,
  `autoresearch_iteration_attempt.v2`, …): bump on schema change,
  migrated forward, never rewritten retroactively.
- **API version** (`/api/v1`): unchanged. A future `/api/v2` would
  be additive, not breaking.

### 7.14 What "native support for all variants" means concretely

After this interface is in place, the operational test of
"generalization" is concrete and falsifiable:

- A new skill is added by creating `skills/<id>/` with `SKILL.yaml`,
  `SKILL.md`, and scripts — **zero orchestrator code changes**.
- The orchestrator source contains **zero** references to
  `direction`, `volatility`, `rl`, `instrument`, `timeframe`,
  `prepare.py`, or `train.yaml`.
- A grep for `config.model_type`, `config.instrument`,
  `config.timeframe` in `src/core/orchestrator.py` returns zero hits.
- The same UI renders every skill's new-session form, metrics chart,
  iteration table, and promotion modal driven entirely by
  `GET /api/v1/skills/{id}` responses.
- A session for a non-ML skill (e.g. `prompt-engineering`) and a
  session for an ML skill (e.g. `ml-direction`) are
  indistinguishable in `research_sessions`, `iterations`,
  `audit_events`, and the WebSocket stream except by their
  `skill_id` field.

Anything short of that means the generalization is incomplete.

---

## 8. Domain skills and auto-initialization

Section 7 specified the *runtime contract* a skill exposes to the
orchestrator. This section specifies the other half of what makes the agent
universal: **a skill is a domain bootstrap kit that initializes the agent
for its domain automatically**, so that "select a domain → agent is ready"
is a single operator action, and adding a new domain does not require
writing orchestrator code.

### 8.1 A skill is more than a manifest

A skill directory is a self-contained package with four logically separable
parts:

| Part | Files | Role |
|---|---|---|
| **Contract** | `SKILL.yaml` | Declarative runtime contract (param schema, metric schema, phase plan, command policy, parser, preflight, promotion target). What Section 7 specified. |
| **Expertise** | `SKILL.md`, `knowledge/` | The domain knowledge that makes the agent effective: primer, best practices, known anti-patterns, parameter heuristics, prior findings. |
| **Harness** | `bootstrap.py`, `scaffold/`, `eval/`, `tools/` | Executable machinery: workspace scaffolding, the evaluation script that produces measurable output (the generalization of `prepare.py`), optional domain-specific tools. |
| **Memory** | `knowledge/`, `research_resume` | Cross-session learnings. Insights from prior sessions feed back into the knowledge base, so the skill gets smarter over time. |

```
skills/<skill_id>/
├── SKILL.yaml              # the contract (Section 7/9)
├── SKILL.md                # domain expertise primer → injected into system prompt
├── CHANGELOG.md            # version history
├── bootstrap.py            # one-shot initializer run at session start
├── scaffold/               # workspace template (rendered per session)
│   └── …
├── knowledge/              # domain knowledge base (RAG corpus / static docs)
│   ├── primer.md
│   ├── heuristics.yaml
│   └── prior_findings/
├── eval/                   # the evaluation harness (≈ prepare.py)
│   └── run.py
├── tools/                  # optional domain-specific tool plugins
├── parser.py               # optional parser plugin (when YAML config is insufficient)
├── preflight.py            # optional preflight plugin
└── resolve_identity.py     # optional trial-identity plugin
```

The contract alone is enough to *run* a session whose workspace is already
prepared. The other three parts are what make a skill **auto-initializing**:
the operator picks a domain, and the skill prepares the workspace, loads
expertise, configures tools, and seeds the search — without the operator
writing setup scripts or hand-crafting prompts.

### 8.2 The initialization lifecycle

When a session starts, four things happen before the first LLM turn:

1. **Domain resolution** — `skill_id` + `skill_version` resolve to an
   installed skill directory. If the caller passed a natural-language
   `goal` instead, the domain classifier (§8.5) proposes a skill.

2. **Bootstrap** — `bootstrap.py` runs once in the session workspace with
   the resolved `skill_params`. It:
   - renders the workspace from `scaffold/` (copy template, substitute
     `{subject_id}`, `{variant}`, params);
   - loads the `knowledge/` corpus into a session-scoped context store;
   - assembles the system prompt = base-agent prompt + `SKILL.md` primer +
     subject-specific context + active phase contract;
   - validates the eval harness is callable (a dry-run smoke check);
   - writes a `session_bootstrap.v1` artifact recording exactly what was
     prepared (rendered file list, knowledge-base hash, assembled
     prompt hash, resolved tool config, seed search space).

3. **Tool registration** — the skill's declared tools (base set + optional
   `tools/` plugins) are registered; the command policy is extended with
   the skill's allow-list. The agent never sees tools the skill did not
   declare.

4. **Search-space seeding** — the skill's `seed_search` section (static
   candidates or `scripts/seed_search.py`) produces the initial candidate
   set / first phase plan. For structured-search skills this becomes the
   bounded `planned_trials` list the orchestrator enforces.

Only then does the tool-use loop begin. The operator's view is: pick a
domain, pick a subject, click start. Everything else is the skill's job.

### 8.3 The `session_bootstrap.v1` artifact

Every session records what its skill prepared, for reproducibility and
audit:

```json
{
  "schema_version": "session_bootstrap.v1",
  "skill_id": "prompt-engineering",
  "skill_version": "0.3.0",
  "rendered_files": ["eval/run.py", "configs/baseline.yaml", "data/eval_set.jsonl"],
  "knowledge_base_hash": "sha256:…",
  "system_prompt_hash": "sha256:…",
  "tool_config": { "base": ["bash","read_file","write_file","glob","grep"],
                   "skill": ["run_eval"] },
  "command_policy_extension_hash": "sha256:…",
  "seed_search": { "kind": "static", "count": 8 },
  "preflight_results": { "status": "ready" },
  "bootstrapped_at": "2026-06-28T12:00:00Z"
}
```

This makes the skill's effect on the session inspectable and replayable —
the same property the existing `research_session_manifest.v1` gives the
server's session setup, generalized to the skill layer.

### 8.4 Domain taxonomy (research categories)

Not all domains are ad-hoc. Research workflows cluster into categories
with shared loop shapes. A skill declares its `category`; the orchestrator
applies category-level defaults, and the UI groups skills sensibly:

| Category | Loop shape | Typical primary metric | Typical promotion target |
|---|---|---|---|
| `optimization` | prepare candidate → measure | objective value (AUC, TPS, latency) | config file / parameter registry |
| `generative` | generate artifact → evaluate against rubric | eval score / pass rate | artifact registry / git PR |
| `exploratory` | query sources → analyze → synthesize | coverage / recall / findings count | report / knowledge graph |
| `validation` | run checks → aggregate against criteria | gate pass rate / defect count | decision record / sign-off |
| `design` | enumerate options → score → recommend | expected utility / information gain | design doc / experiment config |

```yaml
# in SKILL.yaml
category: generative
```

The category is advisory metadata: it drives UI grouping and default
renderers, but the orchestrator does not branch on it. A skill that
genuinely mixes categories (e.g. exploratory research that ends by
promoting a synthesized artifact) just declares the dominant one.

### 8.5 Auto-domain detection (goal → skill)

For operator convenience, `POST /api/v1/research/start` accepts an optional
natural-language `goal` instead of an explicit `skill_id`:

```json
{ "goal": "find the best system prompt for our customer-support chatbot",
  "subject_id": "support-bot-v2",
  "eval_set": "s3://evals/support_evals.jsonl" }
```

A lightweight domain classifier maps the goal to a ranked list of installed
skills. The classifier can be implemented as embedding similarity against
installed skills' `description` + `category`, optionally refined by a single
small LLM call:

```json
{ "matched_skills": [
    { "skill_id": "prompt-engineering", "score": 0.92,
      "confidence": "high",
      "suggested_params": { "eval_set": "s3://evals/support_evals.jsonl" } },
    { "skill_id": "generative-content", "score": 0.41,
      "confidence": "low" }
  ],
  "auto_select_threshold": 0.85 }
```

If the top match exceeds `auto_select_threshold`, the session proceeds with
it; otherwise the operator confirms. The classifier's choice and score are
written to `audit_events` so the mapping is auditable and tunable. When no
installed skill matches, the system offers to **generate** one (§8.6).

This is the user-facing expression of "universal": the operator states a
goal in their own words; the system picks (or drafts) the right kind of
research and bootstraps it.

### 8.6 LLM-assisted skill authoring (the skill generator)

Adding a domain should not require a domain expert to learn YAML or write
a bootstrap script. The universal agent can research how to research a
domain: a **skill generator** is itself a meta-skill (`meta:skill-generator`)
that turns a domain description into a reviewable draft skill.

**Inputs** (operator-supplied):
- a natural-language description of the domain and goal;
- one to three example "good" runs, or an eval script / eval examples;
- the target promotion surface (file path, registry, git, webhook);
- constraints (budget ceiling, allowed tools, data location).

**Outputs** (a draft skill directory under `skills/_drafts/<id>/`):
- `SKILL.yaml` with proposed `param_schema`, `metric_schema`,
  `category`, `phase_plan`, `command_policy`, `output_parser`,
  `preflight`, `promotion_target`;
- `SKILL.md` domain primer drafted from the description plus the
  generator's own knowledge of the category's best practices;
- `bootstrap.py` and `scaffold/` drafted from the category template;
- `eval/` harness wrapping the user-supplied eval (or a generated one
  if only examples were given);
- a proposed initial `seed_search`.

**Review and promotion.** The draft is reviewed through the same promotion
mechanism skills themselves use (§8.7): an operator inspects the generated
manifest, runs a dry bootstrap, and either promotes the draft to
`reviewed` or sends it back for another generation pass with feedback. The
recursion is deliberate and clean — *promoting a skill uses the same
preview/confirm/scopes flow as promoting a research artifact*.

Over time, the generator improves because (a) the category templates
accumulate vetted patterns, and (b) `insights` and `research_resume`
output from successful sessions in a category feed back into that
category's template.

### 8.7 Skill lifecycle and promotion

Skills are themselves versioned, promoted artifacts with a lifecycle:

| Status | Meaning | Can bootstrap sessions? |
|---|---|---|
| `draft` | generated, unreviewed | only in dev, with explicit opt-in |
| `reviewed` | operator-approved | yes (dev / staging) |
| `stable` | battle-tested across N sessions | yes (default for new sessions) |
| `deprecated` | superseded by a newer version | existing sessions continue; new sessions blocked |

- Each promotion bumps semver; multiple versions of the same `skill_id`
  coexist installed; sessions pin a specific `skill_version`.
- `POST /api/v1/skills/{id}/promote/preview` and `/confirm` reuse the
  promotion-target machinery (§7.10) with `target_kind: skill_registry` —
  the artifact being promoted is the skill directory itself.
- Skill promotion is audited in `audit_events` like any other
  consequential action.

### 8.8 Feedback loop: sessions make skills smarter

Every completed session produces two artifacts that feed back into the
skill's knowledge base rather than dying with the session:

- **`insights`** (≤500 chars) — what was learned about the domain on this
  run (parameter sensitivities, dead ends, surprises). Already implemented.
- **`research_resume`** — structured cross-session memory keyed by
  `(skill_id, subject_id, variant)`. Already implemented for ML; generalized
  to every skill.

After a session completes, its insights are appended to
`skills/<id>/knowledge/prior_findings/<subject_id>_<variant>.md` (or
flagged for operator review if the skill declares
`auto_absorb_insights: false`). The next session in the same domain
loads this accumulated memory as part of bootstrap, so the skill's
expertise grows with use without code changes.

This closes the loop: **better skills → more effective sessions → richer
insights → better skills.** That self-improvement property is what
distinguishes a universal research agent from a configurable loop.

---

## 9. Reference: Research Skill Manifest schema

```yaml
schema_version: research_skill.v1
id: ml-direction
version: 1.0.0
display_name: "ML Direction Model Tuning"
description: "Tune price-direction prediction models via walk-forward training."

# ── LLM tier routing ──────────────────────────────────────────────
llm:
  provider: anthropic                  # or openai, gemini, local, router
  primary_model: claude-sonnet-4-20250514
  insight_model: claude-haiku-4-20250514
  max_output_tokens: 8192
  system_prompt: SKILL.md              # relative to skill dir

# ── Workspace layout ──────────────────────────────────────────────
workspace:
  session_path_template: "runs/{skill_id}/{subject_id}/{variant}"

# ── Command policy (extends the orchestrator's base policy) ───────
command_policy:
  allowed_python: [".venv/bin/python"]
  allowed_scripts:
    - scripts/setup.py
    - scripts/prepare.py
    - scripts/enrich.py
    - scripts/resume.py
  allowed_executables: [cp, cat]
  copyable_files: [train.yaml, best_train.yaml]
  readable_files: [train.yaml, best_train.yaml, results.json,
                   last_metrics.txt, hpo_results.json]
  forbidden_tokens: ["|", "||", "&&", ";", "&"]
  forbidden_substrings: ["`", "$", ">", "<", "\n", "\r"]
  secret_markers: [.env, /proc/, /run/secrets, authorization, bearer,
                   credential, id_rsa, password, secret, token]

# ── Prompt templates ──────────────────────────────────────────────
prompt:
  setup_command: |
    .venv/bin/python scripts/setup.py --subject {subject_id} --variant {variant}
  experiment_command: |
    .venv/bin/python scripts/prepare.py --config {workspace}/train.yaml{quick_flag}
  continuation_enabled: true
  anti_waste_rules: CLAUDE.md          # shared or per-skill

# ── Output parsing ────────────────────────────────────────────────
output_parser:
  format: delimited_kv                 # or json_marker, structured, exit_code
  block_delimiter: "---"
  iteration_marker: "ITERATION_RESULT:"
  nonce_field: server_nonce            # for signed-metrics anti-forgery
  required_fields: [status, primary_metric, metric_name, all_gates_passed]
  field_types:
    primary_metric: float
    training_time_s: float
    all_gates_passed: bool
  failure_statuses: [crash, timeout, failed, error, pruned,
                     auth_failed, gpu_busy]
  fallback:
    read_marker_file: last_metrics.txt
    read_results_file: results.json

# ── Metric semantics ──────────────────────────────────────────────
metrics:
  primary: primary_metric
  direction: higher_is_better
  gates: [all_gates_passed]
  composite_formula: null              # or expression string
  inert_change_detection: true         # bit-identical metric → flag

# ── Phase plan ────────────────────────────────────────────────────
phases:
  - id: baseline_capture
    label: "Baseline Capture"
    min_iterations: 1
    max_iterations: 3
    evidence_keys: [baseline_recorded]
    next_action: "Run the immutable baseline config."
    stagnation_exempt: false
  - id: tabular_sweeps
    label: "Tabular Sweeps"
    min_iterations: 6
    max_iterations: 40
    evidence_keys: [tabular_sweep_variant]
    next_action: "Sweep bounded tabular roster, horizon, dead-zone…"
    stagnation_exempt: false
  # …remaining phases…

# ── Trial identity (for cross-session dedup) ──────────────────────
trial_identity:
  hash_fields: [skill_id, subject_id, variant, canonical_config_hash,
                quick_mode, data_split_id]
  resolve_extra_fields: scripts/resolve_identity.py   # optional

# ── Structured HPO (optional) ─────────────────────────────────────
structured_hpo:
  enabled: false
  plan_generator: scripts/generate_hpo_plan.py
  max_trials: 20

# ── Preflight dependencies ────────────────────────────────────────
preflight:
  - name: data-source
    kind: http_health
    url: http://data-ingest:8000/health
    required: true
    timeout_s: 3.0
  - name: trainer
    kind: http_health
    url: http://ensemble-trainer:8000/health
    required: true
  - name: artifact-store
    kind: http_health
    url: http://minio:9000/minio/health/live
    required: false

# ── Promotion target ──────────────────────────────────────────────
promotion:
  target:
    kind: file_path                    # or registry_api, webhook, composite_api
    path_template: "configs/subject_configs/{subject_id}_{variant}.yaml"
    sidecar_extensions: [.meta.yaml]
    atomic_write: true
  scopes:
    - id: development
      approval_required: false
    - id: paper
      approval_required: false
    - id: canary
      approval_required: true
    - id: production
      approval_required: true
      delegate_to: http://mlflow-service:8000/api/v1/composites/{composite_id}/promote
  evidence_collector: scripts/collect_promotion_evidence.py   # optional

# ── Insights extraction ───────────────────────────────────────────
insights:
  prompt_template: insights.md
  model: claude-haiku-4-20250514
  max_chars: 500

# ── UI hints ──────────────────────────────────────────────────────
ui:
  form_fields:
    - name: trading_mode
      type: enum
      options: [stock, margin]
      required: false
    - name: agent_strategy
      type: enum
      options: [AGGR, CONS, BALA, SCAL]
      required: false
  chart:
    primary_metric_label: "Walkforward AUC"
    gates_badge: true
```

The manifest above is one instance (an optimization-category ML skill).
The *same schema* serves a completely different domain by swapping the
harness, parser, phases, command policy, and promotion target — everything
else (loop, guards, audit, UI) is reused unchanged. As a concrete
cross-domain proof, here is a generative-category skill for prompt
engineering:

```yaml
schema_version: research_skill.v1
id: prompt-engineering
version: 0.3.0
category: generative
display_name: "Prompt Engineering Research"
description: "Iterate prompt variants against an eval set and promote the winner."

llm:
  provider: router                    # use the model-router for price/quality
  primary_model: claude-sonnet-4-20250514
  insight_model: claude-haiku-4-20250514
  max_output_tokens: 8192
  system_prompt: SKILL.md

workspace:
  session_path_template: "runs/{skill_id}/{subject_id}/{variant}"

# A generative skill's harness is an eval scorer, not a trainer.
bootstrap:
  script: bootstrap.py                # renders scaffold/, loads eval set
  scaffold: scaffold/
  smoke_check: "eval/run.py --smoke"

command_policy:
  allowed_python: [".venv/bin/python"]
  allowed_scripts:
    - eval/run.py                     # score a candidate prompt
    - eval/render.py                  # render a prompt template
  allowed_executables: [cp, cat, jq]
  copyable_files: [prompt.yaml, best_prompt.yaml]
  readable_files: [prompt.yaml, best_prompt.yaml, eval_result.json]
  forbidden_tokens: ["|", "||", "&&", ";", "&"]
  forbidden_substrings: ["`", "$", ">", "<", "\n", "\r"]

prompt:
  experiment_command: |
    .venv/bin/python eval/run.py --prompt {workspace}/prompt.yaml --eval {workspace}/eval_set.jsonl
  continuation_enabled: true

output_parser:
  format: json_marker                # different parser, same orchestrator
  iteration_marker: "ITERATION_RESULT:"
  nonce_field: server_nonce
  required_fields: [status, primary_metric, metric_name, n_eval_examples]
  failure_statuses: [eval_error, timeout]

metrics:
  primary: primary_metric
  metric_name: composite_eval_score
  direction: higher_is_better
  gates: [passes_min_precision, within_cost_budget]
  inert_change_detection: true

# Generative phases differ from optimization phases.
phases:
  - id: baseline_capture
    min_iterations: 1
    max_iterations: 2
    evidence_keys: [baseline_score]
  - id: strategy_sweep
    min_iterations: 4
    max_iterations: 20
    evidence_keys: [prompt_strategy]
    next_action: "Try few-shot, chain-of-thought, role, self-critique variants."
  - id: robustness
    min_iterations: 3
    max_iterations: 10
    evidence_keys: [paraphrase_invariance, adversarial_pass]
    next_action: "Paraphrase and adversarial eval."
  - id: cost_precision_tradeoff
    min_iterations: 2
    max_iterations: 6
    evidence_keys: [cost_curve_point]
  - id: promotion_proposal
    min_iterations: 1
    max_iterations: 2
    evidence_keys: [promotion_proposal]

trial_identity:
  hash_fields: [skill_id, subject_id, variant, prompt_template_hash,
                eval_set_hash]

preflight:
  - name: eval-set
    kind: local_file
    path: "{workspace}/eval_set.jsonl"
    required: true
  - name: scorer-api
    kind: http_health
    url: "{skill_params.scorer_url}"
    required: true

# Promotion target is a prompt registry, not a config file.
promotion:
  target:
    kind: registry_api
    registry: prompt-registry
    register_endpoint: "{skill_params.registry_url}/api/v1/prompts"
    atomic_write: true
  scopes:
    - { id: development, approval_required: false }
    - { id: staging,     approval_required: false }
    - { id: production,  approval_required: true }

insights:
  prompt_template: insights.md
  model: claude-haiku-4-20250514
  max_chars: 500

ui:
  form_fields:
    - { name: eval_set, type: string, required: true, label: "Eval set path/URL" }
    - { name: scorer_url, type: string, required: true }
    - { name: registry_url, type: string, required: true }
    - { name: target_metric, type: enum, options: [composite_eval_score, precision, f1], default: composite_eval_score }
```

Comparing the two examples side by side shows exactly what is shared
(everything structural: LLM routing, workspace template, command-policy
shape, parser contract, metric semantics, phase-plan shape, trial
identity, preflight shape, promotion scope rules, insights, UI fields)
and what is domain-specific (the script names, the parser format, the
phase list, the promotion target kind). That ratio — large shared core,
small domain surface — is the whole economic argument for the universal
agent. Section 10 develops several more domains at the same level of
detail.

---

## 10. Domains the universal agent supports

Once the orchestrator is skill-driven and skills auto-initialize, the same
service hosts any domain. The table below maps a representative spread;
each row is a real skill that fits the manifest in Section 9 with no
orchestrator changes.

| Domain | Category | Subject | Harness (eval) | Primary metric | Promotion target |
|---|---|---|---|---|---|
| ML model tuning (trading) | optimization | instrument + timeframe | `prepare.py` walk-forward | walkforward AUC / composite RL | config file → mlflow composite |
| ML tuning (any library) | optimization | dataset + model class | user-supplied trainer | accuracy / F1 / custom | model registry |
| Prompt engineering | generative | model + task | eval scorer over labeled set | composite eval score | prompt registry |
| Code refactor | generative | repo + module path | test suite + benchmark + linter | composite (pass rate, perf, complexity) | git branch / PR |
| Literature review | exploratory | topic + question set | QA eval over synthesized graph | coverage recall | report artifact |
| Database config tuning | optimization | engine + workload | pgbench / sysbench runner | TPS @ target latency | live config file (canary → prod) |
| Kubernetes resource tuning | optimization | cluster + workload | load test runner | p99 latency / cost | helm values |
| Security research | exploratory | target scope | finding validator | weighted findings count | security report |
| A/B test design | design | hypothesis + population | power-analysis simulator | expected information gain | experiment config |
| Compliance validation | validation | system + control set | control checker | gate pass rate | sign-off record |
| Hyperparam sweep (scientific) | optimization | dataset + simulator | any `prepare.py`-style runner | domain metric | artifact / paper appendix |

The shared spine (loop, guards, audit, dedup, live UI, promotion handoff)
is identical across all rows. What changes per row is packaged inside the
skill. Four are developed below at the level of detail needed to start
implementation.

### 10.1 ML model tuning (trading) — the existing case, reframed

This is the only domain the service currently supports. Under the universal
model it becomes the `ml-direction` / `ml-volatility` / `ml-rl` skills,
identical in behavior to today but loaded from `SKILL.yaml` instead of
hardcoded. The existing `{instrument, timeframe, model_type}` API becomes a
dual-shape alias for `{subject_id, variant, skill_id}`. No operator-visible
behavior changes; the legacy client keeps working forever.

This domain remains the reference implementation and the regression target,
but it is no longer the architectural center.

### 10.2 Prompt engineering research (`prompt-engineering`)

A generative skill whose full manifest appears in Section 9.

- **Bootstrap** clones the eval set into the workspace, renders a baseline
  prompt template from `skill_params`, and validates the scorer API is up.
- **Loop** iterates: edit `prompt.yaml` → run `eval/run.py` → check
  composite score → keep or revert. Identical loop shape to ML; different
  eval script.
- **Phases** progress baseline → strategy sweep (few-shot, CoT, role,
  self-critique) → robustness (paraphrase, adversarial) → cost/precision
  tradeoff → promotion proposal.
- **Promotion** writes the winning prompt to a prompt registry via
  `registry_api`, with `development → staging → production` scopes.
- **Insights** capture which strategies helped, feeding
  `skills/prompt-engineering/knowledge/prior_findings/` for future runs.

The agent never knows it is doing "prompt engineering" — it knows it is
iterating an artifact against an evaluator, which is the universal loop.

### 10.3 Code refactor research (`code-refactor`)

A generative skill where the promoted artifact is source code.

```yaml
id: code-refactor
category: generative
command_policy:
  allowed_scripts: [eval/run_tests.sh, eval/run_benchmarks.sh, eval/lint.sh]
  allowed_executables: [git, cp, cat, jq]   # git read-only + branch ops
output_parser:
  format: json_marker
metrics:
  primary: composite_refactor_score        # w1·tests + w2·perf_delta + w3·complexity
  gates: [tests_pass, no_perf_regression]
phases:
  - { id: baseline_capture,        evidence_keys: [baseline_metrics] }
  - { id: mechanical_refactors,    evidence_keys: [refactor_applied] }
  - { id: design_refactors,        evidence_keys: [design_change] }
  - { id: validation,              evidence_keys: [full_validation] }
  - { id: promotion_proposal,      evidence_keys: [promotion_proposal] }
promotion:
  target:
    kind: git_branch
    repository: "{skill_params.repo}"
    base_branch: "{skill_params.base_branch}"
    proposed_branch_template: "research/{session_id}"
  scopes:
    - { id: development, approval_required: false }
    - { id: production,  approval_required: true }
```

The agent works inside a governed checkout, the eval harness runs the test
suite + benchmarks + linters and emits a composite score, and promotion
opens a branch / PR with the winning refactor. The command policy extends
to read-only `git` and branch operations; the agent cannot push to
protected branches or touch unrelated modules.

### 10.4 Database configuration optimization (`db-config-tuning`)

An optimization skill, structurally closest to ML tuning but with no ML in
it.

```yaml
id: db-config-tuning
category: optimization
command_policy:
  allowed_scripts: [bench/run_pgbench.sh, bench/apply_config.sh]
output_parser:
  format: delimited_kv                      # reuse the existing parser
metrics:
  primary: tps_at_target_latency
  direction: higher_is_better
  gates: [p99_within_slo, no_regression]
phases:
  - { id: baseline_capture, evidence_keys: [baseline_tps] }
  - { id: memory_tuning,    evidence_keys: [memory_knob_swept] }
  - { id: wal_checkpoint,   evidence_keys: [wal_knob_swept] }
  - { id: planner_costing,  evidence_keys: [planner_knob_swept] }
  - { id: parallelism,      evidence_keys: [parallel_knob_swept] }
  - { id: validation,       evidence_keys: [soak_test_passed] }
  - { id: promotion_proposal, evidence_keys: [promotion_proposal] }
promotion:
  target:
    kind: file_path
    path_template: "configs/db/{subject_id}_{variant}.yaml"
  scopes:
    - { id: development, approval_required: false }
    - { id: canary,      approval_required: true }
    - { id: production,  approval_required: true, delegate_to: "{skill_params.config_manager_url}" }
```

Same loop, same guards, same audit, same UI. The only difference from ML
tuning is the eval script and the metric name.

### 10.5 Literature review / knowledge synthesis (`literature-review`)

An exploratory skill where the promoted artifact is a synthesized report,
not a config.

```yaml
id: literature-review
category: exploratory
command_policy:
  allowed_scripts: [search/query.py, graph/build.py, eval/answer_questions.py]
  allowed_executables: [cat, jq]
output_parser:
  format: json_marker
metrics:
  primary: coverage_recall                # recall against a held-out QA set
  gates: [min_coverage, no_hallucinated_citations]
phases:
  - { id: scope,            evidence_keys: [scope_defined] }
  - { id: source_discovery, evidence_keys: [sources_curated] }
  - { id: extraction,       evidence_keys: [claims_extracted] }
  - { id: synthesis,        evidence_keys: [graph_built] }
  - { id: validation,       evidence_keys: [qa_eval_passed] }
  - { id: promotion_proposal, evidence_keys: [report_drafted] }
promotion:
  target:
    kind: artifact_store                  # report + graph + citations bundle
    path_template: "artifacts/reviews/{subject_id}/{variant}/"
```

The "iteration" here is a research step (query, extract, synthesize) rather
than a hyperparameter trial, but the iteration-detection, dedup, phase, and
promotion machinery is identical. The metric (coverage recall against a
held-out QA set) is what makes the agent's exploration measurable rather
than open-ended.

### 10.6 The economic argument

Every domain above would otherwise reimplement, from scratch: budget
guards, wall-clock timeout, audit and provenance, iteration detection,
cross-session dedup, live UI, phase enforcement, promotion handoff, and
the React app. The universal agent amortizes that work across all of them.
Adding an eleventh domain is a skill directory, not a service fork.

---

## 11. Migration path (incremental, no big-bang)

The existing service is in production. The migration must be
non-disruptive.

### Phase 0 — Hardening (no behavior change)
Fix the operational-debt weaknesses that are independent of
generalization:
- W8 stop-status clobber → `SessionStateMachine`.
- W9 hard timeout → `asyncio.wait_for` wrapper on `run()`.
- W10 migration error masking → narrow `except`.
- W12 atomic promotion → temp + `os.replace`.
- W13 broadcaster lock.
- W15 cursor pagination.
- W18 mandatory production approval.

**Exit criterion:** all four existing model types still pass their
existing tests; new state-machine tests cover transitions.

### Phase 1 — Introduce abstractions, keep behavior identical
- Introduce `LLMProvider` protocol; move Anthropic client behind
  `AnthropicProvider`. Behavior identical.
- Introduce `StateStore` protocol; move SQLite behind
  `SQLiteStateStore`. Behavior identical.
- Introduce `OutputParser` protocol; move `parse_prepare_output` /
  `parse_iteration_marker` behind `DelimitedKVParser`. Behavior
  identical.
- Introduce `PromotionTarget` protocol (§7.10); move `ConfigPromoter`
  behind `FilePathPromotionTarget`. Behavior identical.
- Introduce `PreflightCheck` protocol; move existing checks behind
  `HTTPHealthCheck` instances.
- Introduce the `SkillRuntime` protocol (§7.5) as an empty shell —
  the three existing model types each get a transitional runtime that
  delegates to the current hardcoded code paths. No behavior change.

**Exit criterion:** all existing tests pass; no public API change;
`grep config.model_type src/core/orchestrator.py` still matches (will
be driven to zero in Phase 2).

### Phase 2 — Extract skill descriptors for existing model types
- Write `skills/ml-direction/SKILL.yaml`, `skills/ml-volatility/SKILL.yaml`,
  `skills/ml-rl/SKILL.yaml` reproducing the current hardcoded behavior,
  including the `param_schema`, `metric_schema`, `decision_vocabulary`,
  `phase_plan`, `command_policy`, `output_parser`, `preflight`,
  `promotion_target`, and `form_fields` sections defined in §7.4 and
  Section 8.
- Move each transitional `SkillRuntime` (from Phase 1) onto its
  manifest: phase plans, command policy, parser config, preflight deps,
  and promotion target are loaded from YAML rather than Python
  constants.
- Generalize `ResearchConfig` per §7.3 — `skill_id`/`subject_id`/
  `variant`/`skill_params` become canonical; ML flat fields move into
  `skill_params`. Legacy `model_type`/`instrument`/`timeframe` become
  read-only alias properties.
- Delete the hardcoded constants: `_load_skill` map,
  `DIRECTION_PHASES`/`VOLATILITY_PHASES`/`RL_PHASES`,
  `_ALLOWED_SCRIPTS`, `_AGENT_ACTIONABLE_BLOCKERS`.

**Exit criterion:** existing model types work end-to-end driven purely
by their manifests; `grep -E "config\.(model_type|instrument|timeframe)"
src/core/orchestrator.py` returns zero hits; all four existing model
types pass their existing tests unchanged.

### Phase 3 — Generic session API and dual-shape responses
- Add the skill endpoint surface from §7.6: `GET /api/v1/skills`,
  `/api/v1/skills/{id}`, `/param-schema`, `/form-fields`,
  `/metric-schema`, `/versions`, `/changelog`, `POST /reload`, plus
  `/api/v1/subjects` and `/api/v1/subjects/{id}/variants`.
- Extend `POST /api/v1/research/start` to accept the canonical shape
  from §7.7; implement the legacy auto-translation table so the
  existing shape still works.
- Make every session/iteration response carry both canonical and
  legacy fields per §7.12 (dual-shape guarantee).
- Extend WebSocket payloads with `skill_id`, `skill_version`,
  `skill_phase`, `evidence_keys`, and the skill-declared `metrics`
  object per §7.8.
- Migrate the React UI per §7.9: skill picker on NewResearch, dynamic
  form from `/form-fields`, manifest-driven MetricsChart and
  IterationsTable, `target_kind`-branched promotion modal.
- Bump persisted schema versions (`research_session_manifest.v2`,
  `autoresearch_iteration_attempt.v2`) with forward migrations in
  `ResultsStore.initialize()`.

**Exit criterion:** a new skill can be added by dropping a directory
under `skills/` and reloading — no orchestrator or UI code changes;
the falsifiability tests in §7.14 all pass.

### Phase 4 — Anti-forgery and cross-provider
- Add per-session nonce to the metrics block contract (W11); enforce
  in each skill's `parse_iteration` via the `session_nonce` parameter.
- Add `OpenAIProvider` (and optionally `GeminiProvider`,
  `LocalProvider`) behind the `LLMProvider` protocol.
- Author and ship one non-ML skill end-to-end
  (e.g. `prompt-engineering`) as the cross-domain proof point.

**Exit criterion:** a non-ML skill runs end-to-end on a non-Anthropic
provider; forged `---` blocks without the correct nonce are rejected.

### Phase 5 — Auto-initialization, skill lifecycle, and generator
- Implement the skill directory layout from §8.1 (`SKILL.yaml` + `SKILL.md`
  + `bootstrap.py` + `scaffold/` + `knowledge/` + `eval/` + optional
  plugins). Backfill the three ML skills with their `bootstrap.py` and
  `knowledge/` so they auto-initialize like any other skill.
- Run `bootstrap.py` at session start; record the `session_bootstrap.v1`
  artifact (§8.3). Move the server-side setup logic that today lives in
  `session_manager`/`orchestrator` into each skill's bootstrap.
- Implement skill lifecycle (`draft`/`reviewed`/`stable`/`deprecated`) and
  skill promotion via `target_kind: skill_registry` reusing the existing
  promotion machinery (§8.7).
- Add `category` to the manifest and surface domain taxonomy in the UI
  (§8.4).
- Implement auto-domain detection (§8.5): `POST /research/start` accepts a
  natural-language `goal`; the classifier proposes a skill and writes the
  match to `audit_events`.
- Implement the skill generator meta-skill (§8.6) behind a feature flag;
  drafts land in `skills/_drafts/` and are reviewed through skill promotion.

**Exit criterion:** at least one non-ML domain (e.g. `prompt-engineering`)
runs end-to-end, was added with no orchestrator/UI code changes, and was
optionally drafted by the generator and promoted by an operator.

### Phase 6 — Distributed storage (optional, only if needed)
- Implement `PostgresStateStore` behind the `StateStore` protocol.
- Lift the single-worker guard when distributed locks are in place.

Each phase is independently shippable and independently revertible. Phases
0–3 harden and generalize the runtime; Phase 4 widens provider and trust
surface; **Phase 5 is what turns a configurable loop into a universal
research agent** — the point at which new domains stop requiring engineering
and become an operator action.

---

## 12. Risks and open questions

**R1. Skill manifest expressiveness vs. orchestrator simplicity.**
There's a tension between making the manifest rich enough to cover
real research workflows and keeping the orchestrator's behavioral
contract testable. Mitigation: keep the manifest declarative where
possible (phases, command policy, parser config) and use small,
sandboxed Python plugin files (`parser.py`, `resolve_identity.py`)
only where declarations are insufficient. Plugins run in the same
governed sandbox as the experiment scripts.

**R2. Security boundary around skill plugins.**
A skill that ships its own `parser.py` or `preflight` script runs
server-side Python. Mitigation: skills are installed by the operator
(not by the agent, not by API callers); skill directories are
read-only at runtime; the agent itself can only invoke allow-listed
experiment scripts, never skill plugins.

**R3. Backward compatibility.**
The existing UI, openapi.yaml, runbooks, and operator muscle memory
use `instrument/timeframe/model_type`. Mitigation: the legacy API
adapter in Phase 3 keeps current clients working; the UI migration is
purely additive (skill picker replaces model_type dropdown).

**R4. LLM provider semantic differences.**
Anthropic, OpenAI, and Gemini have different tool-use protocols,
different system-prompt handling, and different retry semantics.
Mitigation: the `LLMProvider` protocol normalizes these at the
boundary; capabilities advertising lets a skill declare requirements
(e.g. "needs native tool-use").

**R5. Phase-contract enforcement across providers.**
The current enforcement relies on injecting continuation messages
when the agent tries to `end_turn` early. Different providers signal
turn-end differently. Mitigation: enforce at the loop level (we
control when we accept a final turn), not at the provider level.

**R6. Distributed-storage correctness.**
Moving off single-instance SQLite is a real distributed-systems
problem (idempotency locks, fencing tokens, concurrent iteration
numbering). Mitigation: don't do it unless a real workload demands
it; the single-instance ceiling is generous for most research work.

**R7. Should "universal" be one service or a library + many services?**
Alternative architecture: extract the orchestrator into a reusable
library (`research-loop` or similar) and let each domain ship its own
thin service. Mitigation discussion: a single service with
multi-skill support is better here because (a) the operational
surface (auth, metrics, audit, UI) is shared and expensive to
replicate, (b) cross-skill features (unified history, shared
research_resume) become possible, and (c) deployment is simpler.
Revisit if any single skill grows domain-specific scaling needs.

**R8. Bootstrap scripts run with the server's privileges.**
A skill's `bootstrap.py` is server-side Python that can touch the
workspace, the knowledge base, and (if buggy) the host. Mitigation:
bootstrap runs in the same governed sandbox as experiment scripts,
with the same path-confinement rules; skills are operator-installed
and read-only at runtime; a `--dry-bootstrap` mode renders the
`session_bootstrap.v1` artifact without side effects for review.

**R9. Auto-domain detection can pick the wrong skill.**
A natural-language `goal` may map ambiguously to several skills, and
a wrong auto-selection silently runs the wrong kind of research.
Mitigation: an explicit `auto_select_threshold` (§8.5); the match
score and rationale are written to `audit_events`; below threshold the
operator confirms; the classifier is tunable and its confusion matrix
is observable from audit history.

**R10. Generated skills can be subtly wrong.**
The skill generator (§8.6) can produce a manifest, bootstrap, and
eval harness that look plausible but encode a wrong metric, a
permissive command policy, or a misleading eval. Mitigation:
generated skills are `draft` status and cannot bootstrap production
sessions until promoted by an operator; the promotion preview shows
the full manifest diff and runs a dry bootstrap; the generator's
output is sandboxed under `skills/_drafts/` and isolated from
`stable` skills. A generated skill that passes review still inherits
all the runtime guards (budget, policy, audit), so the blast radius
of a bad draft is bounded to wasted budget, not unchecked execution.

**R11. Domain expertise can go stale.**
A skill's `knowledge/` corpus can drift out of date as a domain
evolves (new package versions, deprecated APIs, shifted best
practices). Mitigation: the feedback loop in §8.8 surfaces
`insights` that contradict the corpus; skills carry a
`knowledge_last_reviewed` timestamp surfaced in the UI; a skill can
declare `refresh_cadence_days` and the UI flags stale skills for
operator review.

---

## 13. Summary

`autoresearch-agent` already implements the hard parts of a universal
research agent: a server-authoritative tool-use loop with strict command
policy, budget/timeout/iteration guards, audit and provenance, phase
contracts, cross-session memory, and a promotion handoff. Today those
primitives are coupled to one domain (trading-model tuning) by a thin layer
of hardcoded anchors — `model_type`, allowed scripts, output parser, phase
plan, preflight dependencies, and promotion target.

The proposal here is to lift that coupling into **self-contained, installable
domain skills** that do two things a manifest alone cannot:

1. **Govern** the loop declaratively via `SKILL.yaml` (Section 7/9) —
   turning each current weakness into a named extension point.
2. **Auto-initialize** the agent for their domain (Section 8) — rendering
   the workspace, injecting expertise, configuring tools, and seeding the
   search space, so picking a domain makes the agent domain-ready in one
   step.

With both layers in place, the same runtime hosts ML tuning, prompt
engineering, code refactoring, literature review, database and Kubernetes
tuning, security research, A/B design, compliance validation, and arbitrary
scientific sweeps — as peers (Section 10). Adding a domain stops being an
engineering task and becomes an operator action: drop a skill directory, or
describe the domain in natural language and let the skill generator draft
it for review. Legacy trading clients keep working via dual-shape aliases.

The migration is incremental and each phase is independently shippable:
harden operational debt (Phase 0), introduce protocols behind identical
behavior (Phase 1), extract manifests for the three existing ML skills
(Phase 2), open the generic session API and dual-shape responses (Phase 3),
add anti-forgery and cross-provider support (Phase 4), and finally land the
auto-initialization, skill lifecycle, and generator (Phase 5) — the phase
that turns a configurable loop into a genuine universal research agent.
