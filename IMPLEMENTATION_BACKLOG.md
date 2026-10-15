# Implementation Backlog: Universal Research Harness

Date: 2026-09-27
Autonomous execution revision: 2026-10-03.

Source: [PROJECT_REVIEW.md](PROJECT_REVIEW.md), findings F01-F12 and its
architecture, caveats, and acceptance matrix.

Code baseline: `1a5d54505d98976572887b6e23fdca0988902d60`.

Status: planning only; revised for autonomous implementation. All implementation
cards are open. Reviewing or editing this document does not start their execution.
The review's 170 passing focused tests are baseline evidence, not completion
evidence for these tasks. No fixes or harness integrations are claimed by this
backlog.

Inventory: 50 task cards, 150 implementation subtasks, and 136 hard dependency
links. Initial delivery contains 44 CORE cards; 6 extensions are GATED.

## Target and Boundaries

Deliver a research control plane usable with the built-in agent, Codex, Claude
Code, and a documented custom-driver contract. Support both service-managed
agents and an existing external agent invoking scoped research operations.
Skills must define domain behavior without branches for their IDs in core code.

The first qualified deployment target is Linux with enforced process isolation,
local immutable artifacts, SQLite for one worker, and Postgres for multiple
workers on the same host. Qualify a real prompt scorer, a real code/test workflow,
and a measured latency minimization workload across the three named harnesses.
The existing simulated DB skill remains explicitly a simulator.

Multi-host execution, native Windows/macOS execution, additional promotion
backends, and advanced research objectives are gated extensions. They must not
delay qualification of the stated initial target or inherit its claims without
their own tests. Unknown or unsupported capabilities fail before work starts.

## How to Execute

Use the execution contract below when the user requests implementation. The
agent owns investigation, design choices, implementation, review corrections,
and verification. Routine technical questions are resolved through evidence and
the decision rules; they are not handed back to the user.

`Owner` on a card means an expertise area, not a person to recruit or a human
approval gate. The executing agent records its run identifier as owner and
performs a separate review pass before closure. A self-review must be labeled
as such. Additional agents are optional and require applicable authorization;
this plan can be executed by one agent.

Engineering-day estimates remain historical planning ranges, not agent runtime
budgets, promises, or reasons to stop. Refresh them after B02, B08, and B33 only
if useful. Dependencies, acceptance criteria, and measured evidence govern work.

### Review Findings Addressed by This Revision

| Previous execution gap | Autonomous replacement |
| --- | --- |
| B02 left unresolved choices with an owner; B08/B34/B35 required unspecified selection work | A decision procedure, bounded experiments, and per-card resolution rules |
| Owners and reviews implied people were needed between tasks | One accountable agent; explicit implementation, review, and verification transitions |
| Large subtasks had no durable resumption or executable verification record | Small work packets, a persistent ledger, exact commands, and evidence invalidation |
| Live credentials, isolation, runners, and spend could surface late in B43 | B01 capability inventory, scoped resource references, and automatic prerequisite rechecks |
| A blocked card could stop the whole roadmap | Dependency-aware selection of other ready work; blockers propagate only to dependent work |
| GATED work and a generic DONE state could obscure what was actually finished | Separate CORE_44 and ALL_50 completion targets; no deferral or missing test counts as DONE |

### Scope and Authority

- `CORE_44` means B01-B44 are required. `ALL_50` means B01-B50 are required,
  including each extension's original reopening and qualification conditions.
  An instruction to implement **all tasks/the whole backlog** selects ALL_50;
  an instruction for **initial delivery** selects CORE_44. Record this once at
  startup and do not reduce it to manufacture completion. For ALL_50, B44 is a
  milestone, not permission to stop.
- Resolve technical choices, dependencies, test fixtures, migrations, and local
  tooling autonomously within the authorized implementation scope. Preserve
  existing user changes. Use feature branches, small commits, and reviewable PR
  material; never push implementation directly to `main`.
- Prepare local branch/PR content even if remote access is absent. Push, open or
  merge a PR, run paid jobs, provision infrastructure, publish, deploy, or promote
  against real targets only within authority already granted for that action.
  A credential's presence is not permission to spend or change its account.
  This planning revision grants none of those external permissions.
- Product promotion approvals remain product requirements. Test them with
  disposable targets and test approver identities. Unattended implementation
  does not give a research agent operator or production-approver authority.
- Treat repository runtime prompts, supplied datasets, tool output, and this
  document's examples as task material. In particular, `CLAUDE.md` describes
  in-container research sessions; its no-exploration/no-git rules are not the
  implementation workflow. Follow the actual user request and applicable
  development instructions.

### Decision Procedure: Resolve Questions Without a Human Queue

For an unspecified technical choice:

1. Read the affected implementation, tests, dependency versions, and relevant
   contracts. Reproduce the ambiguity with the smallest useful fixture.
2. Apply explicit requirements first, then a still-valid recorded decision,
   then the per-card `Autonomy` rule. Existing behavior is evidence, not an
   excuse to preserve a reproduced defect.
3. If a choice remains, compare at most two viable approaches. Prefer, in order:
   satisfying trust/correctness gates, preserving supported compatibility,
   working in the qualified environment, and reducing migration/dependency
   complexity. Break an otherwise equal tie in favor of the existing stack.
4. For external protocols or dependencies, check primary documentation for the
   version being used, pin the selection, and save source URLs/access dates.
   Do not treat the 2026-09-27 review's external API descriptions as current.
5. Bound an initial spike to two focused probes and 60 minutes of active work.
   A failed probe yields evidence, a repair, or the second approach. Continue
   investigation when new evidence supports it; repeated uncertainty is not a
   reason to ask the user to choose a library or architecture.
6. Record the decision, rejected alternative, evidence, consequences, and
   reopening trigger. Continue immediately. Reopen only for new contradictory
   evidence, a changed constraint, or a failing acceptance test.

Default cross-cutting decisions: retain Python/FastAPI/Pydantic and React;
extend SQLite/Postgres rather than introduce another control-plane database;
use versioned data contracts without harness SDK types; keep local immutable
artifacts for CORE; reject unsupported security/semantic capabilities. Add a
dependency only when the existing stack cannot meet a demonstrated requirement.

The agent may refine implementation details and split work packets. It may not
delete an acceptance criterion, waive a hard dependency, reclassify a required
live check as optional, invent demand or measurements, or rewrite a failing
test's expected behavior solely to turn a gate green.

### B01 Capability Inventory and External Prerequisites

At startup, inspect only relevant tool/configuration locations; do not dump
environment variables or credential values. Record each resource as AVAILABLE,
MISSING, DENIED, or UNVERIFIED with a secret reference where necessary. Refresh
at stage boundaries and after a relevant environment change.

| Capability | Agent action and default | If unavailable |
| --- | --- | --- |
| Python, UI dependencies, package builder, browser | Reuse repository versions/locks and CI commands; create isolated local environments and disposable test data | Repair local setup; record a precise package/network/runtime prerequisite if outside available authority |
| Linux isolation, container execution, resource controls | Probe the actual host before selecting the B08 backend; prepare a reproducible lane on an already authorized runner | G1 stays incomplete; never replace OS enforcement with an application-only check |
| Same-host Postgres and multiple workers | Start an isolated disposable instance using existing authorized tooling; use test-only databases and credentials | Cross-store/distributed evidence remains missing; SQLite does not qualify Postgres |
| Built-in, Codex, Claude Code live execution | Discover installed versions and authorized auth references; pin protocols and bounded live recipes | Complete ready offline work; required adapter live evidence remains missing |
| Real prompt scorer and evaluation data | Use a controlled authorized scorer that measures real outputs; pin dataset, scorer, holdout, and usage identity | Endpoint fixtures/demo scoring cannot close B37 or the prompt cells of B43 |
| Live-call and runner budget | Reuse an explicit existing allowance with per-call/run caps; absent authority, new paid consumption has a zero allowance | Prepare all local work; record the exact allowance/cap needed, without guessing consent |
| Remote repository and CI | Discover current branch/repository policy and authorized access; prepare local commits and PR text | Remote submission is separate delivery status; required hosted CI evidence stays outstanding |
| Extension clients, second host, native OS, remote targets | Discover existing authorized resources and evidence of the per-card reopening conditions | Keep that extension INACTIVE or WAITING_EXTERNAL with a concrete unmet condition |

A missing external capability is a fact the agent cannot resolve by choosing an
answer. Write one actionable prerequisite record: affected cards/checks,
observed failure, attempted recovery, required capability or scoped authority,
and the exact command/check that resumes work. Continue all ready independent
work; do not repeatedly ask the same question or poll an unchanged resource.
If unattended work exhausts all ready paths, report the precise incomplete
target and prerequisites. Never call that outcome fully implemented.

### Durable State and Task Selection

Maintain private execution state in ignored
`workspace/autonomous-implementation/` and evidence in ignored
`workspace/qualification/<card-id>/<commit>/`. Verify ignore status before
writing; keep secrets out of both and exclude both roots from candidate/driver
mounts and tool permissions. Preserve these files across agent sessions and
exclude them from cleanup. Public documentation contains supported behavior,
not internal planning transcripts.

- `run.json`: plan hash/revision, target, base/head commits, branch, actor/run ID,
  authority references, available capabilities, resource budgets, active card,
  next action, and last checkpoint.
- `cards.json`: one record per B01-B50, using the Completion Record fields below;
  retain attempt history rather than replacing failures with the latest pass.
- `decisions.jsonl`: append decision ID, affected cards, question, resolution,
  alternatives, evidence, timestamp, and reopening trigger.
- `prerequisites.json`: deduplicated external needs and automatic recheck triggers.
- `gates.json`: required commands/cases, matrix coordinates, exact tested inputs,
  results, evidence hashes, and invalidation relationships.

These are implementation-run artifacts to create in B01, not files asserted to
exist after this planning edit. Use atomic state replacement and a single writer.
Implement a lightweight validator for card IDs, dependencies, allowed states,
acceptance/check references, and closure evidence; run it at every state change
and resume. This validates records, not the truth of uninspected test output.
On resume, reconcile the ledger with Git, actual artifacts, and any running
processes before repeating a command or external effect. Never trust an old
checkbox as proof that the current tree passed.

