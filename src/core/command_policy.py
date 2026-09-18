"""Command policy for the autoresearch agent's compatibility bash tool."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

_ALLOWED_PYTHON = (".venv/bin/python", "./.venv/bin/python")
# Default-deny: no script is allowed by the base policy. Every skill declares
# its own ``allowed_scripts`` in its SKILL.yaml command_policy section; the
# orchestrator merges them in as the policy extension.
_ALLOWED_SCRIPTS: set[str] = set()
_DISALLOWED_EXECUTABLES = {
    "apt",
    "apt-get",
    "bash",
    "curl",
    "docker",
    "git",
    "ln",
    "pip",
    "pip3",
    "scp",
    "sh",
    "ssh",
    "wget",
}
_FORBIDDEN_TOKENS = {"|", "||", "&&", ";", "&"}
_FORBIDDEN_SUBSTRINGS = ("`", "$", ">", "<", "\n", "\r")
_SECRET_MARKERS = (
    ".env",
    "/proc/",
    "/run/secrets",
    "authorization",
    "bearer",
    "credential",
    "id_rsa",
    "password",
    "secret",
    "token",
)
# Default-deny file sets; skills declare copyable/readable files via their
# manifest command_policy section.
_COPY_FILENAMES: set[str] = set()
_CAT_FILENAMES: set[str] = set()


@dataclass(frozen=True)
class CommandDecision:
    allowed: bool
    argv: list[str] = field(default_factory=list)
    normalized_command: str = ""
    operation: str = ""
    reason: str | None = None


def evaluate_command_policy(
    command: str,
    *,
    workspace_root: str,
    session_workspace: str | None = None,
    policy_extension: Mapping[str, Iterable[str]] | None = None,
) -> CommandDecision:
    """Parse and validate a single agent command before execution.

    ARC-011 review C2 (2026-08-15): ``policy_extension`` is the per-skill
    ``CommandPolicyExtension`` (``skill.command_policy_extension()``). It is
    strictly **additive** — entries union with the base allow-lists and can
    never remove or bypass a base restriction. ``allowed_executables`` is
    accepted but currently a no-op: the base dispatch only knows
    python/cp/cat (all already allowed); widening executable dispatch is
    deferred (P2-023).
    """

    ext: Mapping[str, Iterable[str]] = policy_extension or {}
    allowed_scripts = _ALLOWED_SCRIPTS | set(ext.get("allowed_scripts") or ())
    copyable_files = _COPY_FILENAMES | set(ext.get("copyable_files") or ())
    readable_files = _CAT_FILENAMES | set(ext.get("readable_files") or ())
    # ARC-011 review C4: declared-name → packaged-path resolution map
    # (server-built by the skill runtime; see _evaluate_python).
    script_paths_raw = ext.get("script_paths") or {}
    script_paths: Mapping[str, str] | None = (
        {str(k): str(v) for k, v in dict(script_paths_raw).items()}
        if script_paths_raw else None
    )
    # ARC-012 P7-011: the skill's declared config-artifact flag (confinement
    # + copyable check + pre-run snapshot key on it; default --config).
    config_flag = str(ext.get("config_flag") or "--config")

    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        return _reject(f"Unable to parse command: {exc}")
    if not argv:
        return _reject("Empty commands are not allowed")

    argv = _strip_legacy_workspace_cd(argv, workspace_root)
    if not argv:
        return _reject("Empty commands are not allowed")

    shell_reason = _shell_syntax_reason(command, argv)
    if shell_reason:
        return _reject(shell_reason)

    secret = _secret_reference(argv)
    if secret:
        return _reject(f"Command references a blocked secret or environment path: {secret}")

    executable = os.path.basename(argv[0])
    if executable in _DISALLOWED_EXECUTABLES:
        return _reject(f"Executable {executable!r} is not allowed")

    if _is_allowed_python(argv[0], workspace_root):
        return _evaluate_python(
            argv, workspace_root, session_workspace,
            allowed_scripts=allowed_scripts,
            copyable_files=copyable_files,
            script_paths=script_paths,
            config_flag=config_flag,
        )
    if executable == "cp":
        return _evaluate_cp(
            argv, workspace_root, session_workspace,
            copyable_files=copyable_files,
        )
    if executable == "cat":
        return _evaluate_cat(
            argv, workspace_root, session_workspace,
            readable_files=readable_files,
        )

    return _reject(f"Executable {argv[0]!r} is not allowed")


def _reject(reason: str) -> CommandDecision:
    return CommandDecision(allowed=False, reason=reason)


def _allow(argv: list[str], *, operation: str) -> CommandDecision:
    return CommandDecision(
        allowed=True,
        argv=argv,
        normalized_command=shlex.join(argv),
        operation=operation,
    )


def _strip_legacy_workspace_cd(argv: list[str], workspace_root: str) -> list[str]:
    if len(argv) < 4 or argv[0] != "cd" or argv[2] != "&&":
        return argv
    target = argv[1]
    workspace_real = os.path.realpath(workspace_root)
    if target == "/app/workspace" or os.path.realpath(target) == workspace_real:
        return argv[3:]
    return argv


def _shell_syntax_reason(command: str, argv: Iterable[str]) -> str | None:
    if any(substring in command for substring in _FORBIDDEN_SUBSTRINGS):
        return (
            "Shell pipes, redirection, command substitution, environment "
            "expansion, heredocs, and background execution are not allowed"
        )
    if any(token in _FORBIDDEN_TOKENS for token in argv):
        return "Shell command chaining and background execution are not allowed"
    return None


def _secret_reference(argv: Iterable[str]) -> str | None:
    for token in argv:
        lowered = token.lower()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            return token
    return None


def _is_allowed_python(executable: str, workspace_root: str) -> bool:
    if executable in _ALLOWED_PYTHON:
        return True
    expected = os.path.realpath(os.path.join(workspace_root, ".venv", "bin", "python"))
    return os.path.realpath(executable) == expected


def _evaluate_python(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
    *,
    allowed_scripts: set[str] | None = None,
    copyable_files: set[str] | None = None,
    script_paths: Mapping[str, str] | None = None,
    config_flag: str = "--config",
) -> CommandDecision:
    scripts = _ALLOWED_SCRIPTS if allowed_scripts is None else allowed_scripts
    if len(argv) < 2:
        return _reject("Python commands must invoke a script the skill declares allowed")
    script = _workspace_relative(argv[1], workspace_root)
    exec_argv = argv
    # ARC-011 review C4 (P4-016): a skill manifest declares its scripts
    # workspace-relative (e.g. ``eval/run.py``) and the extension unions the
    # declared names into the allow-set — but the files live in the packaged
    # ``skills/<id>/`` tree, not under the runtime workspace root. Whenever a
    # declared entry is not present at its workspace-root-relative location,
    # resolve it via the server-built ``script_paths`` map to the read-only
    # packaged path (deliberately NOT the agent-writable session workspace,
    # which would turn a name-based allow-list into arbitrary code execution)
    # and rewrite argv so the governed subprocess executes the packaged file.
    packaged = (script_paths or {}).get(script)
    script_present = (
        os.path.isfile(argv[1])
        if os.path.isabs(argv[1])
        else os.path.isfile(os.path.join(workspace_root, script))
    )
    if script not in scripts:
        if packaged is None or not os.path.isfile(packaged):
            return _reject(f"Python script {argv[1]!r} is not approved")
        exec_argv = [argv[0], packaged, *argv[2:]]
    elif packaged and not script_present:
        exec_argv = [argv[0], packaged, *argv[2:]]
    config_error = _validate_prepare_config(
        argv, script, workspace_root, session_workspace,
        copyable_files=copyable_files, config_flag=config_flag,
    )
    if config_error:
        return _reject(config_error)
    return _allow(exec_argv, operation=f"python:{script}")


def _validate_prepare_config(
    argv: list[str],
    script: str,
    workspace_root: str,
    session_workspace: str | None,
    *,
    copyable_files: set[str] | None = None,
    config_flag: str = "--config",
) -> str | None:
    """Confine a script's config-artifact argument to the session workspace.

    Applies to any allowed script invocation that passes the skill's declared
    ``config_flag`` (ARC-012 P7-011; the ML vocabulary's ``--config`` by
    default — non-ML skills declare their own, e.g. ``--prompt``) — the
    config an experiment reads or writes must live in the session workspace
    and be an operator-declared copyable file (default-deny when the skill
    declares none).
    """
    copyable = _COPY_FILENAMES if copyable_files is None else copyable_files
    if config_flag not in argv:
        return None
    index = argv.index(config_flag)
    if index == len(argv) - 1:
        return "--config requires a path"
    config_path = _resolve_workspace_file(
        argv[index + 1],
        workspace_root=workspace_root,
        session_workspace=session_workspace,
    )
    if session_workspace and not _is_within(config_path, session_workspace):
        return "--config must point inside the session workspace"
    if os.path.basename(config_path) not in copyable:
        return "--config may only target files the skill declares copyable"
    return None


def _evaluate_cp(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
    *,
    copyable_files: set[str] | None = None,
) -> CommandDecision:
    copyable = _COPY_FILENAMES if copyable_files is None else copyable_files
    if not session_workspace:
        return _reject("cp requires a resolved session workspace")
    args = argv[1:]
    if args and args[0] == "-f":
        args = args[1:]
    if len(args) != 2:
        return _reject("cp may only copy one source file to one destination")
    resolved = [
        _resolve_workspace_file(
            arg,
            workspace_root=workspace_root,
            session_workspace=session_workspace,
        )
        for arg in args
    ]
    for path in resolved:
        if not _is_within(path, session_workspace):
            return _reject("cp may only operate inside the session workspace")
        if os.path.basename(path) not in copyable:
            return _reject("cp may only copy files the skill declares copyable")
    return _allow(["cp", *resolved], operation="cp:workspace-config")


def _evaluate_cat(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
    *,
    readable_files: set[str] | None = None,
) -> CommandDecision:
    readable = _CAT_FILENAMES if readable_files is None else readable_files
    if not session_workspace:
        return _reject("cat requires a resolved session workspace")
    if len(argv) < 2:
        return _reject("cat requires at least one explicit file")
    resolved: list[str] = []
    for arg in argv[1:]:
        if arg.startswith("-"):
            return _reject("cat options are not allowed")
        path = _resolve_workspace_file(
            arg,
            workspace_root=workspace_root,
            session_workspace=session_workspace,
        )
        if not _is_within(path, session_workspace):
            return _reject("cat may only read explicit files in the session workspace")
        if os.path.basename(path) not in readable:
            return _reject("cat may only read approved workspace result files")
        resolved.append(path)
    return _allow(["cat", *resolved], operation="cat:workspace-result")


def _workspace_relative(path: str, workspace_root: str) -> str:
    if os.path.isabs(path):
        resolved = Path(path).resolve(strict=False)
    else:
        resolved = Path(workspace_root, path).resolve(strict=False)
    workspace_real = Path(workspace_root).resolve(strict=False)
    try:
        return str(resolved.relative_to(workspace_real))
    except ValueError:
        return path


def _resolve_workspace_file(
    raw: str,
    *,
    workspace_root: str,
    session_workspace: str | None,
) -> str:
    if os.path.isabs(raw):
        return str(Path(raw).resolve(strict=False))
    if session_workspace and os.sep not in raw:
        return str(Path(session_workspace, raw).resolve(strict=False))
    return str(Path(workspace_root, raw).resolve(strict=False))


def _is_within(path: str, directory: str) -> bool:
    resolved = Path(path).resolve(strict=False)
    root = Path(directory).resolve(strict=False)
    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False
