"""One resolved execution request shared by policy and subprocesses.

F06: the command policy used to validate a bare config filename against the
session directory while the governed subprocess ran with the shared root as
its working directory and the pre-run snapshot resolved the same argument
with yet another rule set. This module resolves executable, typed argv,
fixed arguments, CWD, inputs, outputs, and timeout ONCE into one immutable
:class:`ExecutionRequest`; authorization, pre-run snapshots, sequential and
parallel execution, and result lookup all consume that request instead of
re-deriving paths from the raw command string.

Also home to the template-shape contract: live and demo command templates
must be plain argv forms. A shell-dependent or ambiguous template is
rejected with a migration diagnostic instead of being silently interpreted
under shell rules the governed runner does not apply.
"""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

#: The request schema version recorded in provenance metadata.
REQUEST_SCHEMA_VERSION = "autoresearch_execution_request.v1"

#: Placeholders a command template may render (the D4 path-template
#: vocabulary). Anything else is ambiguous and must be migrated.
TEMPLATE_PLACEHOLDERS = frozenset(
    {"session_workspace", "skill_id", "subject_id", "variant"}
)

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: Characters that make a template shell-dependent: the governed runner
#: never invokes a shell, so their meaning would silently differ between
#: the template's intent and what actually executes.
_SHELL_DEPENDENT_CHARS = "|;&<>$`()*?~\n\r"

#: Executable bindings the resolver supports. ``python`` binds the
#: skill's explicitly qualified python spellings to the pinned workspace
#: interpreter; ``cp``/``cat`` are the fixed workspace-file bindings.
SUPPORTED_EXECUTABLE_BINDINGS = frozenset({"python", "cp", "cat"})


def template_migration_reason(
    template: str,
    *,
    allowed_placeholders: Iterable[str] = TEMPLATE_PLACEHOLDERS,
) -> Optional[str]:
    """Return why ``template`` cannot resolve safely, else ``None``.

    Shell-dependent templates (pipes, redirection, expansion, chaining,
    globs) and unknown placeholders are ambiguous under an argv-only
    resolver; the diagnostic names the migration instead of guessing.
    """

    text = (template or "").strip()
    if not text:
        return "command template is empty; declare a plain argv command"
    for char in _SHELL_DEPENDENT_CHARS:
        if char in text:
            return (
                f"command template is shell-dependent ({char!r}); migrate to a "
                "plain argv template without pipes, redirection, expansion, "
                "chaining, or globs"
            )
    allowed = set(allowed_placeholders)
    unknown = set(_PLACEHOLDER_RE.findall(text)) - allowed
    if unknown:
        return (
            f"command template uses unsupported placeholders {sorted(unknown)}; "
            f"migrate to the {sorted(allowed)} vocabulary"
        )
    remainder = _PLACEHOLDER_RE.sub("", text)
    if "{" in remainder or "}" in remainder:
        return (
            "command template contains an unparseable placeholder; migrate to "
            f"the {sorted(allowed)} vocabulary"
        )
    return None


@dataclass(frozen=True)
class ExecutionRequest:
    """The immutable, typed result of resolving one execution request."""

    schema_version: str
    operation: str
    #: Absolute pinned interpreter / resolved builtin executable.
    executable: str
    #: Server-fixed interpreter flags (e.g. ``-E -s`` for python).
    exec_prefix: tuple[str, ...]
    #: Absolute digest-pinned packaged script (python runs only).
    script: Optional[str]
    #: Typed arguments after the executable/script; path values absolute.
    arguments: tuple[str, ...]
    #: The exact argv vector the governed subprocess receives.
    argv: tuple[str, ...]
    #: Attempt output root: the session workspace (sequential) or the
    #: trial directory (parallel). Outputs land here.
    cwd: str
    #: Absolute input paths the command reads (config artifact first).
    inputs: tuple[str, ...]
    #: Declared output paths rooted at ``cwd`` (marker/result files).
    outputs: tuple[str, ...]
    #: The resolved config artifact path (the pre-run snapshot source).
    config_path: Optional[str]
    timeout_s: int
    #: Normalized ``flag=value`` tokens: the frozen argument set. Duplicate
    #: flags are rejected at resolution, so an override attempt can never
    #: replace a validated value after the fact.
    fixed_arguments: tuple[str, ...]
    execution_identity: Optional[Mapping[str, Any]] = None

    def to_meta(self) -> dict[str, Any]:
        """JSON-safe provenance summary for tool metadata / markers."""

        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "executable": self.executable,
            "exec_prefix": list(self.exec_prefix),
            "script": self.script,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "config_path": self.config_path,
            "timeout_s": self.timeout_s,
            "fixed_arguments": list(self.fixed_arguments),
        }