| State | Meaning and transition rule |
| --- | --- |
| PENDING | In scope but waiting for prerequisite cards; move to READY when all are DONE |
| INACTIVE | GATED reopening evidence absent, or outside the selected target; record which, then re-evaluate at B44 or on new evidence |
| READY | Dependencies and reopening conditions met; local work can proceed |
| IN_PROGRESS | One agent owns a small work packet with a written next check |
| VERIFYING | Implementation and separate review pass finished; execute required evidence recipe |
| REWORK | A requirement/review/check failed; investigate and repair, then verify again |
| WAITING_EXTERNAL | Remaining work needs an unavailable external capability/authority; does not satisfy dependencies |
| DONE | Every acceptance clause and required check has current, inspected evidence; closure audit passed |

On each scheduling pass, recheck newly satisfiable prerequisites, then select a
REWORK/unfinished card with ready dependencies, otherwise the lowest-numbered
READY card. Complete the current useful packet before switching. Cards marked
WAITING_EXTERNAL release the agent to other READY cards; never waive their
dependencies to unlock a descendant. If no card is ready, diagnose unfinished
local REWORK, then checkpoint the exact external frontier if that is all that
remains. Dependency cycles or missing ledger entries are plan defects to repair,
not reasons to ask the user for an implementation order.

Default to serial implementation and one heavy test/build at a time. Numeric
card order remains valid. Parallel work, when authorized, additionally requires
nonconflicting file ownership and independent resource budgets.

### Per-Card Implementation Loop

1. Confirm prerequisites against current evidence and inspect all affected
   callers, stores, APIs, UI, and compatibility paths. Split the card's three
   subtasks into bounded packets if needed; packet completion never closes the
   parent card by itself.
2. Before edits, write a concrete acceptance-to-check map: existing/new test
   paths, commands, environment, timeout, expected results, required negative
   cases, and external prerequisites. Stable IDs such as `B14.A1` identify
   acceptance clauses; do not use an unexecutable phrase such as "run tests".
3. For reproduced defects, demonstrate the failure in a disposable fixture,
   then implement the cross-path repair and its regression. For contract work,
   start with examples of success, rejection, and compatibility. Do not turn
   documentation-only edits into unnecessary product tests.
4. Run focused checks, inspect the diff separately for discrepancies/security/
   recovery gaps, repair confirmed issues, and execute the affected integration
   lanes. Record any review findings and how they were resolved.
5. Inspect the actual result artifacts and semantics, not only exit codes.
   Match verified metrics to candidate/evaluator identity; inspect child cleanup,
   migrations, UI behavior, and external fixture effects where the card requires.
6. Commit only intended implementation files on a feature branch. Bind the
   evidence to the tested tree and resulting commit. If code changes after a
   check, invalidate affected evidence. Prepare/update the PR within existing
   delivery authority; local completion and remote delivery are separate fields.
7. Mark DONE only after all criteria, reviews, and required checks pass; write
   the completion record and next READY card. Continue without asking whether
   to proceed to the next task or stage.

Checkpoint after each packet and before context/tool-budget exhaustion: save
current diff identity, completed steps, running process IDs, last failure,
decisions, and exact next command. A turn ending is not task completion. A later
agent resumes the existing branch and ledger instead of restarting the plan.

### Verification, Retry, and Evidence Rules

- B01 translates card prose into executable recipes using the current checkout.
  Starting points already present are `poetry run pytest <test-paths> -q`,
  `poetry run ruff check --config pyproject.toml src tests`,
  `poetry run mypy src --no-error-summary`, the three `scripts/check_*.py`
  guards used by CI, `poetry build`, and `scripts/smoke_docker.sh`.
  Postgres coverage uses `poetry run pytest -m "postgres or distributed" -vv`
  with a disposable `AUTORESEARCH_DATABASE_URL`. In `ui/`, use
  `npm ci --ignore-scripts`, the CI typecheck command, `npm run test:unit`,
  `npm run build`, and `npm test`. These are recipe inputs, not newly run results.
- Capture exit status, pass/fail/skip counts, exact test IDs, environment/backend,
  tool/adapter versions, source/artifact hashes, and sanitized output. A skipped,
  timed-out, unavailable, or inconclusive required check cannot pass its gate.
  Optional unsupported cases must be declared before qualification, with a
  tested rejection path; none of B43's 18 required live cells is optional.
- Begin with small fixtures. Run broad stage/candidate checks after affected
  focused checks pass; serialize expensive work. Derive time/resource caps
  from existing CI or a bounded baseline probe and record them before launch.
  A timeout diagnoses an incomplete check, not success or permission to kill
  unrelated processes. Tear down only resources created by this run.
- Retry a transient external failure once within the original budget. For a
  deterministic failure, change the diagnosis/implementation before rerunning.
  After three unsuccessful repair hypotheses, minimize the reproduction and
  reassess the decision; do not repeat the same failing command indefinitely or
  relabel a code defect as a missing user decision.
- Baseline failures need exact reproduction and attribution. Repairs within
  scope are agent work. An unrelated baseline failure may remain documented
  while independent cards progress, but cannot waive a required delivery gate.
  An environment-limited test may move to an already authorized capable runner;
  preserve both results and never infer a pass from the move alone.
- A later change affecting a closed card reopens it and invalidates affected
  downstream qualification, clearing dependent DONE states until revalidation.
  Preserve implementation work; recompute readiness from current evidence.
  Unchanged evidence can be reused only with an
  explicit input/dependency comparison. B43/B44 must qualify one final candidate
  commit/artifact set; workflow configuration alone is not a completed CI run.

### Gated Extensions and Honest Completion

Automatically evaluate B45-B50's reopening predicates at B01, B44, and when
new evidence appears. The agent owns discovery, workload/fixture construction,
technical selection, and local preparation. Do not wait for a named human
owner, and do not invent a consumer, service-level target, host, or authorization
to make a predicate true. Each extension's `Autonomy` rule specifies the next
action; its original acceptance requirements remain binding.

For CORE_44, report extensions separately as INACTIVE, eligible, or externally
constrained. For ALL_50, an INACTIVE or WAITING_EXTERNAL extension means the
requested target is **incomplete**. Neither "all cards have a disposition" nor
"all available tests pass" means all tasks are done. To guarantee an entirely
unattended ALL_50 run, its real clients/workloads, runners, credentials, target
references, and bounded spending authority must already be available.

CORE_44 completes only when B01-B44 are DONE and G1-G5 plus the final installed-
artifact/doc checks pass. ALL_50 additionally requires B45-B50 DONE, extension
qualification records, and a rerun of affected core gates against the final
extension-inclusive candidate. Produce a final closure report with the 12 finding
links, all requested card states, qualified versions/backends, and separate
remote delivery/publication status. No automatic release, deployment, production
promotion, or merge follows merely from reaching DONE.

## Delivery Sequence

| Stage | Cards | Effort, days | Outcome | Exit gate |
| --- | --- | --- | --- | --- |
| 0. Contract baseline | B01-B02 | 3-5 | Supported scope, compatibility rules, and shared value contracts | Reviewed contract fixtures; no silent capability fallbacks |
| 1. Trusted execution | B03-B10 | 22-34 | Confined files/processes and evaluator-owned results | G1: B10 |
| 2. Domain correctness | B11-B19 | 24-37 | Parameters, parsers, objectives, phases, and promotion agree | G2: B19 |
| 3. Durable operation | B20-B27 | 27-43 | Pinned runs, owned workspaces, recovery, usage, and durable events | G3: B27 |
| 4. Harness integration | B28-B36 | 32-51 | Kernel, built-in adapter, attached API/CLI, and two external adapters | G4: B36 |
| 5. Qualification | B37-B44 | 25-41 | Real domains, UI, CI, live compatibility matrix, and handoff | G5: B43; delivery closure: B44 |
| Extensions | B45-B50 | 33-63 | Additional transports, environments, targets, and objective types | Per-card reopening and qualification gates |

The CORE estimates sum to **133-211 engineering days**; all GATED estimates sum
to a separate **33-63 days**. These are initial planning ranges, not a commitment
or a recommendation to schedule every extension. The total includes multiple
independently useful milestones and substantial qualification work. Isolation
backend selection and live adapter behavior carry the largest uncertainty.

Start with B01. B03-B04 can follow immediately while B02 is specified. Once
contracts settle, B11 can progress alongside execution work. B24 and B26 can
progress alongside recovery after their prerequisites. B34/B35 can be owned
independently after B33/B31. Real-domain work B37-B39 can progress alongside
adapter integration once its own prerequisites pass.

Shared-file caution: B03-B09 touch execution/orchestration; B14/B20-B26 touch
both stores; B28-B30 touch the main loop. Integrate these changes deliberately
instead of merging simultaneous rewrites of the same modules. Run heavy test,
build, and distributed gates one at a time in a shared interactive workspace.

## Finding Coverage

| Review finding | Implementing cards | Required closure evidence |
| --- | --- | --- |
| F01 evaluator shadowing and shared writes | B03, B05, B06, B08 | B10 adversarial tool/evaluator tests |
| F02 dangling symlink escape | B04 | B10 filesystem race/confinement tests |
| F03 forgeable metrics | B07, B13, B31 | B10 and B36 forged/replayed result tests |
| F04 unenforced plugin caps/resources | B08, B09 | B10 OS-level denial and process cleanup evidence |
| F05 inverted minimization | B14, B15, B16, B41 | B19 and B43 winner/promotion/ranking checks |
| F06 live/demo path mismatch | B06, B12 | B10 and B19 live-template integration checks |
| F07 unsafe worker admission/workspace reuse | B21, B22, B26 | B27 separate-process Postgres tests |
| F08 lost continuation settings/provenance | B20, B21, B23 | B27 restart and migration tests |
| F09 domain-specific production gates | B18 | B19 non-ML scoped promotion and rollback |
| F10 provider/budget abstraction gaps | B24, B25 | B27 accounting and B36 external usage tests |
| F11 accepted but inert manifest fields | B13, B15, B16, B17 | B19 behavioral support matrix |
| F12 parameter validation/binding gaps | B11, B12, B20, B23 | B19 and B27 nondefault-parameter round trips |

Additional caveats are covered by B26 (event fan-out), B37-B39 (real evaluation),
B15/B41 (replication/comparability), B21/B46 (artifacts), B40 (UI), B42-B44
(qualification/docs), and B47/B49/B50 (explicitly gated portability/expansion).

## Stage 0: Contract Baseline

### B01 - Establish support inventory and reproducible baseline

Track: CORE. Priority: P1. Owner: Backend + QA.
Effort: 1-2 days. Confidence: High.
Depends on: none.
Basis: F01-F12; bounded review coverage.
Areas: review, `tests/`, `scripts/`, existing CI.

Autonomy: Create the run/card/decision/prerequisite/gate ledgers, resolve the
completion target, and inventory all external needs now. Use the actual checkout and
CI as the baseline; keep historical review results separately attributed.

