"""Local content-addressed artifact store: bundles, publication, retention.

Immutable run artifacts — multi-file candidate bundles, results, and parent
snapshots — live in a content-addressed store separate from mutable session
workspaces. Every object is named by its SHA-256 digest and written through
staging plus atomic rename, so a partial write is never visible and an
interrupted run leaves only cleanable staging. Reconstruction verifies every
digest; a tampered object is detected, never silently used.

Imports are confined and bounded: tree imports refuse symlinks and special
files, archive imports refuse traversal names, absolute names, and link
members, and both enforce file/size limits — an imported root can never widen
beyond its declared source. Retention (``gc``) deletes only objects outside a
supplied live-reference set and is idempotent, so an interrupted cleanup
resumes safely and live parent snapshots are never removed.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

BUNDLE_SCHEMA_VERSION = "run_artifacts_bundle.v1"

#: Relative layout of the store under its root.
_OBJECTS_DIR = "objects"
_BUNDLES_DIR = "bundles"
_STAGING_DIR = "staging"


class ArtifactError(ValueError):
    """Raised when an artifact violates the store's safety contract."""


@dataclass(frozen=True)
class ArtifactLimits:
    """Bounds every import respects; a limit violation is an error."""

    max_files: int = 10_000
    max_bytes: int = 512 * 1024 * 1024
    max_file_bytes: int = 64 * 1024 * 1024


DEFAULT_LIMITS = ArtifactLimits()


