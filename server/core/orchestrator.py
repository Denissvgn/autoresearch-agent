"""Agent orchestrator — drives Claude via the Anthropic SDK with tool use."""

from __future__ import annotations

import asyncio
import glob as glob_mod
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import anthropic
import httpx

from server.config import settings
from server.core.consistency_validator import (
    build_consistency_report,
    consistency_report_json,
)
from server.core.command_runner import GovernedCommandRunner, redact_sensitive_text
from server.core.experiment_parser import (
    is_hpo_study_output,
    parse_hpo_study_output,
    parse_iteration_marker,
    parse_prepare_output,
)
from server.core.iteration_snapshot import (
    build_iteration_attempt_snapshot,
    write_iteration_attempt_snapshot,
)
from server.core.log_writer import AgentLogWriter
from server.core.research_phase_plan import build_phase_state, phase_state_json
from server.core.results_store import ResultsStore
from server.ws.events import broadcaster

logger = logging.getLogger(__name__)

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
        "description": "Write content to a file in the workspace. Creates parent directories if needed.",
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
        resolved = os.path.realpath(raw)
    else:
        resolved = os.path.realpath(os.path.join(workspace, raw))
    ws_real = os.path.realpath(workspace)
    if not resolved.startswith(ws_real + os.sep) and resolved != ws_real:
        raise ValueError(f"Path {raw!r} resolves outside workspace")
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
    path = _safe_path(input_data["path"], workspace)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Path(path).write_text(input_data["content"], encoding="utf-8")
    return f"Wrote {len(input_data['content'])} bytes to {input_data['path']}"


