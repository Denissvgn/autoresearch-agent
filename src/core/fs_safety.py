"""Descriptor-relative, no-follow filesystem primitives.

Sensitive writes in this service land in trees whose *contents* are
candidate-influenced (session workspaces, trial staging, server snapshot
directories). Resolve-then-open checks leave a check/use race: a path
component swapped for a symlink between the check and the open redirects the
write outside the authorized root. These helpers close that race on the
qualified Linux target by pinning every path component with a file
descriptor and refusing to follow links at any level.

Link policy (defined here; enforced for writes, imports, and staging):

* **Writes** never follow links. A symlink leaf is denied independently of
  whether its target exists (a dangling link is denied exactly like a link
  to an existing file); symlink parent components are denied; a leaf with
  multiple hard links is denied as an ambiguous alias for a shared file.
  Replacement is atomic (temp file + ``os.replace`` in the pinned parent),
  so a concurrent rename/link swap cannot redirect the write: a rename
  replaces directory entries and never follows links.
* **Imports and staged inputs** (result collection, trial staging) copy
  only regular files with a single hard link, opened ``O_NOFOLLOW``.
  Symlinked, hardlinked, and special entries are skipped or denied with an
  error that names the operation.
* **Plain reads** of candidate files follow links only when the resolved
  target stays inside the authorized roots (enforced by the tool-access
  layer); a leaf with multiple hard links is denied as ambiguous.

The trusted root anchor (a server-derived directory) is opened normally —
its own path may legitimately traverse operator-managed links. Every
component below it is opened ``O_NOFOLLOW | O_DIRECTORY``.
"""

from __future__ import annotations

import os
import secrets
import stat as stat_mod
from typing import Callable, Container, Optional, Sequence

#: Directory components below the trusted root are opened with these flags:
#: descriptor-relative, never following a symlink, never escaping via a
#: non-directory component.
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW

SkipCallback = Callable[[str, str], None]


class FilesystemSafetyError(Exception):
    """A denied filesystem operation.

    ``operation`` names the denied operation (``write`` / ``read`` /
    ``copy`` / ``path``); the message repeats it alongside the path and the
    reason so callers and logs identify exactly what was refused.
    """

    def __init__(self, operation: str, path: str, reason: str) -> None:
        super().__init__(f"{operation} denied for {path!r}: {reason}")
        self.operation = operation
        self.path = path
        self.reason = reason


def _relative_components(relative_path: str) -> list[str]:
    """Split a relative path into components; reject escapes and absolutes."""
    if not relative_path or os.path.isabs(relative_path):
        raise FilesystemSafetyError(
            "path", relative_path, "must be a non-empty relative path"
        )
    parts = [p for p in relative_path.split("/") if p not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise FilesystemSafetyError(
            "path", relative_path, "must not traverse above the root (..)"
        )
    return parts


def _open_root(root: str, operation: str) -> int:
    """Open the trusted root anchor as a directory descriptor."""
    try:
        return os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError as exc:
        raise FilesystemSafetyError(
            operation, root, f"cannot open root directory ({exc.strerror})"
        ) from exc


def _parent_denial_reason(part: str, exc: OSError, *, parent_fd: int) -> str:
    if exc.errno in (getattr(os, "ELOOP", 40), 20):
        # O_DIRECTORY | O_NOFOLLOW surfaces a symlinked parent as ENOTDIR on
        # some kernels and ELOOP on others; classify it precisely.
        try:
            st = os.stat(part, dir_fd=parent_fd, follow_symlinks=False)
        except OSError:
            st = None
        if st is not None and stat_mod.S_ISLNK(st.st_mode):
            return f"parent component {part!r} is a symlink (links are not followed)"
        if exc.errno == 20:
            return f"parent component {part!r} is not a directory"
    if exc.errno == 2:
        return f"parent component {part!r} is missing"
    return f"cannot open parent component {part!r} ({exc.strerror})"


def _open_parent_chain(
    root_fd: int,
    components: Sequence[str],
    *,
    create: bool,
    operation: str,
    display: str,
) -> tuple[int, list[int]]:
    """Walk (and optionally create) parent components without following links.

    Returns the deepest directory descriptor plus every descriptor opened on
    the way (root included) for the caller to close.
    """
    fds = [root_fd]
    current = root_fd
    try:
        for part in components:
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=current)
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise FilesystemSafetyError(
                        operation,
                        display,
                        f"cannot create parent component {part!r} ({exc.strerror})",
                    ) from exc
            try:
                nxt = os.open(part, _DIR_OPEN_FLAGS, dir_fd=current)
            except OSError as exc:
                raise FilesystemSafetyError(
                    operation,
                    display,
                    _parent_denial_reason(part, exc, parent_fd=current),
                ) from exc
            fds.append(nxt)
            current = nxt
    except BaseException:
        _close_chain(fds[1:])
        raise
    return current, fds


