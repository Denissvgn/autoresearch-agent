"""Command policy for the autoresearch agent's compatibility bash tool."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

_ALLOWED_PYTHON = (".venv/bin/python", "./.venv/bin/python")
_ALLOWED_SCRIPTS = {
    "scripts/autotuner/setup.py",
    "scripts/autotuner/direction/prepare.py",
    "scripts/autotuner/volatility/prepare.py",
    "scripts/autotuner/rl/prepare.py",
    "scripts/autotuner/enrich_rl_dataset.py",
    "scripts/autotuner/resume.py",
}
_PREPARE_SCRIPTS = {
    "scripts/autotuner/direction/prepare.py",
    "scripts/autotuner/volatility/prepare.py",
    "scripts/autotuner/rl/prepare.py",
}
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
_COPY_FILENAMES = {"train.yaml", "best_train.yaml"}
_CAT_FILENAMES = {
    "best_train.yaml",
    "hpo_results.json",
    "last_metrics.txt",
    "results.json",
    "train.yaml",
}


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
) -> CommandDecision:
    """Parse and validate a single agent command before execution."""

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
        return _evaluate_python(argv, workspace_root, session_workspace)
    if executable == "cp":
        return _evaluate_cp(argv, workspace_root, session_workspace)
    if executable == "cat":
        return _evaluate_cat(argv, workspace_root, session_workspace)

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
) -> CommandDecision:
    if len(argv) < 2:
        return _reject("Python commands must invoke an approved autotuner script")
    script = _workspace_relative(argv[1], workspace_root)
    if script not in _ALLOWED_SCRIPTS:
        return _reject(f"Python script {argv[1]!r} is not approved")
    config_error = _validate_prepare_config(argv, script, workspace_root, session_workspace)
    if config_error:
        return _reject(config_error)
    return _allow(argv, operation=f"python:{script}")


def _validate_prepare_config(
    argv: list[str],
    script: str,
    workspace_root: str,
    session_workspace: str | None,
) -> str | None:
    if script not in _PREPARE_SCRIPTS:
        return None
    if "--config" not in argv:
        return "prepare.py commands must specify --config"
    index = argv.index("--config")
    if index == len(argv) - 1:
        return "prepare.py --config requires a path"
    config_path = _resolve_workspace_file(
        argv[index + 1],
        workspace_root=workspace_root,
        session_workspace=session_workspace,
    )
    if session_workspace and not _is_within(config_path, session_workspace):
        return "prepare.py --config must point inside the session workspace"
    if os.path.basename(config_path) not in _COPY_FILENAMES:
        return "prepare.py --config may only target train.yaml or best_train.yaml"
    return None


def _evaluate_cp(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
) -> CommandDecision:
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
        if os.path.basename(path) not in _COPY_FILENAMES:
            return _reject("cp may only copy train.yaml and best_train.yaml")
    return _allow(["cp", *resolved], operation="cp:workspace-config")


def _evaluate_cat(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
) -> CommandDecision:
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
        if os.path.basename(path) not in _CAT_FILENAMES:
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
