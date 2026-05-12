"""Agent orchestrator — drives Claude via the Anthropic SDK with tool use."""

from __future__ import annotations

import asyncio
import glob as glob_mod
import json
import logging
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import anthropic
import httpx

from src.config import secret_value, settings
from src.core.command_runner import GovernedCommandRunner, redact_sensitive_text
from src.core.artifact_reference import normalize_artifact_references_in_mapping
from src.core.consistency_validator import (
    build_consistency_report,
    consistency_report_json,
)
from src.core.experiment_parser import (
    is_hpo_study_output,
    parse_hpo_study_output,
    parse_iteration_marker,
    parse_prepare_output,
)
from src.core.gate_status import (
    normalize_training_gate_aliases,
    training_gates_passed_from_iteration,
)
from src.core.iteration_snapshot import (
    build_iteration_attempt_snapshot,
    build_trial_identity,
    canonical_config_hash,
    trial_identity_hash,
    write_iteration_attempt_snapshot,
)
from src.core.iteration_context import (
    ITERATION_CONTEXT_DIGEST_MARKER,
    build_iteration_context_digest,
)
from src.core.log_writer import AgentLogWriter
from src.core.research_phase_plan import (
    build_phase_state,
    incomplete_phase_ids,
    phase_cap_exceeded,
    phase_state_json,
    phases_for_model,
)
from src.core.research_phase_plan import _PHASE_ADVANCEMENT_KEYS
from src.core.result_artifact import enrich_marker_from_result_artifact
from src.core.results_store import ResultsStore
from src.core.structured_hpo import materialize_planned_trials
from src.ws.events import broadcaster

logger = logging.getLogger(__name__)

# Phase 2.2: Claude pricing constants (Sonnet 3.5 baseline). These mirror
# the inline numbers used previously and are referenced both by the
# post-call cost accounting and the pre-spend budget gate.
_CLAUDE_INPUT_USD_PER_TOKEN = 3.0 / 1_000_000
_CLAUDE_OUTPUT_USD_PER_TOKEN = 15.0 / 1_000_000
_CLAUDE_MAX_OUTPUT_TOKENS = 8192

# Phase 5.4: number of consecutive command-policy rejections after which
# the agent loop aborts as ``failed`` and waits for operator review.
_MAX_CONSECUTIVE_POLICY_REJECTIONS = 5

# AR-3: Phases that legitimately emit no config_snapshot because they do NOT
# run a fresh training command — they validate, replay, or promote an already-
# trained artefact.  _record_iteration inherits the most recent non-null
# config_snapshot from the DB for these phases so that consistency reports
# don't flag ``missing_config_snapshot`` as a blocker.
_PROMOTION_FAMILY: frozenset[str] = frozenset({
    "multi_seed_robustness",
    "inference_parity_replay",
    "calibration_replay_gates",
    "promotion_proposal",
})

# ---------------------------------------------------------------------------
# Research config dataclass
# ---------------------------------------------------------------------------


@dataclass
class ResearchConfig:
    id: str
    instrument: str
    timeframe: str
    model_type: str
    tag: str = ""
    quick_mode: bool = False
    max_iterations: int = 30
    max_budget_usd: float = 10.0
    timeout_s: int = 0  # 0 = use server default
    focus_hint: Optional[str] = None
    workspace_path: str = ""
    # RL-specific fixed settings (not in tuning space)
    trading_mode: Optional[str] = None   # stock | margin
    agent_strategy: Optional[str] = None  # AGGR | CONS | BALA | SCAL
    initial_balance: Optional[float] = None
    # ML-59: HPO configuration
    enable_hpo: bool = False
    hpo_trials: int = 20
    hpo_timesteps: int = 50000
    # ML-62: Session resume on timeout
    resumed_from: Optional[str] = None  # parent session ID when continuing
    # ML-63: Parent pipeline ID for phase sessions
    pipeline_id: Optional[str] = None


@dataclass(frozen=True)
class ToolExecutionResult:
    content: str
    meta: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tool definitions for the Claude agent
# ---------------------------------------------------------------------------

AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "bash",
        "description": (
            "Execute one governed command in the workspace. "
            "The working directory is the workspace root and shell syntax "
            "such as pipes, redirection, command substitution, and command "
            "chaining is rejected. Use .venv/bin/python for approved "
            "autotuner Python scripts. "
            "Default timeout is 7200s (2 hours). Set timeout_s for "
            "shorter commands. Minimum enforced: 900s."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "timeout_s": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 7200). Minimum 900.",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative or absolute path within the workspace.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file in the workspace. "
            "Creates parent directories if needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative or absolute path within the workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "File content to write.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "glob",
        "description": "List files matching a glob pattern within the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. 'configs/**/*.yaml').",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep",
        "description": "Search for a regex pattern in files within the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in (default: workspace root).",
                },
                "include": {
                    "type": "string",
                    "description": "Glob to filter files (e.g. '*.py').",
                },
            },
            "required": ["pattern"],
        },
    },
]

SERVER_OWNED_SETUP_INSTRUCTION = (
    "Run the setup command exactly as shown. The server has already prepared "
    "fresh-session cleanup or continuation behavior, so do not add reset flags."
)

PROMOTION_HANDOFF_INSTRUCTION = (
    "Promotion handoff: Do not promote directly. Finish with a best validated "
    "config and let the server preview/confirm."
)

# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def _safe_path(raw: str, workspace: str) -> str:
    """Resolve a path and ensure it stays within the workspace."""
    if os.path.isabs(raw):
        resolved = Path(raw).resolve(strict=False)
    else:
        resolved = Path(workspace, raw).resolve(strict=False)
    ws_real = Path(workspace).resolve(strict=False)
    try:
        resolved.relative_to(ws_real)
    except ValueError as exc:
        raise ValueError(f"Path {raw!r} resolves outside workspace") from exc
    return str(resolved)


def _safe_write_path(raw: str, workspace: str) -> str:
    """Resolve a writable path and ensure existing parents stay in workspace."""

    path = Path(raw) if os.path.isabs(raw) else Path(workspace, raw)
    resolved_parent = path.parent.resolve(strict=False)
    workspace_root = Path(workspace).resolve(strict=False)
    try:
        resolved_parent.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"Path {raw!r} parent resolves outside workspace") from exc
    if path.exists() and path.is_symlink():
        raise ValueError(f"Path {raw!r} is a symlink and cannot be overwritten")
    return str(resolved_parent / path.name)


def _normalize_command_for_plan(command: str) -> str:
    try:
        return " ".join(shlex.split(command))
    except ValueError:
        return command.strip()


def _is_setup_command(command: str) -> bool:
    return "scripts/autotuner/setup.py" in command


def _config_snapshot_path_from_command(
    command: str,
    workspace_root: str,
    session_workspace: str,
) -> Optional[str]:
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if "--config" not in argv:
        return None
    index = argv.index("--config") + 1
    if index >= len(argv):
        return None
    raw_path = argv[index]
    if os.path.isabs(raw_path):
        resolved = os.path.realpath(raw_path)
    elif raw_path.startswith("runs/") or raw_path.startswith("./runs/"):
        resolved = os.path.realpath(os.path.join(workspace_root, raw_path))
    else:
        resolved = os.path.realpath(os.path.join(session_workspace, raw_path))
    session_real = os.path.realpath(session_workspace)
    if not resolved.startswith(session_real + os.sep) and resolved != session_real:
        return None
    return resolved


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _execute_tool(
    name: str,
    input_data: Dict[str, Any],
    workspace: str,
    session_workspace: str | None = None,
) -> ToolExecutionResult:
    """Execute a tool call and return the text result."""
    try:
        if name == "bash":
            return _tool_bash(input_data, workspace, session_workspace)
        elif name == "read_file":
            return ToolExecutionResult(_tool_read_file(input_data, workspace))
        elif name == "write_file":
            return ToolExecutionResult(_tool_write_file(input_data, workspace))
        elif name == "glob":
            return ToolExecutionResult(_tool_glob(input_data, workspace))
        elif name == "grep":
            return ToolExecutionResult(_tool_grep(input_data, workspace))
        else:
            return ToolExecutionResult(f"Unknown tool: {name}")
    except Exception as exc:
        return ToolExecutionResult(f"Tool error ({name}): {exc}")


def _tool_bash(
    input_data: Dict[str, Any],
    workspace: str,
    session_workspace: str | None = None,
) -> ToolExecutionResult:
    command = input_data["command"]
    timeout = input_data.get("timeout_s", 7200)
    # Enforce minimum timeout — agents routinely ignore tool-description hints
    if timeout < 900:
        timeout = 900
    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session_workspace,
    )
    result = runner.run(command, timeout_s=timeout)
    decision = result.decision
    return ToolExecutionResult(
        result.output,
        meta={
            "policy_allowed": decision.allowed,
            "policy_reason": decision.reason,
            "policy_operation": decision.operation,
            "normalized_command": decision.normalized_command,
            "returncode": result.returncode,
            "timed_out": result.timed_out,
        },
    )


def _tool_read_file(input_data: Dict[str, Any], workspace: str) -> str:
    path = _safe_path(input_data["path"], workspace)
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        if len(content) > 100_000:
            content = content[:50_000] + "\n...(truncated)...\n" + content[-50_000:]
        return content
    except FileNotFoundError:
        return f"File not found: {input_data['path']}"


def _tool_write_file(input_data: Dict[str, Any], workspace: str) -> str:
    path = _safe_write_path(input_data["path"], workspace)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Path(path).write_text(input_data["content"], encoding="utf-8")
    return f"Wrote {len(input_data['content'])} bytes to {input_data['path']}"


def _tool_glob(input_data: Dict[str, Any], workspace: str) -> str:
    pattern = input_data["pattern"]
    full_pattern = os.path.join(workspace, pattern)
    matches = sorted(glob_mod.glob(full_pattern, recursive=True))
    # Return paths relative to workspace
    ws = str(Path(workspace).resolve(strict=False))
    relative = []
    for match in matches:
        try:
            safe_match = _safe_path(match, workspace)
            relative.append(str(Path(safe_match).relative_to(ws)))
        except ValueError:
            logger.debug("Filtered glob match outside workspace: %s", match)
    if not relative:
        return "(no matches)"
    return "\n".join(relative[:500])


