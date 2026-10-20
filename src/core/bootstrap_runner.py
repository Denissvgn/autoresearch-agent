"""Bootstrap runner — execute a skill's ``bootstrap.py`` at session start
(ARC-011 P5-005 / P5-006 / P5-008).

The ``BootstrapRunner`` is the first consumer of ``PluginRunner``
(``plugin_runner.py``). It runs a skill's ``bootstrap.py`` once per session to
render the workspace (scaffold/, knowledge/ corpus, eval smoke-check, system
prompt assembly) and writes a ``session_bootstrap.v1`` artifact recording what
was rendered. This is step 2 of the ARC-011 §5.4 auto-initialization lifecycle.

What moves here in Phase 5 (P5-007): the workspace-prep logic that today lives
in ``session_manager`` (``_archive_stale_workspace``, train.yaml/best_train.yaml
rendering, ``{runs_dir}/{instrument}_{timeframe}/{model_type}`` derivation) and
the 61 ``prepare.py``/``train.yaml`` references in ``orchestrator.py`` migrate
into each skill's ``bootstrap.py``. The orchestrator becomes purely loop +
guards; it reads the rendered workspace from this artifact.

Design decisions (P1-007 house style):

* **Thin orchestrator over PluginRunner.** ``BootstrapRunner`` does not spawn
  subprocesses itself — it delegates to ``PluginRunner`` so all skill-supplied
  Python execution funnels through one governed path (X-004 D2).
* **The artifact is the contract.** ``session_bootstrap.v1`` is what the
  orchestrator reads to learn the rendered workspace layout, what P5-008's dry
  mode diffs against, and what P5-024/P5-026 reviewers inspect before promoting
  a draft. Its shape is stable and forward-compat (additive only).
* **Idempotent.** Re-bootstrapping a session whose artifact already matches the
  rendered file hashes is a no-op (P5-009). The caller decides when to invoke.
* **Dry mode (P5-008).** ``run(dry=True)`` executes the bootstrap in a
  throwaway overlay of a fresh workspace, then captures the planned writes
  without committing them to the real session workspace. Required for
  ``draft``/generated skills (X-004 D5); optional for vetted ``stable`` skills.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.core.plugin_runner import PluginResult, PluginRunner
from src.core.skill_loader import SkillLayout
from src.core.skill_manifest import PluginCaps, ResearchSkillManifest

logger = logging.getLogger(__name__)

#: Artifact schema version (additive-only forward compat). The session manifest
#: sidecar is named ``session_bootstrap.v1.json`` and lives next to the session
#: manifest. P5-006 owns the writer; P5-008 owns the dry-mode variant.
BOOTSTRAP_ARTIFACT_VERSION = "session_bootstrap.v1"
BOOTSTRAP_ARTIFACT_FILENAME = "session_bootstrap.v1.json"

#: Standard bootstrap input contract. The bootstrap plugin reads this from
#: stdin and renders the workspace accordingly.
DEFAULT_BOOTSTRAP_INPUT: dict[str, Any] = {
    "workspace": None,  # set per-call
    "mode": "live",  # "live" | "dry"
    "skill_params": {},  # session-supplied params (P2-017)
}


def _server_demo_mode() -> bool:
    from src.config import settings

    return settings.demo_mode is True and str(settings.environment).lower() != "production"


@dataclass(frozen=True)
class BootstrapOutcome:
    """Result of a bootstrap run, including the resolved artifact."""

    ok: bool
    artifact: Optional["SessionBootstrapArtifact"] = None
    #: From the underlying ``PluginResult`` when failed.
    error: Optional[str] = None
    #: Wall-clock duration of the plugin run.
    duration_s: float = 0.0
    #: ``True`` if this run was a dry-mode overlay (no writes to the real ws).
    dry: bool = False
    #: The directory actually bootstrapped (the overlay tmpdir in dry mode).
    bootstrapped_dir: Optional[Path] = None


class SessionBootstrapArtifact:
    """The ``session_bootstrap.v1`` artifact (P5-006).

    A JSON sidecar recording what the bootstrap rendered: the file list with
    sha256 + size, the assembled system-prompt hash, the resolved plugin caps,
    the resolved tool config, and the seed search space. The orchestrator reads
    this to learn the rendered workspace; reviewers read it (in dry mode) to
    approve a draft.

    The shape is additive-only forward-compat (``schema_version`` pins the major).
    """

    def __init__(
        self,
        *,
        schema_version: str = BOOTSTRAP_ARTIFACT_VERSION,
        skill_id: str,
        skill_version: str,
        workspace: str,
        mode: str = "live",
        rendered_files: Optional[list[dict[str, Any]]] = None,
        system_prompt_sha256: Optional[str] = None,
        plugin_caps: Optional[dict[str, Any]] = None,
        tool_config: Optional[dict[str, Any]] = None,
        seed_search: Optional[dict[str, Any]] = None,
        plugin_output: Optional[dict[str, Any]] = None,
        created_at: Optional[str] = None,
    ) -> None:
        self.schema_version = schema_version
        self.skill_id = skill_id
        self.skill_version = skill_version
        self.workspace = workspace
        self.mode = mode
        self.rendered_files = rendered_files or []
        self.system_prompt_sha256 = system_prompt_sha256
        self.plugin_caps = plugin_caps
        self.tool_config = tool_config
        self.seed_search = seed_search
        self.plugin_output = plugin_output or {}
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "workspace": self.workspace,
            "mode": self.mode,
            "rendered_files": self.rendered_files,
            "system_prompt_sha256": self.system_prompt_sha256,
            "plugin_caps": self.plugin_caps,
            "tool_config": self.tool_config,
            "seed_search": self.seed_search,
            "plugin_output": self.plugin_output,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionBootstrapArtifact":
        return cls(
            schema_version=data.get("schema_version", BOOTSTRAP_ARTIFACT_VERSION),
            skill_id=data["skill_id"],
            skill_version=data["skill_version"],
            workspace=data["workspace"],
            mode=data.get("mode", "live"),
            rendered_files=data.get("rendered_files", []),
            system_prompt_sha256=data.get("system_prompt_sha256"),
            plugin_caps=data.get("plugin_caps"),
            tool_config=data.get("tool_config"),
            seed_search=data.get("seed_search"),
            plugin_output=data.get("plugin_output", {}),
            created_at=data.get("created_at"),
        )

    def write(self, path: Path) -> None:
        """Atomically write the artifact to ``path`` (tmp + os.replace)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            import os as _os
            with _os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
                fh.flush()
                _os.fsync(fh.fileno())
            _os.replace(tmp_path, str(path))
        except BaseException:
            try:
                Path(tmp_path).unlink()
            except FileNotFoundError:
                pass
            raise

    @classmethod
    def read(cls, path: Path) -> "SessionBootstrapArtifact":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def matches(self, other: "SessionBootstrapArtifact") -> bool:
        """True if the rendered file hashes match (idempotency check, P5-009)."""
        return self._files_index() == other._files_index()

    def _files_index(self) -> dict[str, str]:
        return {f["path"]: f.get("sha256", "") for f in self.rendered_files}