def default_artifact_root(workspace_root: Optional[str] = None) -> Path:
    base = workspace_root
    if base is None:
        from src.config import settings

        base = settings.workspace_root
    return Path(base) / ".artifacts"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundle_digest(files: Mapping[str, Mapping[str, Any]]) -> str:
    """The bundle identity: SHA-256 over the canonical content map only."""
    canonical = json.dumps(
        dict(files), sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _publish_bytes(dest: Path, data: bytes) -> None:
    """Atomic publication: staging + fsync + rename (never a torn file)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.parent.parent / _STAGING_DIR
    staging.mkdir(parents=True, exist_ok=True)
    tmp = staging / f"{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def _object_path(root: Path, digest: str) -> Path:
    return root / _OBJECTS_DIR / digest[:2] / digest


def _bundle_path(root: Path, digest: str) -> Path:
    return root / _BUNDLES_DIR / f"{digest}.json"


class ArtifactStore:
    """Content-addressed bundles over a local root."""

    def __init__(self, root: Path | str, *, limits: ArtifactLimits = DEFAULT_LIMITS):
        self.root = Path(root)
        self.limits = limits

    # ── Bundle creation ────────────────────────────────────────────────

    def create_bundle(
        self, files: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Publish a bundle from ``{relpath: bytes | Path}`` inputs.

        Returns the bundle descriptor (``digest``, per-file digests/sizes).
        Identical content always yields the identical digest.
        """
        entries: Dict[str, Dict[str, Any]] = {}
        total = 0
        for relpath in sorted(files):
            rel = _safe_relpath(relpath)
            value = files[relpath]
            if isinstance(value, (bytes, bytearray)):
                data = bytes(value)
            else:
                data = Path(value).read_bytes()
            if len(data) > self.limits.max_file_bytes:
                raise ArtifactError(
                    f"file {rel!r} exceeds max_file_bytes"
                )
            total += len(data)
            if total > self.limits.max_bytes:
                raise ArtifactError("bundle exceeds max_bytes")
            if len(entries) >= self.limits.max_files:
                raise ArtifactError("bundle exceeds max_files")
            digest = _sha256_bytes(data)
            entries[rel] = {"sha256": digest, "size": len(data)}
            object_path = _object_path(self.root, digest)
            if not object_path.exists():
                _publish_bytes(object_path, data)
                object_path.chmod(0o444)
        descriptor: Dict[str, Any] = {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "digest": bundle_digest(entries),
            "files": entries,
        }
        _publish_bytes(
            _bundle_path(self.root, descriptor["digest"]),
            (json.dumps(descriptor, indent=1, sort_keys=True) + "\n").encode(
                "utf-8"
            ),
        )
        return descriptor

    # ── Safe imports ───────────────────────────────────────────────────

    def import_tree(
        self, source_root: Path | str, *,
        includes: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Bundle a directory tree, confined to its own root.

        Symlinks and special files are refused outright; relative names are
        normalized so an imported root can never widen beyond its source.
        ``includes`` optionally limits the import to named top-level files.
        """
        root = Path(source_root)
        if not root.is_dir():
            raise ArtifactError(f"import source {str(root)!r} is not a directory")
        selected: Dict[str, Path] = {}
        if includes is not None:
            for name in includes:
                candidate = root / name
                if candidate.is_symlink():
                    raise ArtifactError(
                        f"import refuses symlinked member {name!r}"
                    )
                if not candidate.is_file():
                    raise ArtifactError(
                        f"import member {name!r} is not a regular file"
                    )
                selected[_safe_relpath(name)] = candidate
        else:
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    raise ArtifactError(
                        f"import refuses symlink {str(path.relative_to(root))!r}"
                    )
                if path.is_dir():
                    continue
                if not path.is_file():
                    raise ArtifactError(
                        f"import refuses non-regular file "
                        f"{str(path.relative_to(root))!r}"
                    )
                selected[_safe_relpath(str(path.relative_to(root)))] = path
        return self.create_bundle(selected)

    def import_archive(
        self, archive_path: Path | str,
    ) -> Dict[str, Any]:
        """Bundle a tar/zip archive with traversal and link safety.

        Absolute names, ``..`` traversal, backslash tricks, link members, and
        special members are all refused; per-member and total uncompressed
        sizes and member counts are bounded by the limits. An archive can
        therefore never widen the imported root beyond its own members.
        """
        path = Path(archive_path)
        if not path.is_file():
            raise ArtifactError(f"archive {str(path)!r} not found")
        if tarfile.is_tarfile(path):
            return self._import_tar(path)
        if zipfile.is_zipfile(path):
            return self._import_zip(path)
        raise ArtifactError(f"archive {str(path)!r} is neither tar nor zip")

    def _import_tar(self, path: Path) -> Dict[str, Any]:
        files: Dict[str, bytes] = {}
        total = 0
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                if member.issym() or member.islnk():
                    raise ArtifactError(
                        f"archive refuses link member {member.name!r}"
                    )
                if not member.isfile():
                    raise ArtifactError(
                        f"archive refuses non-file member {member.name!r}"
                    )
                if member.size > self.limits.max_file_bytes:
                    raise ArtifactError(
                        f"archive member {member.name!r} exceeds max_file_bytes"
                    )
                rel = _safe_relpath(member.name)
                total += member.size
                if total > self.limits.max_bytes:
                    raise ArtifactError("archive exceeds max_bytes")
                if len(files) >= self.limits.max_files:
                    raise ArtifactError("archive exceeds max_files")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ArtifactError(
                        f"archive member {member.name!r} cannot be read"
                    )
                files[rel] = extracted.read()
        return self.create_bundle(files)

    def _import_zip(self, path: Path) -> Dict[str, Any]:
        files: Dict[str, bytes] = {}
        total = 0
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise ArtifactError(
                        f"archive refuses symlink member {info.filename!r}"
                    )
                if info.is_dir():
                    continue
                if mode not in (0, 0o100000):
                    raise ArtifactError(
                        f"archive refuses non-file member {info.filename!r}"
                    )
                if info.file_size > self.limits.max_file_bytes:
                    raise ArtifactError(
                        f"archive member {info.filename!r} exceeds "
                        f"max_file_bytes"
                    )
                rel = _safe_relpath(info.filename)
                total += info.file_size
                if total > self.limits.max_bytes:
                    raise ArtifactError("archive exceeds max_bytes")
                if len(files) >= self.limits.max_files:
                    raise ArtifactError("archive exceeds max_files")
                files[rel] = archive.read(info)
        return self.create_bundle(files)

    # ── Read, verify, reconstruct ──────────────────────────────────────

    def load_bundle(self, digest: str) -> Dict[str, Any]:
        path = _bundle_path(self.root, digest)
        if not path.is_file():
            raise ArtifactError(f"bundle {digest!r} is not in the store")
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        if descriptor.get("digest") != digest:
            raise ArtifactError(
                f"bundle descriptor digest mismatch for {digest!r}"
            )
        return descriptor

    def verify_bundle(self, digest: str) -> bool:
        """True when the descriptor and every object match their digests."""
        try:
            descriptor = self.load_bundle(digest)
        except (ArtifactError, ValueError):
            return False
        if bundle_digest(descriptor.get("files") or {}) != digest:
            return False
        for entry in (descriptor.get("files") or {}).values():
            object_path = _object_path(self.root, str(entry.get("sha256")))
            if not object_path.is_file():
                return False
            if _sha256_bytes(object_path.read_bytes()) != entry.get("sha256"):
                return False
        return True

    def reconstruct(
        self, digest: str, dest: Path | str,
    ) -> Dict[str, str]:
        """Materialize a bundle at ``dest`` with per-file digest verification.

        A tampered or missing object raises — reconstruction never emits
        content that does not match its recorded digest.
        """
        descriptor = self.load_bundle(digest)
        dest_root = Path(dest)
        written: Dict[str, str] = {}
        for rel, entry in sorted((descriptor.get("files") or {}).items()):
            object_path = _object_path(self.root, str(entry["sha256"]))
            if not object_path.is_file():
                raise ArtifactError(
                    f"bundle {digest!r} object {entry['sha256']!r} is missing"
                )
            data = object_path.read_bytes()
            if _sha256_bytes(data) != entry["sha256"]:
                raise ArtifactError(
                    f"bundle {digest!r} object {entry['sha256']!r} is corrupt"
                )
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            _publish_bytes(target, data)
            written[rel] = entry["sha256"]
        return written

    # ── Retention and cleanup ──────────────────────────────────────────

    def cleanup_partial(self, *, max_age_s: float = 0.0) -> List[str]:
        """Remove abandoned staging writes; live objects are never touched.

        Safe to interrupt and re-run: staging entries are not visible
        artifacts, so a second pass simply finds less to remove.
        """
        staging = self.root / _STAGING_DIR
        removed: List[str] = []
        if not staging.is_dir():
            return removed
        now = time.time()
        for entry in sorted(staging.iterdir()):
            try:
                if max_age_s > 0 and now - entry.stat().st_mtime < max_age_s:
                    continue
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink()
                removed.append(entry.name)
            except OSError:
                continue
        return removed

    def gc(self, live_digests: Iterable[str]) -> Dict[str, int]:
        """Delete bundles and objects outside the live reference set.

        Retention respects live references absolutely: anything named in
        ``live_digests`` (and every object its bundle needs) is kept. The
        pass is idempotent, so an interrupted cleanup resumes safely.
        """
        live = {str(d) for d in live_digests}
        live_objects: set = set()
        bundles_dir = self.root / _BUNDLES_DIR
        kept_bundles = set()
        if bundles_dir.is_dir():
            for path in sorted(bundles_dir.glob("*.json")):
                digest = path.stem
                if digest not in live:
                    try:
                        path.unlink()
                    except OSError:
                        continue
                else:
                    kept_bundles.add(digest)
        for digest in live:
            try:
                descriptor = self.load_bundle(digest)
                for entry in (descriptor.get("files") or {}).values():
                    live_objects.add(str(entry.get("sha256")))
            except (ArtifactError, ValueError):
                # A live reference whose descriptor is gone keeps whatever
                # objects remain; retention never widens deletion.
                continue
        deleted_objects = 0
        objects_dir = self.root / _OBJECTS_DIR
        if objects_dir.is_dir():
            for path in sorted(objects_dir.rglob("*")):
                if not path.is_file():
                    continue
                if path.name in live_objects:
                    continue
                try:
                    path.chmod(0o644)
                    path.unlink()
                    deleted_objects += 1
                except OSError:
                    continue
        return {
            "kept_bundles": len(kept_bundles),
            "deleted_objects": deleted_objects,
        }


def _safe_relpath(name: str) -> str:
    """Normalize a member name; traversal, absolute names, and tricks refuse."""
    raw = str(name).replace("\\", "/")
    if raw.startswith("/"):
        raise ArtifactError(f"member name {name!r} must be relative")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ArtifactError(f"member name {name!r} traverses (..)")
    return "/".join(parts)


def snapshot_parent_workspace(
    workspace: Path | str,
    store: ArtifactStore,
    *,
    includes: Iterable[str],
) -> Dict[str, Any]:
    """Snapshot a parent run's candidate/result files as a bundle.

    Only the named top-level files are captured (bounded by the store's
    import limits): the parent's candidate and result artifacts, not its
    mutable scratch state. The returned descriptor is the child's retained
    parent reference.
    """
    return store.import_tree(workspace, includes=includes)


__all__ = [
    "ArtifactError",
    "ArtifactLimits",
    "ArtifactStore",
    "BUNDLE_SCHEMA_VERSION",
    "DEFAULT_LIMITS",
    "bundle_digest",
    "default_artifact_root",
    "snapshot_parent_workspace",
]