def _is_negative_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return token.startswith("-")


def _is_flag(token: str) -> bool:
    return token.startswith("-") and token != "-" and not _is_negative_number(token)


@dataclass(frozen=True)
class _ParsedItem:
    """One ordered argv item: a flag with its normalized value, or a positional."""

    flag: Optional[str]
    value: Optional[str]
    positional: Optional[str]

    def render(self) -> tuple[str, ...]:
        if self.flag is None:
            return (self.positional or "",)
        if self.value is None:
            return (self.flag,)
        return (self.flag, self.value)


def _parse_arguments(tokens: Sequence[str]) -> tuple[list[_ParsedItem], Optional[str]]:
    """Normalize argument spellings into ordered typed items.

    ``--flag=value`` and ``--flag value`` normalize to the same typed pair,
    so neither spelling can slip past validation. Any flag appearing twice
    is rejected: argparse's last-wins behaviour would otherwise let a
    duplicate fixed argument override a value the policy already validated.
    """

    items: list[_ParsedItem] = []
    seen: set[str] = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not _is_flag(token):
            items.append(_ParsedItem(None, None, token))
            index += 1
            continue
        if "=" in token:
            flag, value = token.split("=", 1)
        else:
            flag = token
            value = None
        if flag in seen:
            return [], (
                f"duplicate argument {flag!r}: fixed-argument override "
                "attempts cannot evade validation"
            )
        seen.add(flag)
        if value is None and index + 1 < len(tokens) and not _is_flag(tokens[index + 1]):
            value = tokens[index + 1]
            index += 1
        items.append(_ParsedItem(flag, value, None))
        index += 1
    return items, None


def _resolve_path_value(
    raw: str,
    *,
    workspace_root: str,
    workdir: str,
) -> str:
    """Resolve one path-typed argument exactly once.

    Absolute values are used as given; legacy workspace-root paths
    (``runs/...``) resolve against the shared root; everything else
    resolves against the attempt output root so the subprocess opens the
    exact file the request records.
    """

    if os.path.isabs(raw):
        return str(Path(raw).resolve(strict=False))
    if raw.startswith("runs/") or raw.startswith("./runs/"):
        return str(Path(workspace_root, raw).resolve(strict=False))
    return str(Path(workdir, raw).resolve(strict=False))


