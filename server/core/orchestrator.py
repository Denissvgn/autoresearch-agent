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

from server.config import settings
from server.core.experiment_parser import (
    is_hpo_study_output,
    parse_hpo_study_output,
    parse_iteration_marker,
    parse_prepare_output,
)
from server.core.log_writer import AgentLogWriter
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


# ---------------------------------------------------------------------------
# Tool definitions for the Claude agent
# ---------------------------------------------------------------------------

AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "bash",
        "description": (
            "Execute a shell command in the workspace. "
            "The working directory is the workspace root. "
            "Use /app/workspace/.venv/bin/python for Python scripts. "
            "Default timeout is 60 minutes (3600s). Do NOT set timeout_s "
            "below 1800 for training commands."
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
                    "description": "Timeout in seconds (default: 3600). Set higher for full RL training (up to 5400).",
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
) -> str:
    """Execute a tool call and return the text result."""
    try:
        if name == "bash":
            return _tool_bash(input_data, workspace)
        elif name == "read_file":
            return _tool_read_file(input_data, workspace)
        elif name == "write_file":
            return _tool_write_file(input_data, workspace)
        elif name == "glob":
            return _tool_glob(input_data, workspace)
        elif name == "grep":
            return _tool_grep(input_data, workspace)
        else:
            return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Tool error ({name}): {exc}"