def _tool_grep(input_data: Dict[str, Any], workspace: str) -> str:
    pattern = input_data["pattern"]
    search_path = input_data.get("path", ".")
    include = input_data.get("include", "")
    safe_dir = _safe_path(search_path, workspace)

    cmd = ["grep", "-rn", "--color=never"]
    if include:
        cmd += [f"--include={include}"]
    cmd += [pattern, safe_dir]

    # Phase 4.3: this synchronous subprocess.run call is intentional —
    # _execute_tool is already invoked via ``asyncio.to_thread`` from the
    # main agent loop, so blocking work here runs on a worker thread and
    # cannot stall the event loop. Switching to asyncio.create_subprocess_*
    # would force every tool call site to await individually.
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout
        if len(output) > 60_000:
            output = output[:30_000] + "\n...(truncated)...\n" + output[-30_000:]
        return output or "(no matches)"
    except subprocess.TimeoutExpired:
        return "Grep timed out after 30s"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AgentOrchestrator:
    """Runs a Claude agent session for autonomous ML experiment tuning."""

    def __init__(self, store: ResultsStore) -> None:
        self._store = store
        self._client = anthropic.AsyncAnthropic(
            base_url=settings.anthropic_base_url,
            api_key=secret_value(settings.anthropic_auth_token),
            timeout=httpx.Timeout(settings.anthropic_api_timeout_s, connect=30.0),
        )
        self._stop_flags: Dict[str, bool] = {}
        self._pause_flags: Dict[str, bool] = {}
        # AR-4: per-session counter tracking how many consecutive kick attempts
        # have been made for each distinct block_reason.  When the counter
        # reaches 3, the kick escalates to a forced TERMINATE_REQUEST instead
        # of re-injecting the same remediation nudge, preventing infinite
        # re-asking on an unresolvable blocker.
        self._blocker_attempt_counters: Dict[str, Dict[str, int]] = {}

    def request_stop(self, research_id: str) -> None:
        self._stop_flags[research_id] = True

    def request_pause(self, research_id: str) -> None:
        self._pause_flags[research_id] = True

    def request_resume(self, research_id: str) -> None:
        self._pause_flags.pop(research_id, None)

    # ── ML-68: Transient-error retry ─────────────────────────────────────
    _TRANSIENT_EXCEPTIONS = (
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        anthropic.InternalServerError,
    )

    async def _call_claude_with_retry(
        self,
        *,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        research_id: str,
        agent_log: AgentLogWriter,
        turn: int,
        remaining_budget_s: Optional[float] = None,
    ) -> anthropic.types.Message:
        """Call messages.create() with retry + backoff on transient errors.

        Retries on APITimeoutError, APIConnectionError, InternalServerError,
        and RateLimitError (429) / 502 / 503 / 529 status codes.

        Phase 2.3: when ``remaining_budget_s`` is provided, the loop refuses
        to start a backoff sleep that would push the next attempt past the
        session's wall-clock budget; in that case the last exception is
        re-raised immediately so the outer turn loop can fail cleanly
        instead of cancelling mid-sleep.
        """
        max_retries = settings.max_api_retries
        backoff_base = 30  # seconds
        last_exc: Optional[BaseException] = None

        for attempt in range(max_retries + 1):
            try:
                return await self._client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=_CLAUDE_MAX_OUTPUT_TOKENS,
                    system=system_prompt,
                    tools=AGENT_TOOLS,
                    messages=messages,
                )
            except self._TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                if attempt >= max_retries:
                    raise
                wait = backoff_base * (2 ** attempt)
                if (
                    remaining_budget_s is not None
                    and wait >= remaining_budget_s
                ):
                    logger.warning(
                        "Research %s turn %d: skipping retry — backoff %ds "
                        "exceeds remaining budget %.0fs",
                        research_id, turn, wait, remaining_budget_s,
                    )
                    raise
                logger.warning(
                    "Research %s turn %d: transient API error (%s), "
                    "retry %d/%d in %ds",
                    research_id, turn, type(exc).__name__,
                    attempt + 1, max_retries, wait,
                )
                await agent_log.append(
                    "warning",
                    f"API {type(exc).__name__}: retry {attempt + 1}/{max_retries} "
                    f"in {wait}s — {str(exc)[:200]}",
                    turn=turn,
                )
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as exc:
                last_exc = exc
                # Retry on 429 (rate-limit), 502, 503, 529 (overloaded)
                if exc.status_code in (429, 502, 503, 529) and attempt < max_retries:
                    wait = backoff_base * (2 ** attempt)
                    if (
                        remaining_budget_s is not None
                        and wait >= remaining_budget_s
                    ):
                        logger.warning(
                            "Research %s turn %d: skipping retry on HTTP %d "
                            "— backoff %ds exceeds remaining budget %.0fs",
                            research_id, turn, exc.status_code, wait,
                            remaining_budget_s,
                        )
                        raise
                    logger.warning(
                        "Research %s turn %d: API %d, retry %d/%d in %ds",
                        research_id, turn, exc.status_code,
                        attempt + 1, max_retries, wait,
                    )
                    await agent_log.append(
                        "warning",
                        f"API HTTP {exc.status_code}: retry {attempt + 1}/{max_retries} "
                        f"in {wait}s — {str(exc)[:200]}",
                        turn=turn,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

        # Unreachable but satisfies type-checkers
        raise RuntimeError("Retry loop exited without return or raise")  # pragma: no cover

    # ── ML-68: Context compaction ────────────────────────────────────────
    @staticmethod
    def _compact_messages(
        messages: List[Dict[str, Any]],
        keep_recent: int = 40,
    ) -> List[Dict[str, Any]]:
        """Bound retained conversation history to avoid unbounded memory growth.

        Keeps the first message (initial prompt) and the last *keep_recent*
        messages intact. Older messages are represented by one deterministic
        summary marker; detailed history remains in agent_log.jsonl and SQLite.
        """
        if len(messages) <= keep_recent + 1:
            return messages

        compacted = [messages[0]]  # preserve initial user prompt

        old_section = messages[1:-keep_recent]
        if old_section:
            assistant_count = sum(1 for msg in old_section if msg.get("role") == "assistant")
            user_count = sum(1 for msg in old_section if msg.get("role") == "user")
            tool_result_count = 0
            for msg in old_section:
                content = msg.get("content")
                if isinstance(content, list):
                    tool_result_count += sum(
                        1
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "tool_result"
                    )
            content = (
                "[system] Earlier conversation compacted: "
                f"{len(old_section)} messages "
                f"({assistant_count} assistant, {user_count} user, "
                f"{tool_result_count} tool results). "
                "Use the persisted iteration records and agent log for details."
            )
            latest_digest = AgentOrchestrator._latest_iteration_context_digest(
                old_section
            )
            if latest_digest:
                content = f"{content}\n\n{latest_digest}"
            compacted.append({"role": "user", "content": content})

        compacted.extend(messages[-keep_recent:])
        return compacted

    @staticmethod
    def _latest_iteration_context_digest(
        messages: List[Dict[str, Any]],
    ) -> Optional[str]:
        for message in reversed(messages):
            content = message.get("content")
            if isinstance(content, str) and ITERATION_CONTEXT_DIGEST_MARKER in content:
                return content
            if not isinstance(content, list):
                continue
            for block in reversed(content):
                if (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                    and ITERATION_CONTEXT_DIGEST_MARKER in block["text"]
                ):
                    return block["text"]
        return None

    def _should_stop(self, research_id: str) -> bool:
        return self._stop_flags.get(research_id, False)

    async def _wait_while_paused(self, research_id: str) -> None:
        while self._pause_flags.get(research_id, False):
            if self._should_stop(research_id):
                return
            await asyncio.sleep(2)

    async def _load_skill_async(self, model_type: str) -> str:
        return await asyncio.to_thread(self._load_skill, model_type)

    async def _load_claude_md_async(self) -> str:
        return await asyncio.to_thread(self._load_claude_md)

    async def _read_marker_file_async(self, config: ResearchConfig) -> Optional[str]:
        return await asyncio.to_thread(self._read_marker_file, config)

    def _load_skill(self, model_type: str) -> str:
        skill_map = {
            "direction": "direction-autotuner",
            "volatility": "volatility-autotuner",
            "rl": "rl-autotuner",
        }
        skill_name = skill_map[model_type]
        skill_path = os.path.join(
            settings.skills_dir, skill_name, "SKILL.md",
        )
        return Path(skill_path).read_text(encoding="utf-8")

    def _load_claude_md(self) -> str:
        claude_md_path = os.path.join(settings.workspace_root, "CLAUDE.md")
        if os.path.exists(claude_md_path):
            return Path(claude_md_path).read_text(encoding="utf-8")
        return ""

    def _read_marker_file(self, config: ResearchConfig) -> Optional[str]:
        """Read and consume last_metrics.txt marker file if it exists.

        prepare.py writes this file on completion so the orchestrator
        can detect iterations even when the bash tool times out.
        Falls back to parsing results.json directly if the marker file
        is missing (e.g. agent bypassed prepare.py).
        """
        instrument_underscore = config.instrument.replace("-", "_")
        base_dir = os.path.join(
            settings.workspace_root,
            "runs", "autotuner",
            f"{instrument_underscore}_{config.timeframe}",
            config.model_type,
        )
        marker_path = os.path.join(base_dir, "last_metrics.txt")
        if os.path.exists(marker_path):
            # Phase 3.3: rename-then-read so a concurrent prepare.py write
            # cannot have its fresh marker silently deleted by our cleanup.
            # The rename is atomic on POSIX; if it fails because the file
            # vanished underneath us we simply return None.
            claim_path = (
                f"{marker_path}.consumed.{os.getpid()}.{int(time.time() * 1000)}"
            )
            try:
                os.replace(marker_path, claim_path)
            except FileNotFoundError:
                return None
            try:
                content = Path(claim_path).read_text(encoding="utf-8")
            except OSError as exc:
                logger.debug("Failed to read marker file %s: %s", claim_path, exc)
                content = None
            try:
                os.remove(claim_path)
            except OSError:
                logger.debug(
                    "Failed to unlink consumed marker %s", claim_path,
                    exc_info=True,
                )
            return content

        # Fallback: synthesize a marker from results.json when the agent
        # ran the training script directly (bypassing prepare.py).
        results_path = os.path.join(base_dir, "results.json")
        if os.path.exists(results_path):
            claim_path = (
                f"{results_path}.consumed.{os.getpid()}.{int(time.time() * 1000)}"
            )
            try:
                os.replace(results_path, claim_path)
                results_data = json.loads(
                    Path(claim_path).read_text(encoding="utf-8")
                )

                if config.model_type == "rl":
                    # RL results use aggregate metrics. Compute composite_rl_score
                    # ML-61: matching prepare.py: 1.0×sharpe + 0.5×return - 2.0×drawdown - 0.1×cv
                    agg = results_data.get("aggregate", {})
                    mean_sharpe = agg.get("mean_oos_sharpe") or 0.0
                    mean_return = agg.get("mean_oos_return") or 0.0
                    mean_dd = agg.get("mean_oos_drawdown") or 0.0
                    sharpe_cv = agg.get("sharpe_cv") or 0.0
                    primary = (
                        1.0 * mean_sharpe + 0.5 * mean_return
                        - 2.0 * mean_dd - 0.1 * sharpe_cv
                    )
                    n_folds = agg.get("n_folds", 1)
                    folds_passed = agg.get("folds_passed", 0)
                    passed = (
                        agg.get("all_folds_passed", False)
                        and folds_passed / max(n_folds, 1) >= 0.5
                    )
                    metric_name = "composite_rl_score"
                else:
                    # Direction / volatility results
                    wf = results_data.get("walkforward", {})
                    metrics_d = results_data.get("metrics", {})
                    gates = results_data.get("gate_results", {})
                    primary = (
                        wf.get("walkforward_mean_auc")
                        or metrics_d.get("auc")
                        or 0.0
                    )
                    passed = gates.get("all_supported_gates_passed", False)
                    metric_name = "walkforward_mean_auc"

                # Build a synthetic --- block that parse_prepare_output
                # can parse.
                lines = [
                    "---",
                    f"status:             completed",
                    f"primary_metric:     {primary:.6f}",
                    f"metric_name:        {metric_name}",
                    f"direction:          higher_is_better",
                    f"training_gates_passed: {str(passed).lower()}",
                    f"all_gates_passed:   {str(passed).lower()}",
                    f"results_json_path:  {claim_path}",
                    f"result_artifact_consume_source: true",
                    "---",
                ]
                return "\n".join(lines)
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.debug("Failed to synthesize metrics from results.json: %s", exc)
                try:
                    if os.path.exists(claim_path) and not os.path.exists(results_path):
                        os.replace(claim_path, results_path)
                except OSError:
                    logger.debug(
                        "Failed to restore claimed results artifact %s",
                        claim_path,
                        exc_info=True,
                    )
                return None

        return None

    def _load_research_resume(self, config: ResearchConfig) -> str:
        """Load the research resume for this instrument if it exists."""
        instrument_underscore = config.instrument.replace("-", "_")
        resume_path = os.path.join(
            settings.runs_dir,
            f"{instrument_underscore}_{config.timeframe}",
            "research_resume.md",
        )
        content = self._read_research_resume_file(resume_path)
        if not content:
            try:
                self._generate_research_resume_file(
                    config=config,
                    resume_path=resume_path,
                )
            except Exception as exc:
                logger.warning("Research resume fallback raised: %s", exc)
            content = self._read_research_resume_file(resume_path)
        if not content:
            return ""
        return (
            "\n\n## Research Resume (prior experiments on this instrument)\n\n"
            "Use this context to avoid repeating failed experiments and "
            "build on what worked.\n\n"
            f"{content}"
        )

    @staticmethod
    def _read_research_resume_file(resume_path: str) -> str:
        try:
            if not os.path.exists(resume_path):
                return ""
            with open(resume_path, encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return ""
            # Truncate to avoid context window bloat
            if len(content) > 12_000:
                content = content[:6000] + "\n\n*[truncated]*\n\n" + content[-6000:]
            return content
        except Exception as exc:
            logger.warning("Failed to load research resume: %s", exc)
            return ""

    @staticmethod
    def _generate_research_resume_file(
        *,
        config: ResearchConfig,
        resume_path: str,
    ) -> None:
        try:
            resume_script = os.path.join(
                settings.workspace_root,
                "scripts",
                "autotuner",
                "resume.py",
            )
            if not os.path.exists(resume_script):
                logger.warning("Resume script not found: %s", resume_script)
                return
            instrument_underscore = config.instrument.replace("-", "_")
            cmd = [
                settings.venv_python,
                resume_script,
                "--instrument",
                instrument_underscore,
                "--timeframe",
                config.timeframe,
                "--db",
                settings.db_path,
                "--runs-dir",
                settings.runs_dir,
                "--output",
                resume_path,
            ]
            result = subprocess.run(
                cmd,
                cwd=settings.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    "Resume fallback generation failed (rc=%d): %s",
                    result.returncode,
                    result.stderr[:500],
                )
        except Exception as exc:
            logger.warning("Failed to generate research resume fallback: %s", exc)

    def _build_prompt(self, config: ResearchConfig) -> str:
        quick_flag = " --quick" if config.quick_mode else ""
        focus = f"\nFocus hint: {config.focus_hint}" if config.focus_hint else ""
        instrument_underscore = config.instrument.replace("-", "_")
        workspace = (
            f"runs/autotuner/{instrument_underscore}_{config.timeframe}"
            f"/{config.model_type}"
        )

        # Load research resume for cross-session context
        resume_block = self._load_research_resume(config)

        # RL fixed settings — build setup.py args + constraint notice for Claude
        setup_extra_args = ""
        fixed_settings_notice = ""
        if config.model_type == "rl":
            rl_args = []
            fixed_fields = []
            if config.trading_mode:
                rl_args.append(f"--trading-mode {config.trading_mode}")
                fixed_fields.append(f"trading_mode: {config.trading_mode}")
            if config.agent_strategy:
                rl_args.append(f"--agent-strategy {config.agent_strategy}")
                fixed_fields.append(f"agent_strategy: {config.agent_strategy}")
            if config.initial_balance is not None:
                rl_args.append(f"--initial-balance {config.initial_balance}")
                fixed_fields.append(f"initial_balance: {config.initial_balance}")
            if rl_args:
                setup_extra_args = " " + " ".join(rl_args)
            if fixed_fields:
                fields_str = ", ".join(fixed_fields)
                fixed_settings_notice = (
                    f"\n\n**FIXED SETTINGS (do NOT modify in train.yaml):** "
                    f"{fields_str}. These are user-configured and must remain "
                    f"unchanged throughout the research session."
                )

        # ML-59: 3-phase HPO workflow for RL when enable_hpo is set
        if config.model_type == "rl" and config.enable_hpo:
            return self._build_prompt_rl_hpo(
                config, workspace, setup_extra_args, fixed_settings_notice,
                quick_flag, focus, instrument_underscore,
            )

        hpo_block = ""
        if config.enable_hpo and config.model_type in ("direction", "volatility"):
            hpo_block = (
                "\n\nStructured HPO is enabled for this session. The server owns "
                f"the trial list and has bounded it to at most "
                f"{min(config.hpo_trials, config.max_iterations)} training "
                "attempts. After setup, use `server_hpo_plan.json` and run only "
                "the listed expected commands exactly. Do not edit `train.yaml` "
                "or planned trial YAML files for HPO. If you want a follow-up "
                "trial outside the plan, describe it as MANUAL_REVIEW_REQUEST "
                "in text and do not run it. Mark HPO-screening attempts with "
                "search_phase=hpo_screening in any explicit ITERATION_RESULT "
                "payload."
            )

        # RL needs an enrichment step before the first training run
        if config.model_type == "rl":
            enrich_step = (
                f"2. Enrich RL dataset (REQUIRED before any training):\n"
                f"```bash\n"
                f".venv/bin/python "
                f"scripts/autotuner/enrich_rl_dataset.py "
                f"--instrument {instrument_underscore} "
                f"--timeframe {config.timeframe}\n"
                f"```\n"
                f"Verify direction_proba mean is NOT ~0.5 (should show real signal).\n\n"
                f"3. Read guidance (use read_file tool):\n"
                f"   - `scripts/autotuner/{config.model_type}/README.md`\n"
                f"   - `{workspace}/train.yaml`\n\n"
                f"4. Baseline run:\n"
                f"```bash\n"
                f".venv/bin/python "
                f"scripts/autotuner/{config.model_type}/prepare.py "
                f"--config {workspace}/train.yaml{quick_flag}\n"
                f"```\n\n"
                f"5. After baseline, iterate: edit train.yaml → run prepare.py → "
                f"check metrics → keep or revert."
            )
        elif config.enable_hpo and config.model_type in ("direction", "volatility"):
            enrich_step = (
                f"2. Read guidance (use read_file tool):\n"
                f"   - `scripts/autotuner/{config.model_type}/README.md`\n"
                f"   - `{workspace}/server_hpo_plan.json` after setup completes\n\n"
                f"3. Run the server-owned structured trials:\n"
                f"   - The server materializes "
                f"`{workspace}/planned_trials/<trial_id>/train.yaml` files "
                f"from the approved plan immediately after setup.\n"
                f"   - Execute expected commands from "
                f"`{workspace}/server_hpo_plan.json` exactly.\n\n"
                f"4. After planned trials finish, interpret results and propose "
                f"follow-up plans in text only. Off-plan commands require "
                f"manual review."
            )
        else:
            enrich_step = (
                f"2. Read guidance (use read_file tool):\n"
                f"   - `scripts/autotuner/{config.model_type}/README.md`\n"
                f"   - `{workspace}/train.yaml`\n\n"
                f"3. Baseline run:\n"
                f"```bash\n"
                f".venv/bin/python "
                f"scripts/autotuner/{config.model_type}/prepare.py "
                f"--config {workspace}/train.yaml{quick_flag}\n"
                f"```\n\n"
                f"4. After baseline, iterate: edit train.yaml → run prepare.py → "
                f"check metrics → keep or revert."
            )

        # F5: phase contract — the agent previously had no awareness of the
        # 9-phase plan and self-terminated mid-phase. We now describe the
        # active phase list and the evidence keys it must emit on
        # ITERATION_RESULT markers to advance.
        phase_contract_block = self._build_phase_contract_block(config)

        return (
            f"Tune {config.model_type} model for {config.instrument} "
            f"{config.timeframe} (tag: {config.tag}). "
            f"Max {config.max_iterations} iterations.\n\n"
            f"Execute these commands IN ORDER — do not explore first:\n\n"
            f"1. Setup: {SERVER_OWNED_SETUP_INSTRUCTION}\n"
            f"```bash\n"
            f".venv/bin/python scripts/autotuner/setup.py "
            f"--instrument {instrument_underscore} "
            f"--timeframe {config.timeframe} "
            f"--models {config.model_type}{setup_extra_args}\n"
            f"```\n\n"
            f"{enrich_step}\n\n"
            f"{PROMOTION_HANDOFF_INSTRUCTION}\n\n"
            f"Run autonomously. Start with the setup and training steps above "
            f"without exploring the filesystem first."
            f"{fixed_settings_notice}"
            f"{focus}"
            f"{resume_block}"
            f"{hpo_block}"
            f"{phase_contract_block}"
        )

    def _build_phase_contract_block(self, config: ResearchConfig) -> str:
        """F5: render the canonical phase plan for the active model_type as a
        prompt section. The block tells the LLM:

        * which phase ids exist in order
        * the metrics-evidence key(s) each phase requires for advancement
        * the min/max iteration envelope per phase
        * how to flag a phase on an ITERATION_RESULT marker (search_phase)

        Without this, the agent was blind to the phase plan and would
        terminate after a few thousand `tabular_sweeps` iterations declaring
        the task done.
        """
        phases = phases_for_model(config.model_type)
        if not phases:
            return ""
        lines = [
            "",
            "",
            "## Phase Contract (server-tracked)",
            "",
            "Your research session is tracked against a phase plan. The "
            "orchestrator will refuse to let you terminate while phases "
            "remain incomplete and budget is available. Advance through "
            "phases by emitting the listed evidence key(s) in the "
            "`metrics_json` (or `config`) of an ITERATION_RESULT marker. "
            "Tag every ITERATION_RESULT with `search_phase: <phase_id>` "
            "so the server can attribute work correctly.",
            "",
            "| Order | Phase ID | Min iters | Max iters | Evidence key(s) | Next action |",
            "|---|---|---|---|---|---|",
        ]
        for idx, phase in enumerate(phases, start=1):
            pid = phase.get("id", "")
            keys = _PHASE_ADVANCEMENT_KEYS.get(pid, ()) or ()
            keys_str = ", ".join(keys) if keys else "—"
            lines.append(
                f"| {idx} | `{pid}` | "
                f"{phase.get('min_iterations', 0)} | "
                f"{phase.get('max_iterations', '—')} | "
                f"{keys_str} | "
                f"{phase.get('next_action', '')} |"
            )
        lines.extend([
            "",
            "**Termination rules:**",
            "* Do not emit `end_turn` while any phase is `pending` or "
            "`in_progress` and budget remains. The loop guard will reject "
            "it and inject a continuation message.",
            "* If you believe the entire plan should terminate early, "
            "reply with a single line starting `TERMINATE_REQUEST:` and a "
            "structured justification per incomplete phase.",
            "* Reaching a phase's `max_iters` ceiling triggers a system "
            "nudge to advance. Treat it as a hard signal to either emit "
            "the evidence key or move on.",
        ])
        return "\n".join(lines)

    async def _build_resume_prompt(self, config: ResearchConfig) -> str:
        """ML-62: Build a prompt for resuming a timed-out session.

        Instead of setup → enrich → baseline, this tells Claude to continue
        from where the parent session left off, using the preserved workspace
        (train.yaml, best_train.yaml, results).
        """
        parent_id = config.resumed_from
        quick_flag = " --quick" if config.quick_mode else ""
        focus = f"\nFocus hint: {config.focus_hint}" if config.focus_hint else ""
        instrument_underscore = config.instrument.replace("-", "_")
        workspace = (
            f"runs/autotuner/{instrument_underscore}_{config.timeframe}"
            f"/{config.model_type}"
        )

        # Load iteration history from parent session
        parent_session = await self._store.get_session(parent_id) if parent_id else None
        parent_iterations = await self._store.get_iterations(parent_id) if parent_id else []
        parent_insights = (parent_session or {}).get("insights", "") or ""
        parent_best_iter = (parent_session or {}).get("best_iteration")
        parent_best_metric = (parent_session or {}).get("best_metric")
        parent_iter_count = len(parent_iterations)

        # Build compact iteration history
        iter_summary_lines = []
        for it in parent_iterations:
            num = it.get("iteration", "?")
            pm = it.get("primary_metric")
            metric_s = f"{pm:.4f}" if pm is not None else "—"
            gates = "✅" if training_gates_passed_from_iteration(it) else "❌"
            decision = it.get("decision", "?")
            desc = (it.get("description") or "")[:150]
            iter_summary_lines.append(
                f"  {num}. metric={metric_s} training_gates={gates} "
                f"decision={decision} — {desc}"
            )
        iter_summary = (
            "\n".join(iter_summary_lines)
            if iter_summary_lines
            else "  (no iterations recorded)"
        )

        # RL fixed settings notice
        fixed_settings_notice = ""
        if config.model_type == "rl":
            fixed_fields = []
            if config.trading_mode:
                fixed_fields.append(f"trading_mode: {config.trading_mode}")
            if config.agent_strategy:
                fixed_fields.append(f"agent_strategy: {config.agent_strategy}")
            if config.initial_balance is not None:
                fixed_fields.append(f"initial_balance: {config.initial_balance}")
            if fixed_fields:
                fields_str = ", ".join(fixed_fields)
                fixed_settings_notice = (
                    f"\n\n**FIXED SETTINGS (do NOT modify in train.yaml):** "
                    f"{fields_str}. These are user-configured and must remain "
                    f"unchanged throughout the research session."
                )

        # Load research resume for broader cross-session context
        resume_block = self._load_research_resume(config)

        best_info = ""
        if parent_best_metric is not None:
            best_info = (
                f"Best result so far: iteration {parent_best_iter}, "
                f"metric={parent_best_metric:.4f}\n"
            )

        insights_block = ""
        if parent_insights.strip():
            insights_block = (
                f"\n**Insights from parent session:**\n{parent_insights.strip()}\n"
            )

        return (
            f"**CONTINUATION SESSION** — Resuming timed-out research for "
            f"{config.model_type} model on {config.instrument} "
            f"{config.timeframe} (tag: {config.tag}).\n\n"
            f"The previous session (id: {parent_id[:12] if parent_id else '?'}) "
            f"completed {parent_iter_count} iterations before timing out.\n"
            f"{best_info}"
            f"You have {config.max_iterations} iterations remaining.\n\n"
            f"## Parent session iteration history\n"
            f"{iter_summary}\n"
            f"{insights_block}\n"
            f"## Instructions\n\n"
            f"The workspace is ALREADY SET UP from the previous session. "
            f"Do NOT run setup.py, enrich, or baseline again.\n\n"
            f"1. Read the current state:\n"
            f"   - `{workspace}/train.yaml` (current config)\n"
            f"   - `{workspace}/best_train.yaml` (best validated config, if exists)\n"
            f"   - `{workspace}/results.json` (last run results, if exists)\n\n"
            f"2. Continue iterating from where the parent left off:\n"
            f"```bash\n"
            f".venv/bin/python "
            f"scripts/autotuner/{config.model_type}/prepare.py "
            f"--config {workspace}/train.yaml{quick_flag}\n"
            f"```\n\n"
            f"3. After each run, analyze results and iterate: "
            f"edit train.yaml → run prepare.py → check metrics → keep or revert.\n\n"
            f"{PROMOTION_HANDOFF_INSTRUCTION}\n\n"
            f"Build on the parent session's findings. Do NOT repeat experiments "
            f"that already failed. Run autonomously."
            f"{fixed_settings_notice}"
            f"{focus}"
            f"{resume_block}"
        )

    def _build_prompt_rl_hpo(
        self,
        config: ResearchConfig,
        workspace: str,
        setup_extra_args: str,
        fixed_settings_notice: str,
        quick_flag: str,
        focus: str,
        instrument_underscore: str,
    ) -> str:
        """Build prompt for 3-phase HPO workflow (ML-59)."""
        hpo_trials = config.hpo_trials
        hpo_timesteps = config.hpo_timesteps

        # Load research resume for cross-session context
        resume_block = self._load_research_resume(config)

        return (
            f"Tune RL model for {config.instrument} {config.timeframe} "
            f"(tag: {config.tag}) using **3-phase HPO workflow**. "
            f"Max {config.max_iterations} refinement iterations.\n\n"
            f"Execute these phases IN ORDER:\n\n"
            f"## Phase 1: Setup + HPO Screening\n\n"
            f"1. Setup workspace: {SERVER_OWNED_SETUP_INSTRUCTION}\n"
            f"```bash\n"
            f".venv/bin/python scripts/autotuner/setup.py "
            f"--instrument {instrument_underscore} "
            f"--timeframe {config.timeframe} "
            f"--models rl{setup_extra_args}\n"
            f"```\n\n"
            f"2. Enrich RL dataset (REQUIRED):\n"
            f"```bash\n"
            f".venv/bin/python "
            f"scripts/autotuner/enrich_rl_dataset.py "
            f"--instrument {instrument_underscore} "
            f"--timeframe {config.timeframe}\n"
            f"```\n"
            f"Verify direction_proba mean is NOT ~0.5.\n\n"
            f"3. Run Optuna HPO study ({hpo_trials} trials, Bayesian sampling "
            f"with early stopping):\n"
            f"```bash\n"
            f".venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/train.yaml "
            f"--hpo --hpo-trials {hpo_trials} "
            f"--hpo-timesteps {hpo_timesteps}{quick_flag}\n"
            f"```\n"
            f"This will take ~60-120 minutes. The output contains the top-3 "
            f"parameter configs ranked by composite_rl_score.\n\n"
            f"## Phase 2: Validate & Refine\n\n"
            f"4. Read HPO results:\n"
            f"```bash\n"
            f"cat {workspace}/hpo_results.json\n"
            f"```\n\n"
            f"5. For each of the top-3 configs from Phase 1:\n"
            f"   a. Write the trial's params into the `training:` section of "
            f"`{workspace}/train.yaml`\n"
            f"   b. Run full walk-forward validation:\n"
            f"```bash\n"
            f".venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/train.yaml{quick_flag}\n"
            f"```\n"
            f"   c. If `training_gates_passed` and composite is best so far, copy to "
            f"`best_train.yaml`\n\n"
            f"6. Take the best validated config. Then refine using the RL "
            f"diagnostic playbook:\n"
            f"   - Fine-tune `reward_weights` (HPO doesn't search these by "
            f"default)\n"
            f"   - Adjust based on fold-level metrics and trade counts\n"
            f"   - Use the Phase 1-6 diagnostic table in README.md\n\n"
            f"## Phase 3: Robustness Validation\n\n"
            f"7. Run best config with different seeds to confirm stability "
            f"(one bash call per command):\n"
            f"```bash\n"
            f".venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/best_train.yaml --seed 43{quick_flag}\n"
            f"```\n"
            f"```bash\n"
            f".venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/best_train.yaml --seed 44{quick_flag}\n"
            f"```\n"
            f"If composite_rl_score is consistent across seeds (not wildly "
            f"different), the config is robust.\n\n"
            f"{PROMOTION_HANDOFF_INSTRUCTION}\n\n"
            f"Run autonomously."
            f"{fixed_settings_notice}"
            f"{focus}"
            f"{resume_block}"
        )

    async def _update_research_resume(
        self, instrument: str, timeframe: str,
    ) -> None:
        """Rebuild the research resume for an instrument after session ends."""
        try:
            instrument_underscore = instrument.replace("-", "_")
            resume_script = os.path.join(
                settings.workspace_root, "scripts", "autotuner", "resume.py"
            )
            if not os.path.exists(resume_script):
                logger.warning("Resume script not found: %s", resume_script)
                return
            cmd = [
                os.path.join(settings.workspace_root, ".venv", "bin", "python"),
                resume_script,
                "--instrument", instrument_underscore,
                "--timeframe", timeframe,
                "--db", settings.db_path,
                "--runs-dir", settings.runs_dir,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info(
                    "Research resume updated for %s_%s",
                    instrument_underscore, timeframe,
                )
            else:
                logger.warning(
                    "Resume update failed (rc=%d): %s",
                    proc.returncode, stderr.decode()[:500],
                )
        except Exception as exc:
            logger.warning("Failed to update research resume: %s", exc)

    async def _extract_session_insights(self, research_id: str) -> None:
        """ML-60: Use Claude to extract compact insights from a completed session.

        Stores a short text summary (≤500 chars) of what was learned:
        which parameter changes helped/hurt, key metric sensitivities,
        and actionable takeaways for future sessions.
        """
        try:
            session = await self._store.get_session(research_id)
            if not session:
                return
            iterations = await self._store.get_iterations(research_id)
            if not iterations:
                return

            # Build a compact iteration summary for the extraction prompt
            iter_lines = []
            for it in iterations:
                pm = it.get("primary_metric")
                metric_s = f"{pm:.4f}" if pm is not None else "—"
                decision = it.get("decision", "?")
                desc = (it.get("description") or "")[:200]
                config_snap = (it.get("config_snapshot") or "")[:300]
                iter_lines.append(
                    f"Iter {it.get('iteration', '?')}: metric={metric_s} "
                    f"decision={decision} desc={desc}"
                )
                if config_snap:
                    iter_lines.append(f"  config_diff: {config_snap}")

            iter_text = "\n".join(iter_lines)

            prompt = (
                f"You are analyzing a completed ML research session.\n"
                f"Model: {session.get('model_type', '?')} | "
                f"Instrument: {session.get('instrument', '?')} "
                f"{session.get('timeframe', '?')}\n"
                f"Tag: {session.get('tag', '?')} | "
                f"Best metric: {session.get('best_metric')}\n\n"
                f"Iterations:\n{iter_text}\n\n"
                f"Summarize KEY LEARNINGS in 3-5 bullet points (max 500 chars total).\n"
                f"Focus on: which params improved/degraded the metric, "
                f"what ranges worked, what to avoid.\n"
                f"Format: plain bullet points, no markdown headers.\n"
                f"Example:\n"
                f"- Increasing learning_rate from 3e-4 to 1e-3 degraded Sharpe by 0.15\n"
                f"- entropy_coef=0.005 with clip_range=0.15 gave best composite (1.82)\n"
                f"- gamma > 0.995 caused instability (OOS return went negative)"
            )

            response = await self._client.messages.create(
                model=settings.anthropic_default_haiku_model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )

            insights = ""
            for block in response.content:
                if block.type == "text":
                    insights += block.text

            # Trim to 500 chars max
            insights = insights.strip()[:500]

            if insights:
                await self._store.update_session(research_id, insights=insights)
                logger.info(
                    "ML-60: Extracted insights for session %s (%d chars)",
                    research_id[:8], len(insights),
                )
        except Exception as exc:
            logger.warning(
                "ML-60: Failed to extract insights for %s: %s",
                research_id[:8], exc,
            )

    async def _record_command_policy_rejection(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        command: str,
        tool_meta: Dict[str, Any],
    ) -> None:
        reason = str(tool_meta.get("policy_reason") or "Command rejected by policy")
        try:
            await self._store.record_audit_event(
                actor_id="autoresearch-agent",
                action="command.reject",
                research_id=config.id,
                pipeline_id=config.pipeline_id,
                request_metadata={
                    "turn": turn,
                    "tool": "bash",
                    "command": redact_sensitive_text(command),
                    "operation": tool_meta.get("policy_operation"),
                },
                outcome="failure",
                error_message=reason,
            )
        except Exception as exc:
            logger.warning(
                "Research %s turn %d: failed to record command rejection audit event: %s",
                config.id,
                turn,
                exc,
                exc_info=True,
            )

    @staticmethod
    def _structured_hpo_enforced(config: ResearchConfig) -> bool:
        return bool(config.enable_hpo and config.model_type in {"direction", "volatility"})

    async def _active_hpo_study_id(self, research_id: str) -> Optional[str]:
        studies = await self._store.get_hpo_studies(research_id)
        for study in studies:
            if study.get("study_id"):
                return str(study["study_id"])
        return None

    async def _ensure_structured_plan_materialized(
        self,
        *,
        config: ResearchConfig,
        workspace: str,
        agent_log: AgentLogWriter,
        turn: int,
    ) -> None:
        if not self._structured_hpo_enforced(config):
            return
        planned_trials = [
            trial
            for trial in await self._store.get_planned_trials(config.id)
            if trial.get("status") != "manual_review"
        ]
        if not planned_trials:
            return
        plan = {
            "schema_version": "autoresearch_structured_hpo_plan.v1",
            "research_id": config.id,
            "model_type": config.model_type,
            "trials": planned_trials,
        }
        written = await asyncio.to_thread(
            materialize_planned_trials,
            plan,
            workspace,
        )
        if not written:
            await agent_log.append(
                "warning",
                "Structured HPO plan was not materialized because train.yaml "
                "is not available yet.",
                turn=turn,
            )
            return
        for trial in written:
            trial_config_snapshot = None
            materialized_path = trial.get("materialized_config_path")
            if materialized_path:
                try:
                    trial_config_snapshot = Path(materialized_path).read_text(
                        encoding="utf-8",
                    )
                except OSError:
                    trial_config_snapshot = None
            identity = build_trial_identity(
                instrument=config.instrument,
                timeframe=config.timeframe,
                model_type=config.model_type,
                command=trial.get("expected_command"),
                config_snapshot=trial_config_snapshot,
                quick_mode=config.quick_mode,
            )
            await self._store.update_planned_trial_status(
                research_id=config.id,
                trial_id=trial["trial_id"],
                status="materialized",
                train_config_path=trial.get("train_config_path")
                or trial.get("materialized_config_path"),
                canonical_config_hash=identity.get("canonical_config_hash"),
                trial_identity_hash=trial_identity_hash(identity),
                trial_identity=identity,
            )
        await agent_log.append(
            "system",
            f"Materialized {len(written)} server-owned structured HPO trials "
            f"under {workspace}/planned_trials.",
            turn=turn,
        )

    async def _guard_structured_hpo_tool(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        tool_name: str,
        input_data: Dict[str, Any],
    ) -> tuple[Optional[Dict[str, Any]], Optional[ToolExecutionResult]]:
        if not self._structured_hpo_enforced(config):
            return None, None

        if tool_name == "bash":
            command = str(input_data.get("command", ""))
            if _is_setup_command(command):
                return None, None
            is_training_command = (
                "prepare.py" in command
                or "run_phase1c_" in command
                or "run_phase1b_" in command
            )
            if not is_training_command:
                return None, None
            normalized = _normalize_command_for_plan(command)
            planned_trial = await self._store.get_planned_trial_for_command(
                config.id,
                normalized,
            )
            if planned_trial:
                return planned_trial, None
            reason = (
                "Structured HPO command is outside the server-owned plan. "
                "Run expected commands from server_hpo_plan.json exactly or "
                "request manual review."
            )
            await self._record_structured_hpo_manual_review(
                config=config,
                turn=turn,
                proposed_action=normalized,
                reason=reason,
                config_patch={"proposed_command": normalized},
            )
            return None, ToolExecutionResult(
                (
                    "Structured HPO manual review required: this training "
                    "command is outside the server-owned plan. Read "
                    "server_hpo_plan.json and run an expected_command exactly, "
                    "or describe the desired follow-up as MANUAL_REVIEW_REQUEST."
                ),
                meta={
                    "policy_allowed": False,
                    "policy_reason": reason,
                    "policy_operation": "structured_hpo.manual_review",
                    "normalized_command": normalized,
                    "returncode": None,
                    "timed_out": False,
                },
            )

        if tool_name == "write_file":
            raw_path = str(input_data.get("path", ""))
            if not self._is_structured_hpo_config_write(raw_path):
                return None, None
            reason = (
                "Structured HPO config files are server-owned. Proposed YAML "
                "edits must be routed to manual review instead of written."
            )
            await self._record_structured_hpo_manual_review(
                config=config,
                turn=turn,
                proposed_action=f"write_file:{raw_path}",
                reason=reason,
                config_patch={
                    "proposed_write_path": raw_path,
                    "content_length": len(str(input_data.get("content", ""))),
                },
            )
            return None, ToolExecutionResult(
                (
                    "Structured HPO manual review required: train.yaml and "
                    "planned trial YAML files are server-owned in this mode. "
                    "Describe the desired follow-up as MANUAL_REVIEW_REQUEST."
                ),
                meta={
                    "policy_allowed": False,
                    "policy_reason": reason,
                    "policy_operation": "structured_hpo.manual_review",
                    "returncode": None,
                    "timed_out": False,
                },
            )

        return None, None

    @staticmethod
    def _is_structured_hpo_config_write(raw_path: str) -> bool:
        normalized = raw_path.replace("\\", "/")
        basename = normalized.rsplit("/", 1)[-1]
        if basename in {"train.yaml", "best_train.yaml"}:
            return True
        return "/planned_trials/" in normalized and normalized.endswith((".yaml", ".yml"))

    async def _record_structured_hpo_manual_review(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        proposed_action: str,
        reason: str,
        config_patch: Dict[str, Any],
    ) -> None:
        try:
            study_id = await self._active_hpo_study_id(config.id)
            await self._store.record_planned_trial_manual_review(
                research_id=config.id,
                study_id=study_id,
                expected_command=proposed_action,
                reason=reason,
                config_patch=config_patch,
            )
            await self._store.record_audit_event(
                actor_id="autoresearch-agent",
                action="structured_hpo.manual_review",
                research_id=config.id,
                pipeline_id=config.pipeline_id,
                request_metadata={
                    "turn": turn,
                    "model_type": config.model_type,
                    "proposed_action": redact_sensitive_text(proposed_action),
                },
                outcome="manual_review",
                error_message=reason,
            )
        except Exception as exc:
            logger.warning(
                "Research %s turn %d: failed to record structured HPO "
                "manual-review state: %s",
                config.id,
                turn,
                exc,
                exc_info=True,
            )

    @staticmethod
    def _attach_planned_trial_metadata(
        marker: Dict[str, Any],
        planned_trial: Optional[Dict[str, Any]],
    ) -> None:
        if not planned_trial:
            return
        marker.setdefault(
            "search_phase",
            planned_trial.get("search_phase") or "hpo_screening",
        )
        marker["planned_trial_id"] = planned_trial.get("trial_id")
        marker["config_hash"] = planned_trial.get("config_hash")
        marker["expected_command"] = planned_trial.get("expected_command")
        marker["planned_result_path"] = planned_trial.get("result_path")

    async def _finish_planned_trial(
        self,
        *,
        config: ResearchConfig,
        planned_trial: Optional[Dict[str, Any]],
        marker: Dict[str, Any],
        status: str,
    ) -> None:
        if not planned_trial:
            return
        await self._store.update_planned_trial_status(
            research_id=config.id,
            trial_id=planned_trial["trial_id"],
            status=status,
            result_path=planned_trial.get("result_path"),
            mlflow_run_id=marker.get("mlflow_run_id"),
        )

    async def _guard_duplicate_training_attempt(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        command: str,
        config_snapshot: Optional[str],
        planned_trial: Optional[Dict[str, Any]],
    ) -> tuple[Optional[ToolExecutionResult], Optional[Dict[str, Any]]]:
        """Reject an already-attempted config/seed/mode/split identity."""

        identity = build_trial_identity(
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=config.model_type,
            command=command,
            config_snapshot=config_snapshot,
            quick_mode=config.quick_mode,
            marker=planned_trial or {},
        )
        identity_hash = trial_identity_hash(identity)
        if not identity_hash:
            return None, None

        duplicate = await self._store.find_duplicate_trial_identity(
            research_id=config.id,
            trial_identity_hash=identity_hash,
            instrument=config.instrument,
            timeframe=config.timeframe,
            model_type=config.model_type,
            include_cross_session=(
                settings.autoresearch_cross_session_duplicate_check
            ),
        )
        if not duplicate:
            return None, None

        duplicate_research_id = duplicate.get("research_id")
        duplicate_iteration = duplicate.get("iteration")
        duplicate_reason = (
            "Duplicate training attempt rejected: the same canonical config, "
            f"seed={identity.get('seed')}, mode={identity.get('validation_mode')}, "
            f"data_split_id={identity.get('data_split_id')}, model="
            f"{config.model_type}, instrument={config.instrument}, timeframe="
            f"{config.timeframe} already exists in session "
            f"{duplicate_research_id} iteration {duplicate_iteration}."
        )
        marker = {
            "status": "rejected_duplicate",
            "primary_metric": None,
            "metric_name": None,
            "training_gates_passed": False,
            "all_gates_passed": False,
            "decision": "discard",
            "description": f"{duplicate_reason} (turn {turn})",
            "config_snapshot": config_snapshot,
            "canonical_config_hash": identity.get("canonical_config_hash"),
            "trial_identity": identity,
            "trial_identity_hash": identity_hash,
            "duplicate_of_research_id": duplicate_research_id,
            "duplicate_of_iteration": duplicate_iteration,
            "duplicate_reason": duplicate_reason,
        }
        return ToolExecutionResult(
            duplicate_reason,
            meta={
                "policy_allowed": False,
                "policy_reason": duplicate_reason,
                "policy_operation": "duplicate_attempt.reject",
                "normalized_command": _normalize_command_for_plan(command),
                "returncode": None,
                "timed_out": False,
                "trial_identity_hash": identity_hash,
                "duplicate_of_research_id": duplicate_research_id,
                "duplicate_of_iteration": duplicate_iteration,
            },
        ), marker

    async def _build_iteration_context_digest(
        self,
        *,
        config: ResearchConfig,
        total_cost: float,
    ) -> Optional[str]:
        """Build advisory context from persisted attempts for the next turn."""

        try:
            session = await self._store.get_session(config.id) or {}
            session = dict(session)
            session.setdefault("id", config.id)
            session.setdefault("instrument", config.instrument)
            session.setdefault("timeframe", config.timeframe)
            session.setdefault("model_type", config.model_type)
            session.setdefault("max_iterations", config.max_iterations)
            session.setdefault("max_budget_usd", config.max_budget_usd)
            session["total_api_cost_usd"] = total_cost
            iterations = await self._store.get_iterations(config.id)
            get_hpo = getattr(self._store, "get_hpo_studies", None)
            hpo_studies = await get_hpo(config.id) if get_hpo else []
            get_planned = getattr(self._store, "get_planned_trials", None)
            planned_trials = await get_planned(config.id) if get_planned else []
            # Read persisted phase state so the digest can surface the current
            # phase action and stall warning to the LLM on every turn.
            phase_state: Optional[Dict[str, Any]] = None
            phase_state_raw = session.get("phase_state_json")
            if phase_state_raw:
                try:
                    phase_state = json.loads(phase_state_raw)
                except (json.JSONDecodeError, TypeError):
                    phase_state = None
            return build_iteration_context_digest(
                session=session,
                iterations=iterations,
                hpo_studies=hpo_studies,
                planned_trials=planned_trials,
                phase_state=phase_state,
                max_chars=settings.iteration_context_max_chars,
                recent_attempts=settings.iteration_context_recent_attempts,
            )
        except Exception as exc:
            logger.warning("Failed to build iteration context digest: %s", exc)
            return None

    async def _append_iteration_context_digest(
        self,
        *,
        config: ResearchConfig,
        tool_results: List[Dict[str, Any]],
        turn_recorded_iteration: bool,
        total_cost: float,
    ) -> None:
        if not turn_recorded_iteration or not settings.iteration_context_enabled:
            return
        digest = await self._build_iteration_context_digest(
            config=config,
            total_cost=total_cost,
        )
        if digest:
            tool_results.append({"type": "text", "text": digest})

    async def run(self, config: ResearchConfig) -> None:
        """Run the autonomous research loop for a single session."""
        research_id = config.id
        workspace = config.workspace_path or os.path.join(
            settings.runs_dir,
            f"{config.instrument}_{config.timeframe}",
            config.model_type,
        )

        # Load system prompt (async to avoid blocking event loop)
        skill_content = await self._load_skill_async(config.model_type)
        claude_md = await self._load_claude_md_async()
        system_prompt = f"{claude_md}\n\n---\n\n{skill_content}"

        # Build initial user message
        # ML-62: Use resume prompt for continuation sessions
        if config.resumed_from:
            user_prompt = await self._build_resume_prompt(config)
        else:
            user_prompt = self._build_prompt(config)

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": user_prompt},
        ]

        iteration_count = 0
        total_cost = 0.0
        last_input_tokens = 0  # Phase 2.2: rolling estimate for budget gate
        # Phase 5.4: abort the session if the agent keeps trying to run
        # commands the policy keeps rejecting — usually a sign of a bad
        # plan/loop, and burning budget on rejected calls is wasteful.
        policy_rejections_consecutive = 0
        _policy_aborted = False
        start_time = time.monotonic()
        max_turns = config.max_iterations * 10  # ~10 turns per iteration

        # Agent log capture
        agent_log = AgentLogWriter(
            Path(workspace) / "agent_log.jsonl", research_id,
            pipeline_id=config.pipeline_id,
            phase=config.model_type if config.pipeline_id else None,
        )
        await agent_log.append(
            "system",
            f"Research session started: {config.instrument} {config.timeframe} "
            f"{config.model_type} tag={config.tag} max_iter={config.max_iterations}",
        )
        await self._refresh_phase_state(research_id)

        try:
            _timed_out = False  # ML-62: track timeout vs normal completion
            for turn in range(max_turns):
                # Check stop/pause conditions
                if self._should_stop(research_id):
                    logger.info("Research %s: stop requested", research_id)
                    await agent_log.append("system", "Stop requested by user", turn=turn)
                    break

                await self._wait_while_paused(research_id)

                if self._should_stop(research_id):
                    break

                if _policy_aborted:
                    # Phase 5.4: bail out as soon as the rejection counter
                    # tripped on the previous turn.
                    break

                # Check timeout (per-session override or server default)
                elapsed = time.monotonic() - start_time
                _timeout = (
                    config.timeout_s
                    if config.timeout_s > 0
                    else settings.experiment_timeout_s
                )
                if elapsed > _timeout:
                    logger.info("Research %s: timeout after %.0fs", research_id, elapsed)
                    await agent_log.append("system", f"Timeout after {elapsed:.0f}s", turn=turn)
                    _timed_out = True
                    break

                # Phase 2.2: pre-spend cost gate. Refuse to call Claude if
                # we are already over budget OR if the worst-case spend on
                # the next turn would exceed the budget. ``last_input_tokens``
                # tracks the last turn's input size as a proxy for the next
                # turn's input prompt; for the first turn we fall back to a
                # conservative max-context estimate.
                projected_input = max(last_input_tokens, 32_000)
                projected_turn_cost = (
                    projected_input * _CLAUDE_INPUT_USD_PER_TOKEN
                    + _CLAUDE_MAX_OUTPUT_TOKENS * _CLAUDE_OUTPUT_USD_PER_TOKEN
                )
                if total_cost >= config.max_budget_usd or (
                    total_cost + projected_turn_cost > config.max_budget_usd
                ):
                    logger.info(
                        "Research %s: budget gate triggered "
                        "(spent=$%.4f, projected_next=$%.4f, cap=$%.4f)",
                        research_id, total_cost, projected_turn_cost,
                        config.max_budget_usd,
                    )
                    await agent_log.append(
                        "system",
                        f"Budget cap reached: spent=${total_cost:.4f}, "
                        f"projected_next=${projected_turn_cost:.4f}, "
                        f"cap=${config.max_budget_usd:.4f}",
                        turn=turn,
                    )
                    break

                # Call Claude (ML-68: with retry + context compaction)
                _api_messages = self._compact_messages(
                    messages, keep_recent=settings.context_compaction_threshold // 2,
                )
                response = await self._call_claude_with_retry(
                    messages=_api_messages,
                    system_prompt=system_prompt,
                    research_id=research_id,
                    agent_log=agent_log,
                    turn=turn,
                    remaining_budget_s=max(0.0, _timeout - elapsed),
                )

                # Track cost (approximate from usage)
                turn_cost = 0.0
                if response.usage:
                    last_input_tokens = response.usage.input_tokens
                    turn_cost = (
                        response.usage.input_tokens * _CLAUDE_INPUT_USD_PER_TOKEN
                        + response.usage.output_tokens * _CLAUDE_OUTPUT_USD_PER_TOKEN
                    )
                    total_cost += turn_cost

                # Process response content blocks
                assistant_content = response.content
                tool_results = []
                agent_text = ""
                turn_recorded_iteration = False
                last_planned_trial_for_turn: Optional[Dict[str, Any]] = None

                for block in assistant_content:
                    if block.type == "text":
                        agent_text += block.text
                        if block.text.strip():
                            logger.info(
                                "Research %s turn %d: text=%s",
                                research_id, turn, block.text[:200],
                            )
                            await agent_log.append("text", block.text, turn=turn)
                    elif block.type == "tool_use":
                        logged_input = block.input
                        if block.name == "bash" and isinstance(block.input, dict):
                            logged_input = {
                                **block.input,
                                "command": redact_sensitive_text(
                                    str(block.input.get("command", ""))
                                ),
                            }
                        logger.info(
                            "Research %s turn %d: tool=%s input=%s",
                            research_id, turn, block.name,
                            str(logged_input)[:200],
                        )
                        await agent_log.append(
                            "tool_call", block.name, turn=turn,
                            meta={"tool_id": block.id, "input": logged_input},
                        )

                        planned_trial_for_tool: Optional[Dict[str, Any]] = None
                        structured_rejection: Optional[ToolExecutionResult] = None
                        if isinstance(block.input, dict):
                            (
                                planned_trial_for_tool,
                                structured_rejection,
                            ) = await self._guard_structured_hpo_tool(
                                config=config,
                                turn=turn,
                                tool_name=block.name,
                                input_data=block.input,
                            )
                        if planned_trial_for_tool:
                            last_planned_trial_for_turn = planned_trial_for_tool
                        raw_command_for_tool = (
                            str(block.input.get("command", ""))
                            if isinstance(block.input, dict)
                            else ""
                        )

                        # Pre-snapshot: capture train.yaml BEFORE running
                        # prepare.py so we have an immutable config record
                        # for this attempt — preserved even on crash/timeout.
                        _pending_snapshot: Optional[str] = None
                        if (
                            structured_rejection is None
                            and isinstance(block.input, dict)
                            and block.name == "bash"
                            and any(
                                token in raw_command_for_tool
                                for token in (
                                    "prepare.py",
                                    "run_phase1c_",
                                    "run_phase1b_",
                                )
                            )
                        ):
                            snapshot_path = _config_snapshot_path_from_command(
                                raw_command_for_tool,
                                settings.workspace_root,
                                workspace,
                            ) or os.path.join(workspace, "train.yaml")
                            try:
                                _pending_snapshot = Path(snapshot_path).read_text(
                                    encoding="utf-8",
                                )
                            except OSError:
                                logger.warning(
                                    "Research %s: could not pre-snapshot "
                                    "%s before prepare.py run",
                                    research_id,
                                    snapshot_path,
                                )

                        duplicate_rejection: Optional[ToolExecutionResult] = None
                        duplicate_marker: Optional[Dict[str, Any]] = None
                        if (
                            structured_rejection is None
                            and isinstance(block.input, dict)
                            and block.name == "bash"
                            and any(
                                token in raw_command_for_tool
                                for token in (
                                    "prepare.py",
                                    "run_phase1c_",
                                    "run_phase1b_",
                                )
                            )
                        ):
                            (
                                duplicate_rejection,
                                duplicate_marker,
                            ) = await self._guard_duplicate_training_attempt(
                                config=config,
                                turn=turn,
                                command=raw_command_for_tool,
                                config_snapshot=_pending_snapshot,
                                planned_trial=planned_trial_for_tool,
                            )

                        runtime_command_id: Optional[int] = None
                        if (
                            structured_rejection is None
                            and duplicate_rejection is None
                            and isinstance(block.input, dict)
                            and block.name == "bash"
                        ):
                            runtime_command = await self._store.record_runtime_command(
                                research_id=research_id,
                                turn=turn,
                                tool_name=block.name,
                                command=redact_sensitive_text(raw_command_for_tool),
                                timeout_s=self._effective_tool_timeout(block.input),
                                metadata={"tool_id": block.id},
                            )
                            runtime_command_id = runtime_command["id"]

                        if structured_rejection is not None:
                            tool_execution = structured_rejection
                        elif duplicate_rejection is not None:
                            iteration_count += 1
                            duplicate_marker = duplicate_marker or {}
                            self._attach_planned_trial_metadata(
                                duplicate_marker,
                                planned_trial_for_tool,
                            )
                            await self._record_iteration(
                                research_id, iteration_count,
                                duplicate_marker, total_cost,
                                workspace=workspace,
                                turn=turn,
                                command=redact_sensitive_text(raw_command_for_tool),
                            )
                            if planned_trial_for_tool:
                                await self._store.update_planned_trial_status(
                                    research_id=config.id,
                                    trial_id=planned_trial_for_tool["trial_id"],
                                    status="duplicate_rejected",
                                    result_path=planned_trial_for_tool.get("result_path"),
                                    manual_review_reason=(
                                        duplicate_marker.get("duplicate_reason")
                                    ),
                                )
                            turn_recorded_iteration = True
                            tool_execution = duplicate_rejection
                        else:
                            if planned_trial_for_tool:
                                await self._store.update_planned_trial_status(
                                    research_id=config.id,
                                    trial_id=planned_trial_for_tool["trial_id"],
                                    status="running",
                                )
                            tool_execution = await asyncio.to_thread(
                                _execute_tool,
                                block.name,
                                block.input,
                                settings.workspace_root,
                                workspace,
                            )
                        tool_result = tool_execution.content
                        tool_meta = tool_execution.meta
                        if runtime_command_id is not None:
                            tool_meta = dict(tool_meta)
                            tool_meta["runtime_command_id"] = runtime_command_id
                            await self._store.finish_runtime_command(
                                runtime_command_id,
                                status=self._runtime_command_status(tool_meta),
                                returncode=tool_meta.get("returncode"),
                                timed_out=bool(tool_meta.get("timed_out")),
                                output_preview=tool_result[:5000],
                                metadata=tool_meta,
                            )
                        logger.info(
                            "Research %s turn %d: tool=%s result=%s",
                            research_id, turn, block.name,
                            tool_result[:200],
                        )
                        if (
                            block.name == "bash"
                            and _is_setup_command(raw_command_for_tool)
                            and tool_meta.get("policy_allowed") is not False
                            and tool_meta.get("returncode") in (0, None)
                        ):
                            await self._ensure_structured_plan_materialized(
                                config=config,
                                workspace=workspace,
                                agent_log=agent_log,
                                turn=turn,
                            )
                        if (
                            block.name == "bash"
                            and tool_meta.get("policy_allowed") is False
                        ):
                            await self._record_command_policy_rejection(
                                config=config,
                                turn=turn,
                                command=str(block.input.get("command", "")),
                                tool_meta=tool_meta,
                            )
                            policy_rejections_consecutive += 1
                            if policy_rejections_consecutive >= _MAX_CONSECUTIVE_POLICY_REJECTIONS:
                                _policy_aborted = True
                                logger.warning(
                                    "Research %s: aborting after %d "
                                    "consecutive policy rejections",
                                    research_id,
                                    policy_rejections_consecutive,
                                )
                                await agent_log.append(
                                    "system",
                                    f"Aborting: {policy_rejections_consecutive} "
                                    "consecutive command-policy rejections. "
                                    "Operator review required.",
                                    turn=turn,
                                )
                        elif (
                            block.name == "bash"
                            and tool_meta.get("policy_allowed") is True
                        ):
                            policy_rejections_consecutive = 0
                        await agent_log.append(
                            "tool_result", tool_result[:5000], turn=turn,
                            meta={
                                "tool_id": block.id,
                                "tool_name": block.name,
                                **tool_meta,
                            },
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result,
                        })
                        _cmd_str = redact_sensitive_text(
                            str(block.input.get("command", ""))
                        )

                        # Universal detection: scan bash output for
                        # prepare.py --- delimited metrics blocks.
                        # This works regardless of LLM model since it's
                        # parsing deterministic Python script output.

                        # ML-59: Check for HPO study output first (mode: hpo_study)
                        if (
                            block.name == "bash"
                            and not turn_recorded_iteration
                            and "---" in tool_result
                            and is_hpo_study_output(tool_result)
                        ):
                            hpo_result = parse_hpo_study_output(tool_result)
                            if hpo_result and hpo_result.status in ("completed", "success"):
                                # Record as a special HPO study iteration
                                iteration_count += 1
                                hpo_marker = hpo_result.to_dict()
                                self._attach_runtime_command_metadata(
                                    hpo_marker, tool_meta,
                                )
                                hpo_marker["decision"] = "hpo_screening"
                                hpo_marker["config_snapshot"] = _pending_snapshot
                                hpo_marker["primary_metric"] = hpo_result.best_composite
                                hpo_marker["metric_name"] = "hpo_best_composite"
                                hpo_marker["search_phase"] = "hpo_screening"
                                hpo_marker["description"] = (
                                    f"HPO study completed: {hpo_result.completed_trials}/"
                                    f"{hpo_result.n_trials} trials, best composite="
                                    f"{hpo_result.best_composite:.4f} (turn {turn})"
                                )
                                self._attach_planned_trial_metadata(
                                    hpo_marker,
                                    planned_trial_for_tool,
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    hpo_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                await self._finish_planned_trial(
                                    config=config,
                                    planned_trial=planned_trial_for_tool,
                                    marker=hpo_marker,
                                    status="completed",
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: HPO study completed "
                                    "(%d/%d trials, best=%.4f)",
                                    research_id, turn,
                                    hpo_result.completed_trials,
                                    hpo_result.n_trials,
                                    hpo_result.best_composite or 0.0,
                                )
                                await agent_log.append(
                                    "hpo_study", json.dumps(hpo_marker)[:5000],
                                    turn=turn,
                                )

                        elif (
                            block.name == "bash"
                            and not turn_recorded_iteration
                            and "---" in tool_result
                        ):
                            metrics = parse_prepare_output(tool_result)
                            if (
                                metrics.primary_metric is not None
                                and metrics.status in ("completed", "success")
                            ):
                                iteration_count += 1
                                marker_from_tool = metrics.to_dict()
                                self._attach_runtime_command_metadata(
                                    marker_from_tool, tool_meta,
                                )
                                # Determine keep/discard by comparing against
                                # current session best — not just gates.
                                decision = await self._infer_decision(
                                    research_id,
                                    metrics.primary_metric,
                                    metrics.training_gates_passed,
                                )
                                marker_from_tool["decision"] = decision
                                # Attach the pre-captured snapshot so the DB
                                # is the sole source of truth for the config.
                                marker_from_tool["config_snapshot"] = _pending_snapshot
                                marker_from_tool["description"] = (
                                    f"Auto-detected from prepare.py output "
                                    f"(turn {turn})"
                                )
                                self._attach_planned_trial_metadata(
                                    marker_from_tool,
                                    planned_trial_for_tool,
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    marker_from_tool, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                await self._finish_planned_trial(
                                    config=config,
                                    planned_trial=planned_trial_for_tool,
                                    marker=marker_from_tool,
                                    status="completed",
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: auto-detected "
                                    "iteration %d from bash output "
                                    "(%s=%.4f, training_gates=%s)",
                                    research_id, turn, iteration_count,
                                    metrics.metric_name,
                                    metrics.primary_metric,
                                    metrics.training_gates_passed,
                                )
                            elif (
                                metrics.status in (
                                    "crash", "timeout", "failed", "error",
                                    "pruned",
                                )
                            ):
                                # Record failed attempts as first-class discard
                                # iterations so the full audit trail is in DB
                                # and the agent cannot revisit the same invalid
                                # config region without a recorded trace.
                                iteration_count += 1
                                crash_marker = metrics.to_dict()
                                self._attach_runtime_command_metadata(
                                    crash_marker, tool_meta,
                                )
                                crash_marker["decision"] = "discard"
                                crash_marker["config_snapshot"] = _pending_snapshot
                                crash_marker["description"] = (
                                    f"Failed ({metrics.status}) — "
                                    f"auto-detected from prepare.py output "
                                    f"(turn {turn})"
                                )
                                self._attach_planned_trial_metadata(
                                    crash_marker,
                                    planned_trial_for_tool,
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    crash_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                await self._finish_planned_trial(
                                    config=config,
                                    planned_trial=planned_trial_for_tool,
                                    marker=crash_marker,
                                    status="failed",
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: recorded failed "
                                    "attempt %d (%s) from bash output",
                                    research_id, turn, iteration_count,
                                    metrics.status,
                                )

                        # Fallback: if bash timed out or output was piped,
                        # check for a last_metrics.txt marker file written
                        # by prepare.py on completion.  Also trigger when
                        # the agent runs a training script directly (e.g.
                        # run_phase1c_direction.py) to handle cases where
                        # prepare.py was bypassed.
                        if (
                            block.name == "bash"
                            and not turn_recorded_iteration
                            and (
                                "prepare.py" in _cmd_str
                                or "run_phase1c_" in _cmd_str
                                or "run_phase1b_" in _cmd_str
                            )
                        ):
                            marker_text = await self._read_marker_file_async(config)
                            if marker_text:
                                metrics = parse_prepare_output(marker_text)
                                if (
                                    metrics.primary_metric is not None
                                    and metrics.status in ("completed", "success")
                                ):
                                    iteration_count += 1
                                    marker_from_file = metrics.to_dict()
                                    self._attach_runtime_command_metadata(
                                        marker_from_file, tool_meta,
                                    )
                                    decision = await self._infer_decision(
                                        research_id,
                                        metrics.primary_metric,
                                        metrics.training_gates_passed,
                                    )
                                    marker_from_file["decision"] = decision
                                    # Attach snapshot for marker-file path too.
                                    marker_from_file["config_snapshot"] = _pending_snapshot
                                    marker_from_file["description"] = (
                                        f"Auto-detected from marker file "
                                        f"(turn {turn})"
                                    )
                                    self._attach_planned_trial_metadata(
                                        marker_from_file,
                                        planned_trial_for_tool,
                                    )
                                    await self._record_iteration(
                                        research_id, iteration_count,
                                        marker_from_file, total_cost,
                                        workspace=workspace,
                                        turn=turn,
                                        command=_cmd_str,
                                    )
                                    await self._finish_planned_trial(
                                        config=config,
                                        planned_trial=planned_trial_for_tool,
                                        marker=marker_from_file,
                                        status="completed",
                                    )
                                    turn_recorded_iteration = True
                                    logger.info(
                                    "Research %s turn %d: auto-detected "
                                    "iteration %d from marker file "
                                    "(%s=%.4f, training_gates=%s)",
                                        research_id, turn, iteration_count,
                                        metrics.metric_name,
                                        metrics.primary_metric,
                                        metrics.training_gates_passed,
                                    )
                                elif metrics.status in (
                                    "crash", "timeout", "failed", "error",
                                    "pruned",
                                ):
                                    iteration_count += 1
                                    crash_marker = metrics.to_dict()
                                    self._attach_runtime_command_metadata(
                                        crash_marker, tool_meta,
                                    )
                                    crash_marker["decision"] = "discard"
                                    crash_marker["config_snapshot"] = _pending_snapshot
                                    crash_marker["description"] = (
                                        f"Failed ({metrics.status}) — "
                                        f"auto-detected from marker file "
                                        f"(turn {turn})"
                                    )
                                    self._attach_planned_trial_metadata(
                                        crash_marker,
                                        planned_trial_for_tool,
                                    )
                                    await self._record_iteration(
                                        research_id, iteration_count,
                                        crash_marker, total_cost,
                                        workspace=workspace,
                                        turn=turn,
                                        command=_cmd_str,
                                    )
                                    await self._finish_planned_trial(
                                        config=config,
                                        planned_trial=planned_trial_for_tool,
                                        marker=crash_marker,
                                        status="failed",
                                    )
                                    turn_recorded_iteration = True
                                    logger.info(
                                        "Research %s turn %d: recorded failed "
                                        "attempt %d (%s) from marker file",
                                        research_id, turn, iteration_count,
                                        metrics.status,
                                    )

                        if (
                            block.name == "bash"
                            and not turn_recorded_iteration
                            and (
                                "prepare.py" in _cmd_str
                                or "run_phase1c_" in _cmd_str
                                or "run_phase1b_" in _cmd_str
                            )
                        ):
                            failed_status = self._infer_failed_attempt_status(
                                tool_result
                            )
                            if failed_status:
                                iteration_count += 1
                                failed_marker = {
                                    "status": failed_status,
                                    "primary_metric": None,
                                    "metric_name": None,
                                    "training_gates_passed": False,
                                    "all_gates_passed": False,
                                    "decision": "discard",
                                    "description": (
                                        f"Failed ({failed_status}) — "
                                        f"server-detected training command "
                                        f"failure (turn {turn})"
                                    ),
                                    "config_snapshot": _pending_snapshot,
                                }
                                self._attach_runtime_command_metadata(
                                    failed_marker, tool_meta,
                                )
                                self._attach_planned_trial_metadata(
                                    failed_marker,
                                    planned_trial_for_tool,
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    failed_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                await self._finish_planned_trial(
                                    config=config,
                                    planned_trial=planned_trial_for_tool,
                                    marker=failed_marker,
                                    status="failed",
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: recorded failed "
                                    "attempt %d (%s) from command status",
                                    research_id, turn, iteration_count,
                                    failed_status,
                                )

                        if planned_trial_for_tool and not turn_recorded_iteration:
                            rc = tool_meta.get("returncode")
                            if tool_meta.get("timed_out") or (
                                isinstance(rc, int) and rc != 0
                            ):
                                await self._store.update_planned_trial_status(
                                    research_id=config.id,
                                    trial_id=planned_trial_for_tool["trial_id"],
                                    status="failed",
                                    result_path=planned_trial_for_tool.get("result_path"),
                                )

                # Secondary: check for explicit ITERATION_RESULT: markers
                # in agent text. If the model emits one, it may carry richer
                # fields (decision, description) so we prefer it over the
                # auto-detected one.  If this turn already recorded an
                # iteration from bash output, overwrite it with the richer
                # marker instead of creating a duplicate.
                if agent_text:
                    marker = parse_iteration_marker(agent_text)
                    if marker:
                        self._attach_planned_trial_metadata(
                            marker,
                            last_planned_trial_for_turn,
                        )
                        if turn_recorded_iteration:
                            # Overwrite last iteration with richer marker
                            await self._attach_consistency_report(
                                research_id, iteration_count, marker,
                            )
                            await self._store.update_iteration(
                                research_id, iteration_count, marker,
                            )
                            await self._refresh_phase_state(research_id)
                            logger.info(
                                "Research %s turn %d: overwrote iteration "
                                "%d with explicit ITERATION_RESULT marker",
                                research_id, turn, iteration_count,
                            )
                        else:
                            iteration_count += 1
                            await self._record_iteration(
                                research_id, iteration_count, marker,
                                total_cost,
                                workspace=workspace,
                                turn=turn,
                            )

                # Check if we've hit max iterations
                if iteration_count >= config.max_iterations:
                    logger.info(
                        "Research %s: max iterations (%d) reached",
                        research_id, config.max_iterations,
                    )
                    break

                # If the model stopped (end_turn) and no tool calls → done
                if response.stop_reason == "end_turn" and not tool_results:
                    terminate_request = self._extract_terminate_request(agent_text)
                    if terminate_request:
                        logger.info(
                            "Research %s turn %d: honoring TERMINATE_REQUEST",
                            research_id, turn,
                        )
                        await agent_log.append(
                            "system",
                            f"Terminate request accepted: {terminate_request[:1800]}",
                            turn=turn,
                        )
                        break

                    # F1: refuse to terminate while the phase plan has
                    # incomplete phases AND the run still has both budget and
                    # iteration headroom. The agent self-terminated run
                    # res_0efe45aaa28f at turn 305 having spent only $16.49
                    # of $100 with 158 iterations remaining and the phase
                    # plan still on tabular_sweeps. Inject a continuation
                    # nudge instead of breaking.
                    continuation_kick = await self._build_phase_continuation_kick(
                        research_id=research_id,
                        iteration_count=iteration_count,
                        total_cost=total_cost,
                        config=config,
                    )
                    if continuation_kick is None:
                        logger.info(
                            "Research %s: agent ended conversation",
                            research_id,
                        )
                        break
                    logger.info(
                        "Research %s turn %d: rejecting end_turn — %s",
                        research_id, turn, continuation_kick["reason"],
                    )
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                    })
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text": continuation_kick["text"]}],
                    })
                    continue

                # Append assistant message and tool results
                messages.append({"role": "assistant", "content": assistant_content})

                if tool_results:
                    await self._append_iteration_context_digest(
                        config=config,
                        tool_results=tool_results,
                        turn_recorded_iteration=turn_recorded_iteration,
                        total_cost=total_cost,
                    )
                    # Inject orchestrator iteration count so the agent's
                    # numbering stays in sync with the DB record.
                    tool_results.append({
                        "type": "text",
                        "text": (
                            f"[system] Orchestrator iteration count: "
                            f"{iteration_count}/{config.max_iterations}. "
                            f"Use iteration={iteration_count + 1} for your "
                            f"next experiment."
                        ),
                    })
                    # F7: warn the LLM when the active phase has saturated its
                    # iteration cap. Forces the agent to advance instead of
                    # grinding the same phase with duplicate configs.
                    phase_cap_message = await self._maybe_phase_cap_nudge(
                        research_id=research_id,
                    )
                    if phase_cap_message:
                        tool_results.append({
                            "type": "text",
                            "text": phase_cap_message,
                        })
                    # AR-7: warn the LLM when no metric improvement has been
                    # recorded for global_stagnation_window consecutive
                    # iterations. Forces a TERMINATE_REQUEST instead of burning
                    # the rest of the budget on stagnant experiments.
                    stagnation_message = await self._maybe_global_stagnation_terminate(
                        research_id=research_id,
                        iteration_count=iteration_count,
                    )
                    if stagnation_message:
                        tool_results.append({
                            "type": "text",
                            "text": stagnation_message,
                        })
                    messages.append({"role": "user", "content": tool_results})
                    messages = self._compact_messages(
                        messages,
                        keep_recent=settings.context_compaction_threshold // 2,
                    )
                else:
                    # Model generated text only — no more tool calls → done
                    break

            # ML-62 / hardening Phase 1.1: distinguish stop/timeout/completion.
            # Stop must take precedence over timeout: an operator-driven stop
            # while the timeout window has also elapsed should not be reported
            # as `timed_out`, and a stopped session must never auto-promote.
            if self._should_stop(research_id):
                final_status = "stopped"
            elif _policy_aborted:
                # Phase 5.4: explicit failure — agent kept hitting the
                # command policy; operator review is required.
                final_status = "failed"
            elif _timed_out:
                final_status = "timed_out"
            else:
                final_status = "completed"
            elapsed_total = time.monotonic() - start_time
            # F9: derive a structured terminal_reason so postmortems can tell
            # apart "phase plan finished" from "agent quit at turn 305 with
            # phases still open and $83 of budget left".
            terminal_reason = await self._derive_terminal_reason(
                research_id=research_id,
                final_status=final_status,
                iteration_count=iteration_count,
                total_cost=total_cost,
                config=config,
                timed_out=_timed_out,
                policy_aborted=_policy_aborted,
            )
            await self._store.update_session(
                research_id,
                status=final_status,
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_api_cost_usd=round(total_cost, 4),
                terminal_reason=terminal_reason,
            )
            await broadcaster.broadcast({
                "event": "research_completed",
                "research_id": research_id,
                "status": final_status,
                "iterations": iteration_count,
                "total_cost_usd": round(total_cost, 4),
                "elapsed_s": round(elapsed_total, 1),
            })
            logger.info(
                "Research %s %s: %d iterations, $%.4f, %.0fs",
                research_id, final_status, iteration_count, total_cost, elapsed_total,
            )
            await agent_log.append(
                "system",
                f"{final_status.replace('_', ' ').title()}: {iteration_count} iterations, "
                f"${total_cost:.4f}, {elapsed_total:.0f}s",
            )

            # ML-60: Extract compact insights before rebuilding resume
            await self._extract_session_insights(research_id)

            # Auto-update research resume for this instrument
            await self._update_research_resume(
                config.instrument, config.timeframe,
            )

            # ── ML-53 Fix 2.4: Auto-promote standalone sessions ──────────
            # When a standalone (non-pipeline) session completes with a
            # best iteration that passed training gates and promotion preview
            # readiness, call config_promoter.confirm() to write the winning
            # config and PATCH the composite in mlflow-service. This closes
            # the gap where promotion-ready models were "orphaned" after
            # standalone tuning.
            if (
                final_status == "completed"
                and not getattr(config, "pipeline_id", None)
            ):
                await self._try_auto_promote(research_id, config, agent_log)
            # ── end ML-53 Fix 2.4 ────────────────────────────────────────

        except asyncio.CancelledError:
            await self._store.update_session(
                research_id,
                status="stopped",
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_api_cost_usd=round(total_cost, 4),
            )
            logger.info("Research %s: cancelled", research_id)
            await agent_log.append("system", "Session cancelled")
            # ML-60: Still extract insights from partial sessions
            await self._extract_session_insights(research_id)
            raise

        except Exception as exc:
            logger.exception("Research %s failed: %s", research_id, exc)
            terminal_reason = f"error_unrecoverable:{type(exc).__name__}"
            await self._store.update_session(
                research_id,
                status="failed",
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_api_cost_usd=round(total_cost, 4),
                error_message=str(exc)[:2000],
                terminal_reason=terminal_reason,
            )
            await broadcaster.broadcast({
                "event": "research_failed",
                "research_id": research_id,
                "error": str(exc)[:500],
            })
            await agent_log.append("error", str(exc)[:2000])

        finally:
            self._stop_flags.pop(research_id, None)
            self._pause_flags.pop(research_id, None)
            self._blocker_attempt_counters.pop(research_id, None)

    # ── ML-53 Fix 2.4 helper ─────────────────────────────────────────────
    async def _try_auto_promote(
        self,
        research_id: str,
        config: ResearchConfig,
        agent_log: AgentLogWriter,
    ) -> None:
        """Auto-promote the best iteration if it is promotion-ready.

        Instantiates ConfigPromoter on-demand (not injected into __init__
        to avoid circular dependencies or changing the constructor).
        """
        try:
            session = await self._store.get_session(research_id)
            if not session:
                return

            best_iter = session.get("best_iteration")
            if best_iter is None:
                return

            # Fetch the best iteration record to check gates
            iterations = await self._store.get_iterations(research_id)
            best_record = None
            for it in iterations:
                if it.get("iteration") == best_iter:
                    best_record = it
                    break
            if not best_record:
                return

            if not training_gates_passed_from_iteration(best_record):
                logger.info(
                    "ML-53: Auto-promote skipped for %s - best iteration %d did not pass training gates",
                    research_id, best_iter,
                )
                return

            # Import here to avoid circular dependency at module level
            from src.core.config_promoter import ConfigPromoter

            promoter = ConfigPromoter(self._store)
            phase_state = await self._auto_promotion_phase_state(
                research_id=research_id,
                session=session,
                iterations=iterations,
            )
            incomplete_phases = [
                phase
                for phase in incomplete_phase_ids(phase_state)
                if phase != "promotion_proposal"
            ]
            if incomplete_phases:
                await self._emit_auto_promotion_skipped(
                    research_id=research_id,
                    config=config,
                    agent_log=agent_log,
                    reason="incomplete_research_phases",
                    iteration=best_iter,
                    terminal_reason=session.get("terminal_reason"),
                    incomplete_phases=incomplete_phases,
                    promotion_allowed=False,
                    blockers=[],
                )
                return

            try:
                preview = await promoter.preview(research_id)
            except ValueError as exc:
                await self._emit_auto_promotion_skipped(
                    research_id=research_id,
                    config=config,
                    agent_log=agent_log,
                    reason="promotion_preview_failed",
                    iteration=best_iter,
                    terminal_reason=session.get("terminal_reason"),
                    incomplete_phases=[],
                    promotion_allowed=False,
                    blockers=[str(exc)],
                )
                return

            promotion_allowed = bool(preview.get("promotion_allowed"))
            if not promotion_allowed:
                blockers = self._auto_promotion_preview_blockers(preview)
                await self._emit_auto_promotion_skipped(
                    research_id=research_id,
                    config=config,
                    agent_log=agent_log,
                    reason="promotion_preview_blocked",
                    iteration=best_iter,
                    terminal_reason=session.get("terminal_reason"),
                    incomplete_phases=[],
                    promotion_allowed=False,
                    blockers=blockers,
                )
                return

            result = await promoter.confirm(research_id)
            logger.info(
                "ML-53: Auto-promoted development session %s (iter=%d): %s",
                research_id, best_iter, result,
            )
            await agent_log.append(
                "system",
                f"Auto-promoted best iteration {best_iter} to development config",
            )
            await broadcaster.broadcast({
                "event": "auto_promoted",
                "research_id": research_id,
                "iteration": best_iter,
                "instrument": config.instrument,
                "model_type": config.model_type,
            })

        except Exception as exc:
            logger.warning(
                "ML-53: Auto-promotion failed for %s: %s",
                research_id, exc, exc_info=True,
            )
            await agent_log.append(
                "warning",
                f"Auto-promotion failed: {exc}",
            )
    # ── end ML-53 Fix 2.4 helper ─────────────────────────────────────────

    async def _auto_promotion_phase_state(
        self,
        *,
        research_id: str,
        session: Dict[str, Any],
        iterations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return phase state for auto-promotion without mutating the session."""
        raw_state = session.get("phase_state_json")
        if isinstance(raw_state, str) and raw_state.strip():
            try:
                parsed = json.loads(raw_state)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("phases"), list):
                return parsed

        get_hpo_studies = getattr(self._store, "get_hpo_studies", None)
        hpo_studies = (
            await get_hpo_studies(research_id)
            if callable(get_hpo_studies)
            else []
        )
        list_promotions = getattr(self._store, "list_promotions", None)
        promotions = await list_promotions() if callable(list_promotions) else []
        return build_phase_state(
            session=session,
            iterations=iterations,
            hpo_studies=hpo_studies,
            promotions=[
                row for row in promotions
                if row.get("research_id") == research_id
            ],
        )

    async def _emit_auto_promotion_skipped(
        self,
        *,
        research_id: str,
        config: ResearchConfig,
        agent_log: AgentLogWriter,
        reason: str,
        iteration: Optional[int],
        terminal_reason: Optional[str],
        incomplete_phases: List[str],
        promotion_allowed: bool,
        blockers: List[str],
    ) -> None:
        """Emit structured observability for expected auto-promotion skips."""
        payload = {
            "event": "auto_promotion_skipped",
            "research_id": research_id,
            "iteration": iteration,
            "instrument": config.instrument,
            "timeframe": config.timeframe,
            "model_type": config.model_type,
            "reason": reason,
            "terminal_reason": terminal_reason,
            "incomplete_phases": incomplete_phases,
            "promotion_allowed": promotion_allowed,
            "blockers": blockers,
        }
        logger.info(
            "ML-53: Auto-promotion skipped for %s: reason=%s iteration=%s blockers=%s",
            research_id,
            reason,
            iteration,
            blockers,
        )
        record_audit_event = getattr(self._store, "record_audit_event", None)
        if callable(record_audit_event):
            try:
                await record_audit_event(
                    actor_id="autoresearch-agent",
                    action="promotion.auto_skip",
                    outcome="success",
                    research_id=research_id,
                    request_metadata={
                        key: value for key, value in payload.items()
                        if key != "event"
                    },
                )
            except Exception:
                logger.debug(
                    "Failed to record auto-promotion skip audit event for %s",
                    research_id,
                    exc_info=True,
                )
        try:
            await agent_log.append(
                "system",
                f"Auto-promotion skipped: {reason}",
            )
        except Exception:
            logger.debug(
                "Failed to append auto-promotion skip to agent log for %s",
                research_id,
                exc_info=True,
            )
        try:
            await broadcaster.broadcast(payload)
        except Exception:
            logger.debug(
                "Failed to broadcast auto-promotion skip for %s",
                research_id,
                exc_info=True,
            )

    @staticmethod
    def _auto_promotion_preview_blockers(preview: Dict[str, Any]) -> List[str]:
        blockers: List[str] = []
        for key in ("gate_bundle_evaluation", "consistency_report"):
            container = preview.get(key)
            if not isinstance(container, dict):
                continue
            for blocker in container.get("blockers") or []:
                blocker_s = str(blocker)
                if blocker_s not in blockers:
                    blockers.append(blocker_s)
        return blockers

    async def _infer_decision(
        self,
        research_id: str,
        primary_metric: Optional[float],
        training_gates_passed: bool,
    ) -> str:
        """Determine keep/improve/discard by comparing against session best.

        ML-53: Three-way decision taxonomy:
        - 'keep'    — training gates passed AND metric improved
        - 'improve' — training gates NOT passed but metric improved
        - 'discard' — metric did not improve or is None
        """
        if primary_metric is None:
            return "discard"

        session = await self._store.get_session(research_id)
        best = session.get("best_metric") if session else None

        metric_improved = (best is None) or (
            primary_metric > best + settings.global_stagnation_epsilon
        )

        if training_gates_passed and metric_improved:
            return "keep"
        elif metric_improved:
            return "improve"
        else:
            return "discard"

    async def _record_iteration(
        self,
        research_id: str,
        iteration: int,
        marker: Dict[str, Any],
        cumulative_cost: float,
        *,
        workspace: Optional[str] = None,
        turn: Optional[int] = None,
        command: Optional[str] = None,
    ) -> None:
        """Record an iteration and broadcast the event."""
        marker = dict(marker)
        normalize_artifact_references_in_mapping(marker)
        # AR-1: coerce dict/list config_snapshot to a JSON string so all
        # downstream consumers that declare config_snapshot: Optional[str]
        # receive a valid string.  The LLM may emit a JSON object instead of
        # YAML text when self-reporting a config_snapshot on ITERATION_RESULT.
        _cs = marker.get("config_snapshot")
        if isinstance(_cs, (dict, list)):
            marker["config_snapshot"] = json.dumps(_cs, sort_keys=True)
        training_gates = normalize_training_gate_aliases(
            marker,
            logger=logger,
            context=f"{research_id} iteration {iteration}",
        )
        primary_metric = marker.get("primary_metric")
        decision = marker.get("decision", "unknown")
        description = marker.get("description", "")
        metric_name = marker.get("metric_name", "")
        training_time = marker.get("training_time_s")

        session = await self._store.get_session(research_id)
        active_phase = self._active_phase_from_marker_or_session(marker, session)
        if active_phase and not marker.get("search_phase"):
            marker["search_phase"] = active_phase

        # AR-3: For promotion-family phases the agent does not run a fresh
        # training command and legitimately emits no config_snapshot.  Inherit
        # from the most recent iteration that recorded one so consistency
        # reports don't fire ``missing_config_snapshot`` as a blocker.
        if not marker.get("config_snapshot"):
            if active_phase in _PROMOTION_FAMILY:
                _inherited = (
                    await self._store.get_latest_iteration_with_config_snapshot(
                        research_id
                    )
                )
                if _inherited and _inherited.get("config_snapshot"):
                    marker["config_snapshot"] = _inherited["config_snapshot"]
                    marker["config_snapshot_inherited_from_iteration"] = (
                        _inherited["iteration"]
                    )

        if session:
            identity = marker.get("trial_identity")
            if not identity:
                identity = build_trial_identity(
                    instrument=str(session.get("instrument") or ""),
                    timeframe=str(session.get("timeframe") or ""),
                    model_type=str(session.get("model_type") or marker.get("model_type") or ""),
                    command=command,
                    config_snapshot=marker.get("config_snapshot"),
                    quick_mode=bool(session.get("quick_mode")),
                    marker=marker,
                )
                marker["trial_identity"] = identity
            marker["canonical_config_hash"] = (
                marker.get("canonical_config_hash")
                or identity.get("canonical_config_hash")
                or canonical_config_hash(marker.get("config_snapshot"))
            )
            marker["trial_identity_hash"] = (
                marker.get("trial_identity_hash")
                or trial_identity_hash(identity)
            )
        else:
            marker["canonical_config_hash"] = (
                marker.get("canonical_config_hash")
                or canonical_config_hash(marker.get("config_snapshot"))
            )

        if workspace:
            enrich_marker_from_result_artifact(
                marker=marker,
                workspace=workspace,
                iteration=iteration,
                logger=logger,
            )

        attempt_snapshot = None
        attempt_snapshot_path = None
        attempt_snapshot_hash = None
        if workspace and command:
            attempt_snapshot = build_iteration_attempt_snapshot(
                research_id=research_id,
                iteration=iteration,
                turn=turn if turn is not None else -1,
                command=command,
                config_snapshot=marker.get("config_snapshot"),
                workspace=workspace,
                marker=marker,
            )
            attempt_snapshot_hash = attempt_snapshot.get("snapshot_hash")
            try:
                attempt_snapshot_path = write_iteration_attempt_snapshot(
                    workspace=workspace,
                    snapshot=attempt_snapshot,
                )
            except OSError as exc:
                logger.warning(
                    "Research %s iteration %d: could not write attempt "
                    "snapshot: %s",
                    research_id,
                    iteration,
                    exc,
                )
            marker["attempt_snapshot"] = attempt_snapshot
            marker["attempt_snapshot_path"] = attempt_snapshot_path
            marker["attempt_snapshot_hash"] = attempt_snapshot_hash

        model_type = (session or {}).get("model_type") or marker.get("model_type") or ""
        consistency_report = build_consistency_report(
            research_id=research_id,
            iteration=iteration,
            model_type=model_type,
            config_snapshot=marker.get("config_snapshot"),
            metrics_payload=marker,
            attempt_snapshot=attempt_snapshot,
            search_phase=active_phase,
        )
        marker["consistency_report"] = consistency_report
        marker["consistency_report_passed"] = bool(
            consistency_report.get("passed")
        )

        await self._store.add_iteration(
            research_id=research_id,
            iteration=iteration,
            primary_metric=primary_metric,
            metric_name=metric_name,
            all_gates_passed=training_gates,
            decision=decision,
            description=description,
            config_snapshot=marker.get("config_snapshot"),
            metrics_json=json.dumps(marker),
            training_time_s=training_time,
            mlflow_run_id=marker.get("mlflow_run_id"),
            canonical_config_hash=marker.get("canonical_config_hash"),
            trial_identity_hash=marker.get("trial_identity_hash"),
            trial_identity_json=(
                json.dumps(marker.get("trial_identity"), sort_keys=True)
                if marker.get("trial_identity") is not None
                else marker.get("trial_identity_json")
            ),
            duplicate_of_research_id=marker.get("duplicate_of_research_id"),
            duplicate_of_iteration=marker.get("duplicate_of_iteration"),
            duplicate_reason=marker.get("duplicate_reason"),
            attempt_snapshot_json=(
                json.dumps(attempt_snapshot, sort_keys=True)
                if attempt_snapshot is not None
                else None
            ),
            attempt_snapshot_path=attempt_snapshot_path,
            attempt_snapshot_hash=attempt_snapshot_hash,
            consistency_report_json=consistency_report_json(consistency_report),
            search_phase=active_phase,
            metric_improvement_epsilon=settings.global_stagnation_epsilon,
        )

        # ML-59: If this is an HPO study result, also persist to hpo_studies
        if marker.get("mode") == "hpo_study":
            top_trials = marker.get("top_trials")
            await self._store.add_hpo_study(
                research_id=research_id,
                iteration=iteration,
                n_trials=marker.get("n_trials", 0),
                completed_trials=marker.get("completed_trials", 0),
                best_composite=marker.get("best_composite"),
                training_time_s=training_time,
                top_trials_json=json.dumps(top_trials) if top_trials else None,
                study_id=marker.get("study_id"),
                max_trials=marker.get("n_trials"),
                search_space_json=json.dumps(marker.get("search_space"), sort_keys=True)
                if marker.get("search_space")
                else None,
                budget_json=json.dumps(marker.get("budget"), sort_keys=True)
                if marker.get("budget")
                else None,
                timeout_s=marker.get("timeout_s"),
            )

        await self._refresh_phase_state(research_id)

        event = {
            "event": "iteration_complete",
            "research_id": research_id,
            "iteration": iteration,
            "primary_metric": primary_metric,
            "metric_name": metric_name,
            "training_gates_passed": training_gates,
            "all_gates_passed": training_gates,
            "consistency_report_passed": bool(consistency_report.get("passed")),
            "decision": decision,
            "description": description,
            "training_time_s": training_time,
            "cumulative_api_cost_usd": round(cumulative_cost, 4),
            "search_phase": marker.get("search_phase"),
            "attempt_snapshot_hash": attempt_snapshot_hash,
            "result_artifact_path": marker.get("result_artifact_path"),
            "result_artifact_sha256": marker.get("result_artifact_sha256"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await broadcaster.broadcast(event)
        metric_display = (
            f"{primary_metric:.4f}"
            if isinstance(primary_metric, (float, int))
            else "None"
        )
        logger.info(
            "Research %s iteration %d: metric=%s training_gates=%s decision=%s — %s",
            research_id,
            iteration,
            metric_display,
            training_gates,
            decision,
            description,
        )

    async def _attach_consistency_report(
        self,
        research_id: str,
        iteration: int,
        marker: Dict[str, Any],
    ) -> None:
        """Attach/update consistency report before overwriting an iteration."""
        normalize_artifact_references_in_mapping(marker)
        session = await self._store.get_session(research_id)
        existing = await self._store.get_iteration(research_id, iteration)
        attempt_snapshot = None
        if existing and existing.get("attempt_snapshot_json"):
            try:
                attempt_snapshot = json.loads(existing["attempt_snapshot_json"])
            except (json.JSONDecodeError, TypeError):
                attempt_snapshot = None
        active_phase = self._active_phase_from_marker_or_session(
            marker,
            session,
            existing,
        )
        if active_phase and not marker.get("search_phase"):
            marker["search_phase"] = active_phase

        marker["consistency_report"] = build_consistency_report(
            research_id=research_id,
            iteration=iteration,
            model_type=(session or {}).get("model_type") or marker.get("model_type") or "",
            config_snapshot=marker.get("config_snapshot")
            or (existing or {}).get("config_snapshot"),
            metrics_payload=marker,
            attempt_snapshot=attempt_snapshot,
            search_phase=active_phase,
        )

    @staticmethod
    def _active_phase_from_marker_or_session(
        marker: Dict[str, Any],
        session: Optional[Dict[str, Any]],
        existing: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Resolve the phase used for iteration storage and validation."""
        for candidate in (
            marker.get("search_phase"),
            (existing or {}).get("search_phase"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate

        phase_state_raw = (session or {}).get("phase_state_json")
        if isinstance(phase_state_raw, str) and phase_state_raw.strip():
            try:
                phase_state_obj = json.loads(phase_state_raw)
            except (json.JSONDecodeError, TypeError, AttributeError):
                return None
            if isinstance(phase_state_obj, dict):
                candidate = phase_state_obj.get("current_phase")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
        if isinstance(phase_state_raw, dict):
            candidate = phase_state_raw.get("current_phase")
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None

    @staticmethod
    def _extract_terminate_request(agent_text: str) -> Optional[str]:
        """Return the assistant's TERMINATE_REQUEST line/body, if present."""
        if not agent_text:
            return None
        lines = agent_text.splitlines()
        for index, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.upper().startswith("TERMINATE_REQUEST:"):
                return "\n".join([stripped, *lines[index + 1 :]]).strip()
        return None

    async def _refresh_phase_state(self, research_id: str) -> None:
        session = await self._store.get_session(research_id)
        if not session:
            return
        iterations = await self._store.get_iterations(research_id)
        hpo_studies = await self._store.get_hpo_studies(research_id)
        promotions = await self._store.list_promotions()
        state = build_phase_state(
            session=session,
            iterations=iterations,
            hpo_studies=hpo_studies,
            promotions=[
                row for row in promotions
                if row.get("research_id") == research_id
            ],
        )
        await self._store.update_session(
            research_id,
            current_phase=state.get("current_phase"),
            next_action=state.get("next_action"),
            phase_state_json=phase_state_json(state),
        )

    async def _build_phase_continuation_kick(
        self,
        *,
        research_id: str,
        iteration_count: int,
        total_cost: float,
        config: ResearchConfig,
    ) -> Optional[Dict[str, str]]:
        """F1: decide whether an `end_turn` should be honored.

        Returns ``None`` when termination is acceptable (phase plan complete,
        or no headroom in budget/iterations). Returns a dict with ``reason``
        (for logs) and ``text`` (a user-turn message that re-engages the LLM
        with the outstanding phase work) when the loop should continue.

        AR-4 blocker escalation:
        When ``state["blocked"]`` is True the LLM is stuck on an unresolvable
        consistency gate.  We count how many consecutive kick attempts have
        been made for the same ``block_reason``.  On the 3rd attempt we return
        a ``blocker_unresolved_terminate`` kick that demands a
        ``TERMINATE_REQUEST`` instead of another experiment nudge, preventing
        the loop from spinning 7+ times on the same broken promotion.
        """
        # Refresh phase state so this decision uses the latest evidence.
        await self._refresh_phase_state(research_id)
        session = await self._store.get_session(research_id)
        if not session:
            return None
        phase_state_raw = session.get("phase_state_json")
        if not isinstance(phase_state_raw, str) or not phase_state_raw.strip():
            return None
        try:
            state = json.loads(phase_state_raw)
        except (json.JSONDecodeError, TypeError):
            return None

        blocked = bool(state.get("blocked"))
        incomplete = incomplete_phase_ids(state)

        # When every phase is "completed" AND there is no active blocker, the
        # phase plan is genuinely done — honour end_turn.
        if not incomplete and not blocked:
            return None

        budget_remaining = max(0.0, config.max_budget_usd - total_cost)
        iterations_remaining = max(0, config.max_iterations - iteration_count)
        # If neither budget nor iteration headroom is left, allow exit.
        if budget_remaining <= 0.10 or iterations_remaining <= 0:
            return None

        # AR-4: blocker-attempt counting + escalation.
        if blocked:
            key = str(state.get("block_reason") or "")
            session_counters = self._blocker_attempt_counters.setdefault(
                research_id, {}
            )
            session_counters[key] = session_counters.get(key, 0) + 1
            attempt_count = session_counters[key]
            if attempt_count >= 3:
                logger.warning(
                    "Research %s: blocker '%s' unresolved after %d attempts — "
                    "escalating to forced TERMINATE_REQUEST",
                    research_id, key, attempt_count,
                )
                return {
                    "reason": "blocker_unresolved_terminate",
                    "text": (
                        f"BLOCKER_PERSISTED: '{key}' has not been resolved "
                        f"after {attempt_count} attempts. "
                        "Reply with a single line beginning `TERMINATE_REQUEST:` "
                        "followed by structured justification referencing each "
                        "incomplete phase id. "
                        "Do NOT silently end_turn and do NOT run another experiment."
                    ),
                }
            # First or second attempt: emit a targeted blocker-remediation nudge
            # so the LLM knows it is blocked, not just incomplete.
            current_phase = state.get("current_phase") or (incomplete[0] if incomplete else "")
            next_action = state.get("next_action") or "Resolve the consistency blocker."
            return {
                "reason": "blocker_remediation",
                "text": (
                    "[system] You issued an end_turn but the phase plan is "
                    f"blocked on phase '{current_phase}'. "
                    f"Active blocker: {key}. "
                    f"Incomplete phases remaining: "
                    f"{', '.join(incomplete) if incomplete else current_phase}. "
                    f"Budget remaining: "
                    f"${budget_remaining:.2f} of ${config.max_budget_usd:.2f}. "
                    f"Iterations remaining: "
                    f"{iterations_remaining}/{config.max_iterations}. "
                    f"Required next action: {next_action} "
                    "Resolve the consistency blocker before advancing. If the "
                    "blocker cannot be resolved, reply with a single line "
                    "beginning `TERMINATE_REQUEST:` followed by structured "
                    "justification referencing each incomplete phase id."
                ),
            }

        # No active blocker — standard phase-continuation nudge.
        current_phase = state.get("current_phase") or incomplete[0]
        next_action = state.get("next_action") or "Continue the phase plan."
        text = (
            "[system] You issued an end_turn but the phase plan is incomplete. "
            f"Current phase: {current_phase}. Incomplete phases remaining: "
            f"{', '.join(incomplete)}. Budget remaining: "
            f"${budget_remaining:.2f} of ${config.max_budget_usd:.2f}. "
            f"Iterations remaining: {iterations_remaining}/{config.max_iterations}. "
            f"Required next action: {next_action} "
            "Do NOT terminate. Run the next experiment for the current phase, "
            "or — if your evidence shows the phase is genuinely complete — "
            "emit the metrics evidence key (see SKILL.md \"Phase Advancement\") "
            "so the phase plan can advance. If you believe the entire phase "
            "plan should terminate early, reply with a single line beginning "
            "TERMINATE_REQUEST: followed by a structured justification "
            "referencing each incomplete phase id."
        )
        return {
            "reason": (
                f"phase plan incomplete ({len(incomplete)} phases, current "
                f"{current_phase}); ${budget_remaining:.2f} budget and "
                f"{iterations_remaining} iterations remaining"
            ),
            "text": text,
        }

    async def _maybe_phase_cap_nudge(
        self,
        *,
        research_id: str,
    ) -> Optional[str]:
        """F7: return a system-message text when the current phase's
        ``max_iterations`` cap has been hit without producing the phase's
        evidence key. The orchestrator injects this into the next user turn
        so the LLM moves on instead of grinding inside the same phase.
        """
        session = await self._store.get_session(research_id)
        if not session:
            return None
        phase_state_raw = session.get("phase_state_json")
        if not isinstance(phase_state_raw, str) or not phase_state_raw.strip():
            return None
        try:
            state = json.loads(phase_state_raw)
        except (json.JSONDecodeError, TypeError):
            return None
        current_id = state.get("current_phase")
        if not current_id:
            return None
        iterations = await self._store.get_iterations(research_id)
        in_phase = sum(
            1 for it in iterations
            if (it.get("search_phase") or "") == current_id
        )
        if not phase_cap_exceeded(state, in_phase):
            return None
        next_action = state.get("next_action") or "Advance the phase plan."
        return (
            f"[system] Phase '{current_id}' has reached its iteration cap "
            f"({in_phase} iterations recorded for this phase). Stop tuning "
            f"inside this phase. Emit the phase's evidence key (see SKILL.md "
            f"\"Phase Advancement\") to advance, or proceed to the next phase. "
            f"Next phase guidance: {next_action}"
        )

    async def _maybe_global_stagnation_terminate(
        self,
        *,
        research_id: str,
        iteration_count: int,
    ) -> Optional[str]:
        """AR-7: return a system-message text when global metric stagnation is
        detected.

        The check fires when the session's ``best_iteration`` recorded in the
        DB is more than ``settings.global_stagnation_window`` iterations ago,
        meaning no metric improvement has occurred across that many consecutive
        iterations.  When that condition holds the LLM is instructed to reply
        with a ``TERMINATE_REQUEST:`` line.

        Returns a warning string to be injected into the tool-results block, or
        ``None`` when the session has not stagnated.
        """
        session = await self._store.get_session(research_id)
        if not session:
            return None
        best_iteration = session.get("best_iteration")
        best_metric = session.get("best_metric")
        # No qualifying iteration yet — skip (conservative).
        if best_iteration is None or best_metric is None:
            return None
        gap = iteration_count - best_iteration
        window = settings.global_stagnation_window
        epsilon = settings.global_stagnation_epsilon
        if gap < window:
            return None
        logger.warning(
            "Research %s: global stagnation detected — %d iterations since "
            "best metric %.4f at iteration %d (window=%d, epsilon=%.1e)",
            research_id, gap, best_metric, best_iteration, window, epsilon,
        )
        return (
            f"GLOBAL_STAGNATION: {gap} iterations have produced no metric "
            f"improvement >{epsilon:.0e} above the session best of {best_metric:.4f} "
            f"(achieved at iteration {best_iteration}). "
            "Reply on the next turn with a single line beginning "
            "`TERMINATE_REQUEST:` and structured justification listing each "
            "phase still incomplete and why further training is unlikely to "
            "improve. Do NOT continue running experiments."
        )

    async def _derive_terminal_reason(
        self,
        *,
        research_id: str,
        final_status: str,
        iteration_count: int,
        total_cost: float,
        config: ResearchConfig,
        timed_out: bool,
        policy_aborted: bool,
    ) -> str:
        """F9: produce a single structured token explaining why a session
        ended. Postmortems and the UI can group runs by this value without
        re-deriving heuristics. Values are ASCII, snake_case, optionally
        suffixed with ``:<phase_id>`` when the cause is phase-scoped.

        Vocabulary (success path — called when the loop exits normally):
          policy_aborted                  — policy rejected commands too many times
          wallclock_timeout               — session reached its time limit
          operator_stopped                — user sent stop request
          error_unrecoverable             — used only by _derive_terminal_reason
                                           for legacy completions marked failed
          max_iterations_reached          — hit config.max_iterations
          budget_exhausted                — spent >=99% of max_budget_usd
          phase_plan_completed            — all phases done
          agent_self_terminated_during_phase:<phase_id>  — agent quit early

        Exception path (written directly in the except Exception handler):
          error_unrecoverable:<ExcClass>  — unhandled exception, ExcClass is
                                           the Python exception class name
                                           (e.g. error_unrecoverable:AttributeError)
        """
        if policy_aborted:
            return "policy_aborted"
        if timed_out:
            return "wallclock_timeout"
        if final_status == "stopped":
            return "operator_stopped"
        if final_status == "failed":
            return "error_unrecoverable"
        # final_status == "completed": refine.
        if iteration_count >= config.max_iterations:
            return "max_iterations_reached"
        # Compare against the *budget cap*: a run that ate >=99% of its
        # budget terminated because it ran out of money.
        if total_cost >= 0.99 * config.max_budget_usd:
            return "budget_exhausted"
        # Look at the phase state to decide between "phase plan finished"
        # and "agent self-terminated early".
        session = await self._store.get_session(research_id)
        if session:
            raw = session.get("phase_state_json")
            if isinstance(raw, str) and raw.strip():
                try:
                    state = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    state = None
                if isinstance(state, dict):
                    incomplete = incomplete_phase_ids(state)
                    if not incomplete:
                        return "phase_plan_completed"
                    current = state.get("current_phase") or incomplete[0]
                    return f"agent_self_terminated_during_phase:{current}"
        return "phase_plan_completed"

    @staticmethod
    def _infer_failed_attempt_status(tool_result: str) -> Optional[str]:
        lowered = tool_result.lower()
        if "command timed out" in lowered:
            return "timeout"
        if "trialpruned" in lowered or "trial pruned" in lowered:
            return "pruned"
        if "[exit code:" in lowered:
            return "failed"
        return None

    @staticmethod
    def _effective_tool_timeout(input_data: Dict[str, Any]) -> int:
        timeout = input_data.get("timeout_s", 7200)
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = 7200
        return max(timeout, 900)

    @staticmethod
    def _runtime_command_status(tool_meta: Dict[str, Any]) -> str:
        if tool_meta.get("policy_allowed") is False:
            return "rejected"
        if tool_meta.get("timed_out") is True:
            return "timed_out"
        returncode = tool_meta.get("returncode")
        if isinstance(returncode, int) and returncode != 0:
            return "failed"
        return "completed"

    @staticmethod
    def _attach_runtime_command_metadata(
        marker: Dict[str, Any],
        tool_meta: Dict[str, Any],
    ) -> None:
        runtime_command_id = tool_meta.get("runtime_command_id")
        if runtime_command_id is None:
            return
        marker["runtime_command"] = {
            "id": runtime_command_id,
            "status": AgentOrchestrator._runtime_command_status(tool_meta),
            "returncode": tool_meta.get("returncode"),
            "timed_out": bool(tool_meta.get("timed_out")),
            "policy_operation": tool_meta.get("policy_operation"),
            "normalized_command": tool_meta.get("normalized_command"),
        }