def _close_chain(fds: Sequence[int]) -> None:
    for fd in reversed(fds):
        try:
            os.close(fd)
        except OSError:  # pragma: no cover - defensive
            pass


def _unlink_quiet(parent_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=parent_fd)
    except OSError:  # pragma: no cover - defensive cleanup
        pass


def _leaf_denial_reason(leaf: str, st: os.stat_result) -> Optional[str]:
    """Why this leaf cannot be written/imported, or ``None`` when allowed."""
    if stat_mod.S_ISLNK(st.st_mode):
        return (
            f"leaf {leaf!r} is a symlink (links are not followed; a dangling "
            "link is denied exactly like a link to an existing file)"
        )
    if not stat_mod.S_ISREG(st.st_mode):
        return f"leaf {leaf!r} is not a regular file"
    if st.st_nlink > 1:
        return (
            f"leaf {leaf!r} has multiple hard links (ambiguous alias for a "
            "shared file)"
        )
    return None


def _write_at(parent_fd: int, leaf: str, data: bytes, *, display: str) -> None:
    """Replace one leaf in a pinned parent directory, never following links.

    The content is written to a fresh exclusive temp file and ``os.replace``
    swaps directory entries atomically. A path swapped to a symlink between
    the leaf check and the replace is *replaced*, never followed, so no
    bytes can land outside the pinned parent.
    """
    try:
        st = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        st = None
    if st is not None:
        reason = _leaf_denial_reason(leaf, st)
        if reason:
            raise FilesystemSafetyError("write", display, reason)
    tmp = f".{leaf}.tmp-{secrets.token_hex(6)}"
    try:
        fd = os.open(
            tmp,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o644,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise FilesystemSafetyError(
            "write", display, f"cannot create temporary file ({exc.strerror})"
        ) from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    except OSError as exc:
        _unlink_quiet(parent_fd, tmp)
        raise FilesystemSafetyError(
            "write", display, f"cannot replace leaf ({exc.strerror})"
        ) from exc
    except BaseException:
        _unlink_quiet(parent_fd, tmp)
        raise


def safe_write_bytes(root: str, relative_path: str, data: bytes) -> str:
    """Write ``data`` to ``root/relative_path`` with no-follow safety.

    Parents are created as needed; every component below ``root`` is opened
    descriptor-relative with ``O_NOFOLLOW``. Returns the joined target path.
    """
    parts = _relative_components(relative_path)
    dirs, leaf = parts[:-1], parts[-1]
    # The root is a server-derived trusted anchor; create it if missing, as
    # the previous parent-mkdir behavior did.
    os.makedirs(root, exist_ok=True)
    root_fd = _open_root(root, "write")
    try:
        parent_fd, chain = _open_parent_chain(
            root_fd, dirs, create=True, operation="write", display=relative_path
        )
        try:
            _write_at(parent_fd, leaf, data, display=relative_path)
        finally:
            _close_chain(chain[1:])
    finally:
        os.close(root_fd)
    return os.path.join(root, *parts)


def safe_write_text(
    root: str, relative_path: str, text: str, *, encoding: str = "utf-8"
) -> str:
    """Text convenience wrapper over :func:`safe_write_bytes`."""
    return safe_write_bytes(root, relative_path, text.encode(encoding))


def read_regular_file(
    root: str, relative_path: str, *, max_bytes: Optional[int] = None
) -> bytes:
    """Read a file for import: regular, single-link, never through a link.

    Used by result collection and any copy-in of candidate-supplied files.
    A symlink leaf or a multi-link (hardlinked) leaf is denied even when its
    content would resolve inside the roots — an import must not alias a
    shared file.
    """
    parts = _relative_components(relative_path)
    dirs, leaf = parts[:-1], parts[-1]
    root_fd = _open_root(root, "read")
    try:
        parent_fd, chain = _open_parent_chain(
            root_fd, dirs, create=False, operation="read", display=relative_path
        )
        try:
            try:
                fd = os.open(
                    leaf,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                raise
            except OSError as exc:
                if exc.errno == getattr(os, "ELOOP", 40):
                    raise FilesystemSafetyError(
                        "read",
                        relative_path,
                        "leaf is a symlink (imports never follow links)",
                    ) from exc
                raise FilesystemSafetyError(
                    "read", relative_path, f"cannot open leaf ({exc.strerror})"
                ) from exc
            with os.fdopen(fd, "rb") as handle:
                st = os.fstat(handle.fileno())
                reason = _leaf_denial_reason(leaf, st)
                if reason:
                    raise FilesystemSafetyError("read", relative_path, reason)
                if max_bytes is None:
                    return handle.read()
                return handle.read(max_bytes)
        finally:
            _close_chain(chain[1:])
    finally:
        os.close(root_fd)


def _copy_dir_at(
    src_fd: int, dst_fd: int, *, on_skip: Optional[SkipCallback], display: str
) -> None:
    """Recursively copy a directory's regular, single-link files."""
    for name in sorted(os.listdir(src_fd)):
        child_display = f"{display}/{name}"
        try:
            _copy_entry_at(src_fd, dst_fd, name, on_skip=on_skip, display=child_display)
        except FilesystemSafetyError as exc:
            if on_skip is not None:
                on_skip(child_display, exc.reason)
        except OSError as exc:
            if on_skip is not None:
                on_skip(child_display, exc.strerror or str(exc))


def _copy_entry_at(
    src_fd: int, dst_fd: int, name: str, *, on_skip: Optional[SkipCallback], display: str
) -> bool:
    """Copy one entry (and its subtree) without following any link."""
    st = os.stat(name, dir_fd=src_fd, follow_symlinks=False)
    if stat_mod.S_ISLNK(st.st_mode):
        raise FilesystemSafetyError(
            "copy", display, "entry is a symlink (staging never follows links)"
        )
    if stat_mod.S_ISDIR(st.st_mode):
        try:
            os.mkdir(name, 0o755, dir_fd=dst_fd)
        except FileExistsError:
            pass
        child_src = os.open(name, _DIR_OPEN_FLAGS, dir_fd=src_fd)
        try:
            child_dst = os.open(name, _DIR_OPEN_FLAGS, dir_fd=dst_fd)
        except OSError:
            os.close(child_src)
            raise
        try:
            _copy_dir_at(child_src, child_dst, on_skip=on_skip, display=display)
        finally:
            os.close(child_src)
            os.close(child_dst)
        return True
    if stat_mod.S_ISREG(st.st_mode):
        if st.st_nlink > 1:
            raise FilesystemSafetyError(
                "copy",
                display,
                "entry has multiple hard links (ambiguous alias for a shared file)",
            )
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=src_fd)
        with os.fdopen(fd, "rb") as handle:
            data = handle.read()
        _write_at(dst_fd, name, data, display=display)
        return True
    raise FilesystemSafetyError("copy", display, "entry is not a regular file")


def copy_tree_regular_files(
    src_root: str,
    dst_root: str,
    *,
    ignore: Container[str] = (),
    on_skip: Optional[SkipCallback] = None,
) -> int:
    """Copy a tree's regular, single-link files; never follow any link.

    Symlinked, hardlinked, and special entries are skipped with an
    ``on_skip(display, reason)`` call instead of being materialized — a
    planted link must not pull shared content into the copied tree.

    Returns the number of top-level entries copied. Per-entry problems are
    reported through ``on_skip`` and skipped; opening either root raises
    (callers that fail open catch ``OSError``/:class:`FilesystemSafetyError`).
    """
    os.makedirs(dst_root, exist_ok=True)
    src_fd = _open_root(src_root, "copy")
    try:
        dst_fd = _open_root(dst_root, "copy")
        try:
            copied = 0
            for name in sorted(os.listdir(src_fd)):
                if name in ignore:
                    continue
                try:
                    if _copy_entry_at(src_fd, dst_fd, name, on_skip=on_skip, display=name):
                        copied += 1
                except FilesystemSafetyError as exc:
                    if on_skip is not None:
                        on_skip(name, exc.reason)
                except OSError as exc:
                    if on_skip is not None:
                        on_skip(name, exc.strerror or str(exc))
            return copied
        finally:
            os.close(dst_fd)
    finally:
        os.close(src_fd)