"""Command policy for the autoresearch agent's compatibility bash tool."""

from __future__ import annotations

import hashlib
import os
import shlex
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from src.core.execution_request import (
    DISALLOWED_EXECUTABLES as _DISALLOWED_EXECUTABLES,
)
from src.core.execution_request import (
    FORBIDDEN_SUBSTRINGS as _FORBIDDEN_SUBSTRINGS,
)
from src.core.execution_request import (
    FORBIDDEN_TOKENS as _FORBIDDEN_TOKENS,
)
from src.core.execution_request import (
    PYTHON_BINDINGS,
    ExecutionRequest,
    resolve_execution_request,
)
from src.core.execution_request import (
    SECRET_MARKERS as _SECRET_MARKERS,
)
from src.core.fs_safety import FilesystemSafetyError, sha256_regular_file
from src.core.tool_access import ToolAccessContext, build_tool_access_context

_ALLOWED_PYTHON = PYTHON_BINDINGS
# Default-deny: no script is allowed by the base policy. Every skill declares
# its own ``allowed_scripts`` in its SKILL.yaml command_policy section; the
# orchestrator merges them in as the policy extension.
_ALLOWED_SCRIPTS: set[str] = set()

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
    # The one resolved execution request this decision authorizes and the
    # governed subprocess executes (F06). None for rejections.
    request: ExecutionRequest | None = None


def evaluate_command_policy(
    command: str,
    *,
    workspace_root: str,
    session_workspace: str | None = None,
    policy_extension: Mapping[str, Iterable[str]] | None = None,
    access: ToolAccessContext | None = None,
    workdir: str | None = None,
    timeout_s: int | None = None,
) -> CommandDecision:
    """Resolve one command into an ExecutionRequest, then authorize it.

    F06: resolution happens exactly once through
    :func:`src.core.execution_request.resolve_execution_request` — the same
    typed request feeds this authorization, the pre-run snapshot, the
    governed subprocess, and result lookup, so policy and process always
    observe the same candidate bytes and paths. ``workdir`` is the attempt
    output root (a trial directory for parallel trials, the session
    workspace otherwise); relative path-typed arguments resolve against it
    and declared outputs land there.

    ``policy_extension`` is the per-skill ``CommandPolicyExtension``
    (``skill.command_policy_extension()``). It is strictly **additive** —
    entries union with the base allow-lists and can never remove or bypass
    a base restriction. ``access`` is the shared file-operation
    authorization context; when omitted, one is derived server-side from
    the session workspace and the skill's declarations.
    """

    ext: Mapping[str, Any] = policy_extension or {}
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

    request, error = resolve_execution_request(
        command,
        workspace_root=workspace_root,
        session_workspace=session_workspace,
        workdir=workdir,
        policy_extension=ext,
        access=access,
        timeout_s=7200 if timeout_s is None else timeout_s,
    )
    if request is None:
        return _reject(error or "Command is not allowed")

    if request.script is not None:
        return _authorize_python_request(
            request,
            ext=ext,
            workspace_root=workspace_root,
            session_workspace=session_workspace,
            copyable_files=copyable_files,
            access=access,
        )
    if request.executable == "cp":
        for operand in request.arguments:
            if os.path.basename(operand) not in copyable_files:
                return _reject("cp may only copy files the skill declares copyable")
        return _allow(
            list(request.argv),
            operation=request.operation,
            request=request,
        )
    if request.executable == "cat":
        for operand in request.arguments:
            if os.path.basename(operand) not in readable_files:
                return _reject(
                    "cat may only read approved workspace result files"
                )
        return _allow(
            list(request.argv),
            operation=request.operation,
            request=request,
        )
    return _reject(f"Executable {request.executable!r} is not allowed")


def _reject(reason: str) -> CommandDecision:
    return CommandDecision(allowed=False, reason=reason)


def _allow(
    argv: list[str],
    *,
    operation: str,
    execution_identity: dict[str, Any] | None = None,
    request: ExecutionRequest | None = None,
) -> CommandDecision:
    return CommandDecision(
        allowed=True,
        argv=argv,
        normalized_command=shlex.join(argv),
        operation=operation,
        execution_identity=execution_identity,
        request=request,
    )


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


def _authorize_python_request(
    request: ExecutionRequest,
    *,
    ext: Mapping[str, Any],
    workspace_root: str,
    session_workspace: str | None,
    copyable_files: set[str],
    access: ToolAccessContext,
) -> CommandDecision:
    """Authorize a resolved python request and pin its execution identity.

    Runs the approval gates on the typed request: the declared script must
    carry a matching pinned digest (missing or changed pinned content fails
    before launch), the config artifact must be a copyable file confined to
    the session workspace, and evaluation data must be digestible.
    """

    script_name = request.operation.removeprefix("python:")
    script_digests = {
        str(k): str(v) for k, v in dict(ext.get("script_digests") or {}).items()
    }
    pinned_digest = script_digests.get(script_name)
    if pinned_digest is None or request.script is None:
        return _reject(
            f"Python script {script_name!r} has no pinned package asset; "
            "workspace fallbacks are not allowed"
        )
    try:
        evaluator_digest = sha256_regular_file(request.script)
    except (OSError, FilesystemSafetyError) as exc:
        return _reject(
            f"pinned evaluator asset {script_name!r} is missing or unreadable: {exc}"
        )
    if evaluator_digest != pinned_digest:
        return _reject(
            f"pinned evaluator asset {script_name!r} changed since pinning"
        )

    if request.config_path is not None:
        if session_workspace:
            try:
                access.authorize_write(request.config_path)
            except ValueError as exc:
                first_error = str(exc)
                # The attempt output root (a trial directory) is
                # server-owned provenance for candidate file tools, but it
                # is the legitimate home of the attempt's own staged config
                # copies — authorize those against the attempt root with
                # the same leaf rules instead of the session tool surface.
                attempt_access = build_tool_access_context(
                    request.cwd,
                    workspace_root=workspace_root,
                    extra_protected_names=ext.get("write_protected_files"),
                )
                try:
                    attempt_access.authorize_write(request.config_path)
                except ValueError:
                    return _reject(
                        "--config must point inside the session workspace: "
                        f"{first_error}"
                    )
        if os.path.basename(request.config_path) not in copyable_files:
            return _reject(
                "--config may only target files the skill declares copyable"
            )

    interpreter = _pinned_interpreter(workspace_root)
    if interpreter is None:
        return _reject("pinned interpreter is missing from the workspace venv")
    try:
        interpreter_digest = hashlib.sha256(
            Path(interpreter).read_bytes()
        ).hexdigest()
    except OSError as exc:
        return _reject(f"pinned interpreter is unreadable: {exc}")
    try:
        evaluation_data = _evaluation_data_digests(
            ext.get("write_protected_files") or (), session_workspace
        )
    except ValueError as exc:
        return _reject(str(exc))

    execution_identity: dict[str, Any] = {
        "schema_version": "autoresearch_execution_identity.v1",
        "evaluator": {
            "name": script_name,
            "path": request.script,
            "sha256": evaluator_digest,
        },
        "interpreter": {
            "path": interpreter,
            "sha256": interpreter_digest,
        },
        "import_flags": list(request.exec_prefix),
        "evaluation_data": evaluation_data,
    }
    authorized = replace(request, execution_identity=execution_identity)
    return _allow(
        list(authorized.argv),
        operation=authorized.operation,
        execution_identity=execution_identity,
        request=authorized,
    )