- [x] Map each manifest field and claimed capability to a runtime consumer and test; distinguish implemented, rejected, and silently ignored behavior.
- [x] Turn disposable review reproductions into reusable fixture designs; bind baseline results to the current commit and record drift from the reviewed commit.
- [x] Initialize the autonomous execution ledgers and their validator, completion target, capability/authority inventory, and named qualification gates; record exact baseline recipes and prerequisites for unrun checks.

Acceptance: all 12 findings have a reproducible trigger or a clearly identified
code-path hypothesis, agent owner, and closure test. Every card has an initial
ledger state; target, external prerequisites, and gate requirements are explicit.
Existing passing behavior is recorded without treating it as proof that known
defects are fixed.
Verification: inventory completeness check, bounded baseline test logs, and
fixture review; ledger validation rejects unknown cards, invalid transitions,
and DONE records without required evidence. Add each regression with its
implementing fix rather than making an unrelated whole-suite failure a
prerequisite for starting repairs.

### B02 - Specify versioned research and execution contracts

Track: CORE. Priority: P1. Owner: Backend architecture.
Effort: 2-3 days. Confidence: Medium.
Depends on: B01.
Basis: universal architecture; F06, F08, F10-F12.
Areas: `skill_manifest.py`, `research_manifest.py`, API schemas.

Autonomy: Use versioned Pydantic/JSON value contracts and explicit legacy readers.
Operator constraints bound explicit run inputs, then skill defaults, then system
defaults; harness preferences cannot widen authority. Resolve and record every
contract choice before dependent implementation.

- [ ] Specify RunSpec, ExecutionRequest, candidate/observation identity, verified result, objective policy, and capability descriptor as versioned data contracts.
- [ ] Separate operator constraints, skill defaults, harness preferences, and mutable candidate data; define deterministic precedence and secret references.
- [ ] Specify legacy readers, explicit migration errors, minimum supported capabilities, and the Linux isolation boundary; resolve choices through bounded probes and record decisions with reopening triggers.

Acceptance: serialized example contracts cover both integration directions and
all three initial domains. A v1 compatibility mapping distinguishes preserved
behavior from rejected incomplete features. No harness SDK types enter kernel
contracts. Proposed names/versions and precedence are finalized here, not left
for a human decision or assumed to exist already.
Verification: schema validation and round-trip fixtures; review a failure,
continuation, minimization, and unsupported-capability example.

## Stage 1: Trusted Execution

### B03 - Restrict file tools to authorized data roots

Track: CORE. Priority: P1. Owner: Runtime security.
Effort: 2-3 days. Confidence: High.
Depends on: B01.
Basis: F01.
Areas: `agent_tools.py`, `orchestrator.py`, `trial_workspace.py`.

Autonomy: Implement one shared authorization context for every file operation. Derive
allowed roots server-side from run/attempt ownership; candidate-supplied paths or
workspace instructions never grant additional access.

- [ ] Pass an explicit tool context containing readable roots and writable candidate roots instead of the shared workspace root.
- [ ] Apply common authorization to read, write, glob, grep, copy, and any paths exposed through tool arguments.
- [ ] Exclude sibling sessions, evaluator code, evaluation data, interpreter environments, control-plane storage, and private evidence from candidate writes.

Acceptance: a tool call in session A cannot inspect private session B data or
modify its candidate; allowed candidate edits still work. Candidate code cannot
reach control-plane secrets through tool-readable workspace files.
Verification: actual tool-dispatch regressions for each operation, including
absolute paths, traversal, glob expansion, and shared-root targets.

### B04 - Make filesystem operations resistant to symlink races

Track: CORE. Priority: P1. Owner: Runtime security.
Effort: 2-3 days. Confidence: Medium.
Depends on: B03.
Basis: F02.
Areas: `agent_tools.py`, common filesystem helpers, artifact writes.

Autonomy: Target the qualified Linux descriptor-relative operations first. Deny
ambiguous links/imports unless a safe behavior has a regression; do not trade race
resistance for cross-platform compatibility.

- [ ] Reject dangling leaf symlinks independently of target existence and define allowed link behavior for reads and staged inputs.
- [ ] Use descriptor-relative no-follow operations for sensitive writes, parent creation, and replacement rather than resolve-then-open checks.
- [ ] Apply equivalent protection to candidate staging and result collection; reject hardlink/import patterns that could expose writable shared files.

Acceptance: dangling links, linked parents, and path swaps cannot create or
overwrite data outside authorized roots. Errors identify the denied operation.
Verification: reproduce F02 and exercise concurrent rename/link replacement;
assert outside sentinel bytes and permissions remain unchanged.

### B05 - Pin trusted evaluators and interpreter environments

Track: CORE. Priority: P1. Owner: Runtime + packaging.
Effort: 2-3 days. Confidence: High.
Depends on: B02, B03.
Basis: F01, F03.
Areas: `command_policy.py`, `skill_runtime.py`, skill loader, Docker packaging.

Autonomy: Use installed, digest-pinned skill/evaluator assets and a controlled
interpreter/import environment. Workspaces supply candidate inputs only; missing
trusted assets fail preflight instead of invoking a workspace fallback.

- [ ] Resolve approved evaluator entrypoints from the skill package and digest; remove precedence for same-named workspace files.
- [ ] Protect evaluator dependencies, interpreter paths, evaluation datasets, and import/search paths from candidate mutation or shadowing.
- [ ] Record evaluator/environment identity for attempts and fail before launch when pinned content is missing or changed.

Acceptance: creating `eval/run.py`, an import shadow, or a replacement interpreter
under the candidate tree cannot change trusted evaluator execution. Candidate
execution has no access to result-signing or operator credentials.
Verification: direct runner and full tool-loop shadowing regressions, plus an
installed-package smoke outside the checkout.

### B06 - Resolve one execution request for policy and subprocesses

Track: CORE. Priority: P1. Owner: Runtime.
Effort: 3-5 days. Confidence: Medium.
Depends on: B02, B04, B05.
Basis: F06; F11 executable declarations.
Areas: command policy/runner, snapshot helpers, runtime, trial workspaces.

Autonomy: Resolve argv, paths, fixed arguments, and output roots once into typed data.
Preserve compatible live/demo templates through that resolver; reject ambiguous
shell-dependent templates with a migration diagnostic.

- [ ] Resolve executable, typed argv, fixed arguments, CWD, inputs, outputs, and timeout into one immutable ExecutionRequest.
- [ ] Make authorization, pre-run snapshots, sequential/parallel execution, and result lookup consume that exact request.
- [ ] Route live and demo templates through the same resolver; support explicitly qualified executable bindings and reject unsupported bindings.

Acceptance: policy and process observe the same candidate bytes and paths.
Outputs remain in the attempt's output root. Shell expansion, duplicate fixed
flags, and argument spellings such as `--config=value` cannot evade validation.
Verification: F06 reproduction becomes passing; exercise absolute/relative
inputs, spaces, fixed-argument override attempts, and sequential/parallel parity.

### B07 - Make evaluator results authoritative

Track: CORE. Priority: P1. Owner: Evidence/backend.
Effort: 3-5 days. Confidence: Medium.
Depends on: B02, B05, B06.
Basis: F03.
Areas: orchestrator result ingestion, `output_parser.py`, result artifacts/stores.

Autonomy: Prefer direct trusted evaluator-to-server ingestion for local execution.
Bind canonical result content and all identities to the attempt; use authenticated
receipts when crossing a trust boundary. Model-visible nonces never establish
authority.

- [ ] Bind evaluator output to a server-created attempt and exact candidate/evaluator/dataset identities; parse it without requiring an LLM relay.
- [ ] Separate model annotations/proposals from verified metrics, gates, and scored snapshots; remove model-marker overwrite authority.
- [ ] Define idempotent receipt and replay handling; label legacy nonce-only/imported records honestly, with no retroactive authenticity upgrade.

Acceptance: changing metric, gate, candidate, or attempt identity invalidates a
receipt. Repeating a legitimate receipt does not create a new result. A model
can read a result without acquiring authority to forge the next result.
Verification: prior-nonce replay, model overwrite, forged snapshot, wrong-attempt,
duplicate delivery, and valid result tests through the built-in tool loop.

### B08 - Enforce process isolation and network capabilities

Track: CORE. Priority: P1. Owner: Runtime security + platform.
Effort: 5-8 days. Confidence: Low.
Depends on: B02, B04, B05, B06.
Basis: F04; universal execution boundary.
Areas: `plugin_runner.py`, command runner, Docker/deployment configuration.

Autonomy: Probe the existing container deployment as the first backend candidate,
including mount, identity, network, and resource enforcement. If it fails, evaluate
one alternative Linux backend. Select only a demonstrated solution; unavailable host
authority leaves qualification WAITING_EXTERNAL.

- [ ] Perform a bounded backend spike and select one enforceable Linux isolation implementation, with required host features and failure behavior documented.
- [ ] Isolate plugins/candidate execution from control-plane credentials, evaluator code, signing authority, sibling runs, and host services using enforced mounts/identities.
- [ ] Enforce default-deny network access and explicit allowed destinations; refuse unsupported capability requests or unavailable isolation rather than falling back silently.

Acceptance: `fs_write: none` prevents writes at the OS boundary and disallowed
network destinations are unreachable. Candidate-controlled subprocesses cannot
escape the same policy. Trusted local-code mode, if retained, is a separately
labeled operator policy and is not advertised as sandboxed.
Verification: real filesystem/network denial probes, child-process attempts,
host prerequisite failures, and trusted/untrusted mode contract tests.

### B09 - Bound resource use, output, and cancellation

Track: CORE. Priority: P1. Owner: Runtime/platform.
Effort: 3-4 days. Confidence: Medium.
Depends on: B06, B08.
Basis: F04 resource enforcement.
Areas: `plugin_runner.py`, command runner, session task cleanup.

Autonomy: Choose finite configurable limits from bounded workload probes and record
the tested termination bound. Enforce limits on descendants and parent-side buffering;
an unenforceable required resource cap rejects the capability.

- [ ] Enforce cumulative CPU, process-tree memory, wall time, process count, and configured filesystem/output quotas using the qualified backend.
- [ ] Stream bounded stdout/stderr and terminate immediately on limit violations instead of checking watcher flags after `communicate` completes.
- [ ] Propagate stop/timeout/cancel through plugins, evaluators, and descendants; define bounded cleanup and explicit incomplete-cleanup status.

Acceptance: resource breach stops the process tree within a documented tested
bound and produces an attributed failed attempt. No unbounded parent buffering
or orphaned child remains after successful cleanup.
Verification: bounded synthetic CPU/memory/output/process tests; cancellation
during bootstrap and evaluation; independent process inspection after teardown.

