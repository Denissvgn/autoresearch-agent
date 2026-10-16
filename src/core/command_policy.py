"""Command policy for the autoresearch agent's compatibility bash tool."""

from __future__ import annotations

import hashlib
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from src.core.fs_safety import FilesystemSafetyError, sha256_regular_file
from src.core.tool_access import ToolAccessContext, build_tool_access_context

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
    # Server-computed identity of the pinned evaluator, interpreter,
    # and evaluation data consumed by this launch. Recorded in attempt
    # provenance; None for non-evaluator commands and rejections.
    execution_identity: dict[str, Any] | None = None


def evaluate_command_policy(
    command: str,
    *,
    workspace_root: str,
    session_workspace: str | None = None,
    policy_extension: Mapping[str, Iterable[str]] | None = None,
    access: ToolAccessContext | None = None,
) -> CommandDecision:
    """Parse and validate a single agent command before execution.

    ARC-011 review C2 (2026-08-15): ``policy_extension`` is the per-skill
    ``CommandPolicyExtension`` (``skill.command_policy_extension()``). It is
    strictly **additive** — entries union with the base allow-lists and can
    never remove or bypass a base restriction. ``allowed_executables`` is
    accepted but currently a no-op: the base dispatch only knows
    python/cp/cat (all already allowed); widening executable dispatch is
    deferred (P2-023).

    ``access`` is the shared file-operation authorization context (the same
    one the file tools use). When omitted, one is derived server-side from
    the session workspace and the skill's declarations. Every path a command
    exposes — copy sources/destinations, readable result files, and the
    config-artifact flag value — is authorized through it.
    """

    ext: Mapping[str, Iterable[str]] = policy_extension or {}
    allowed_scripts = _ALLOWED_SCRIPTS | set(ext.get("allowed_scripts") or ())
    copyable_files = _COPY_FILENAMES | set(ext.get("copyable_files") or ())
    readable_files = _CAT_FILENAMES | set(ext.get("readable_files") or ())
    if access is None:
        access = build_tool_access_context(
            session_workspace or workspace_root,
            workspace_root=workspace_root,
            extra_protected_names=ext.get("write_protected_files"),
        )
    else:
        # Defense in depth: skill-declared evaluation data is enforced even
        # when the caller's context predates the declaration.
        access = access.with_extra_protected(ext.get("write_protected_files"))
    # ARC-011 review C4: declared-name → packaged-path resolution map
    # (server-built by the skill runtime; see _evaluate_python).
    script_paths_raw = ext.get("script_paths") or {}
    script_paths: Mapping[str, str] | None = (
        {str(k): str(v) for k, v in dict(script_paths_raw).items()}
        if script_paths_raw else None
    )
    # Declared-name → pinned sha256 of the packaged script. The
    # evaluator runs only from digest-verified package assets.
    script_digests_raw = ext.get("script_digests") or {}
    script_digests: Mapping[str, str] | None = (
        {str(k): str(v) for k, v in dict(script_digests_raw).items()}
        if script_digests_raw else None
    )
    write_protected_files = set(ext.get("write_protected_files") or ())
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
            script_digests=script_digests,
            write_protected_files=write_protected_files,
            config_flag=config_flag,
            access=access,
        )
    if executable == "cp":
        return _evaluate_cp(
            argv, workspace_root, session_workspace,
            copyable_files=copyable_files,
            access=access,
        )
    if executable == "cat":
        return _evaluate_cat(
            argv, workspace_root, session_workspace,
            readable_files=readable_files,
            access=access,
        )

    return _reject(f"Executable {argv[0]!r} is not allowed")


def _reject(reason: str) -> CommandDecision:
    return CommandDecision(allowed=False, reason=reason)