def _tool_glob(input_data: Dict[str, Any], workspace: str) -> str:
    pattern = input_data["pattern"]
    full_pattern = os.path.join(workspace, pattern)
    matches = sorted(glob_mod.glob(full_pattern, recursive=True))
    # Return paths relative to workspace
    ws = workspace.rstrip("/") + "/"
    relative = [m.replace(ws, "", 1) for m in matches]
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
            api_key=settings.anthropic_auth_token,
            timeout=httpx.Timeout(settings.anthropic_api_timeout_s, connect=30.0),
        )
        self._stop_flags: Dict[str, bool] = {}
        self._pause_flags: Dict[str, bool] = {}

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
    ) -> anthropic.types.Message:
        """Call messages.create() with retry + backoff on transient errors.

        Retries on APITimeoutError, APIConnectionError, InternalServerError,
        and RateLimitError (429) / 502 / 503 / 529 status codes.
        """
        max_retries = settings.max_api_retries
        backoff_base = 30  # seconds

        for attempt in range(max_retries + 1):
            try:
                return await self._client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=8192,
                    system=system_prompt,
                    tools=AGENT_TOOLS,
                    messages=messages,
                )
            except self._TRANSIENT_EXCEPTIONS as exc:
                if attempt >= max_retries:
                    raise
                wait = backoff_base * (2 ** attempt)
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
                # Retry on 429 (rate-limit), 502, 503, 529 (overloaded)
                if exc.status_code in (429, 502, 503, 529) and attempt < max_retries:
                    wait = backoff_base * (2 ** attempt)
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
        """Truncate old tool results to reduce context size.

        Keeps the first message (initial prompt) and the last *keep_recent*
        messages intact. For older messages, tool_result content blocks are
        truncated to a short tail so the model retains awareness of what
        happened without the full output.
        """
        if len(messages) <= keep_recent + 1:
            return messages

        compacted = [messages[0]]  # preserve initial user prompt

        old_section = messages[1:-keep_recent]
        for msg in old_section:
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                # User messages with tool_result blocks
                new_content = []
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        text = block.get("content", "")
                        if isinstance(text, str) and len(text) > 300:
                            block = {
                                **block,
                                "content": f"[compacted — {len(text)} chars]\n…{text[-200:]}",
                            }
                    new_content.append(block)
                compacted.append({**msg, "content": new_content})
            else:
                compacted.append(msg)

        compacted.extend(messages[-keep_recent:])
        return compacted

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
            try:
                content = Path(marker_path).read_text(encoding="utf-8")
                os.remove(marker_path)  # Consume so we don't recount
                return content
            except Exception:
                return None

        # Fallback: synthesize a marker from results.json when the agent
        # ran the training script directly (bypassing prepare.py).
        results_path = os.path.join(base_dir, "results.json")
        if os.path.exists(results_path):
            try:
                results_data = json.loads(
                    Path(results_path).read_text(encoding="utf-8")
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
                    f"all_gates_passed:   {str(passed).lower()}",
                    "---",
                ]
                # Remove results.json so we don't recount on the next
                # bash invocation (it'll be regenerated by the next run).
                os.remove(results_path)
                return "\n".join(lines)
            except Exception:
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
        if not os.path.exists(resume_path):
            return ""
        try:
            with open(resume_path) as f:
                content = f.read()
            if not content.strip():
                return ""
            # Truncate to avoid context window bloat
            if len(content) > 12_000:
                content = content[:6000] + "\n\n*[truncated]*\n\n" + content[-6000:]
            return (
                "\n\n## Research Resume (prior experiments on this instrument)\n\n"
                "Use this context to avoid repeating failed experiments and "
                "build on what worked.\n\n"
                f"{content}"
            )
        except Exception as exc:
            logger.warning("Failed to load research resume: %s", exc)
            return ""

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
                "\n\nStructured HPO is enabled for this session. Keep the sweep "
                f"bounded to at most {min(config.hpo_trials, config.max_iterations)} "
                "training attempts and only vary manifest-approved knobs: "
                "prediction_horizon, deadzone/ATR threshold, roster, calibration, "
                "operating threshold, and adaptive_features. Mark HPO-screening "
                "attempts with search_phase=hpo_screening in any explicit "
                "ITERATION_RESULT payload."
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
        )

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
            gates = "✅" if it.get("all_gates_passed") else "❌"
            decision = it.get("decision", "?")
            desc = (it.get("description") or "")[:150]
            iter_summary_lines.append(
                f"  {num}. metric={metric_s} gates={gates} "
                f"decision={decision} — {desc}"
            )
        iter_summary = "\n".join(iter_summary_lines) if iter_summary_lines else "  (no iterations recorded)"

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
            f"   c. If `all_gates_passed` and composite is best so far, copy to "
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
        except Exception:
            logger.warning(
                "Research %s turn %d: failed to record command rejection audit event",
                config.id,
                turn,
                exc_info=True,
            )

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

                # Check timeout (per-session override or server default)
                elapsed = time.monotonic() - start_time
                _timeout = config.timeout_s if config.timeout_s > 0 else settings.experiment_timeout_s
                if elapsed > _timeout:
                    logger.info("Research %s: timeout after %.0fs", research_id, elapsed)
                    await agent_log.append("system", f"Timeout after {elapsed:.0f}s", turn=turn)
                    _timed_out = True
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
                )

                # Track cost (approximate from usage)
                if response.usage:
                    turn_cost = (
                        response.usage.input_tokens * 3 / 1_000_000
                        + response.usage.output_tokens * 15 / 1_000_000
                    )
                    total_cost += turn_cost

                # Process response content blocks
                assistant_content = response.content
                tool_results = []
                agent_text = ""
                turn_recorded_iteration = False

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

                        # Pre-snapshot: capture train.yaml BEFORE running
                        # prepare.py so we have an immutable config record
                        # for this attempt — preserved even on crash/timeout.
                        _pending_snapshot: Optional[str] = None
                        if (
                            block.name == "bash"
                            and any(
                                token in str(block.input.get("command", ""))
                                for token in (
                                    "prepare.py",
                                    "run_phase1c_",
                                    "run_phase1b_",
                                )
                            )
                        ):
                            try:
                                _pending_snapshot = Path(
                                    os.path.join(workspace, "train.yaml")
                                ).read_text(encoding="utf-8")
                            except OSError:
                                logger.warning(
                                    "Research %s: could not pre-snapshot "
                                    "train.yaml before prepare.py run",
                                    research_id,
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
                        logger.info(
                            "Research %s turn %d: tool=%s result=%s",
                            research_id, turn, block.name,
                            tool_result[:200],
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
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    hpo_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
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
                                # Determine keep/discard by comparing against
                                # current session best — not just gates.
                                decision = await self._infer_decision(
                                    research_id,
                                    metrics.primary_metric,
                                    metrics.all_gates_passed,
                                )
                                marker_from_tool["decision"] = decision
                                # Attach the pre-captured snapshot so the DB
                                # is the sole source of truth for the config.
                                marker_from_tool["config_snapshot"] = _pending_snapshot
                                marker_from_tool["description"] = (
                                    f"Auto-detected from prepare.py output "
                                    f"(turn {turn})"
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    marker_from_tool, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: auto-detected "
                                    "iteration %d from bash output "
                                    "(%s=%.4f, gates=%s)",
                                    research_id, turn, iteration_count,
                                    metrics.metric_name,
                                    metrics.primary_metric,
                                    metrics.all_gates_passed,
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
                                crash_marker["decision"] = "discard"
                                crash_marker["config_snapshot"] = _pending_snapshot
                                crash_marker["description"] = (
                                    f"Failed ({metrics.status}) — "
                                    f"auto-detected from prepare.py output "
                                    f"(turn {turn})"
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    crash_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
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
                                    decision = await self._infer_decision(
                                        research_id,
                                        metrics.primary_metric,
                                        metrics.all_gates_passed,
                                    )
                                    marker_from_file["decision"] = decision
                                    # Attach snapshot for marker-file path too.
                                    marker_from_file["config_snapshot"] = _pending_snapshot
                                    marker_from_file["description"] = (
                                        f"Auto-detected from marker file "
                                        f"(turn {turn})"
                                    )
                                    await self._record_iteration(
                                        research_id, iteration_count,
                                        marker_from_file, total_cost,
                                        workspace=workspace,
                                        turn=turn,
                                        command=_cmd_str,
                                    )
                                    turn_recorded_iteration = True
                                    logger.info(
                                        "Research %s turn %d: auto-detected "
                                        "iteration %d from marker file "
                                        "(%s=%.4f, gates=%s)",
                                        research_id, turn, iteration_count,
                                        metrics.metric_name,
                                        metrics.primary_metric,
                                        metrics.all_gates_passed,
                                    )
                                elif metrics.status in (
                                    "crash", "timeout", "failed", "error",
                                    "pruned",
                                ):
                                    iteration_count += 1
                                    crash_marker = metrics.to_dict()
                                    crash_marker["decision"] = "discard"
                                    crash_marker["config_snapshot"] = _pending_snapshot
                                    crash_marker["description"] = (
                                        f"Failed ({metrics.status}) — "
                                        f"auto-detected from marker file "
                                        f"(turn {turn})"
                                    )
                                    await self._record_iteration(
                                        research_id, iteration_count,
                                        crash_marker, total_cost,
                                        workspace=workspace,
                                        turn=turn,
                                        command=_cmd_str,
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
                                    "all_gates_passed": False,
                                    "decision": "discard",
                                    "description": (
                                        f"Failed ({failed_status}) — "
                                        f"server-detected training command "
                                        f"failure (turn {turn})"
                                    ),
                                    "config_snapshot": _pending_snapshot,
                                }
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    failed_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: recorded failed "
                                    "attempt %d (%s) from command status",
                                    research_id, turn, iteration_count,
                                    failed_status,
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
                    logger.info("Research %s: agent ended conversation", research_id)
                    break

                # Append assistant message and tool results
                messages.append({"role": "assistant", "content": assistant_content})

                if tool_results:
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
                    messages.append({"role": "user", "content": tool_results})
                else:
                    # Model generated text only — no more tool calls → done
                    break

            # ML-62: Distinguish timeout from normal completion
            final_status = "timed_out" if _timed_out else "completed"
            elapsed_total = time.monotonic() - start_time
            await self._store.update_session(
                research_id,
                status=final_status,
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_api_cost_usd=round(total_cost, 4),
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
            # best iteration that passed all gates, automatically call
            # config_promoter.confirm() to write the winning config and
            # PATCH the composite in mlflow-service.  This closes the gap
            # where winning models were "orphaned" after standalone tuning.
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
            await self._store.update_session(
                research_id,
                status="failed",
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_api_cost_usd=round(total_cost, 4),
                error_message=str(exc)[:2000],
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

    # ── ML-53 Fix 2.4 helper ─────────────────────────────────────────────
    async def _try_auto_promote(
        self,
        research_id: str,
        config: ResearchConfig,
        agent_log: AgentLogWriter,
    ) -> None:
        """Auto-promote the best iteration if it passed all gates.

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

            if not best_record.get("all_gates_passed", False):
                logger.info(
                    "ML-53: Auto-promote skipped for %s — best iteration %d did not pass all gates",
                    research_id, best_iter,
                )
                return

            # Import here to avoid circular dependency at module level
            from server.core.config_promoter import ConfigPromoter

            promoter = ConfigPromoter(self._store)
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

    async def _infer_decision(
        self,
        research_id: str,
        primary_metric: Optional[float],
        all_gates_passed: bool,
    ) -> str:
        """Determine keep/improve/discard by comparing against session best.

        ML-53: Three-way decision taxonomy:
        - 'keep'    — gates passed AND metric improved (production-worthy)
        - 'improve' — gates NOT passed but metric improved (research progress)
        - 'discard' — metric did not improve or is None
        """
        if primary_metric is None:
            return "discard"

        session = await self._store.get_session(research_id)
        best = session.get("best_metric") if session else None

        metric_improved = (best is None) or (primary_metric > best)

        if all_gates_passed and metric_improved:
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
        primary_metric = marker.get("primary_metric")
        all_gates = marker.get("all_gates_passed", False)
        decision = marker.get("decision", "unknown")
        description = marker.get("description", "")
        metric_name = marker.get("metric_name", "")
        training_time = marker.get("training_time_s")

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

        session = await self._store.get_session(research_id)
        model_type = (session or {}).get("model_type") or marker.get("model_type") or ""
        consistency_report = build_consistency_report(
            research_id=research_id,
            iteration=iteration,
            model_type=model_type,
            config_snapshot=marker.get("config_snapshot"),
            metrics_payload=marker,
            attempt_snapshot=attempt_snapshot,
        )
        marker["consistency_report"] = consistency_report

        await self._store.add_iteration(
            research_id=research_id,
            iteration=iteration,
            primary_metric=primary_metric,
            metric_name=metric_name,
            all_gates_passed=all_gates,
            decision=decision,
            description=description,
            config_snapshot=marker.get("config_snapshot"),
            metrics_json=json.dumps(marker),
            training_time_s=training_time,
            mlflow_run_id=marker.get("mlflow_run_id"),
            attempt_snapshot_json=(
                json.dumps(attempt_snapshot, sort_keys=True)
                if attempt_snapshot is not None
                else None
            ),
            attempt_snapshot_path=attempt_snapshot_path,
            attempt_snapshot_hash=attempt_snapshot_hash,
            consistency_report_json=consistency_report_json(consistency_report),
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
            "all_gates_passed": all_gates,
            "decision": decision,
            "description": description,
            "training_time_s": training_time,
            "cumulative_api_cost_usd": round(cumulative_cost, 4),
            "search_phase": marker.get("search_phase"),
            "attempt_snapshot_hash": attempt_snapshot_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await broadcaster.broadcast(event)
        metric_display = (
            f"{primary_metric:.4f}"
            if isinstance(primary_metric, (float, int))
            else "None"
        )
        logger.info(
            "Research %s iteration %d: metric=%s gates=%s decision=%s — %s",
            research_id,
            iteration,
            metric_display,
            all_gates,
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
        session = await self._store.get_session(research_id)
        existing = await self._store.get_iteration(research_id, iteration)
        attempt_snapshot = None
        if existing and existing.get("attempt_snapshot_json"):
            try:
                attempt_snapshot = json.loads(existing["attempt_snapshot_json"])
            except (json.JSONDecodeError, TypeError):
                attempt_snapshot = None
        marker["consistency_report"] = build_consistency_report(
            research_id=research_id,
            iteration=iteration,
            model_type=(session or {}).get("model_type") or marker.get("model_type") or "",
            config_snapshot=marker.get("config_snapshot")
            or (existing or {}).get("config_snapshot"),
            metrics_payload=marker,
            attempt_snapshot=attempt_snapshot,
        )

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