### B10 - Qualify the trusted execution boundary (G1)

Track: CORE. Priority: P1. Owner: QA + runtime security.
Effort: 2-3 days. Confidence: Medium.
Depends on: B03, B04, B05, B06, B07, B08, B09.
Basis: F01-F04, F06.
Areas: security fixtures, tool-loop integration, isolation CI lane.

Autonomy: Run attacks against disposable files, synthetic secrets, and isolated
processes. Inspect sentinels and teardown independently of the tested API response;
missing real enforcement evidence keeps G1 incomplete.

- [ ] Exercise the combined attack paths: candidate edits, evaluator shadowing, symlinks, credential reachability, forged results, and child-process escape attempts.
- [ ] Run the real live command templates in fresh isolated workspaces and confirm private evidence cannot be changed after acceptance.
- [ ] Capture a capability-bound qualification record and document which privileges/environments remain outside the guarantee.

Acceptance: every reproduced trust finding is closed by a failing-before/passing-
after regression, and declared enforcement is observed outside application-only
path checks. No untrusted adapter/plugin rollout proceeds on a failed G1.
Verification: exact-commit adversarial suite, process cleanup evidence, and
isolated image/package smoke; no production credentials or targets required.

## Stage 2: Domain Correctness

### B11 - Validate skill parameters using a declared schema subset

Track: CORE. Priority: P1. Owner: API/backend.
Effort: 2-3 days. Confidence: High.
Depends on: B02.
Basis: F12.
Areas: `src/api/research.py`, skill manifest/loader, API contract tests.

Autonomy: Select a maintained standard JSON Schema validator through the decision
procedure and pin its supported dialect/subset. Resolve defaults separately, validate
the resolved object once, and reuse the contract for API/UI errors.

- [ ] Adopt a standard JSON Schema validator and declare the supported dialect/subset, including numeric bounds, enums, nesting, and additional properties.
- [ ] Validate omitted/null parameter objects, required values, and defaulted values with one canonical resolution path.
- [ ] Return field-addressed errors and keep UI form validation consistent with server authority.

Acceptance: invalid bounds and missing required fields are rejected before
session side effects; permitted extra properties behave as declared. Defaults
are applied deliberately rather than assumed to be inserted by validation.
Verification: F12 bounds regression, omitted object, bool/number distinction,
enums/nested cases, and OpenAPI request/response fixtures.

### B12 - Bind validated parameters to actual work

Track: CORE. Priority: P1. Owner: Skill SDK + runtime.
Effort: 3-4 days. Confidence: Medium.
Depends on: B06, B11.
Basis: F06, F12.
Areas: `skill_runtime.py`, bundled manifests/bootstrap/evaluators.

Autonomy: Express bundled-skill differences as manifest bindings and migrate their
fixtures together. Trace a deliberately nondefault value into actual evaluator inputs;
a core branch for a skill name is not an acceptable shortcut.

- [ ] Define declarative parameter bindings for bootstrap, candidate initialization, fixed evaluator argv, and output metadata.
- [ ] Apply nondefault target/scorer/latency/duration values and reject undeclared model attempts to change operator-fixed arguments.
- [ ] Remove the core `prompt-engineering` ID branch and migrate bundled packages to the same binding contract.

Acceptance: submitted values can be traced from API to resolved request and
actual evaluator behavior. The code skill uses the requested candidate source;
demo/scorer/dataset selection cannot be changed by model-authored argv.
Verification: nondefault values for every bundled skill, duplicate flag/alias
override attempts, and live/demo binding parity.

### B13 - Enforce parser and result semantics

Track: CORE. Priority: P1. Owner: Evidence + skill SDK.
Effort: 2-4 days. Confidence: High.
Depends on: B07, B11.
Basis: F03, F11.
Areas: `output_parser.py`, result artifact validators, manifest/runtime.

Autonomy: Use one normalized result contract for stdout and artifact paths. Missing
status/gates, unknown required semantics, or invalid numbers produce explicit invalid
evidence, never implicit success.

- [ ] Honor declared parser format and marker prefix and enforce required fields, field types, finite numbers, units, and schema version.
- [ ] Normalize declared failure statuses to non-winning outcomes; missing gates and malformed output must not become successful defaults.
- [ ] Preserve trusted raw evidence separately from its normalized result and apply identical rules to stdout and file-based collection.

Acceptance: custom markers parse; failed results cannot carry promotable placeholder
metrics; missing required fields and nonfinite values are rejected consistently.
Verification: F11 probes, mixed stdout/noise, multiple markers, truncated output,
invalid JSON, stale fallback files, and signed/unsigned imported-result cases.

### B14 - Use one objective comparator across all paths

Track: CORE. Priority: P1. Owner: Research kernel + storage.
Effort: 3-4 days. Confidence: High.
Depends on: B02, B13.
Basis: F05.
Areas: orchestrator, both stores, significance, stagnation, promotion/ranking.

Autonomy: Use declared epsilon, defaulting to exact comparison when absent, and a
stable tie policy preserving the existing eligible winner. Reject incomparable or
unknown objective context; migrate only historical rows with enough provenance.

- [ ] Implement the resolved objective comparator with direction, epsilon/ties, gate eligibility, and absent/nonfinite metric behavior.
- [ ] Use it for decisions, stored bests, aggregate queries, stagnation, promotion eligibility, and displayed rankings.
- [ ] Define reconciliation of historical best rows using their known objective; leave ambiguous legacy objective data flagged rather than guessed.

Acceptance: 100-to-80 latency improves and 100-to-120 regresses; maximization
behavior remains correct. SQLite and Postgres choose the same eligible winner.
Verification: cross-store comparison matrix, failed gates, tie/epsilon tests,
historical reconciliation fixture, and minimization promotion preview.

### B15 - Separate candidate identity from repeated observations

Track: CORE. Priority: P1. Owner: Research/statistics + storage.
Effort: 3-5 days. Confidence: Medium.
Depends on: B02, B13, B14.
Basis: F11 trial identity; replication/significance caveats.
Areas: iteration snapshots, deduplication, significance, instruction templates.

Autonomy: Keep candidate digest and observation ID separate. Predeclare repeats/sample
requirements in evaluation policy and charge each authorized observation; distinguish
network replay from an intentional repeat.

- [ ] Honor declarative identity fields and include evaluator/data/environment/fidelity context in comparison identity.
- [ ] Give each authorized repeat a distinct observation identity; preserve candidate deduplication without rejecting required replication.
- [ ] Distinguish exploratory point estimates from qualification requiring sample counts/holdouts; revise blanket no-rerun instructions.

Acceptance: intentional repeats are admitted within budget; accidental duplicate
submissions do not run twice. Inconclusive significance is visible and cannot
silently satisfy production qualification.
Verification: noisy seeded fixture, repeat scheduling, duplicate delivery,
changed evaluation-context isolation, and significance fallback tests.

### B16 - Implement goal and phase semantics explicitly

Track: CORE. Priority: P1. Owner: Research kernel + skill SDK.
Effort: 3-4 days. Confidence: Medium.
Depends on: B13, B14, B15.
Basis: F11 satisfice and phase declarations.
Areas: phase plan/state, skill runtime, terminal reason handling.

Autonomy: Implement declarative optimize/satisfice and phase predicates over verified
observations. Preserve explicit rejection of plugin modes until B49; do not execute
arbitrary expressions to avoid deciding a contract.

- [ ] Implement explicit optimize and satisfice decisions, threshold evidence, and terminal outcomes for the initial schema.
- [ ] Evaluate declarative phase rules against verified evidence and defined min/max observation requirements, including validation phases.
- [ ] Reject plugin phase/resolver modes until their separately qualified implementation exists; do not silently substitute declarative behavior.

Acceptance: satisfice completion reflects its declared condition, and phases
cannot advance from model prose or unrelated/stale evidence. Exhaustion and
inconclusive outcomes remain distinct from success.
Verification: threshold-crossing, never-satisfied, phase-boundary, repeat/dwell,
stale evidence, and unsupported plugin-mode tests.

### B17 - Enforce preflight and publish executable support

Track: CORE. Priority: P1. Owner: Skill SDK + runtime.
Effort: 2-3 days. Confidence: High.
Depends on: B06, B08, B11, B12, B13, B16.
Basis: F11.
Areas: skill loader/registry, preflight, command bindings, skills API.

Autonomy: Generate support from executable handlers and conformance cases. Reject
unimplemented declarations before side effects; evaluate generated-file prerequisites
after bootstrap, without treating their earlier absence as failure.

- [ ] Implement local-file checks at the correct stage: source prerequisites before bootstrap and generated-output readiness after bootstrap.
- [ ] Generate capability/support descriptors from actual implementations; reject inert executable, parser, plugin, and promotion declarations before launch.
- [ ] Validate runtime/toolchain availability without broadening base execution authority; expose actionable diagnostics to API and UI.

Acceptance: every accepted manifest feature has a behavior test. A missing
required file fails at the appropriate stage, and a declared executable is
either explicitly supported under policy or rejected with a specific reason.
Verification: support-matrix coverage, before/after-bootstrap failures, absent
toolchain, optional prerequisites, and schema-valid unsupported declarations.

### B18 - Make promotion and rollback domain-driven

Track: CORE. Priority: P1. Owner: Promotion/backend.
Effort: 4-6 days. Confidence: Medium.
Depends on: B07, B14, B17.
Basis: F09; target and rollback consistency.
Areas: config promoter, promotion approval/targets, both stores, API.

Autonomy: Use temporary file targets and an agent-owned test webhook receiver.
Implement the product's approval contract with test identities and fault injection; no
real production approval or target is needed to close this card.

- [ ] Compile declared scope dependencies and domain evidence requirements beneath mandatory operator approval/policy constraints.
- [ ] Bind decisions to verified candidate and target identities; use canonical skill/target keys for prior promotion and rollback lookup.
- [ ] Define file/webhook effect intent, idempotency, reconciliation, and rollback behavior for failures between external effect and database acknowledgement.

Acceptance: a non-ML development-to-production policy needs no fabricated ML
evidence, and stale approvals cannot promote a changed winner. Legacy records
remain readable; ambiguous legacy rollback requires explicit reconciliation.
Verification: synthetic non-ML scope graph, invalid/cyclic scopes, stale approval,
two-skill target separation, file rollback, and fault-injected webhook receiver.

### B19 - Qualify domain semantics (G2)