def _allow(
    argv: list[str],
    *,
    operation: str,
    execution_identity: dict[str, Any] | None = None,
) -> CommandDecision:
    return CommandDecision(
        allowed=True,
        argv=argv,
        normalized_command=shlex.join(argv),
        operation=operation,
        execution_identity=execution_identity,
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


def _pinned_interpreter(workspace_root: str) -> str | None:
    """Canonical absolute path of the sanctioned interpreter.

    The venv interpreter beside the workspace root is the only interpreter
    evaluator commands may use; resolving to the real path here means a
    same-named relative executable planted under the session or trial tree
    can never be what the governed subprocess actually launches.
    """

    expected = os.path.realpath(
        os.path.join(workspace_root, ".venv", "bin", "python")
    )
    return expected if os.path.isfile(expected) else None


def _evaluation_data_digests(
    names: Iterable[str],
    session_workspace: str | None,
) -> dict[str, str]:
    """Digest the skill-declared evaluation data a launch will consume.

    Absence is recorded as ``missing`` (files may legitimately be rendered
    later in a session); aliased or unreadable content raises so a tampered
    dataset fails the command instead of feeding the evaluator.
    """

    digests: dict[str, str] = {}
    if not session_workspace:
        return digests
    for name in sorted(set(names)):
        path = os.path.join(session_workspace, name)
        if not os.path.lexists(path):
            digests[name] = "missing"
            continue
        try:
            digests[name] = sha256_regular_file(path)
        except (OSError, FilesystemSafetyError) as exc:
            raise ValueError(
                f"evaluation data {name!r} is not a digestible regular file: {exc}"
            ) from exc
    return digests


def _evaluate_python(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
    *,
    allowed_scripts: set[str] | None = None,
    copyable_files: set[str] | None = None,
    script_paths: Mapping[str, str] | None = None,
    script_digests: Mapping[str, str] | None = None,
    write_protected_files: set[str] | None = None,
    config_flag: str = "--config",
    access: ToolAccessContext | None = None,
) -> CommandDecision:
    scripts = _ALLOWED_SCRIPTS if allowed_scripts is None else allowed_scripts
    if len(argv) < 2:
        return _reject("Python commands must invoke a script the skill declares allowed")
    script = _workspace_relative(argv[1], workspace_root)
    if script not in scripts:
        return _reject(f"Python script {argv[1]!r} is not approved")
    # Approved evaluator entrypoints resolve ONLY to their digest-pinned
    # packaged asset. A same-named workspace file never runs — the old
    # workspace-precedence (F01) let candidate files shadow trusted
    # evaluators, and a declared entry with no packaged asset used to fall
    # back to the workspace copy. Missing trusted assets now fail here,
    # before launch, instead of invoking a workspace fallback.
    packaged = (script_paths or {}).get(script)
    pinned_digest = (script_digests or {}).get(script)
    if packaged is None or pinned_digest is None:
        return _reject(
            f"Python script {script!r} has no pinned package asset; "
            "workspace fallbacks are not allowed"
        )
    try:
        evaluator_digest = sha256_regular_file(packaged)
    except (OSError, FilesystemSafetyError) as exc:
        return _reject(
            f"pinned evaluator asset {script!r} is missing or unreadable: {exc}"
        )
    if evaluator_digest != pinned_digest:
        return _reject(
            f"pinned evaluator asset {script!r} changed since pinning"
        )
    interpreter = _pinned_interpreter(workspace_root)
    if interpreter is None:
        return _reject("pinned interpreter is missing from the workspace venv")
    # The venv interpreter is a symlink to the real binary; hash the resolved
    # file so the recorded environment identity describes what actually runs.
    try:
        interpreter_digest = hashlib.sha256(
            Path(interpreter).read_bytes()
        ).hexdigest()
    except OSError as exc:
        return _reject(f"pinned interpreter is unreadable: {exc}")
    # Rewrite argv server-side: absolute pinned interpreter + absolute
    # packaged script, with an isolated import environment. ``-E`` ignores
    # PYTHON* variables (PYTHONPATH/PYTHONHOME shadowing) and ``-s`` disables
    # user site-packages (a candidate-writable ~/.local cannot shadow
    # evaluator dependencies). The candidate tree is only ever the argument
    # list and the working directory — never the code, interpreter, or
    # import path.
    exec_argv = [interpreter, "-E", "-s", packaged, *argv[2:]]
    config_error = _validate_prepare_config(
        argv, script, workspace_root, session_workspace,
        copyable_files=copyable_files, config_flag=config_flag,
        access=access,
    )
    if config_error:
        return _reject(config_error)
    try:
        evaluation_data = _evaluation_data_digests(
            write_protected_files or (), session_workspace
        )
    except ValueError as exc:
        return _reject(str(exc))
    execution_identity: dict[str, Any] = {
        "schema_version": "autoresearch_execution_identity.v1",
        "evaluator": {
            "name": script,
            "path": packaged,
            "sha256": evaluator_digest,
        },
        "interpreter": {
            "path": interpreter,
            "sha256": interpreter_digest,
        },
        "import_flags": ["-E", "-s"],
        "evaluation_data": evaluation_data,
    }
    return _allow(
        exec_argv,
        operation=f"python:{script}",
        execution_identity=execution_identity,
    )


def _validate_prepare_config(
    argv: list[str],
    script: str,
    workspace_root: str,
    session_workspace: str | None,
    *,
    copyable_files: set[str] | None = None,
    config_flag: str = "--config",
    access: ToolAccessContext | None = None,
) -> str | None:
    """Confine a script's config-artifact argument to the session workspace.

    Applies to any allowed script invocation that passes the skill's declared
    ``config_flag`` (ARC-012 P7-011; the ML vocabulary's ``--config`` by
    default — non-ML skills declare their own, e.g. ``--prompt``) — the
    config an experiment reads or writes must live in the session workspace,
    pass the shared file authorization, and be an operator-declared copyable
    file (default-deny when the skill declares none).
    """
    copyable = _COPY_FILENAMES if copyable_files is None else copyable_files
    if config_flag not in argv:
        return None
    index = argv.index(config_flag)
    if index == len(argv) - 1:
        return "--config requires a path"
    raw = argv[index + 1]
    if session_workspace:
        if access is None:
            access = build_tool_access_context(
                session_workspace, workspace_root=workspace_root
            )
        try:
            config_path = access.authorize_write(raw)
        except ValueError as exc:
            return f"--config must point inside the session workspace: {exc}"
    else:
        config_path = _resolve_workspace_file(
            raw,
            workspace_root=workspace_root,
            session_workspace=session_workspace,
        )
    if os.path.basename(config_path) not in copyable:
        return "--config may only target files the skill declares copyable"
    return None


def _evaluate_cp(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
    *,
    copyable_files: set[str] | None = None,
    access: ToolAccessContext | None = None,
) -> CommandDecision:
    copyable = _COPY_FILENAMES if copyable_files is None else copyable_files
    if not session_workspace:
        return _reject("cp requires a resolved session workspace")
    if access is None:
        access = build_tool_access_context(
            session_workspace,
            workspace_root=workspace_root,
            extra_protected_names=None,
        )
    args = argv[1:]
    if args and args[0] == "-f":
        args = args[1:]
    if len(args) != 2:
        return _reject("cp may only copy one source file to one destination")
    resolved: list[str] = []
    for index, arg in enumerate(args):
        try:
            # Source is a strict import (never through a link, never a
            # multi-link alias); the destination is a candidate write and
            # faces the same protection rules as the write tool.
            path = access.authorize_import(arg) if index == 0 else access.authorize_write(arg)
        except ValueError as exc:
            return _reject(f"cp may only operate inside the session workspace: {exc}")
        if os.path.basename(path) not in copyable:
            return _reject("cp may only copy files the skill declares copyable")
        resolved.append(path)
    return _allow(["cp", *resolved], operation="cp:workspace-config")


def _evaluate_cat(
    argv: list[str],
    workspace_root: str,
    session_workspace: str | None,
    *,
    readable_files: set[str] | None = None,
    access: ToolAccessContext | None = None,
) -> CommandDecision:
    readable = _CAT_FILENAMES if readable_files is None else readable_files
    if not session_workspace:
        return _reject("cat requires a resolved session workspace")
    if access is None:
        access = build_tool_access_context(
            session_workspace, workspace_root=workspace_root
        )
    if len(argv) < 2:
        return _reject("cat requires at least one explicit file")
    resolved: list[str] = []
    for arg in argv[1:]:
        if arg.startswith("-"):
            return _reject("cat options are not allowed")
        try:
            path = access.authorize_read(arg)
        except ValueError as exc:
            return _reject(f"cat may only read explicit files in the session workspace: {exc}")
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