#: Shell constructs the governed runner never interprets. Tokens carry
#: chaining semantics; substrings carry expansion/redirection semantics.
FORBIDDEN_TOKENS: tuple[str, ...] = ("|", "||", "&&", ";", "&")
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = ("`", "$", ">", "<", "\n", "\r")
SECRET_MARKERS: tuple[str, ...] = (
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
#: Executables the base policy refuses outright.
DISALLOWED_EXECUTABLES: frozenset[str] = frozenset(
    {
        "apt", "apt-get", "bash", "curl", "docker", "git", "ln",
        "pip", "pip3", "scp", "sh", "ssh", "wget",
    }
)
#: Explicitly qualified python executable spellings (the ``allowed_python``
#: binding vocabulary).
PYTHON_BINDINGS: tuple[str, ...] = (".venv/bin/python", "./.venv/bin/python")
#: Fixed workspace-file bindings.
BUILTIN_BINDINGS: frozenset[str] = frozenset({"cp", "cat"})


def _shell_reason(command: str, argv: Iterable[str]) -> Optional[str]:
    if any(substring in command for substring in FORBIDDEN_SUBSTRINGS):
        return (
            "Shell pipes, redirection, command substitution, environment "
            "expansion, heredocs, and background execution are not allowed"
        )
    if any(token in FORBIDDEN_TOKENS for token in argv):
        return "Shell command chaining and background execution are not allowed"
    return None

def _secret_reason(argv: Iterable[str]) -> Optional[str]:
    for token in argv:
        lowered = token.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            return f"Command references a blocked secret or environment path: {token}"
    return None


def _pinned_interpreter_path(workspace_root: str) -> Optional[str]:
    expected = os.path.realpath(
        os.path.join(workspace_root, ".venv", "bin", "python")
    )
    return expected if os.path.isfile(expected) else None


def _strip_legacy_cd(argv: list[str], workspace_root: str) -> list[str]:
    if len(argv) < 4 or argv[0] != "cd" or argv[2] != "&&":
        return argv
    target = argv[1]
    workspace_real = os.path.realpath(workspace_root)
    if target == "/app/workspace" or os.path.realpath(target) == workspace_real:
        return argv[3:]
    return argv


def resolve_execution_request(
    command: str,
    *,
    workspace_root: str,
    session_workspace: Optional[str],
    workdir: Optional[str] = None,
    policy_extension: Optional[Mapping[str, Any]] = None,
    access: Any = None,
    timeout_s: int = 7200,
) -> tuple[Optional[ExecutionRequest], Optional[str]]:
    """Resolve one command into an immutable :class:`ExecutionRequest`.

    The single resolver both the policy and the subprocess side consume.
    It performs the structural checks (shell shapes, secret references,
    executable bindings, argument spellings, duplicate flags), classifies
    every argument, and resolves each path-typed value exactly once against
    the attempt output root. Authorization decisions (script approval,
    digest pins, copyable/readable membership, confinement) stay with the
    policy layer and operate on this request.

    Returns ``(request, None)`` or ``(None, reason)``.
    """

    ext: Mapping[str, Any] = policy_extension or {}
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        return None, f"Unable to parse command: {exc}"
    if not argv:
        return None, "Empty commands are not allowed"
    argv = _strip_legacy_cd(argv, workspace_root)
    if not argv:
        return None, "Empty commands are not allowed"
    shell_reason = _shell_reason(command, argv)
    if shell_reason:
        return None, shell_reason
    secret_reason = _secret_reason(argv)
    if secret_reason:
        return None, secret_reason

    executable_token = argv[0]
    executable_name = os.path.basename(executable_token)
    if executable_name in DISALLOWED_EXECUTABLES:
        return None, f"Executable {executable_name!r} is not allowed"

    declared_executables = {
        str(name) for name in (ext.get("allowed_executables") or ())
    }
    config_flag = str(ext.get("config_flag") or "--config")
    output_files = tuple(str(name) for name in (ext.get("output_files") or ()))
    attempt_root = workdir or session_workspace or workspace_root

    python_spellings = {
        str(name) for name in (ext.get("allowed_python") or ())
    } | set(PYTHON_BINDINGS)
    if executable_token in python_spellings:
        return _resolve_python(
            argv,
            workspace_root=workspace_root,
            attempt_root=attempt_root,
            ext=ext,
            config_flag=config_flag,
            output_files=output_files,
            timeout_s=timeout_s,
        )

    if executable_name in BUILTIN_BINDINGS:
        return _resolve_builtin(
            argv,
            session_workspace=session_workspace,
            attempt_root=attempt_root,
            timeout_s=timeout_s,
            access=access,
        )

    if (
        executable_name in declared_executables
        or executable_token in declared_executables
    ):
        return None, (
            f"executable binding {executable_name!r} is unsupported: no "
            "qualified runner binding exists; migrate the command to a "
            "supported executable"
        )
    return None, f"Executable {executable_token!r} is not allowed"


def _python_script_name(raw: str, workspace_root: str) -> str:
    """Normalize a script argument to its workspace-relative declared name."""

    base = Path(workspace_root).resolve(strict=False)
    candidate = Path(raw) if os.path.isabs(raw) else Path(workspace_root, raw)
    try:
        return str(candidate.resolve(strict=False).relative_to(base))
    except ValueError:
        return raw


def _resolve_python(
    argv: list[str],
    *,
    workspace_root: str,
    attempt_root: str,
    ext: Mapping[str, Any],
    config_flag: str,
    output_files: Sequence[str],
    timeout_s: int,
) -> tuple[Optional[ExecutionRequest], Optional[str]]:
    if len(argv) < 2:
        return None, (
            "Python commands must invoke a script the skill declares allowed"
        )
    raw_script = argv[1]
    script_name = _python_script_name(raw_script, workspace_root)
    allowed_scripts = {str(s) for s in (ext.get("allowed_scripts") or ())}
    if script_name not in allowed_scripts:
        return None, f"Python script {raw_script!r} is not approved"
    script_paths = {
        str(k): str(v) for k, v in dict(ext.get("script_paths") or {}).items()
    }
    packaged = script_paths.get(script_name)
    if packaged is None:
        return None, (
            f"Python script {raw_script!r} has no pinned package asset; "
            "workspace fallbacks are not allowed"
        )
    interpreter = _pinned_interpreter_path(workspace_root)
    if interpreter is None:
        return None, "pinned interpreter is missing from the workspace venv"

    items, parse_error = _parse_arguments(argv[2:])
    if parse_error:
        return None, parse_error
    declared_names = {
        os.path.basename(str(name))
        for key in ("copyable_files", "readable_files", "write_protected_files")
        for name in (ext.get(key) or ())
    }
    arguments: list[str] = []
    inputs: list[str] = []
    fixed: list[str] = []
    config_path: Optional[str] = None
    for item in items:
        if item.flag is None:
            arguments.append(item.positional or "")
            continue
        flag, value = item.flag, item.value
        if value is None:
            if flag == config_flag:
                return None, f"{config_flag} requires a path"
            fixed.append(flag)
            arguments.extend(item.render())
            continue
        is_path_value = (
            flag == config_flag or os.path.basename(value) in declared_names
        )
        if not is_path_value:
            arguments.extend((flag, value))
            fixed.append(f"{flag}={value}")
            continue
        resolved = _resolve_path_value(
            value, workspace_root=workspace_root, workdir=attempt_root
        )
        if flag == config_flag:
            config_path = resolved
        inputs.append(resolved)
        arguments.extend((flag, resolved))
        fixed.append(f"{flag}={resolved}")

    return ExecutionRequest(
        schema_version=REQUEST_SCHEMA_VERSION,
        operation=f"python:{script_name}",
        executable=interpreter,
        exec_prefix=("-E", "-s"),
        script=packaged,
        arguments=tuple(arguments),
        argv=(interpreter, "-E", "-s", packaged, *arguments),
        cwd=attempt_root,
        inputs=tuple(inputs),
        outputs=tuple(str(Path(attempt_root) / name) for name in output_files),
        config_path=config_path,
        timeout_s=int(timeout_s),
        fixed_arguments=tuple(fixed),
    ), None


def _resolve_builtin(
    argv: list[str],
    *,
    session_workspace: Optional[str],
    attempt_root: str,
    timeout_s: int,
    access: Any,
) -> tuple[Optional[ExecutionRequest], Optional[str]]:
    """Resolve the fixed ``cp``/``cat`` workspace-file bindings."""

    name = os.path.basename(argv[0])
    if not session_workspace or access is None:
        return None, f"{name} requires a resolved session workspace"
    operands = list(argv[1:])
    if name == "cp":
        if operands and operands[0] == "-f":
            operands = operands[1:]
        if len(operands) != 2:
            return None, "cp may only copy one source file to one destination"
    else:
        if not operands:
            return None, "cat requires at least one explicit file"
        if any(arg.startswith("-") for arg in operands):
            return None, "cat options are not allowed"
    resolved: list[str] = []
    inputs: list[str] = []
    outputs: list[str] = []
    for index, arg in enumerate(operands):
        try:
            if name == "cp":
                path = (
                    access.authorize_import(arg)
                    if index == 0
                    else access.authorize_write(arg)
                )
                (inputs if index == 0 else outputs).append(path)
            else:
                path = access.authorize_read(arg)
                inputs.append(path)
        except ValueError as exc:
            if name == "cp":
                return None, f"cp may only operate inside the session workspace: {exc}"
            return None, (
                f"cat may only read explicit files in the session workspace: {exc}"
            )
        resolved.append(path)
    return ExecutionRequest(
        schema_version=REQUEST_SCHEMA_VERSION,
        operation=(
            "cp:workspace-config" if name == "cp" else "cat:workspace-result"
        ),
        executable=name,
        exec_prefix=(),
        script=None,
        arguments=tuple(resolved),
        argv=(name, *resolved),
        cwd=attempt_root,
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        config_path=None,
        timeout_s=int(timeout_s),
        fixed_arguments=(),
    ), None