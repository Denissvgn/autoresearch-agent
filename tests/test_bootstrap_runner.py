"""BootstrapRunner tests (ARC-011 P5-005 / P5-006 / P5-008 / P5-009).

Covers:

* **P5-005** — the runner delegates to ``PluginRunner`` (env/path/fail-closed
  guarantees are tested in ``test_plugin_runner.py``; here we pin the
  bootstrap-specific wiring).
* **P5-006** — the ``session_bootstrap.v1`` artifact writer (shape, atomicity,
  round-trip, rendered-file hashing).
* **P5-008** — ``--dry-bootstrap`` overlay mode (no writes to the real ws;
  artifact carries ``mode: dry``).
* **P5-009** — idempotency (re-bootstrap is a no-op when hashes match), and
  the failure paths (missing bootstrap plugin, plugin failure).
"""

from __future__ import annotations

import asyncio
import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from src.core.bootstrap_runner import (
    BOOTSTRAP_ARTIFACT_FILENAME,
    BOOTSTRAP_ARTIFACT_VERSION,
    BootstrapRunner,
    SessionBootstrapArtifact,
)
from src.core.skill_loader import load_layout
from src.core.skill_manifest import SCHEMA_VERSION, ResearchSkillManifest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _manifest_dict(**overrides: Any) -> dict[str, Any]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "id": "test-skill",
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "T",
        "description": "d",
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"}
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [{"id": "p1", "min_iterations": 1, "max_iterations": 2}],
        "command_policy": {},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {
            "primary": {"kind": "file_path", "path_template": "/tmp/x"}
        },
    }
    base.update(overrides)
    return base


