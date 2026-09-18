"""Agent tool surface — the 5 sandboxed tools + path safety (P1-1 split).

Extracted verbatim from ``orchestrator.py`` (behavior-identical): the
``ToolExecutionResult`` value type, the ``AGENT_TOOLS`` definitions handed to
the LLM provider, the workspace path-safety helpers, the five tool
implementations (``bash`` / ``read_file`` / ``write_file`` / ``glob`` /
``grep``), the packaged-skill primer loader, and the W11 nonce-env narrowing
helper. ``orchestrator.py`` re-exports all of these for back-compat; new code
should import from here.
"""

from __future__ import annotations

import glob as glob_mod
import logging
import math
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.core.command_runner import (
    CommandProcessRegistry,
    GovernedCommandRunner,
    OutputCallback,
    _build_child_env,
    _collect_process_output,
    _SessionOutputLog,
)
from src.core.llm_provider import ToolDef

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolExecutionResult:
    content: str
    meta: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tool definitions for the Claude agent
# ---------------------------------------------------------------------------

AGENT_TOOLS: list[ToolDef] = [
    ToolDef(
        name="bash",
        description=(
            "Execute one governed command in the workspace. "
            "The working directory is the workspace root and shell syntax "
            "such as pipes, redirection, command substitution, and command "
            "chaining is rejected. Use .venv/bin/python for approved "
            "autotuner Python scripts. "
            "Default timeout is 7200s (2 hours). Set timeout_s for "
            "shorter commands. Minimum enforced: 900s."
        ),
        input_schema={
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
    ),
    ToolDef(
        name="read_file",
        description="Read the contents of a file in the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative or absolute path within the workspace.",
                },
            },
            "required": ["path"],
        },
    ),
    ToolDef(
        name="write_file",
        description=(
            "Write content to a file in the workspace. "
            "Creates parent directories if needed."
        ),
        input_schema={
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
    ),
    ToolDef(
        name="glob",
        description="List files matching a glob pattern within the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. 'configs/**/*.yaml').",
                },
            },
            "required": ["pattern"],
        },
    ),
    ToolDef(
        name="grep",
        description="Search for a regex pattern in files within the workspace.",
        input_schema={
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
    ),
]


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
    # Strip a leading ``cd <dir> && `` wrapper before normalizing: the agent
    # prefixes its bash commands with ``cd /app/workspace && `` (per the workspace
    # CLAUDE.md), but planned-trial ``expected_command``s are stored WITHOUT it.
    # Without stripping, the structured-HPO guard never matches the agent's
    # planned-trial command → every trial is rejected as off-plan → the session
    # aborts after 5 rejections at iteration 0 (observed on the honest E1/E3 run).
    command = re.sub(r"^\s*cd\s+\S+\s*&&\s*", "", command)
    try:
        return " ".join(shlex.split(command))
    except ValueError:
        return command.strip()