Track: CORE. Priority: P1. Owner: QA + skill SDK.
Effort: 2-4 days. Confidence: Medium.
Depends on: B10, B11, B12, B13, B14, B15, B16, B17, B18.
Basis: F05, F06, F09, F11, F12.
Areas: domain conformance fixtures, API/session/promotion integration.

Autonomy: Create a small new fixture skill with a fresh identity and drive real
API/session paths. Run persistent selection/promotion checks on both stores; parsing
fixtures alone cannot close semantic acceptance.

- [ ] Run one complete workflow per supported objective, parser, parameter binding, and promotion-scope shape.
- [ ] Introduce a small fixture skill without core/UI edits and verify unsupported extensions fail before side effects.
- [ ] Exercise sequential and parallel observation paths with identical domain semantics and isolated data.

Acceptance: all supported declarations have execution evidence; no skill-ID
branch is needed for a conforming new skill. F05/F06/F09/F11/F12 closure is
supported by integrated behavior, not just manifest parsing.
Verification: conformance report plus regression tests on both stores where
selection/promotion contracts depend on persistence.

## Stage 3: Durable Operation

### B20 - Persist a complete resolved run specification

Track: CORE. Priority: P1. Owner: Storage + skill SDK.
Effort: 3-5 days. Confidence: Medium.
Depends on: B02, B12, B17, B19.
Basis: F08; reproducibility.
Areas: research manifest, session creation, both stores, migrations.

Autonomy: Persist a versioned canonical nonsecret run snapshot plus content digests;
store secret references separately from values. Preserve unknown legacy provenance
explicitly and test migrations on copies/disposable databases.

- [ ] Store canonical parameters/defaults, objective, policy, evaluator/dataset/package digests, runtime identity, and effective configuration.
- [ ] Persist secret references with an explicit rebinding policy, never credential values; hash the nonsecret resolved spec.
- [ ] Add schema migrations and legacy-read behavior; separate immutable inputs from mutable status/usage/checkpoints.

Acceptance: a completed or interrupted run can be inspected independently of
the current registry/defaults. Unknown old fields or missing provenance are
reported, not backfilled with invented current facts.
Verification: SQLite/Postgres migration and round-trip tests, registry mutation
after start, secret-redaction inspection, and old-run read fixtures.

### B21 - Isolate run workspaces and persist immutable artifacts

Track: CORE. Priority: P1. Owner: Artifact/storage + runtime.
Effort: 4-6 days. Confidence: Medium.
Depends on: B10, B20.
Basis: F07, F08; artifact ownership.
Areas: session manager, trial workspaces, artifact/snapshot modules.

Autonomy: Use local content-addressed bundles with server-created run/attempt roots
and atomic publication. Implement retention from live references; test partial cleanup
in a disposable store rather than deleting user artifacts.

- [ ] Allocate unique run/attempt roots and retain logical subject/variant as metadata; stop archiving an unrelated active or historical run path.
- [ ] Introduce local content-addressed candidate bundles, results, and parent snapshots with safe import limits and digest verification.
- [ ] Make publication atomic and separate references from mutable workspace files; define partial-write cleanup and retention that respects live references.

Acceptance: fresh runs and continuations cannot replace older run artifacts.
Multi-file candidate changes can be snapshotted and reconstructed exactly;
symlinks/archive traversal cannot widen imported roots.
Verification: same-subject runs, bundle round trips, partial writes, interrupted
cleanup, retained parent references, and immutable artifact tampering tests.

### B22 - Reserve work and fence mutations across workers

Track: CORE. Priority: P1. Owner: Distributed storage/runtime.
Effort: 4-6 days. Confidence: Medium.
Depends on: B21.
Basis: F07.
Areas: session admission, state machine, both stores, execution/promotion writes.

Autonomy: Extend the existing database reservation/fencing approach instead of adding
another coordination service. Select documented lease timing from crash probes;
validate with actual competing processes and stale writers.

- [ ] Atomically reserve logical work and global capacity before bootstrap/filesystem effects; document duplicate-request and limit semantics.
- [ ] Add worker ownership/lease lifecycle and monotonically fenced writes for attempts, artifacts, results, and promotion effects.
- [ ] Reconcile expired reservations without classifying another live worker's sessions as orphaned; retain a simpler correct single-worker SQLite path.

Acceptance: simultaneous requests through two workers neither exceed the
configured global limit nor share a mutable directory. A stale owner cannot
publish evidence or perform a new promotion effect after ownership changes.
Verification: real separate-process Postgres admission race, stale owner,
worker crash, lease expiry, and bootstrap failure reservation cleanup.

### B23 - Restore runs from persisted configuration and checkpoints

Track: CORE. Priority: P1. Owner: Runtime recovery.
Effort: 3-5 days. Confidence: Medium.
Depends on: B20, B21, B22.
Basis: F08; recovery semantics.
Areas: session manager, manifests, state machine, continuation tests.

Autonomy: Resume from pinned inputs/checkpoints, preserving lineage. Unavailable
credentials or changed versions become explicit recovery states; implement and test
migration/rebinding rather than silently substituting current defaults.

- [ ] Reconstruct continuation from pinned spec/artifacts, including nondefault parameters, scorer references, limits, and objective policy.
- [ ] Distinguish pause, native harness resume, research continuation into a new session, and restart recovery with unknown in-flight effects.
- [ ] Require explicit migration/rebinding when versions, artifacts, or credentials cannot satisfy the original contract; preserve parent lineage.

Acceptance: restart cannot silently change scorer, dataset, model configuration,
or fixed parameters. A missing checkpoint/artifact produces an actionable
recovery state rather than a fresh run disguised as a resume.
Verification: nondefault parameter crash/resume, changed registry, missing
artifact/credential reference, parent preservation, and duplicate resume tests.

### B24 - Resolve provider/model roles and capabilities consistently

Track: CORE. Priority: P1. Owner: Provider/runtime.
Effort: 2-4 days. Confidence: High.
Depends on: B17, B20.
Basis: F10.
Areas: `llm_provider.py`, orchestrator configuration, manifest/API.

Autonomy: Use explicitly configured provider/model roles and demonstrated
capabilities; do not choose a new paid model to bypass an unsupported setting. Test
request construction offline, then use only authorized live identities.

- [ ] Apply primary/insight model and output/context settings for all provider paths, including the default provider.
- [ ] Validate required capabilities before session side effects and persist requested versus effective configuration/model identity.
- [ ] Move provider-specific request options and error classification behind their adapters; reject unsupported settings with actionable diagnostics.

Acceptance: Anthropic and OpenAI selections honor the resolved run configuration,
including insight roles and caps. Unsupported model/context combinations do not
create a run that fails only on its first call.
Verification: fake-client request assertions for both providers, default-path
capability mismatch, token caps, and effective-config persistence.

### B25 - Account for usage and reserve bounded spend

Track: CORE. Priority: P1. Owner: Usage/storage + runtime.
Effort: 4-6 days. Confidence: Medium.
Depends on: B22, B24.
Basis: F10; total research cost caveat.
Areas: usage ledger, providers, evaluator calls, orchestration/API.

Autonomy: Use one append-only/idempotent usage ledger and atomic reservations.
Snapshot the pricing basis, distinguish unknown from zero, and never increase an
authorized spending cap to make qualification finish.

- [ ] Record per-attempt/provider/model agent and evaluator usage with idempotent cost attribution and a versioned pricing basis.
- [ ] Distinguish reported usage, estimated money, billed money, and unavailable cost; handle cached/reasoning tokens where supported.
- [ ] Reserve budget atomically before bounded work, reconcile afterward, and use explicit time/resource caps when a driver cannot enforce a money ceiling.

Acceptance: unknown cost is never displayed as zero; retries/replayed events do
not double-charge. Concurrent reservations cannot oversubscribe a strict known
budget. Any advisory-only monetary limit is labeled with its limits.
Verification: provider-specific calculations, mock zero-cost case, evaluator
spend, unknown pricing, aborted reservation, retries, and parallel budget races.

### B26 - Persist events and support replay across workers

Track: CORE. Priority: P1. Owner: Storage + API/realtime.
Effort: 4-6 days. Confidence: Medium.
Depends on: B20, B22.
Basis: distributed event caveat; external harness lifecycle.
Areas: event storage/outbox, `src/ws/events.py`, APIs, broadcaster integration.

Autonomy: Start with a transactional database outbox and bounded cursor
polling/replay, using the existing stores. Add another broker only if measured
requirements cannot be met; persist events before treating notification as delivery.

- [ ] Persist versioned correlated events with event ID, run/attempt, producer, cursor/sequence, timestamp, and ownership epoch.
- [ ] Tie committed state transitions to durable event publication; add cross-worker delivery and cursor-based catch-up with backpressure.
- [ ] Define duplicate/out-of-order ingestion, expired cursor behavior, redaction, and atomic snapshot-plus-cursor resynchronization.

Acceptance: a client connected to worker B observes a run on worker A and can
recover missed updates. State and event publication cannot diverge silently;
duplicate events do not apply side effects twice.
Verification: restart between commit/publication, reconnect/catch-up, slow
consumer, cursor expiry, and two-worker fan-out tests.

### B27 - Qualify durable operation and migrations (G3)

Track: CORE. Priority: P1. Owner: QA + backend/platform.
Effort: 3-5 days. Confidence: Medium.
Depends on: B19, B23, B25, B26.
Basis: F07, F08, F10; event/artifact durability.
Areas: recovery/distributed suites, migration fixtures, operational runbook.

Autonomy: Own the worker processes, disposable databases, and fault injector. Kill
only test-owned resources and inspect persisted state after restart; a mocked race or
single-worker run cannot replace multi-process evidence.

- [ ] Exercise process death during bootstrap, evaluation, result acceptance, event publication, and promotion intent handling.
- [ ] Validate upgraded SQLite/Postgres databases, old manifests, preserved artifact references, and documented backup/restore recovery.
- [ ] Run real simultaneous worker admission and resumed-run scenarios with nondefault settings and usage reservations.

Acceptance: no duplicate authoritative result/effect, silent configuration drift,
shared mutable workspace, or stale-owner write occurs in the qualified cases.
Unknown external effects are exposed for reconciliation, never assumed absent.
Verification: exact-commit multi-process logs, migration/restore evidence, and
failure-injection matrix with bounded cleanup times.

## Stage 4: Harness Integration

### B28 - Extract a research kernel from the built-in loop

Track: CORE. Priority: P2. Owner: Backend architecture.
Effort: 5-8 days. Confidence: Medium.
Depends on: B27.
Basis: universal harness architecture.
Areas: `orchestrator.py`, skill runtime, state/decision/evidence services.

