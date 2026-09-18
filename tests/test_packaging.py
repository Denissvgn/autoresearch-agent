"""Release metadata and archive-content regressions.

Set AUTORESEARCH_DIST_DIR to freshly built wheel/sdist artifacts to check
archive contents. Ordinary unit runs do not build or install anything.
"""

from __future__ import annotations

import os
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_SKILL_IDS = ("code-refactor", "db-config-tuning", "prompt-engineering")
SKILL_ARCHIVE_PREFIX = "skills/"


def _pyproject_includes() -> list[dict]:
    """Parse the ``tool.poetry`` include table from pyproject.toml."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return data["tool"]["poetry"].get("include", [])


def test_pyproject_includes_bundled_skill_dirs_explicitly_for_both_formats():
    includes = _pyproject_includes()
    skill_includes = [entry for entry in includes if entry["path"].startswith("skills/")]
    assert {entry["path"] for entry in skill_includes} == {
        f"skills/{skill_id}" for skill_id in BUNDLED_SKILL_IDS
    }
    for entry in skill_includes:
        assert "sdist" in entry["format"], entry
        assert "wheel" in entry["format"], entry


def test_pyproject_does_not_package_drafts_or_the_whole_skills_tree():
    paths = {entry["path"] for entry in _pyproject_includes()}
    assert "skills" not in paths
    assert "skills/" not in paths
    assert "skills/_drafts" not in paths
    # Registry-side reserved name, asserted here so a future packaging entry
    # cannot quietly reintroduce it.
    registry = (REPO_ROOT / "src" / "core" / "skill_registry.py").read_text()
    assert '_DRAFTS_SUBDIR = "_drafts"' in registry


def test_bundled_skill_dirs_each_carry_a_loadable_manifest():
    for skill_id in BUNDLED_SKILL_IDS:
        manifest_path = REPO_ROOT / "skills" / skill_id / "SKILL.yaml"
        assert manifest_path.is_file(), f"bundled skill {skill_id} is missing SKILL.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        assert manifest["id"] == skill_id
        assert manifest["schema_version"] == "research_skill.v1"


def test_default_skills_root_is_sibling_of_installed_src_package():
    """Conceptual pin for the installed-layout contract (Dockerfile parity).

    DEFAULT_SKILLS_ROOT is ``parents[2] / "skills"`` of
    ``<root>/src/core/skill_registry.py``. The pyproject ``include`` entries
    above (plus the Dockerfile's ``skills/ /app/skills/`` copy) install the
    sibling at exactly that path; assert both sides of the contract.
    """
    from src.core.skill_registry import DEFAULT_SKILLS_ROOT

    # In the checkout the sibling must be the tracked skills/ directory.
    assert DEFAULT_SKILLS_ROOT == REPO_ROOT / "skills"
    # Dockerfile: skills land at /app/skills, src at /app/src → same sibling
    # layout as the wheel (update both together if the layout changes).
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=appuser:appuser src/ /app/src/" in dockerfile
    assert "COPY --chown=appuser:appuser skills/ /app/skills/" in dockerfile


@pytest.mark.parametrize("archive_format", ["wheel", "sdist"])
def test_release_archives_contain_only_bundled_skills(archive_format):
    dist_dir = os.environ.get("AUTORESEARCH_DIST_DIR")
    if not dist_dir:
        pytest.skip("Set AUTORESEARCH_DIST_DIR to freshly built release artifacts")
    pattern = "*.whl" if archive_format == "wheel" else "*.tar.gz"
    archives = list(Path(dist_dir).glob(pattern))
    assert len(archives) == 1, archives
    if archive_format == "wheel":
        with zipfile.ZipFile(archives[0]) as archive:
            names = {info.filename for info in archive.infolist() if not info.is_dir()}
    else:
        with tarfile.open(archives[0]) as archive:
            # An sdist adds a single name-version directory above the project.
            names = {
                member.name.partition("/")[2]
                for member in archive.getmembers()
                if member.isfile()
            }
    assert "src/core/skill_registry.py" in names
    skill_names = {name for name in names if name.startswith(SKILL_ARCHIVE_PREFIX)}
    assert {name.split("/")[1] for name in skill_names} == set(BUNDLED_SKILL_IDS)
    for skill_id in BUNDLED_SKILL_IDS:
        for asset in ("SKILL.yaml", "SKILL.md", "bootstrap.py", "eval/run.py"):
            assert f"skills/{skill_id}/{asset}" in skill_names

