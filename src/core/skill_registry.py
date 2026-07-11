"""Skill registry — startup discovery + hot reload (ARC-011 P2-003).

The registry discovers ``skills/<id>/SKILL.yaml`` manifests under a
configurable root, caches the loaded ``ResearchSkillManifest`` objects keyed by
``id``, and reloads them on mtime change (hot reload). Manifests are loaded
lazily (the YAML is parsed on first access).

The discovery root defaults to the service's ``skills/`` directory — **not**
``Settings.skills_dir`` (which points at ``{workspace_root}/.github/skills``,
the workspace-side prompt-primer location). The two are distinct:

* ``services/autoresearch-agent/skills/<id>/SKILL.yaml`` — the authoritative
  ``research_skill.v1`` manifest this registry loads (P2-005/009/013).
* ``{workspace}/.github/skills/<name>/SKILL.md`` — the legacy per-``model_type``
  prompt primer ``orchestrator._load_skill`` reads (removed in P2-021).

Design decisions (P1-007 house style):

* **Lazy + cached.** A manifest is parsed once on first ``get()``; subsequent
  calls return the cached object until the file's mtime changes. This keeps
  startup cheap and lets a skill author edit YAML and have the next session pick
  it up without a server restart (the X-003 hot-reload intent).
* **Not a singleton at import time.** ``SkillRegistry`` is instantiated where
  needed (a module-level ``default_registry`` is provided for convenience, but
  tests pass their own). Avoids import-time file-system access.
* **Unknown skill id raises, not returns ``None``.** A missing manifest is an
  authoring/deployment error, surfaced loudly.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Optional

from src.core.skill_loader import load_skill_manifest
from src.core.skill_manifest import ResearchSkillManifest

logger = logging.getLogger(__name__)

#: Filename every skill package must declare (ARC-011 §5.2).
SKILL_MANIFEST_FILENAME = "SKILL.yaml"

#: Default discovery root: the service's ``skills/`` directory. Resolved
#: relative to this file so it's correct regardless of the process CWD.
DEFAULT_SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"


class SkillNotRegisteredError(KeyError):
    """Raised when a skill id is not present in the registry."""

    def __init__(self, skill_id: str, *, available: Iterable[str] = ()) -> None:
        super().__init__(skill_id)
        self.skill_id = skill_id
        self.available = sorted(available)

    def __str__(self) -> str:  # pragma: no cover - trivial
        avail = ", ".join(self.available) or "<none>"
        return f"skill {self.skill_id!r} not registered (available: {avail})"


class SkillRegistry:
    """Discovers, caches, and serves ``research_skill.v1`` manifests.

    Parameters
    ----------
    root:
        Directory to scan for ``skills/<id>/SKILL.yaml``. Defaults to
        ``DEFAULT_SKILLS_ROOT`` (the service's ``skills/`` dir).
    settings_obj:
        Forwarded to ``load_skill_manifest`` for ``{settings.*}`` interpolation
        (G6). Defaults to ``None`` (loader falls back to ``src.config.settings``).
    """

    def __init__(
        self,
        *,
        root: Optional[Path] = None,
        settings_obj: Any = None,
    ) -> None:
        self._root: Path = Path(root) if root is not None else DEFAULT_SKILLS_ROOT
        self._settings_obj = settings_obj
        # skill_id -> (manifest | None placeholder, manifest_path, mtime_at_load).
        # ``None`` marks a slot registered via ``register_path`` but not yet
        # loaded; ``get()`` lazily materializes it on first access.
        self._cache: dict[str, tuple[Optional[ResearchSkillManifest], Path, float]] = {}
        # Ids discovered on disk (lazy-loaded; not yet in ``_cache``).
        self._discovered: set[str] = set()
        self._scanned = False

    # ── Discovery ──────────────────────────────────────────────────────────
    def discover(self) -> list[str]:
        """Scan ``root`` for skill packages and return their ids (sorted).

        Does not load the manifests (lazy); only records which ids exist so
        ``available()`` is cheap. ``get()`` loads on demand.
        """
        self._discovered = set()
        if self._root.is_dir():
            for entry in sorted(self._root.iterdir()):
                if entry.is_dir() and (entry / SKILL_MANIFEST_FILENAME).is_file():
                    self._discovered.add(entry.name)
        self._scanned = True
        return sorted(self._discovered)

    def available(self) -> list[str]:
        """Ids known to the registry (scans once, then caches the listing)."""
        if not self._scanned:
            self.discover()
        # Merge discovered ids (on disk) with loaded + explicitly registered.
        registered = self._discovered | set(self._cache)
        return sorted(registered)

    # ── Registration ───────────────────────────────────────────────────────
    def register_path(self, skill_id: str, manifest_path: Path) -> None:
        """Register a manifest by explicit path (used by tests / non-standard
        layouts). Validated lazily on first ``get()``."""
        self._cache.pop(skill_id, None)  # force reload
        # Store a placeholder mtime so get() loads it fresh.
        self._cache[skill_id] = (None, Path(manifest_path), -1.0)
        self._discovered.add(skill_id)
        self._scanned = True

    # ── Retrieval ──────────────────────────────────────────────────────────
    def get(self, skill_id: str) -> ResearchSkillManifest:
        """Return the validated manifest for ``skill_id``, loading/reloading as
        needed. Raises ``SkillNotRegisteredError`` if the id is unknown."""
        entry = self._cache.get(skill_id)
        if entry is None:
            # Lazy discovery: look for skills/<id>/SKILL.yaml under root.
            candidate = self._root / skill_id / SKILL_MANIFEST_FILENAME
            if not candidate.is_file():
                raise SkillNotRegisteredError(skill_id, available=self.available())
            manifest = self._load(candidate)
            self._cache[skill_id] = (manifest, candidate, candidate.stat().st_mtime)
            return manifest
        manifest, path, mtime_loaded = entry
        # Hot-reload: re-read if the file changed on disk.
        if path.exists() and path.stat().st_mtime != mtime_loaded:
            manifest = self._load(path)
            self._cache[skill_id] = (manifest, path, path.stat().st_mtime)
            return manifest
        if manifest is None:  # registered via register_path, never loaded
            manifest = self._load(path)
            self._cache[skill_id] = (manifest, path, path.stat().st_mtime)
            return manifest
        return manifest

    def _load(self, path: Path) -> ResearchSkillManifest:
        logger.debug("loading skill manifest %s", path)
        return load_skill_manifest(path, settings_obj=self._settings_obj)

    def reload_all(self) -> int:
        """Force-reload every cached manifest. Returns the count reloaded.
        Useful in tests after mutating a manifest on disk."""
        count = 0
        for skill_id in list(self._cache):
            self._cache[skill_id] = (None, self._cache[skill_id][1], -1.0)
            self.get(skill_id)  # triggers reload
            count += 1
        return count


#: Module-level convenience registry for production wiring. Tests should
#: construct their own ``SkillRegistry`` with a temp root / stub settings.
default_registry = SkillRegistry()


__all__ = [
    "SKILL_MANIFEST_FILENAME",
    "DEFAULT_SKILLS_ROOT",
    "SkillNotRegisteredError",
    "SkillRegistry",
    "default_registry",
]