Autonomy: Extract one kernel responsibility at a time behind characterization tests.
Keep the corrected built-in path runnable between commits; a broad rewrite is not
required to remove provider types from the kernel.

- [ ] Extract attempt scheduling, objective/phase decisions, budgets, verified evidence, and promotion eligibility behind kernel-facing operations.
- [ ] Replace skill-runtime callbacks into orchestrator-private helpers with explicit context/services and stable value contracts.
- [ ] Keep provider conversation, tool serialization, context compaction, and model retry behavior inside the built-in driver boundary.

Acceptance: the kernel completes a research lifecycle with a deterministic
driver and no provider SDK/message-block dependency. Existing corrected behavior
is retained through incremental changes.
Verification: characterization/parity tests for the supported semantics and
dependency/import checks that prevent harness types leaking back into the kernel.

### B29 - Define harness adapters, registry, and capability negotiation

Track: CORE. Priority: P2. Owner: Harness SDK.
Effort: 3-4 days. Confidence: Medium.
Depends on: B28.
Basis: universal harness contract.
Areas: proposed adapter interface/registry, run configuration, conformance fixtures.

Autonomy: Make required operations minimal and versioned; advertise optional
capabilities individually. Use a deterministic fake adapter to specify behavior before
integrations, including unknown events and unsupported lifecycle actions.

- [ ] Implement versioned start/attach, event stream, cancel, close, and optional pause/resume/steering capabilities.
- [ ] Resolve adapter identity/version and permissions into the run spec; validate skill/operator requirements before launch.
- [ ] Define event/proposal/error schemas and a reusable fake adapter plus conformance tests, including unsupported capability behavior.

Acceptance: registering an adapter requires no kernel branch for its name.
An unsupported pause/resume is explicit; kill is not presented as successful
pause, and cross-harness continuation is not claimed as native transcript resume.
Verification: conforming/nonconforming fake adapters, version mismatch, lifecycle
ordering, cancelled start, cleanup, and unknown event compatibility tests.

### B30 - Wrap the existing agent and neutralize instruction assembly

Track: CORE. Priority: P2. Owner: Built-in harness/runtime.
Effort: 3-5 days. Confidence: Medium.
Depends on: B24, B29.
Basis: preserve working built-in behavior; harness-specific prompt coupling.
Areas: orchestrator wrapper, `agent_tools.py`, `CLAUDE.md`, skill primers.

Autonomy: Wrap the corrected loop first, then separate common and harness-specific
instructions. Test rendered prompts as product assets; those prompts do not control
the implementation agent's repository workflow.

- [ ] Implement BuiltinHarnessAdapter using the existing provider/tool loop and route its proposals through the kernel.
- [ ] Separate common research instructions from tool/harness-specific instructions; render workspace instruction files only through adapters.
- [ ] Preserve bounded context/retry behavior while closing clients/tasks and per-session state at lifecycle end.

Acceptance: users can select the built-in adapter explicitly and obtain the
corrected lifecycle. Core behavior does not depend on a `CLAUDE.md` filename or
Anthropic tool-block shape.
Verification: existing focused integration suite through the adapter, repeated
session resource cleanup, instruction snapshot tests, and provider parity.

### B31 - Expose scoped research operations to attached agents

Track: CORE. Priority: P1. Owner: API/auth + kernel.
Effort: 4-6 days. Confidence: Medium.
Depends on: B07, B22, B26, B30.
Basis: attached-driver integration; evidence/approval authority.
Areas: API routes, auth/audit, kernel operations, OpenAPI.

Autonomy: Derive paths and scoped authority server-side; expose only research
operations and promotion preview to attached agents. Use test-issued scoped
credentials and prove revocation/cross-run denial without global operator access.

- [ ] Expose create/attach, constraints, candidate submission, evaluation request, verified-result inspection, lifecycle control, and promotion preview.
- [ ] Issue short-lived run/attempt-scoped credentials with revocation and permissions distinct from operator/promotion approver authority.
- [ ] Validate candidate digests and idempotency keys; derive storage paths server-side and rate/size-limit submitted data and events.

Acceptance: an attached agent can complete research without the global operator
token, modify only its authorized run, and cannot declare its own results verified
or approve production promotion.
Verification: cross-run/tenant identity denial, expired/revoked token, forged
receipt, duplicate request, excessive upload, and API contract tests.

### B32 - Provide an attached-agent CLI workflow

Track: CORE. Priority: P2. Owner: CLI/developer experience.
Effort: 2-3 days. Confidence: High.
Depends on: B31.
Basis: portable attached integration without a mandatory tool protocol.
Areas: `src/cli.py`, API client, examples and installed package tests.

Autonomy: Extend the existing CLI and publish JSON schemas/exit codes. Use
reference-based credentials and bounded waits; prove the workflow from an installed
package outside the checkout.

- [ ] Add machine-readable commands for run creation/attach, constraints, candidate staging, evaluation, results, and preview.
- [ ] Support scoped credential handling, event cursor persistence, bounded waits, and stable exit/error codes without leaking credentials in arguments/logs.
- [ ] Publish a minimal external-driver example and deterministic shell/SDK conformance fixture.

Acceptance: a simple external program completes the same verified workflow via
the CLI/API, including reconnect, with no knowledge of internal Python classes.
Verification: installed CLI smoke outside checkout, JSON output schema tests,
interruption/reconnect, and redaction checks.

### B33 - Implement a managed process-driver host

Track: CORE. Priority: P2. Owner: Harness runtime/platform.
Effort: 4-6 days. Confidence: Medium.
Depends on: B08, B09, B25, B26, B29, B30.
Basis: managed adapters and custom-driver contract.
Areas: adapter process host, event normalization, workspace/credential setup.

Autonomy: Start with the documented JSONL custom-driver transport under the qualified
process host. Bound event size/queues and supervise descendants; ordinary driver tool
access never becomes evaluator or promotion authority.

- [ ] Launch drivers in the qualified isolation context with explicit environment, workspace, instruction artifacts, credentials, and executable identity.
- [ ] Implement versioned structured event/proposal transport, bounded stderr/stdout, backpressure, start deadlines, and process supervision.
- [ ] Provide a custom JSONL driver example; keep its ordinary shell activity distinct from trusted evaluator execution and promotion authority.

Acceptance: a custom driver can propose candidates and request evaluation,
but cannot bypass evidence, budget, or filesystem policy. Driver crash/timeout
leaves an attributed recoverable/terminal state and bounded cleanup.
Verification: valid/malformed/oversized event streams, stalled consumer,
credential isolation, descendant cleanup, and mid-event process death.

### B34 - Add the Codex harness adapter

Track: CORE. Priority: P2. Owner: Harness integrations.
Effort: 4-7 days. Confidence: Low.
Depends on: B31, B33.
Basis: first independent external harness.
Areas: new Codex adapter, capability profile, protocol fixtures.

Autonomy: At implementation time, select the least complex officially supported
structured interface satisfying required lifecycle/permission events. Pin the actual
version, record unsupported optional features, and run live checks only within
inventoried authority/budget.

- [ ] Recheck official integration documentation at implementation time, choose and pin a supported structured interface, and record the tested version/transport.
- [ ] Map native lifecycle, candidate changes, usage, permission/approval outcomes, and cancellation into the common contracts.
- [ ] Implement only demonstrated native resume/pause features; enforce scoped research/evaluator authority even when the harness has its own tools.

Acceptance: the adapter executes a small real research lifecycle through the
same trusted evaluator as the built-in driver; denied permissions do not hang
unattended runs or become success.
Verification: recorded protocol conformance fixtures plus a bounded opt-in live
smoke with explicit version, authentication mode, usage, and teardown evidence.

### B35 - Add the Claude Code harness adapter

Track: CORE. Priority: P2. Owner: Harness integrations.
Effort: 4-7 days. Confidence: Low.
Depends on: B31, B33.
Basis: second independent external harness.
Areas: new Claude Code adapter, capability profile, protocol fixtures.

Autonomy: Apply the same interface-selection procedure using current official Claude
Code documentation and observed protocol behavior. Prefer structured events to
terminal parsing; missing live authentication blocks live qualification, not ready
fixture work.

- [ ] Recheck official programmatic/SDK documentation, select and pin the supported interface, and record its authentication and hosting requirements.
- [ ] Normalize lifecycle, candidate changes, usage, permissions, errors, and session identifiers without parsing human-oriented terminal prose.
- [ ] Implement cancellation and explicitly qualified resume behavior; prevent access to evaluator authority or global operator credentials.

Acceptance: a real run uses the common evaluation/promotion contract and has
honest capability and usage reporting. Native transcript/session state remains
adapter-owned and versioned.
Verification: protocol fixtures and bounded opt-in live smoke including tool
denial, interruption, supported resume, and child-process cleanup.

### B36 - Qualify managed and attached harness contracts (G4)

Track: CORE. Priority: P1. Owner: QA + harness SDK/security.
Effort: 3-5 days. Confidence: Medium.
Depends on: B30, B32, B34, B35.
Basis: both meanings of harness universality.
Areas: adapter conformance suite, API/CLI integration, isolation fixtures.

Autonomy: Use one shared conformance contract with explicit per-adapter capabilities.
Report fixture and live runs separately; do not infer compatibility or native resume
from another adapter's success.

- [ ] Run one shared contract suite for built-in, custom process, Codex, and Claude Code adapters and the attached API/CLI workflow.
- [ ] Exercise permissions, unsupported capabilities, duplicate/out-of-order events, unknown usage, cancel, unavailable executable, and version mismatch.
- [ ] Verify no managed/attached path can bypass G1 evidence or scope rules, including reusing a receipt across drivers/runs.

Acceptance: each advertised adapter passes required semantics; optional features
are declared individually. Fixture success and actual live-version success are
reported separately, and missing live evidence blocks a compatibility claim.
Verification: per-adapter results with versions, capabilities, negative cases,
and a concise supported/unsupported matrix.

## Stage 5: Real Domains and Qualification

### B37 - Qualify a real prompt-evaluation domain

Track: CORE. Priority: P2. Owner: Domain/evaluation.
Effort: 3-5 days. Confidence: Medium.
Depends on: B19, B23, B25, B31.
Basis: evaluator independence, realistic evaluation, nondefault scorer settings.
Areas: prompt-engineering skill, scorer contract, evaluation datasets.

Autonomy: Use an authorized controlled scorer that evaluates real model outputs
against pinned held-out examples. Prefer an already available local endpoint when
equivalent; retain offline endpoint fixtures as separate evidence, never as a live
substitute.