def _tool_bash(input_data: Dict[str, Any], workspace: str) -> str:
    command = input_data["command"]
    timeout = input_data.get("timeout_s", 5400)
    # Enforce minimum timeout — agents routinely ignore tool-description hints
    if timeout < 900:
        timeout = 900
    # Auto-escalate timeout for training commands (prepare.py, run_phase)
    if timeout < 5400 and ("prepare.py" in command or "run_phase" in command):
        timeout = 5400
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n--- stderr ---\n" + result.stderr) if output else result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        # Truncate very long output
        if len(output) > 60_000:
            output = output[:30_000] + "\n...(truncated)...\n" + output[-30_000:]
        return output or "(no output)"
    except subprocess.TimeoutExpired as exc:
        # Preserve any output captured before the timeout
        partial = ""
        if exc.stdout:
            text = exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", errors="replace")
            partial += text
        if exc.stderr:
            text = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", errors="replace")
            partial += ("\n--- stderr ---\n" + text) if partial else text
        if partial and len(partial) > 60_000:
            partial = partial[:30_000] + "\n...(truncated)...\n" + partial[-30_000:]
        timeout_msg = f"\n[Command timed out after {timeout}s]"
        return (partial + timeout_msg) if partial else f"Command timed out after {timeout}s"


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
        )
        self._stop_flags: Dict[str, bool] = {}
        self._pause_flags: Dict[str, bool] = {}

    def request_stop(self, research_id: str) -> None:
        self._stop_flags[research_id] = True

    def request_pause(self, research_id: str) -> None:
        self._pause_flags[research_id] = True

    def request_resume(self, research_id: str) -> None:
        self._pause_flags.pop(research_id, None)

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
                    # matching prepare.py: 1.0×sharpe + 0.5×return - 2.0×drawdown
                    agg = results_data.get("aggregate", {})
                    mean_sharpe = agg.get("mean_oos_sharpe") or 0.0
                    mean_return = agg.get("mean_oos_return") or 0.0
                    mean_dd = agg.get("mean_oos_drawdown") or 0.0
                    primary = (
                        1.0 * mean_sharpe + 0.5 * mean_return - 2.0 * mean_dd
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

        # RL needs an enrichment step before the first training run
        if config.model_type == "rl":
            enrich_step = (
                f"2. Enrich RL dataset (REQUIRED before any training):\n"
                f"```bash\n"
                f"cd /app/workspace && .venv/bin/python "
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
                f"cd /app/workspace && .venv/bin/python "
                f"scripts/autotuner/{config.model_type}/prepare.py "
                f"--config {workspace}/train.yaml{quick_flag} 2>&1\n"
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
                f"cd /app/workspace && .venv/bin/python "
                f"scripts/autotuner/{config.model_type}/prepare.py "
                f"--config {workspace}/train.yaml{quick_flag} 2>&1\n"
                f"```\n\n"
                f"4. After baseline, iterate: edit train.yaml → run prepare.py → "
                f"check metrics → keep or revert."
            )

        return (
            f"Tune {config.model_type} model for {config.instrument} "
            f"{config.timeframe} (tag: {config.tag}). "
            f"Max {config.max_iterations} iterations.\n\n"
            f"Execute these commands IN ORDER — do not explore first:\n\n"
            f"1. Setup:\n"
            f"```bash\n"
            f"cd /app/workspace && .venv/bin/python scripts/autotuner/setup.py "
            f"--instrument {instrument_underscore} "
            f"--timeframe {config.timeframe} "
            f"--models {config.model_type}{setup_extra_args}\n"
            f"```\n\n"
            f"{enrich_step}\n\n"
            f"Run autonomously. Do NOT check service health or explore the "
            f"filesystem — everything is pre-verified and ready."
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
            f"1. Setup workspace:\n"
            f"```bash\n"
            f"cd /app/workspace && .venv/bin/python scripts/autotuner/setup.py "
            f"--instrument {instrument_underscore} "
            f"--timeframe {config.timeframe} "
            f"--models rl{setup_extra_args}\n"
            f"```\n\n"
            f"2. Enrich RL dataset (REQUIRED):\n"
            f"```bash\n"
            f"cd /app/workspace && .venv/bin/python "
            f"scripts/autotuner/enrich_rl_dataset.py "
            f"--instrument {instrument_underscore} "
            f"--timeframe {config.timeframe}\n"
            f"```\n"
            f"Verify direction_proba mean is NOT ~0.5.\n\n"
            f"3. Run Optuna HPO study ({hpo_trials} trials, Bayesian sampling "
            f"with early stopping):\n"
            f"```bash\n"
            f"cd /app/workspace && .venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/train.yaml "
            f"--hpo --hpo-trials {hpo_trials} "
            f"--hpo-timesteps {hpo_timesteps}{quick_flag} 2>&1\n"
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
            f"cd /app/workspace && .venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/train.yaml{quick_flag} 2>&1\n"
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
            f"7. Run best config with different seeds to confirm stability:\n"
            f"```bash\n"
            f"cd /app/workspace && .venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/best_train.yaml --seed 43{quick_flag} 2>&1\n"
            f"cd /app/workspace && .venv/bin/python "
            f"scripts/autotuner/rl/prepare.py "
            f"--config {workspace}/best_train.yaml --seed 44{quick_flag} 2>&1\n"
            f"```\n"
            f"If composite_rl_score is consistent across seeds (not wildly "
            f"different), the config is robust.\n\n"
            f"Run autonomously. Do NOT check service health."
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
        )
        await agent_log.append(
            "system",
            f"Research session started: {config.instrument} {config.timeframe} "
            f"{config.model_type} tag={config.tag} max_iter={config.max_iterations}",
        )

        try:
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
                    break

                # Call Claude
                response = await self._client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=8192,
                    system=system_prompt,
                    tools=AGENT_TOOLS,
                    messages=messages,
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
                        logger.info(
                            "Research %s turn %d: tool=%s input=%s",
                            research_id, turn, block.name,
                            str(block.input)[:200],
                        )
                        await agent_log.append(
                            "tool_call", block.name, turn=turn,
                            meta={"tool_id": block.id, "input": block.input},
                        )

                        # Pre-snapshot: capture train.yaml BEFORE running
                        # prepare.py so we have an immutable config record
                        # for this attempt — preserved even on crash/timeout.
                        _pending_snapshot: Optional[str] = None
                        if (
                            block.name == "bash"
                            and "prepare.py" in str(block.input.get("command", ""))
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

                        tool_result = await asyncio.to_thread(
                            _execute_tool,
                            block.name,
                            block.input,
                            settings.workspace_root,
                        )
                        logger.info(
                            "Research %s turn %d: tool=%s result=%s",
                            research_id, turn, block.name,
                            tool_result[:200],
                        )
                        await agent_log.append(
                            "tool_result", tool_result[:5000], turn=turn,
                            meta={"tool_id": block.id, "tool_name": block.name},
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result,
                        })

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
                                    "crash", "timeout", "failed", "error"
                                )
                                and metrics.primary_metric is not None
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
                        _cmd_str = str(block.input.get("command", ""))
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
                            await self._store.update_iteration(
                                research_id, iteration_count, marker,
                            )
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
                    messages.append({"role": "user", "content": tool_results})
                else:
                    # Model generated text only — no more tool calls → done
                    break

            # Update session as completed
            elapsed_total = time.monotonic() - start_time
            await self._store.update_session(
                research_id,
                status="completed",
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_api_cost_usd=round(total_cost, 4),
            )
            await broadcaster.broadcast({
                "event": "research_completed",
                "research_id": research_id,
                "iterations": iteration_count,
                "total_cost_usd": round(total_cost, 4),
                "elapsed_s": round(elapsed_total, 1),
            })
            logger.info(
                "Research %s completed: %d iterations, $%.4f, %.0fs",
                research_id, iteration_count, total_cost, elapsed_total,
            )
            await agent_log.append(
                "system",
                f"Completed: {iteration_count} iterations, "
                f"${total_cost:.4f}, {elapsed_total:.0f}s",
            )

            # Auto-update research resume for this instrument
            await self._update_research_resume(
                config.instrument, config.timeframe,
            )

        except asyncio.CancelledError:
            await self._store.update_session(
                research_id,
                status="stopped",
                completed_at=datetime.now(timezone.utc).isoformat(),
                total_api_cost_usd=round(total_cost, 4),
            )
            logger.info("Research %s: cancelled", research_id)
            await agent_log.append("system", "Session cancelled")
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

    async def _infer_decision(
        self,
        research_id: str,
        primary_metric: Optional[float],
        all_gates_passed: bool,
    ) -> str:
        """Determine keep/discard by comparing against session best.

        - 'keep' only if gates passed AND metric is strictly better than
          the current best (or this is the first iteration with no best yet).
        - 'discard' otherwise.
        """
        if not all_gates_passed or primary_metric is None:
            return "discard"

        session = await self._store.get_session(research_id)
        if not session:
            return "keep"  # shouldn't happen, but safe default

        best = session.get("best_metric")
        if best is None:
            return "keep"  # first iteration — always keep

        if primary_metric > best:
            return "keep"

        return "discard"

    async def _record_iteration(
        self,
        research_id: str,
        iteration: int,
        marker: Dict[str, Any],
        cumulative_cost: float,
    ) -> None:
        """Record an iteration and broadcast the event."""
        primary_metric = marker.get("primary_metric")
        all_gates = marker.get("all_gates_passed", False)
        decision = marker.get("decision", "unknown")
        description = marker.get("description", "")
        metric_name = marker.get("metric_name", "")
        training_time = marker.get("training_time_s")

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
            )

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await broadcaster.broadcast(event)
        logger.info(
            "Research %s iteration %d: metric=%.4f gates=%s decision=%s — %s",
            research_id,
            iteration,
            primary_metric or 0.0,
            all_gates,
            decision,
            description,
        )