@pytest.fixture()
def skill_with_bootstrap(tmp_path: Path) -> tuple[Path, ResearchSkillManifest]:
    """A skill package with a working ``bootstrap.py`` that renders two files."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    manifest = ResearchSkillManifest.model_validate(_manifest_dict())
    (skill_dir / "SKILL.yaml").write_text(json.dumps(_manifest_dict()))
    (skill_dir / "bootstrap.py").write_text(
        textwrap.dedent(
            """
            import json, sys, os
            data = json.load(sys.stdin)
            ws = data["workspace"]
            os.makedirs(ws, exist_ok=True)
            open(os.path.join(ws, "config.yaml"), "w").write("key: value\\n")
            open(os.path.join(ws, "seed.txt"), "w").write("seed-data\\n")
            print(json.dumps({"rendered": ["config.yaml", "seed.txt"]}))
            """
        )
    )
    return skill_dir, manifest


# ---------------------------------------------------------------------------
# P5-006 — session_bootstrap.v1 artifact
# ---------------------------------------------------------------------------


class TestBootstrapArtifact:
    def test_artifact_round_trip(self, tmp_path: Path):
        artifact = SessionBootstrapArtifact(
            skill_id="s",
            skill_version="1.0.0",
            workspace=str(tmp_path),
            rendered_files=[{"path": "a.txt", "sha256": "abc", "size_bytes": 3}],
            system_prompt_sha256="def",
            plugin_caps={"fs_write": "workspace"},
        )
        path = tmp_path / BOOTSTRAP_ARTIFACT_FILENAME
        artifact.write(path)
        assert path.is_file()
        restored = SessionBootstrapArtifact.read(path)
        assert restored.skill_id == "s"
        assert restored.rendered_files == artifact.rendered_files
        assert restored.system_prompt_sha256 == "def"

    def test_artifact_version_is_stable(self):
        assert BOOTSTRAP_ARTIFACT_VERSION == "session_bootstrap.v1"

    def test_artifact_to_dict_is_json_serializable(self, tmp_path: Path):
        artifact = SessionBootstrapArtifact(
            skill_id="s", skill_version="1", workspace=str(tmp_path),
        )
        # Must round-trip through json without error.
        roundtripped = json.loads(json.dumps(artifact.to_dict()))
        assert roundtripped["skill_id"] == "s"


# ---------------------------------------------------------------------------
# P5-005 — BootstrapRunner live execution
# ---------------------------------------------------------------------------


class TestBootstrapRunnerLive:
    @pytest.mark.asyncio
    async def test_live_bootstrap_renders_and_indexes(
        self, skill_with_bootstrap: tuple[Path, ResearchSkillManifest], tmp_path: Path
    ):
        skill_dir, manifest = skill_with_bootstrap
        layout = load_layout(skill_dir, manifest)
        ws = tmp_path / "session"
        runner = BootstrapRunner()
        outcome = await runner.run(
            skill_dir=skill_dir,
            layout=layout,
            manifest=manifest,
            workspace=ws,
            system_prompt="You are helpful.",
            tool_config={"tools": ["bash"]},
        )
        assert outcome.ok is True
        assert outcome.artifact is not None
        assert outcome.artifact.mode == "live"
        assert outcome.artifact.skill_id == "test-skill"
        rendered_paths = {f["path"] for f in outcome.artifact.rendered_files}
        assert rendered_paths == {"config.yaml", "seed.txt"}
        # Each rendered file has a sha256 + size.
        for entry in outcome.artifact.rendered_files:
            assert len(entry["sha256"]) == 64
            assert entry["size_bytes"] > 0
        assert outcome.artifact.system_prompt_sha256 is not None
        assert outcome.artifact.tool_config == {"tools": ["bash"]}
        # The real workspace got the files.
        assert (ws / "config.yaml").read_text() == "key: value\n"

    @pytest.mark.asyncio
    async def test_skill_without_bootstrap_fails_clearly(
        self, tmp_path: Path
    ):
        skill_dir = tmp_path / "bare"
        skill_dir.mkdir()
        manifest = ResearchSkillManifest.model_validate(_manifest_dict())
        (skill_dir / "SKILL.yaml").write_text(json.dumps(_manifest_dict()))
        layout = load_layout(skill_dir, manifest)
        runner = BootstrapRunner()
        outcome = await runner.run(
            skill_dir=skill_dir,
            layout=layout,
            manifest=manifest,
            workspace=tmp_path / "ws",
        )
        assert outcome.ok is False
        assert "no bootstrap plugin" in (outcome.error or "")

    @pytest.mark.asyncio
    async def test_plugin_failure_propagates_as_outcome_error(
        self, tmp_path: Path
    ):
        skill_dir = tmp_path / "broken"
        skill_dir.mkdir()
        manifest = ResearchSkillManifest.model_validate(_manifest_dict(id="broken"))
        (skill_dir / "SKILL.yaml").write_text(json.dumps(_manifest_dict(id="broken")))
        (skill_dir / "bootstrap.py").write_text(
            "import sys; sys.exit(3)\n"
        )
        layout = load_layout(skill_dir, manifest)
        runner = BootstrapRunner()
        outcome = await runner.run(
            skill_dir=skill_dir,
            layout=layout,
            manifest=manifest,
            workspace=tmp_path / "ws",
        )
        assert outcome.ok is False
        assert "non-zero" in (outcome.error or "") or "failed" in (outcome.error or "")


# ---------------------------------------------------------------------------
# P5-008 — --dry-bootstrap overlay mode
# ---------------------------------------------------------------------------


class TestBootstrapRunnerDry:
    @pytest.mark.asyncio
    async def test_dry_mode_does_not_touch_real_workspace(
        self, skill_with_bootstrap: tuple[Path, ResearchSkillManifest], tmp_path: Path
    ):
        skill_dir, manifest = skill_with_bootstrap
        layout = load_layout(skill_dir, manifest)
        ws = tmp_path / "real-session"
        ws.mkdir()
        runner = BootstrapRunner()
        outcome = await runner.run(
            skill_dir=skill_dir,
            layout=layout,
            manifest=manifest,
            workspace=ws,
            dry=True,
        )
        assert outcome.ok is True
        assert outcome.dry is True
        assert outcome.artifact is not None
        assert outcome.artifact.mode == "dry"
        # The artifact reports the REAL workspace path...
        assert outcome.artifact.workspace == str(ws)
        # ...but the real workspace was NOT written to.
        assert not (ws / "config.yaml").exists()
        assert not (ws / "seed.txt").exists()
        # The overlay (bootstrapped_dir) had the files, but it's a tmpdir that
        # is now gone (the context manager exited).
        assert outcome.bootstrapped_dir is not None

    @pytest.mark.asyncio
    async def test_dry_mode_captures_planned_writes(
        self, skill_with_bootstrap: tuple[Path, ResearchSkillManifest], tmp_path: Path
    ):
        skill_dir, manifest = skill_with_bootstrap
        layout = load_layout(skill_dir, manifest)
        ws = tmp_path / "real-session"
        ws.mkdir()
        runner = BootstrapRunner()
        outcome = await runner.run(
            skill_dir=skill_dir,
            layout=layout,
            manifest=manifest,
            workspace=ws,
            dry=True,
        )
        assert outcome.ok is True
        assert outcome.artifact is not None
        rendered = {f["path"] for f in outcome.artifact.rendered_files}
        assert rendered == {"config.yaml", "seed.txt"}
        # The hashes match what live mode would produce.
        live = await runner.run(
            skill_dir=skill_dir, layout=layout, manifest=manifest, workspace=ws,
        )
        assert live.ok is True
        dry_index = outcome.artifact._files_index()
        assert live.artifact is not None
        live_index = live.artifact._files_index()
        assert dry_index == live_index


# ---------------------------------------------------------------------------
# P5-009 — idempotency
# ---------------------------------------------------------------------------


class TestBootstrapIdempotency:
    @pytest.mark.asyncio
    async def test_rebootstrap_is_noop_when_hashes_match(
        self, skill_with_bootstrap: tuple[Path, ResearchSkillManifest], tmp_path: Path
    ):
        skill_dir, manifest = skill_with_bootstrap
        layout = load_layout(skill_dir, manifest)
        ws = tmp_path / "session"
        runner = BootstrapRunner()
        first = await runner.run(
            skill_dir=skill_dir, layout=layout, manifest=manifest, workspace=ws,
        )
        assert first.ok is True
        # The workspace hasn't changed → idempotent.
        assert first.artifact is not None
        assert runner.is_idempotent(
            existing_artifact=first.artifact, workspace=ws
        ) is True

    @pytest.mark.asyncio
    async def test_idempotency_breaks_when_workspace_changes(
        self, skill_with_bootstrap: tuple[Path, ResearchSkillManifest], tmp_path: Path
    ):
        skill_dir, manifest = skill_with_bootstrap
        layout = load_layout(skill_dir, manifest)
        ws = tmp_path / "session"
        runner = BootstrapRunner()
        first = await runner.run(
            skill_dir=skill_dir, layout=layout, manifest=manifest, workspace=ws,
        )
        # Mutate the workspace after bootstrap.
        (ws / "config.yaml").write_text("key: CHANGED\n")
        assert first.artifact is not None
        assert runner.is_idempotent(
            existing_artifact=first.artifact, workspace=ws
        ) is False

    @pytest.mark.asyncio
    async def test_artifact_write_and_read_roundtrip(
        self, skill_with_bootstrap: tuple[Path, ResearchSkillManifest], tmp_path: Path
    ):
        skill_dir, manifest = skill_with_bootstrap
        layout = load_layout(skill_dir, manifest)
        ws = tmp_path / "session"
        runner = BootstrapRunner()
        outcome = await runner.run(
            skill_dir=skill_dir, layout=layout, manifest=manifest, workspace=ws,
        )
        artifact_path = tmp_path / "artifacts" / BOOTSTRAP_ARTIFACT_FILENAME
        assert outcome.artifact is not None
        outcome.artifact.write(artifact_path)
        restored = SessionBootstrapArtifact.read(artifact_path)
        assert restored.matches(outcome.artifact) is True