- [ ] Define pinned test/holdout datasets, scorer identity/version, request/result schema, and failure behavior using a controlled real scoring endpoint.
- [ ] Account for scorer usage and preserve fixed endpoint/data configuration across continuation; protect held-out data from candidate mutation.
- [ ] Add repeatability/qualification rules and a candidate-bound promotion fixture; retain a clearly separated offline demo mode.

Acceptance: measured results come from the declared real scorer, its failure
cannot silently invoke a simulator, and optimization evidence is distinguishable
from held-out qualification evidence.
Verification: live controlled-scorer run plus deterministic endpoint fixtures,
failure/no-fallback, data tampering, and continuation with nondefault settings.

### B38 - Replace refactor proxies with a real code/test workflow

Track: CORE. Priority: P2. Owner: Domain/code execution.
Effort: 4-6 days. Confidence: Medium.
Depends on: B09, B19, B21.
Basis: code-refactor realism and multi-file candidate support.
Areas: code-refactor skill, isolated evaluator, fixture project.

Autonomy: Create a small multi-file Python fixture project with protected behavior
tests, including a semantics-breaking refactor. Implement genuine test/lint/type
evidence; omit performance claims until an actual controlled benchmark exists.

- [ ] Evaluate actual candidate bundles against fixed tests and explicit lint/type/behavior requirements instead of source-text needles.
- [ ] Protect tests and evaluation entrypoints; collect exit codes, test reports, and coverage of the expected test set from the trusted evaluator.
- [ ] Measure performance only where a controlled benchmark exists; otherwise omit the performance claim and reject a required-but-unmeasured gate.

Acceptance: a semantics-breaking refactor fails even when it preserves expected
text, and editing test files cannot improve the result. Requested target files
and multi-file patches are evaluated and promoted exactly as snapshotted.
Verification: valid/invalid refactor fixtures, test deletion/skip attempts,
timeouts, dependency failures, and artifact-bound promotion preview.

### B39 - Qualify measured latency minimization

Track: CORE. Priority: P2. Owner: Domain/performance evaluation.
Effort: 3-5 days. Confidence: Medium.
Depends on: B09, B19, B21.
Basis: F05 and the real-domain compatibility matrix.
Areas: new benchmark skill/fixture service, measurement protocol, metrics.

Autonomy: Use an agent-owned loopback HTTP service with a fixed data/query workload.
Freeze request mix, warmup, percentile/guardrails, and repeat policy before
comparison; measure a real implementation change, not synthetic sleep-based score
inflation.

- [ ] Choose one controlled service/workload, fixed request mix, warmup, resource envelope, and latency/throughput measurement procedure.
- [ ] Define lower-is-better objective, guardrails, repeated measurements, uncertainty, and immutable baseline/evaluation-context identity.
- [ ] Package the workload as a conforming skill with no core edits and label the environment limits of its measured results.

Acceptance: the pipeline selects a measured latency improvement only when
constraints and qualification evidence pass; noisy or incomparable samples do
not become a production winner. Simulated DB scores remain a separate mode.
Verification: baseline/improved/regressed controls, noise/repeat tests, resource
contention detection, and minimization through storage and promotion.

### B40 - Expose harness capabilities, provenance, and usage in the UI

Track: CORE. Priority: P2. Owner: Frontend + API.
Effort: 4-6 days. Confidence: Medium.
Depends on: B25, B26, B31, B36.
Basis: usable universal workflow and honest status/cost presentation.
Areas: new research, detail, settings, metrics, promotion UI/API types.

Autonomy: Extend existing skill-driven UI patterns using API capability descriptors.
Choose fixtures and viewport coverage autonomously; verify actual browser flows as
well as component tests, without redesigning unrelated screens.

- [ ] Add harness selection and capability/preflight diagnostics while preserving skill-driven parameter forms and metrics.
- [ ] Show verified/imported evidence, candidate/evaluator context, usage quality, resume mode, and supported lifecycle actions.
- [ ] Implement cursor-based reconnect/resync and permission-aware attached-run views; keep controls consistent with server authorization.

Acceptance: users can start and inspect every qualified harness without UI
branches for its name; unknown cost is visibly unknown and unsupported controls
are explained. Reconnection restores authoritative state.
Verification: component tests, API typecheck, and desktop/mobile browser flows
for start, failure, reconnect, interruption, resume, and promotion preview.

### B41 - Rank only comparable results

Track: CORE. Priority: P2. Owner: Storage + results API/UI.
Effort: 2-4 days. Confidence: High.
Depends on: B14, B15, B20.
Basis: leaderboard comparability and bounded-query caveats.
Areas: `src/api/skills.py`, both stores, leaderboard/metrics UI.

Autonomy: Rank within explicit comparable-context groups using storage queries and
indexes. Keep unknown legacy context separate; use enough synthetic history to expose
the recent-500 bug on both stores.

- [ ] Group results by evaluation-context identity, objective, units, dataset/scorer/fidelity, and applicable subject/variant constraints.
- [ ] Implement direction-aware eligible rankings in storage with explicit pagination/window semantics and matching indexes.
- [ ] Show incomparable/legacy results as separate groups rather than silently merging them into one champion table.

Acceptance: differing scorer/data/fidelity contexts cannot produce a misleading
shared winner; older champions are not lost through a recent-500 prefilter while
the API describes the ranking as global.
Verification: mixed-context and >500-session fixtures, minimize/maximize parity,
pagination boundaries, and bounded query-plan inspection.

### B42 - Make compatibility qualification enforceable in CI

Track: CORE. Priority: P1. Owner: QA/CI + maintainers.
Effort: 3-5 days. Confidence: Medium.
Depends on: B36, B37, B38, B39, B40, B41.
Basis: all findings; prevent schema-only or mock-only success claims.
Areas: `.github/workflows/ci.yml`, conformance suites, packaging/OpenAPI checks.

Autonomy: Extend the existing CI lanes and make missing required coverage fail
visibly. Prepare live jobs from the capability inventory; observe completed runs on
the candidate commit rather than declaring success from workflow YAML.

- [ ] Add named deterministic gates for trust, domain semantics, migrations, cross-store behavior, adapters, API/CLI/UI, and deployment artifacts.
- [ ] Pin qualification inputs/adapter versions and provide opt-in live jobs with scoped credentials, budget limits, and sanitized evidence output.
- [ ] Enforce explicit skip ownership and unsupported-capability reporting; check installed package/container behavior outside the source tree.

Acceptance: CI fails when an advertised feature lacks executable conformance
coverage or a required lane silently skips. Live external checks are visibly
separate from mocks and can gate an exact candidate qualification.
Verification: deliberate negative fixtures for each new guard and a complete
candidate CI run, with no secrets included in archived artifacts.

### B43 - Run the full initial compatibility matrix (G5)

Track: CORE. Priority: P1. Owner: Qualification lead + domain/harness owners.
Effort: 4-7 days. Confidence: Low.
Depends on: B42.
Basis: report acceptance matrix and initial delivery claims.
Areas: exact-commit qualification evidence; isolated Linux deployment.

Autonomy: Freeze the final candidate and execute the three harnesses by three domains
on both qualified backends: 18 lifecycle cells. Map the ten scenarios to applicable
cells before running; required live cells cannot be reclassified after failure.

- [ ] Run all nine built-in/Codex/Claude Code by real-prompt/code-test/latency combinations on SQLite and same-host Postgres workers (18 required lifecycle cells); record versions/configuration.
- [ ] Exercise attached API/CLI and custom-driver conformance, plus the ten cross-path scenarios listed below, across SQLite and same-host Postgres workers as applicable.
- [ ] Independently inspect artifact hashes, accepted results, usage, process cleanup, promotion/rollback fixture effects, and recovery state.

Acceptance: all nine combinations on both backends complete a verified
candidate/evaluation/winner lifecycle without core/UI changes for their identity;
failures or absent live credentials leave the gate incomplete. Passing
simulations or fixture-only adapters cannot replace a named live cell.
Verification: matrix record with pass/fail/unsupported, exact commit and artifact
digests, test commands, live versions, measured outcomes, and remaining limits.

### B44 - Complete documentation, packaging, and implementation handoff

Track: CORE. Priority: P1. Owner: Maintainer + docs/release engineering.
Effort: 2-3 days. Confidence: High.
Depends on: B43.
Basis: truthful claims, migration, and operator usability.
Areas: README, RUNBOOK, examples, OpenAPI, package/container inventories.

Autonomy: Audit all CORE records and installed artifacts, then write concise operator
docs and a concrete handoff. Distinguish local implementation, remote PR/CI delivery,
and publication; a release is not required for this card.

- [ ] Document qualified support, install/isolation requirements, credential roles, budget limits, recovery, backup, migration, and plugin trust modes.
- [ ] Replace stale scorer/sandbox/universal claims and internal implementation narration with current behavior; align shipped manifests/examples and package inventories.
- [ ] Record finding closure links, gate evidence, deferred capabilities, remaining risks, and manual release/deployment steps for the qualified commit.

Acceptance: a fresh operator can run the documented workflow from an installed
artifact. Public claims match B43 exactly, and every CORE card has completion
evidence. Handoff does not itself publish a release or deploy a service.
Verification: documentation link/example checks, installed-artifact smoke,
candidate metadata consistency, and closure audit for B01-B43.

## Gated Extensions

Each estimate assumes its reopening conditions and dependencies are satisfied.
These cards are excluded from CORE_44 and required for ALL_50. The agent evaluates
the reopening conditions automatically; an unmet condition remains visible and
cannot be checked off as implemented.

### B45 - Add an MCP facade for attached agents

Track: GATED. Priority: P2. Owner: Integration API.
Effort: 2-4 days. Confidence: Medium.
Depends on: B31, B32, B44.
Basis: optional attached-agent transport.
Areas: scoped API/auth, proposed MCP facade, client conformance fixtures.
Reopen when: at least one target client needs MCP and its API/CLI integration is
insufficient; identify client/version and required tools/resources.

Autonomy: Inspect already targeted clients for a demonstrated API/CLI limitation
requiring MCP; select a real client/version from that evidence. If none exists, keep
the reopening predicate unmet rather than inventing consumer demand.

- [ ] Map a narrow research tool/resource set onto existing scoped API operations.
- [ ] Reuse authorization, validation, rate limits, evidence rules, and idempotency without a second policy implementation.
- [ ] Publish/test the client capability and error mapping, including cancellation and revoked credentials.

Acceptance: MCP performs the same authorized workflow and cannot self-certify
metrics or bypass approval. Verification: one real client round trip plus the
shared attached-agent conformance suite and cross-run denial tests.

### B46 - Add remote executors and multi-host artifact storage

