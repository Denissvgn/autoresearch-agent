"""Manifest schema + loader + registry tests (ARC-011 P2-001 / P2-002 / P2-003).

These are structural / contract tests in the Phase-1 house style (mirror
``test_output_parser.py`` P1-014, ``test_preflight.py`` P1-022). They pin:

* **P2-001** — the ``ResearchSkillManifest`` schema validates all five X-003
  spike drafts (the GO-verdict stress test), rejects malformed manifests with
  field-specific errors, and covers every section + gap (G1–G13).
* **P2-002** — the loader interpolates ``{settings.*}`` (G6 semantics), reports
  field-specific errors on missing settings, gates ``schema_version``, and
  accepts path / inline-YAML / dict sources.
* **P2-003** — the registry discovers ``skills/<id>/SKILL.yaml``, loads lazily,
  hot-reloads on mtime change, and raises on unknown ids.

The behavioral gate for the downstream ``ManifestSkillRuntime`` is the parity
suite (X-002) + the per-skill suites (P2-008/012/016).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from src.core.skill_loader import load_layout, load_skill_manifest
from src.core.skill_manifest import (
    SCHEMA_VERSION,
    ManifestValidationError,
    ManifestVersionError,
    PluginCaps,
    ResearchSkillManifest,
)
from src.core.skill_registry import (
    DEFAULT_SKILLS_ROOT,
    DRAFTS_SUBDIR,
    SKILL_MANIFEST_FILENAME,
    SkillNotRegisteredError,
    SkillRegistry,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SPIKE_DIR = REPO_ROOT / "docs" / "adr" / "skill-manifest-drafts"


# ---------------------------------------------------------------------------
# Stub settings (avoids the env-required singleton for G6 interpolation)
# ---------------------------------------------------------------------------


class _StubSettings:
    """Minimal settings object exposing every attr the reference manifests
    reference via ``{settings.*}``."""

    mlflow_tracking_uri = "http://mlflow:5000"
    host_configs_path = "/mnt/host_configs"


STUB_SETTINGS = _StubSettings()


def _minimal_manifest_dict() -> dict[str, Any]:
    """A minimal valid manifest dict, extended per-test as needed."""
    return {
        "schema_version": SCHEMA_VERSION,
        "id": "test-skill",
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "Test",
        "description": "test skill",
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


# ===========================================================================
# P2-001 — schema
# ===========================================================================


@pytest.mark.parametrize(
    "draft_name",
    [
        "prompt-engineering",
        "code-refactor",
        "db-config-tuning",
        "literature-review",
    ],
)
def test_schema_validates_every_spike_draft(draft_name: str):
    """The X-003 GO-verdict stress test: all spike drafts validate against
    the P2-001 schema (covers four promotion kinds + all five categories)."""
    path = SPIKE_DIR / f"{draft_name}.yaml"
    data = yaml.safe_load(path.read_text())
    manifest = ResearchSkillManifest.model_validate(data)
    assert manifest.id == draft_name
    assert len(manifest.phase_plan) >= 1


def test_schema_version_is_v1():
    assert SCHEMA_VERSION == "research_skill.v1"


def test_schema_rejects_wrong_schema_version():
    data = _minimal_manifest_dict()
    data["schema_version"] = "research_skill.v2"
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "schema_version" in str(exc.value)


def test_schema_rejects_unknown_top_level_key():
    data = _minimal_manifest_dict()
    data["mystery_section"] = {}
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "mystery_section" in str(exc.value)


def test_schema_rejects_unknown_promotion_kind():
    data = _minimal_manifest_dict()
    data["promotion_target"]["primary"]["kind"] = "s3_upload"
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "promotion_target" in str(exc.value)


def test_schema_rejects_phase_min_gt_max():
    data = _minimal_manifest_dict()
    data["phase_plan"][0]["min_iterations"] = 99
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "min_iterations" in str(exc.value) or "max_iterations" in str(exc.value)


def test_schema_rejects_duplicate_phase_ids():
    data = _minimal_manifest_dict()
    data["phase_plan"].append({"id": "p1", "min_iterations": 1, "max_iterations": 2})
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "duplicate" in str(exc.value).lower()


def test_schema_phase_advancement_plugin_requires_plugin_path():
    data = _minimal_manifest_dict()
    data["phase_advancement"] = {"mode": "plugin"}
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "plugin" in str(exc.value).lower()


# --- P5-014 / P5-028 / P5-029 manifest field additions --------------------


@pytest.mark.parametrize(
    "cat", ["optimization", "generative", "exploratory", "validation", "design"])
def test_schema_accepts_all_five_categories(cat: str):
    """P5-014: the Category literal covers all five ARC-011 §13 values."""
    data = _minimal_manifest_dict()
    data["category"] = cat
    manifest = ResearchSkillManifest.model_validate(data)
    assert manifest.category == cat


def test_schema_rejects_unknown_category():
    data = _minimal_manifest_dict()
    data["category"] = "bogus"
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "category" in str(exc.value)


def test_schema_accepts_feedback_loop_fields():
    """P5-028/029: auto_absorb_insights + knowledge_last_reviewed +
    refresh_cadence_days are optional, default-off/None."""
    data = _minimal_manifest_dict()
    data["auto_absorb_insights"] = True
    data["knowledge_last_reviewed"] = "2026-07-27T00:00:00Z"
    data["refresh_cadence_days"] = 30
    manifest = ResearchSkillManifest.model_validate(data)
    assert manifest.auto_absorb_insights is True
    assert manifest.knowledge_last_reviewed == "2026-07-27T00:00:00Z"
    assert manifest.refresh_cadence_days == 30


def test_schema_feedback_fields_default_off():
    data = _minimal_manifest_dict()
    manifest = ResearchSkillManifest.model_validate(data)
    assert manifest.auto_absorb_insights is False
    assert manifest.knowledge_last_reviewed is None
    assert manifest.refresh_cadence_days is None


def test_schema_rejects_zero_refresh_cadence():
    data = _minimal_manifest_dict()
    data["refresh_cadence_days"] = 0
    with pytest.raises(ValidationError):
        ResearchSkillManifest.model_validate(data)


def test_schema_declarative_trial_identity_requires_hash_fields():
    data = _minimal_manifest_dict()
    data["trial_identity"] = {"hash_fields": [], "resolve": {"mode": "declarative"}}
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "hash_fields" in str(exc.value)


def test_schema_registry_api_requires_production_scope():
    data = _minimal_manifest_dict()
    data["promotion_target"] = {
        "primary": {
            "kind": "registry_api",
            "registry": "x",
            "register_endpoint": "http://x",
        },
        "scopes": [{"id": "development", "approval_required": False}],
    }
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "production" in str(exc.value).lower()


def test_schema_metric_goal_accepts_satisfice():
    data = _minimal_manifest_dict()
    data["metric_schema"]["goal"] = "satisfice"
    manifest = ResearchSkillManifest.model_validate(data)
    assert manifest.metric_schema.goal == "satisfice"


# ===========================================================================
# P2-002 — loader
# ===========================================================================


def _reference_manifest_dict() -> dict[str, Any]:
    """A domain-neutral manifest exercising ``{settings.*}`` interpolation."""
    data = _minimal_manifest_dict()
    data["id"] = "reference-skill"
    data["preflight"] = [
        {
            "name": "mlflow_tracking",
            "kind": "http_health",
            "url": "{settings.mlflow_tracking_uri}",
        },
    ]
    data["promotion_target"]["primary"]["path_template"] = (
        "{settings.host_configs_path}/reference.yaml"
    )
    return data


@pytest.fixture()
def reference_manifest_path(tmp_path: Path) -> Path:
    path = tmp_path / "reference-skill.yaml"
    path.write_text(yaml.safe_dump(_reference_manifest_dict()))
    return path


def test_loader_resolves_settings_placeholders(reference_manifest_path: Path):
    """Loading the reference manifest resolves ``{settings.*}`` placeholders
    (G6 semantics owned by the loader)."""
    manifest = load_skill_manifest(
        reference_manifest_path, settings_obj=STUB_SETTINGS
    )
    assert manifest.id == "reference-skill"
    # G6: the preflight URL is now the resolved setting, not the placeholder.
    mlflow_target = next(t for t in manifest.preflight if t.name == "mlflow_tracking")
    assert mlflow_target.url == "http://mlflow:5000"


def test_loader_missing_setting_raises_field_specific_error(
    reference_manifest_path: Path,
):
    class Empty:
        pass

    with pytest.raises(ManifestValidationError) as exc:
        load_skill_manifest(reference_manifest_path, settings_obj=Empty())
    msg = str(exc.value)
    assert "settings.mlflow_tracking_uri" in msg
    assert "preflight" in msg  # field-specific path


def test_loader_missing_setting_value_none_raises(reference_manifest_path: Path):
    """A setting that resolves to ``None`` (present but unset) is an error."""

    class NoneSettings:
        mlflow_tracking_uri = None
        host_configs_path = "/x"

    with pytest.raises(ManifestValidationError):
        load_skill_manifest(reference_manifest_path, settings_obj=NoneSettings())


def test_loader_rejects_wrong_version_with_version_error():
    data = _minimal_manifest_dict()
    data["schema_version"] = "research_skill.v2"
    with pytest.raises(ManifestVersionError):
        load_skill_manifest(data, settings_obj=STUB_SETTINGS)


def test_loader_accepts_inline_yaml_string():
    inline = yaml.safe_dump(_minimal_manifest_dict())
    manifest = load_skill_manifest(inline, settings_obj=STUB_SETTINGS)
    assert manifest.id == "test-skill"


def test_loader_accepts_dict_source():
    manifest = load_skill_manifest(_minimal_manifest_dict(), settings_obj=STUB_SETTINGS)
    assert manifest.phase_plan[0].id == "p1"


def test_loader_wraps_validation_errors_field_specific():
    data = _minimal_manifest_dict()
    data["metric_schema"]["primary"]["direction"] = "sideways"
    with pytest.raises(ManifestValidationError) as exc:
        load_skill_manifest(data, settings_obj=STUB_SETTINGS)
    assert "direction" in str(exc.value)


def test_loader_skill_params_unresolvable_at_load_time():
    """``{skill_params.*}`` cannot be resolved without session context — a
    manifest referencing it at load time raises a field-specific error."""
    data = _minimal_manifest_dict()
    data["promotion_target"]["primary"]["path_template"] = "{skill_params.outfile}"
    with pytest.raises(ManifestValidationError) as exc:
        load_skill_manifest(data, settings_obj=STUB_SETTINGS)
    assert "skill_params" in str(exc.value)


def test_loader_skill_params_resolvable_when_supplied():
    data = _minimal_manifest_dict()
    data["promotion_target"]["primary"]["path_template"] = "{skill_params.outfile}"
    manifest = load_skill_manifest(
        data, settings_obj=STUB_SETTINGS, skill_params={"outfile": "/tmp/out"}
    )
    assert manifest.promotion_target.primary.path_template == "/tmp/out"


# ===========================================================================
# P2-003 — registry
# ===========================================================================


@pytest.fixture()
def temp_skills_root(tmp_path: Path) -> Path:
    """A temp ``skills/`` dir with one valid ``reference-skill`` package."""
    skill_dir = tmp_path / "reference-skill"
    skill_dir.mkdir()
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump(_reference_manifest_dict())
    )
    return tmp_path


def test_registry_discovers_skill_packages(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    assert reg.discover() == ["reference-skill"]
    # available() reflects discovered ids even before lazy load
    assert reg.available() == ["reference-skill"]


def test_registry_loads_lazily_and_caches(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    m1 = reg.get("reference-skill")
    m2 = reg.get("reference-skill")
    assert m1 is m2  # cached, no reload


def test_registry_hot_reloads_on_mtime_change(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    m1 = reg.get("reference-skill")
    manifest_path = temp_skills_root / "reference-skill" / SKILL_MANIFEST_FILENAME
    # bump mtime into the future
    future = time.time() + 10
    os.utime(manifest_path, (future, future))
    m2 = reg.get("reference-skill")
    assert m1 is not m2  # reloaded


def test_registry_unknown_id_raises(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    with pytest.raises(SkillNotRegisteredError) as exc:
        reg.get("nope")
    assert "nope" in str(exc.value)


def test_registry_register_path(temp_skills_root: Path):
    reg = SkillRegistry(settings_obj=STUB_SETTINGS)
    path = temp_skills_root / "reference-skill" / SKILL_MANIFEST_FILENAME
    reg.register_path("reference-skill", path)
    assert "reference-skill" in reg.available()
    assert reg.get("reference-skill").id == "reference-skill"


def test_registry_default_root_points_at_service_skills_dir():
    """The default discovery root is the service's ``skills/`` dir, NOT
    ``Settings.skills_dir`` (which is the workspace-side primer location)."""
    # DEFAULT_SKILLS_ROOT resolves to <service>/skills
    expected = Path(__file__).resolve().parents[1] / "skills"
    assert DEFAULT_SKILLS_ROOT == expected


# ===========================================================================
# P5-001 — full skill-package layout (SkillLayout, PluginCaps, drafts discovery)
# ===========================================================================


def test_schema_accepts_minimal_manifest_without_plugins():
    """Back-compat: existing skills (no ``plugins`` block) still validate."""
    data = _minimal_manifest_dict()
    manifest = ResearchSkillManifest.model_validate(data)
    assert manifest.plugins.entries == []


def test_schema_accepts_declared_plugins_block():
    data = _minimal_manifest_dict()
    data["plugins"] = {
        "entries": [
            {"kind": "bootstrap", "path": "bootstrap.py"},
            {"kind": "parser", "path": "parser.py"},
        ]
    }
    manifest = ResearchSkillManifest.model_validate(data)
    kinds = {e.kind for e in manifest.plugins.entries}
    assert kinds == {"bootstrap", "parser"}


def test_schema_rejects_duplicate_plugin_kind():
    data = _minimal_manifest_dict()
    data["plugins"] = {
        "entries": [
            {"kind": "bootstrap", "path": "bootstrap.py"},
            {"kind": "bootstrap", "path": "bootstrap2.py"},
        ]
    }
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "duplicate plugin kind" in str(exc.value)


def test_schema_rejects_duplicate_plugin_path():
    data = _minimal_manifest_dict()
    data["plugins"] = {
        "entries": [
            {"kind": "bootstrap", "path": "x.py"},
            {"kind": "parser", "path": "x.py"},
        ]
    }
    with pytest.raises(ValidationError) as exc:
        ResearchSkillManifest.model_validate(data)
    assert "duplicate plugin path" in str(exc.value)


def test_plugin_caps_defaults_are_default_deny():
    """X-004 §6: a bare ``PluginCaps()`` is default-deny (read-only, no net)."""
    caps = PluginCaps()
    assert caps.fs_write == "none"
    assert caps.network_egress == []
    assert caps.env == []


def test_load_layout_reports_minimal_package(tmp_path: Path):
    """A skill with only SKILL.yaml/SKILL.md resolves to an empty layout."""
    skill_dir = tmp_path / "bare"
    skill_dir.mkdir()
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump(_minimal_manifest_dict())
    )
    layout = load_layout(skill_dir)
    assert layout.has_bootstrap is False
    assert layout.has_scaffold is False
    assert layout.has_knowledge is False
    assert layout.has_eval is False
    assert layout.plugins == {}
    assert layout.missing_plugin_paths == []


def test_load_layout_detects_full_directory_tree(tmp_path: Path):
    """All optional layout slots are detected from on-disk presence."""
    skill_dir = tmp_path / "full"
    skill_dir.mkdir()
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump(_minimal_manifest_dict())
    )
    (skill_dir / "bootstrap.py").write_text("# noop\n")
    (skill_dir / "scaffold").mkdir()
    (skill_dir / "knowledge").mkdir()
    (skill_dir / "eval").mkdir()
    (skill_dir / "tools").mkdir()
    layout = load_layout(skill_dir)
    assert layout.has_bootstrap is True
    assert layout.has_scaffold is True
    assert layout.has_knowledge is True
    assert layout.has_eval is True
    assert layout.has_tools is True


def test_load_layout_backfills_bootstrap_from_disk_presence(tmp_path: Path):
    """A skill shipping ``bootstrap.py`` without a manifest ``plugins`` block
    gets a default-capped bootstrap entry (X-004 per-kind defaults)."""
    skill_dir = tmp_path / "implicit"
    skill_dir.mkdir()
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump(_minimal_manifest_dict())
    )
    (skill_dir / "bootstrap.py").write_text("# noop\n")
    layout = load_layout(skill_dir)
    assert "bootstrap" in layout.plugins
    entry = layout.plugins["bootstrap"]
    assert entry.path == "bootstrap.py"
    # X-004 §6 default for bootstrap: workspace write, no egress.
    assert entry.caps is not None
    assert entry.caps.fs_write == "workspace"
    assert entry.caps.network_egress == []


def test_load_layout_resolves_declared_plugin_caps_to_default(tmp_path: Path):
    """A declared plugin with ``caps: None`` takes the per-kind default."""
    skill_dir = tmp_path / "declared"
    skill_dir.mkdir()
    data = _minimal_manifest_dict()
    data["plugins"] = {"entries": [{"kind": "parser", "path": "parser.py"}]}
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(yaml.safe_dump(data))
    (skill_dir / "parser.py").write_text("# noop\n")
    layout = load_layout(skill_dir)
    entry = layout.plugins["parser"]
    assert entry.caps is not None
    # parser default: read-only, no egress (X-004 §6).
    assert entry.caps.fs_write == "none"
    assert entry.caps.network_egress == []


def test_load_layout_rejects_caps_widening_beyond_kind_default(tmp_path: Path):
    """R10: a manifest may narrow but not widen plugin caps. A parser declaring
    ``fs_write: workspace`` widens the per-kind default (none) and is rejected."""
    skill_dir = tmp_path / "wide"
    skill_dir.mkdir()
    data = _minimal_manifest_dict()
    data["plugins"] = {
        "entries": [
            {
                "kind": "parser",
                "path": "parser.py",
                "caps": {"fs_write": "workspace"},
            }
        ]
    }
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(yaml.safe_dump(data))
    (skill_dir / "parser.py").write_text("# noop\n")
    with pytest.raises(ManifestValidationError) as exc:
        load_layout(skill_dir)
    assert "widens" in str(exc.value).lower() or "widen" in str(exc.value).lower()


def test_load_layout_allows_caps_narrowing(tmp_path: Path):
    """A manifest may legitimately tighten resource caps (smaller = safer)."""
    skill_dir = tmp_path / "narrow"
    skill_dir.mkdir()
    data = _minimal_manifest_dict()
    data["plugins"] = {
        "entries": [
            {
                "kind": "bootstrap",
                "path": "bootstrap.py",
                "caps": {"timeout_s": 10.0, "max_rss_mb": 128},
            }
        ]
    }
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(yaml.safe_dump(data))
    (skill_dir / "bootstrap.py").write_text("# noop\n")
    layout = load_layout(skill_dir)
    entry = layout.plugins["bootstrap"]
    assert entry.caps is not None
    assert entry.caps.timeout_s == 10.0
    assert entry.caps.max_rss_mb == 128


def test_load_layout_reports_missing_declared_plugin_paths(tmp_path: Path):
    """A plugin declared in the manifest but absent on disk is flagged."""
    skill_dir = tmp_path / "missing"
    skill_dir.mkdir()
    data = _minimal_manifest_dict()
    data["plugins"] = {"entries": [{"kind": "parser", "path": "ghost.py"}]}
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(yaml.safe_dump(data))
    layout = load_layout(skill_dir)
    assert "ghost.py" in layout.missing_plugin_paths


# --- Registry drafts discovery (P5-001) -----------------------------------


def test_registry_discover_skips_drafts_subdir(tmp_path: Path):
    """``_drafts/`` is not enumerated as a top-level skill package."""
    root = tmp_path
    (root / "real-skill").mkdir()
    (root / "real-skill" / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump(_minimal_manifest_dict())
    )
    drafts = root / DRAFTS_SUBDIR
    drafts.mkdir()
    (drafts / "draft-skill").mkdir()
    (drafts / "draft-skill" / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump(_minimal_manifest_dict())
    )
    reg = SkillRegistry(root=root, settings_obj=STUB_SETTINGS)
    assert reg.discover() == ["real-skill"]
    assert DRAFTS_SUBDIR not in reg.available()


def test_registry_discover_drafts_enumerates_drafts_dir(tmp_path: Path):
    """``discover_drafts()`` returns ids under ``_drafts/``."""
    root = tmp_path
    drafts = root / DRAFTS_SUBDIR
    drafts.mkdir()
    (drafts / "alpha").mkdir()
    (drafts / "alpha" / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump({**_minimal_manifest_dict(), "id": "alpha"})
    )
    (drafts / "beta").mkdir()
    (drafts / "beta" / SKILL_MANIFEST_FILENAME).write_text(
        yaml.safe_dump({**_minimal_manifest_dict(), "id": "beta"})
    )
    reg = SkillRegistry(root=root, settings_obj=STUB_SETTINGS)
    assert reg.discover_drafts() == ["alpha", "beta"]


def test_registry_discover_drafts_empty_when_no_dir(tmp_path: Path):
    reg = SkillRegistry(root=tmp_path, settings_obj=STUB_SETTINGS)
    assert reg.discover_drafts() == []
    assert reg.drafts_root == tmp_path / DRAFTS_SUBDIR
