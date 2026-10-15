"""Shared file-tool authorization: one context for every file operation.

Every path a tool call exposes — read, write, glob, grep, copy, and any
path-bearing tool argument — resolves through the same authorization
context. The context is derived server-side from run/attempt ownership
(the run's session workspace) plus skill declarations; tool-supplied paths,
candidate files, and workspace instructions never grant additional access.

Authorization model:

* ``readable_roots`` / ``writable_roots`` are explicit roots. A resolved
  path outside every root of the requested kind is rejected — sibling
  sessions, evaluator packages, interpreter environments, control-plane
  storage, and shared evaluation assets are excluded by construction
  because they live outside the owning session's workspace.
* ``protected_paths`` / ``protected_names`` carve server-owned state out of
  the writable roots: private evidence, command logs, trial staging, the
  bootstrap and session manifests, and skill-declared evaluation data are
  never candidate-writable even though they live inside the workspace.
* Relative tool paths resolve against the session workspace; the legacy
  shared-root path style is still accepted when it lands inside the
  authorized roots. Absolute paths are accepted only when they land inside
  an authorized root.

The shared workspace root is carried for command-policy plumbing (the
governed interpreter and legacy ``cd`` normalization live there); it is
never an authorization root for file access.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

#: Server-owned directories inside a session workspace that candidate writes
#: must never touch: private evidence snapshots, captured command output, and
#: the server-managed trial staging tree.
PROTECTED_SESSION_DIRS = ("server_snapshots", "command_logs", ".trials")

#: Server-owned single files inside a session workspace, plus filename
#: patterns (the session manifest is written under a per-run name).
PROTECTED_SESSION_FILES = ("session_bootstrap.v1.json", "research_manifest.json")
PROTECTED_SESSION_FILE_PATTERNS = ("research_manifest_*.json",)


def _resolved(path: str | os.PathLike[str]) -> str:
    return str(Path(path).resolve(strict=False))


def path_within_roots(
    path: str, roots: Sequence[str], *, follow_leaf: bool = True
) -> bool:
    """Whether ``path`` resolves inside one of ``roots``.

    ``follow_leaf=False`` keeps the final path component un-followed (write
    targets: a symlink leaf must stay visible to the leaf check instead of
    being resolved into its target before containment).
    """
    if follow_leaf:
        resolved = Path(path).resolve(strict=False)
    else:
        candidate = Path(path)
        resolved = candidate.parent.resolve(strict=False) / candidate.name
    for root in roots:
        try:
            resolved.relative_to(Path(root).resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def matches_protected_name(relative: str, patterns: Sequence[str]) -> bool:
    """Whether a workspace-relative path matches a protected name/pattern.

    Both the full relative path and the basename are matched, so a skill can
    declare a bare filename or a scoped path.
    """
    name = os.path.basename(relative)
    return any(
        fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(relative, pattern)
        for pattern in patterns
    )


@dataclass(frozen=True)
class ToolAccessContext:
    """Server-derived file authorization for one run/attempt's tool calls.

    Built once per run from the owning session workspace and the skill's
    declarations; tool arguments never construct or extend it.
    """

    #: The run-owned session workspace; relative tool paths anchor here.
    session_workspace: str
    #: Shared workspace root — command-policy plumbing only. Never an
    #: authorization root for file access.
    workspace_root: str
    readable_roots: tuple[str, ...] = field(default_factory=tuple)
    writable_roots: tuple[str, ...] = field(default_factory=tuple)
    protected_paths: tuple[str, ...] = field(default_factory=tuple)
    protected_names: tuple[str, ...] = field(default_factory=tuple)

    def resolve_candidates(self, raw: str, *, write: bool = False) -> list[str]:
        """Resolve a tool-supplied path to its authorized candidates.

        Relative paths may be expressed against the session workspace (the
        primary anchor) or against the shared workspace root (the legacy
        tool contract); both candidates are considered and every candidate
        must still land inside the authorized roots to be usable. Absolute
        paths yield themselves. Reads resolve fully (a link is followed and
        then containment-checked); writes resolve the parent directory and
        keep the leaf un-followed so a symlink leaf is detectable.
        """
        if os.path.isabs(raw):
            raw_paths = [Path(raw)]
        else:
            raw_paths = [
                Path(anchor) / raw
                for anchor in (self.workspace_root, self.session_workspace)
            ]
        candidates: list[str] = []
        for path in raw_paths:
            if write:
                candidate = str(path.parent.resolve(strict=False) / path.name)
            else:
                candidate = str(path.resolve(strict=False))
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    def resolve(self, raw: str) -> str:
        """Resolve ``raw`` to the authorized target path.

        Among the candidates that land inside the requested roots, an
        existing path wins (the canonical location beats an accidental
        shadow); otherwise the first candidate in anchor order is used.
        """
        return self._select(raw, write=False)[1]

    def _select(self, raw: str, *, write: bool) -> tuple[Optional[str], str]:
        """Return ``(denial_reason, resolved)`` for one tool-supplied path."""
        roots = self.writable_roots if write else self.readable_roots
        in_root = [
            candidate
            for candidate in self.resolve_candidates(raw, write=write)
            if path_within_roots(candidate, roots, follow_leaf=not write)
        ]
        if not in_root:
            kind = "writable candidate roots" if write else "readable roots"
            return f"Path {raw!r} resolves outside the {kind}", ""
        existing = [candidate for candidate in in_root if os.path.lexists(candidate)]
        chosen = existing[0] if existing else in_root[0]
        if write:
            if self.is_write_protected(chosen):
                return (
                    f"Path {raw!r} is protected server-owned or evaluation "
                    "state and cannot be written by candidate tools",
                    "",
                )
            if os.path.islink(chosen):
                return f"Path {raw!r} is a symlink and cannot be overwritten", ""
        return None, chosen

    def authorize_read(self, raw: str) -> str:
        """Resolve ``raw`` and require it to land inside a readable root."""
        reason, resolved = self._select(raw, write=False)
        if reason:
            raise ValueError(reason)
        return resolved

    def authorize_write(self, raw: str) -> str:
        """Resolve ``raw`` and require an authorized, unprotected target.

        Rejects paths outside the writable candidate roots, server-owned
        protected paths/names, and existing symlink leaves (a write must not
        follow a link out of the workspace).
        """
        reason, resolved = self._select(raw, write=True)
        if reason:
            raise ValueError(reason)
        return resolved

    def is_write_protected(self, resolved: str) -> bool:
        """Whether a resolved path is server-owned/evaluation state."""
        path = Path(_resolved(resolved))
        for protected in self.protected_paths:
            protected_path = Path(_resolved(protected))
            if path == protected_path:
                return True
            try:
                path.relative_to(protected_path)
                return True
            except ValueError:
                continue
        for root in self.writable_roots:
            try:
                relative = str(path.relative_to(_resolved(root)))
            except ValueError:
                continue
            if matches_protected_name(relative, self.protected_names):
                return True
        return False

    def filter_readable(self, candidates: Iterable[str]) -> list[str]:
        """Keep only candidates that resolve inside a readable root."""
        kept: list[str] = []
        for candidate in candidates:
            try:
                kept.append(self.authorize_read(candidate))
            except ValueError:
                continue
        return kept

    def with_extra_protected(self, names: Optional[Iterable[str]]) -> "ToolAccessContext":
        """Return a copy with additional protected names merged in.

        Used where a skill's declared evaluation data must be enforced even
        if the caller's context predates the declaration.
        """
        extra = tuple(names or ())
        if not extra:
            return self
        merged = tuple(dict.fromkeys(self.protected_names + extra))
        return ToolAccessContext(
            session_workspace=self.session_workspace,
            workspace_root=self.workspace_root,
            readable_roots=self.readable_roots,
            writable_roots=self.writable_roots,
            protected_paths=self.protected_paths,
            protected_names=merged,
        )


def build_tool_access_context(
    session_workspace: str,
    *,
    workspace_root: Optional[str] = None,
    extra_protected_names: Optional[Iterable[str]] = None,
) -> ToolAccessContext:
    """Derive the file authorization for one run/attempt, server-side.

    Roots come from run ownership: the run's session workspace is both the
    readable and the writable candidate root. Server-owned state inside it
    (private evidence, command logs, trial staging, bootstrap and session
    manifests) is carved out of the writable set, and the skill's declared
    evaluation-data names (``command_policy.write_protected_files``) are
    added on top. Everything else the shared workspace holds — sibling
    sessions, evaluator packages, interpreter environments, control-plane
    storage — is outside the roots and therefore unreachable.
    """
    root = _resolved(session_workspace)
    protected_paths = tuple(_resolved(os.path.join(root, name)) for name in PROTECTED_SESSION_DIRS)
    protected_names: tuple[str, ...] = (
        tuple(PROTECTED_SESSION_FILES)
        + tuple(PROTECTED_SESSION_FILE_PATTERNS)
        + tuple(extra_protected_names or ())
    )
    return ToolAccessContext(
        session_workspace=root,
        workspace_root=_resolved(workspace_root) if workspace_root else root,
        readable_roots=(root,),
        writable_roots=(root,),
        protected_paths=protected_paths,
        protected_names=protected_names,
    )