def _hash_file(path: Path, *, relative_to: Path) -> Optional[dict[str, Any]]:
    """Return ``{path, sha256, size_bytes}`` for one rendered file, or None."""
    try:
        rel = path.relative_to(relative_to).as_posix()
    except ValueError:
        return None
    if not path.is_file():
        return None
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
            size += len(chunk)
    return {"path": rel, "sha256": h.hexdigest(), "size_bytes": size}


def _index_rendered(workspace: Path) -> list[dict[str, Any]]:
    """Walk the workspace and record every rendered file's hash + size."""
    out: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*")):
        if path.is_file():
            entry = _hash_file(path, relative_to=workspace)
            if entry is not None:
                out.append(entry)
    return out


def _hash_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BootstrapRunner:
    """Run a skill's ``bootstrap.py`` once at session start (P5-005).

    Parameters
    ----------
    plugin_runner:
        The governed-subprocess runner (X-004 §6). Injected for testability;
        production wires a single shared instance.
    skills_root:
        Optional skills root for path confinement (forwarded to PluginRunner).
    """

    def __init__(
        self,
        *,
        plugin_runner: Optional[PluginRunner] = None,
        skills_root: Optional[Path] = None,
    ) -> None:
        self._plugin_runner = plugin_runner or PluginRunner(skills_root=skills_root)

    async def run(
        self,
        *,
        skill_dir: Path,
        layout: SkillLayout,
        manifest: ResearchSkillManifest,
        workspace: Path,
        skill_params: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        tool_config: Optional[dict[str, Any]] = None,
        seed_search: Optional[dict[str, Any]] = None,
        dry: bool = False,
        timeout_s: Optional[float] = None,
        proc_registry: Any = None,
        research_id: Optional[str] = None,
    ) -> BootstrapOutcome:
        """Execute the skill's ``bootstrap.py`` and write the artifact.

        ``dry=True`` runs the bootstrap in a throwaway overlay (P5-008 D5(b)),
        capturing the planned writes without touching the real workspace.
        ``proc_registry`` registers the live plugin spawn so a session
        stop/cancel can reap the bootstrap tree through bounded cleanup.
        """
        bootstrap_entry = layout.plugins.get("bootstrap")
        if bootstrap_entry is None:
            return BootstrapOutcome(
                ok=False,
                error=(
                    f"skill {manifest.id!r} declares no bootstrap plugin; "
                    "the layout resolved no bootstrap.py"
                ),
            )
        caps = bootstrap_entry.caps or PluginCaps(fs_write="workspace")
        # Resolve prompt data paths before switching to the plugin's cwd (or
        # dry overlay). Never copy executable files from the source directory.
        skill_params = dict(skill_params or {})
        if manifest.id == "prompt-engineering" and skill_params.get("eval_set") is not None:
            source = skill_params["eval_set"]
            if not isinstance(source, str) or not source or ".." in Path(source).parts:
                return BootstrapOutcome(ok=False, error="invalid eval_set path", dry=dry)
            path = Path(source)
            if not path.is_absolute():
                path = workspace.absolute() / path
            skill_params["eval_set"] = str(path)
        if dry:
            return await self._run_dry(
                skill_dir=skill_dir,
                plugin=bootstrap_entry.path,
                manifest=manifest,
                workspace=workspace,
                caps=caps,
                skill_params=skill_params,
                system_prompt=system_prompt,
                tool_config=tool_config,
                seed_search=seed_search,
                timeout_s=timeout_s,
                proc_registry=proc_registry,
                research_id=research_id,
            )
        workspace.mkdir(parents=True, exist_ok=True)
        input_json = {
            **DEFAULT_BOOTSTRAP_INPUT,
            "workspace": str(workspace),
            "mode": "live",
            "demo_mode": _server_demo_mode(),
            "skill_params": skill_params or {},
        }
        result = await self._plugin_runner.run(
            skill_dir=skill_dir,
            plugin=bootstrap_entry.path,
            kind="bootstrap",
            input_json=input_json,
            caps=caps,
            workspace=workspace,
            timeout_s=timeout_s,
            proc_registry=proc_registry,
            research_id=research_id,
        )
        if not result.ok:
            return BootstrapOutcome(
                ok=False,
                error=result.error or "bootstrap plugin failed",
                duration_s=result.duration_s,
            )
        rendered = _index_rendered(workspace)
        artifact = SessionBootstrapArtifact(
            skill_id=manifest.id,
            skill_version=manifest.version,
            workspace=str(workspace),
            mode="live",
            rendered_files=rendered,
            system_prompt_sha256=_hash_str(system_prompt) if system_prompt else None,
            plugin_caps=caps.model_dump(mode="json") if caps else None,
            tool_config=tool_config,
            seed_search=seed_search,
            plugin_output=result.output or {},
        )
        return BootstrapOutcome(
            ok=True,
            artifact=artifact,
            duration_s=result.duration_s,
            dry=False,
            bootstrapped_dir=workspace,
        )

    async def _run_dry(
        self,
        *,
        skill_dir: Path,
        plugin: str,
        manifest: ResearchSkillManifest,
        workspace: Path,
        caps: PluginCaps,
        skill_params: Optional[dict[str, Any]],
        system_prompt: Optional[str],
        tool_config: Optional[dict[str, Any]],
        seed_search: Optional[dict[str, Any]],
        timeout_s: Optional[float],
        proc_registry: Any = None,
        research_id: Optional[str] = None,
    ) -> BootstrapOutcome:
        """X-004 D5(b) overlay dry mode (P5-008).

        Executes the bootstrap in a throwaway copy of a fresh workspace, then
        captures the planned writes without committing them to the real session
        workspace. The mechanism is ``tempfile`` + ``shutil.copy2`` (CoW FS
        support is opportunistic, not required — the spike cares about capture
        correctness, not the FS layer).
        """
        with tempfile.TemporaryDirectory(prefix="bootstrap-dry-") as overlay_str:
            overlay = Path(overlay_str)
            overlay.mkdir(parents=True, exist_ok=True)
            input_json = {
                **DEFAULT_BOOTSTRAP_INPUT,
                "workspace": str(overlay),
                "mode": "dry",
                "demo_mode": _server_demo_mode(),
                "skill_params": skill_params or {},
            }
            result = await self._plugin_runner.run(
                skill_dir=skill_dir,
                plugin=plugin,
                kind="bootstrap",
                input_json=input_json,
                caps=caps,
                workspace=overlay,
                timeout_s=timeout_s,
                proc_registry=proc_registry,
                research_id=research_id,
            )
            if not result.ok:
                return BootstrapOutcome(
                    ok=False,
                    error=result.error or "bootstrap plugin failed (dry)",
                    duration_s=result.duration_s,
                    dry=True,
                )
            rendered = _index_rendered(overlay)
            artifact = SessionBootstrapArtifact(
                skill_id=manifest.id,
                skill_version=manifest.version,
                # The artifact reports the REAL workspace path (where the writes
                # would land) even though the overlay is what got rendered.
                workspace=str(workspace),
                mode="dry",
                rendered_files=rendered,
                system_prompt_sha256=_hash_str(system_prompt) if system_prompt else None,
                plugin_caps=caps.model_dump(mode="json") if caps else None,
                tool_config=tool_config,
                seed_search=seed_search,
                plugin_output=result.output or {},
            )
            return BootstrapOutcome(
                ok=True,
                artifact=artifact,
                duration_s=result.duration_s,
                dry=True,
                bootstrapped_dir=overlay,
            )

    def is_idempotent(
        self,
        *,
        existing_artifact: SessionBootstrapArtifact,
        workspace: Path,
    ) -> bool:
        """P5-009 idempotency: True if the workspace's current hashes match the
        artifact (a re-bootstrap would be a no-op)."""
        current = _index_rendered(workspace)
        current_index = {f["path"]: f.get("sha256", "") for f in current}
        return current_index == existing_artifact._files_index()


__all__ = [
    "BOOTSTRAP_ARTIFACT_FILENAME",
    "BOOTSTRAP_ARTIFACT_VERSION",
    "BootstrapOutcome",
    "BootstrapRunner",
    "SessionBootstrapArtifact",
]