def _config_snapshot_path_from_command(
    command: str,
    workspace_root: str,
    session_workspace: str,
    base_dir: str | None = None,
    config_flag: str = "--config",
) -> Optional[str]:
    """Resolve the config artifact a command references.

    The artifact rides the skill's declared ``config_flag`` (ARC-012 P7-011;
    ``--config`` for the ML vocabulary, ``--prompt``/``--target``/... for
    non-ML skills).

    ``base_dir`` (P2 per-workdir state) is the directory the command will
    actually run in — a trial directory when the skill opted into parallel
    trials, ``None``/the session workspace otherwise. Relative config paths
    resolve against it, so the pre-run snapshot reads the exact copy the
    subprocess will see. The containment check stays anchored to the session
    workspace (a trial dir lives inside it), so the override can never point
    a snapshot outside the session tree.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if config_flag not in argv:
        return None
    index = argv.index(config_flag) + 1
    if index >= len(argv):
        return None
    raw_path = argv[index]
    if os.path.isabs(raw_path):
        resolved = os.path.realpath(raw_path)
    elif raw_path.startswith("runs/") or raw_path.startswith("./runs/"):
        resolved = os.path.realpath(os.path.join(workspace_root, raw_path))
    else:
        resolved = os.path.realpath(
            os.path.join(base_dir if base_dir is not None else session_workspace, raw_path)
        )
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
    output_callback: OutputCallback | None = None,
    *,
    command_deadline_mono: float | None = None,
    proc_registry: CommandProcessRegistry | None = None,
    research_id: str | None = None,
    extra_env: Mapping[str, str] | None = None,
    policy_extension: Mapping[str, Any] | None = None,
    cwd: str | None = None,
) -> ToolExecutionResult:
    """Execute a tool call and return the text result.

    ``cwd`` (P2 per-workdir state) overrides the bash subprocess working
    directory (trial-directory execution); other tools ignore it.
    """
    try:
        if name == "bash":
            return _tool_bash(
                input_data, workspace, session_workspace, output_callback,
                command_deadline_mono=command_deadline_mono,
                proc_registry=proc_registry,
                research_id=research_id,
                extra_env=extra_env,
                policy_extension=policy_extension,
                cwd=cwd,
            )
        elif name == "read_file":
            return ToolExecutionResult(_tool_read_file(input_data, workspace))
        elif name == "write_file":
            return ToolExecutionResult(_tool_write_file(input_data, workspace))
        elif name == "glob":
            return ToolExecutionResult(_tool_glob(input_data, workspace))
        elif name == "grep":
            return ToolExecutionResult(_tool_grep(input_data, workspace, session_workspace))
        else:
            return ToolExecutionResult(f"Unknown tool: {name}")
    except Exception as exc:
        return ToolExecutionResult(f"Tool error ({name}): {exc}")


def _tool_bash(
    input_data: Dict[str, Any],
    workspace: str,
    session_workspace: str | None = None,
    output_callback: OutputCallback | None = None,
    *,
    command_deadline_mono: float | None = None,
    proc_registry: CommandProcessRegistry | None = None,
    research_id: str | None = None,
    extra_env: Mapping[str, str] | None = None,
    policy_extension: Mapping[str, Any] | None = None,
    cwd: str | None = None,
) -> ToolExecutionResult:
    command = input_data["command"]
    timeout = input_data.get("timeout_s", 7200)
    # Enforce minimum timeout — agents routinely ignore tool-description hints
    if timeout < 900:
        timeout = 900
    # ARC-011 P0-006: cap the per-command timeout at the session's remaining
    # soft budget so the command_runner's own psutil kill path fires at the
    # session boundary. The cap wins even below the 900s floor — a session
    # about to time out must not start a 15-minute command. ``ceil`` (not
    # truncation) so the command overruns by <1s into the grace buffer and the
    # soft check then trips cleanly, avoiding a cap≈0 thrash of subprocesses.
    if command_deadline_mono is not None:
        timeout = min(timeout, max(0, math.ceil(command_deadline_mono - time.monotonic())))
    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session_workspace,
        policy_extension=policy_extension,
    )
    result = runner.run(
        command, timeout_s=timeout, output_callback=output_callback,
        proc_registry=proc_registry, research_id=research_id,
        extra_env=extra_env, cwd=cwd,
    )
    # Preserve the existing orchestrator/output_digest integration and its
    # settings.agent_output_digest_max_chars (0 disables digesting). The runner
    # bounds capture independently; digesting here would alter server parsing.
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
            "command_log_path": result.log_path,
            "command_log_truncated": result.log_truncated,
        },
    )


def _tool_read_file(input_data: Dict[str, Any], workspace: str) -> str:
    """Read at most 100,001 characters, never materializing a whole large file.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as workspace:
    ...     path = Path(workspace) / "large.txt"
    ...     _ = path.write_text("x" * 100_001, encoding="utf-8")
    ...     result = _tool_read_file({"path": "large.txt"}, workspace)
    ...     assert result.startswith("x" * 100_000)
    ...     assert "truncated" in result and len(result) < 100_100
    ...     _ = path.write_text("é" * 100_000, encoding="utf-8")
    ...     assert _tool_read_file({"path": "large.txt"}, workspace) == "é" * 100_000
    """
    path = _safe_path(input_data["path"], workspace)
    try:
        with open(path, encoding="utf-8", errors="replace") as source:
            content = source.read(100_001)
        if len(content) > 100_000:
            content = content[:100_000] + (
                "\n...(truncated: showing first 100000 characters; "
                "use grep to narrow)...\n"
            )
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


def _tool_grep(
    input_data: Dict[str, Any], workspace: str, session_workspace: str | None = None,
) -> str:
    """Incremental grep capture, excluding its own active log.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as workspace:
    ...     _ = Path(workspace, "keep.py").write_text("match" * 30000)
    ...     _ = Path(workspace, "skip.txt").write_text("match")
    ...     result = _tool_grep({"pattern": "match", "include": "*.py"}, workspace)
    ...     assert "keep.py" in result and "skip.txt" not in result
    ...     assert "truncated" in result and len(result) <= 60020
    ...     logs = list(Path(workspace, "logs").glob("*.log"))
    ...     assert len(logs) == 1 and logs[0].stat().st_size > 120000
    """
    pattern = input_data["pattern"]
    search_path = input_data.get("path", ".")
    include = input_data.get("include", "")
    safe_dir = _safe_path(search_path, workspace)

    cmd = ["grep", "-rn", "--color=never"]
    if include:
        cmd += [f"--include={include}"]
    cmd += [pattern, safe_dir]

    # Remains synchronous under the orchestrator's asyncio.to_thread wrapper.
    # Drain both pipes in fixed-size chunks, including arbitrarily long lines.
    # Keep the governed child environment and the existing no-match sentinel.
    log = None
    try:
        log = _SessionOutputLog(session_workspace or workspace)
        # Never search our own growing capture file (recursive grep would feed
        # matches back into its output). Other existing logs remain searchable.
        # Keep include first: GNU grep's first include/exclude rule determines
        # whether unmatched files are searched by default.
        cmd.insert(len(cmd) - 2, f"--exclude={log.name}")
    except OSError:
        pass  # collector reports unavailable logging without dropping output
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=_build_child_env(), start_new_session=True,
        )
    except BaseException:
        if log is not None:
            log.close()
        raise
    output, _, timed_out, _, _ = _collect_process_output(
        proc, timeout_s=30, workspace=session_workspace or workspace, log=log,
    )
    if timed_out:
        return "Grep timed out after 30s"
    return output or "(no matches)"


def _load_packaged_skill_md(skill_id: str, primer: str = "SKILL.md") -> str:
    """Read the packaged ``skills/<skill_id>/<primer>`` domain primer (C2-2).

    Manifest-driven sessions use the skill package's own primer instead of
    the legacy workspace ``.github/skills/<model_type>/SKILL.md``.
    ``primer`` is the manifest-declared filename (``llm.system_prompt``;
    ``SKILL.md`` by default). A missing packaged primer degrades to an empty
    string (logged) rather than failing the session — the manifest body
    already carries the directive content.
    """
    from src.core.skill_registry import DEFAULT_SKILLS_ROOT

    path = DEFAULT_SKILLS_ROOT / skill_id / primer
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Packaged skill primer missing for %s: %s", skill_id, path)
        return ""


def _nonce_env_for_command(
    nonce_env: Optional[Mapping[str, str]],
    command: object,
    policy_extension: Optional[Mapping[str, Any]],
) -> Optional[Mapping[str, str]]:
    """Narrow the W11 nonce env delivery to the skill's declared scripts (C3).

    The nonce must reach the sanctioned eval subprocess, but handing it to
    every governed command re-creates the leak review C3 closes (any
    sanctioned script that surfaces its environment exposes the secret to
    the agent relaying its output). Only commands invoking one of the
    skill's manifest-declared scripts receive the env. A false negative is
    loud, not silent: without the env the eval cannot echo the nonce and its
    markers are rejected with explicit guidance.
    """
    if nonce_env is None:
        return None
    declared = (policy_extension or {}).get("allowed_scripts") or ()
    cmd = str(command or "")
    if any(str(script) in cmd for script in declared):
        return nonce_env
    return None