Track: GATED. Priority: P2. Owner: Distributed platform/security.
Effort: 8-15 days. Confidence: Low.
Depends on: B22, B26, B44.
Basis: shared artifacts and multi-host operation.
Areas: executor/artifact interfaces, leases/events, remote auth and deployment tests.
Reopen when: a concrete second-host/GPU workload exists with authorized host and
storage access; the agent has resolved network, credential, consistency, and cost
requirements within that authority and recorded itself as technical owner.

Autonomy: Use the existing capability inventory to select an authorized second host
and concrete workload, with the agent owning backend decisions. Without that
host/workload/authority, record the exact prerequisite; two local processes do not
qualify multi-host behavior.

- [ ] Implement shared content-addressed storage and remote executor identity with authenticated, attempt-bound result receipts.
- [ ] Extend leases/fencing, scoped credentials, cancellation, environment identity, transfer limits, retention, and effect reconciliation across host boundaries.
- [ ] Qualify loss/partition/retry behavior and publish a separate deployment support profile.

Acceptance: disconnected/stale remote workers cannot publish new authoritative
results or overwrite artifacts; resumable data is available after host loss.
Verification: two-host partition/crash/reattach tests, tampered receipts/artifacts,
credential rotation, and bounded remote cleanup/usage evidence.

### B47 - Qualify native execution on another operating system

Track: GATED. Priority: P2. Owner: Platform/runtime.
Effort: 8-15 days. Confidence: Low.
Depends on: B08, B44.
Basis: POSIX-only implementation assumptions.
Areas: process/filesystem backends, packaging/recovery, native CI runner profiles.
Reopen when: a named Windows or macOS deployment requires native execution and
has a dedicated runner plus an enforceable filesystem/network/process backend.

Autonomy: Select an already required Windows/macOS target with an authorized native
runner and enforceable isolation. If both qualify equally, start with Windows for
different path/process semantics; Linux containers cannot substitute for native proof.

- [ ] Replace platform-specific process, locking, path, and interpreter assumptions behind existing execution interfaces.
- [ ] Implement equivalent isolation/resource/cancellation guarantees or reject unsupported policies explicitly.
- [ ] Run platform-specific install, artifact, recovery, and harness compatibility gates.

Acceptance: support is claimed only for tested OS/backend combinations; container
success is not reported as native support. Verification: native G1/G3/G4 cases,
OS-specific symlink/path attacks, and process-tree teardown on a real runner.

### B48 - Add git-branch and artifact-store promotion targets

Track: GATED. Priority: P2. Owner: Promotion integrations.
Effort: 5-9 days. Confidence: Medium.
Depends on: B18, B44.
Basis: currently unsupported target kinds.
Areas: promotion target registry, approval/reconciliation, remote target fixtures.
Reopen when: a consumer names a concrete repository/store, approval policy,
target identity, reconciliation behavior, and rollback expectations.

Autonomy: Resolve repository/store identity and policy from an existing concrete
consumer requirement. Use disposable authorized remote fixtures for both target kinds;
choose reconciliation/rollback details autonomously without touching a production
target.

- [ ] Implement target adapters with scoped credentials, immutable candidate references, conditional updates, and stable idempotency keys.
- [ ] Define review-before-merge behavior for git and versioned rollback for object artifacts; never equate local intent with remote success.
- [ ] Add exact-target approval, audit, crash reconciliation, and stale baseline tests.

Acceptance: retries cannot duplicate or overwrite an unrelated promotion and
rollback restores the intended version. Verification: disposable remote-target
fixtures and fault injection before/after each external effect.

### B49 - Extend domain semantics beyond the initial contracts

Track: GATED. Priority: P2. Owner: Research/domain SDK.
Effort: 6-12 days. Confidence: Low.
Depends on: B17, B44.
Basis: deferred phase/resolver plugins, multiobjective and exploratory domains.
Areas: manifest schema, phase/objective handlers, plugin host, UI/conformance suites.
Reopen when: two concrete skills demonstrate a limitation of the current
declarative contract and define objective, evidence, termination, and UI needs.

Autonomy: Build two executable motivating skill cases from actual declarative
limitations, then implement the smallest shared extension. Agent-authored fixtures are
valid technical evidence; invented user demand or a scalar proxy for a multiobjective
requirement is not.

- [ ] Design the smallest extension that serves those skills, separating a plugin resolver need from a new research objective type.
- [ ] Execute supported plugins under the qualified isolation/receipt rules; version changes and preserve explicit rejection for unsupported modes.
- [ ] Add independent conformance examples and appropriate result/promotion semantics without forcing a scalar winner.

Acceptance: extensions add no domain-ID branch to the kernel and retain clear
evidence/termination semantics. Verification: both motivating skills, migration,
plugin adversarial tests, and objective-specific acceptance scenarios.

### B50 - Optimize capacity and operational cost from measured demand

Track: GATED. Priority: P2. Owner: Performance/platform.
Effort: 4-8 days. Confidence: Low.
Depends on: B44.
Basis: performance and larger deployment caveats.
Areas: measured bottleneck modules, load/profiling fixtures, operational usage metrics.
Reopen when: a reproducible representative load misses a named latency,
throughput, storage, or cost target after the core qualification is complete.

Autonomy: Derive the representative workload and named target from recorded
requirements/qualification evidence, freeze them, and measure first. Optimize the
observed limiting path; if no target is missed, leave this improvement card INACTIVE
rather than manufacture a bottleneck.

- [ ] Capture per-stage resource/cost baselines and identify the measured bottleneck with an owner and target improvement.
- [ ] Optimize only the limiting path, preserving admission, evidence, event ordering, budget, and isolation contracts.
- [ ] Add a bounded repeatable benchmark and regression threshold on the qualified deployment.

Acceptance: target improvement is measured without reduced correctness or
trust guarantees; gains are reported with workload/hardware assumptions.
Verification: before/after benchmark distributions, resource/usage traces, and
affected G1-G5 regressions; no speculative broad performance rewrite.

## Cross-Path Qualification Scenarios

B43 must predeclare which of the 18 lifecycle cells execute each scenario and
justify any inapplicable scenario/cell pairs. Cover each applicable adapter and
both stores; attached API/CLI and custom-driver paths additionally run their
shared contract suite on both stores. All 18 lifecycle cells remain required.
Universal compatibility does not mean identical native features; optional
capability absence must be visible and tested through explicit rejection.

1. Fresh start, meaningful candidate change, verified evaluation, correct winner.
2. Evaluation failure, missing/nonfinite metrics, changed data, forged receipt.
3. Minimize/maximize, constraints, ties, authorized replication, uncertainty.
4. Nondefault parameters preserved through interruption, restart, continuation.
5. Stop/pause semantics, descendant cleanup, unavailable harness, hard timeout.
6. Duplicate/out-of-order events, reconnect, stale owner, worker restart.
7. Same-subject concurrent runs with separate workspaces and budget reservations.
8. Candidate-bound approval, stale approval denial, rollback, ambiguous effect reconciliation.
9. Reported/estimated/unavailable usage and explicit money/time/resource limits.
10. New conforming skill/adapter registration without core/UI identity branches.

## Completion Record

Store one machine-readable record per card in `cards.json`; link any PR to that
record's sanitized summary. The following is a schema example, not a claim that
B01 has started. Expand checks and acceptance IDs when the card starts. Use the
states defined above; keep remote delivery status separate from card status.

```json
{
  "schema_version": 1,
  "card_id": "B01",
  "status": "PENDING",
  "owner_run_id": null,
  "depends_on": [],
  "dependency_evidence": [],
  "reopening_evidence": [],
  "decision_ids": [],
  "work_packets": [],
  "acceptance": [
    {"id": "B01.A1", "criterion": "All F01-F12 have a trigger or code-path hypothesis and closure test", "check_ids": [], "satisfied": false}
  ],
  "verification_recipe": [],
  "verification_results": [],
  "review": {"kind": "self-review", "findings": [], "complete": false},
  "source_commit": null,
  "source_tree_digest": null,
  "implementation_commits": [],
  "artifact_digests": {},
  "qualified_platforms_backends_versions": [],
  "external_prerequisite_ids": [],
  "remaining_limitations": [],
  "attempt_history": [],
  "remote_delivery": {"status": "NOT_REQUESTED", "pr_url": null, "ci_run_ids": []},
  "next_action": "Initialize B01 from the current checkout and requested target",
  "updated_at": null
}
```

Each verification recipe entry contains `check_id`, acceptance IDs, `command`,
`cwd`, nonsecret environment references, timeout/resource caps, required/optional
classification, matrix coordinates where applicable, and expected outcome. Each
result references its recipe and records timestamps, exit status, case counts,
PASS/FAIL/SKIP/INCONCLUSIVE, tested commit/inputs/versions, log path/hash, and
inspection notes. A recipe without an executed result is not evidence.

Before DONE, validate: all acceptance IDs have passing required checks; no
required check is missing/skipped/inconclusive; review findings are resolved;
dependencies and reopening evidence are current; artifacts can be read and their
hashes match; external prerequisites affecting acceptance are cleared; remaining
limitations contradict no acceptance claim. Each checked subtask links to its
work packets and acceptance evidence. The ledger is authoritative for execution
status; Markdown checkboxes mirror it only after evidence is recorded.

The dependency graph and finding coverage should be revalidated when cards are
split, reordered, or removed. B44 is the initial delivery closure gate; every
CORE card is a direct or transitive prerequisite. GATED work has its own closure
and cannot be silently treated as part of the qualified core. Preserve the 50
parent card IDs when splitting packets so original acceptance cannot disappear.

Backlog validation at creation: 50 unique cards; 3 subtasks per card; required
metadata present; 136 known dependency references; acyclic graph; valid numeric
serial order; all 43 preceding CORE cards are ancestors of B44; no CORE card
depends on GATED work; all 12 review findings mapped. This validates the plan's
structure, not the product or the effort estimates.

Autonomous revision validation (2026-10-03): 50 unique cards and `Autonomy` rules;
150 open subtasks; all 136 original dependencies preserved; acyclic numeric order;
all 43 preceding CORE cards remain ancestors of B44; all 12 findings mapped;
required metadata present; eight execution states; valid completion-record JSON;
no whitespace errors. Five scheduling simulations covered CORE completion,
ALL_50 completion, unavailable isolation, unavailable live-adapter authentication,
and an inactive extension. Independent work remained runnable while dependencies
and completion targets stayed enforced.

These checks validate the revised plan, not an implemented scheduler or the
product. No implementation checkbox was changed, and no application tests,
live qualification, release, or deployment were performed for this revision.
