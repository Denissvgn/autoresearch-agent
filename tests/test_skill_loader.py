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

from src.core.skill_loader import load_skill_manifest
from src.core.skill_manifest import (
    SCHEMA_VERSION,
    ManifestValidationError,
    ManifestVersionError,
    ResearchSkillManifest,
)
from src.core.skill_registry import (
    DEFAULT_SKILLS_ROOT,
    SKILL_MANIFEST_FILENAME,
    SkillNotRegisteredError,
    SkillRegistry,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SPIKE_DIR = REPO_ROOT / "docs" / "adr" / "arc-011-manifest-spike"


# ---------------------------------------------------------------------------
# Stub settings (avoids the env-required singleton for G6 interpolation)
# ---------------------------------------------------------------------------


class _StubSettings:
    """Minimal settings object exposing every attr the spike manifests
    reference via ``{settings.*}``."""

    mlflow_tracking_uri = "http://mlflow:5000"
    mlflow_service_url = "http://mlflow-svc:8000"
    data_ingest_url = "http://ingest:9000"
    ensemble_trainer_url = "http://ens:9001"
    rl_trainer_url = "http://rl:9002"
    feature_service_url = "http://feat:9003"
    inference_service_url = "http://inf:9004"
    admin_service_url = "http://admin:9005"
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
        "ml-direction",
        "prompt-engineering",
        "code-refactor",
        "db-config-tuning",
        "literature-review",
    ],
)
def test_schema_validates_every_spike_draft(draft_name: str):
    """The X-003 GO-verdict stress test: all five spike drafts validate against
    the P2-001 schema (covers all four promotion kinds + all three categories)."""
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


def test_loader_loads_spike_ml_direction_with_interpolation():
    """Loading the reference manifest resolves ``{settings.*}`` placeholders
    (G6 semantics owned by the loader)."""
    manifest = load_skill_manifest(
        SPIKE_DIR / "ml-direction.yaml", settings_obj=STUB_SETTINGS
    )
    assert manifest.id == "ml-direction"
    # G6: the preflight URL is now the resolved setting, not the placeholder.
    mlflow_target = next(t for t in manifest.preflight if t.name == "mlflow_tracking")
    assert mlflow_target.url == "http://mlflow:5000"


def test_loader_missing_setting_raises_field_specific_error():
    class Empty:
        pass

    with pytest.raises(ManifestValidationError) as exc:
        load_skill_manifest(SPIKE_DIR / "ml-direction.yaml", settings_obj=Empty())
    msg = str(exc.value)
    assert "settings.mlflow_tracking_uri" in msg
    assert "preflight" in msg  # field-specific path


def test_loader_missing_setting_value_none_raises():
    """A setting that resolves to ``None`` (present but unset) is an error."""

    class NoneSettings:
        mlflow_tracking_uri = None
        mlflow_service_url = "u"
        data_ingest_url = "u"
        ensemble_trainer_url = "u"
        rl_trainer_url = "u"
        feature_service_url = "u"
        host_configs_path = "/x"

    with pytest.raises(ManifestValidationError):
        load_skill_manifest(SPIKE_DIR / "ml-direction.yaml", settings_obj=NoneSettings())


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
    """A temp ``skills/`` dir with one valid ``ml-direction`` skill package."""
    skill_dir = tmp_path / "ml-direction"
    skill_dir.mkdir()
    (skill_dir / SKILL_MANIFEST_FILENAME).write_text(
        (SPIKE_DIR / "ml-direction.yaml").read_text()
    )
    return tmp_path


def test_registry_discovers_skill_packages(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    assert reg.discover() == ["ml-direction"]
    # available() reflects discovered ids even before lazy load
    assert reg.available() == ["ml-direction"]


def test_registry_loads_lazily_and_caches(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    m1 = reg.get("ml-direction")
    m2 = reg.get("ml-direction")
    assert m1 is m2  # cached, no reload


def test_registry_hot_reloads_on_mtime_change(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    m1 = reg.get("ml-direction")
    manifest_path = temp_skills_root / "ml-direction" / SKILL_MANIFEST_FILENAME
    # bump mtime into the future
    future = time.time() + 10
    os.utime(manifest_path, (future, future))
    m2 = reg.get("ml-direction")
    assert m1 is not m2  # reloaded


def test_registry_unknown_id_raises(temp_skills_root: Path):
    reg = SkillRegistry(root=temp_skills_root, settings_obj=STUB_SETTINGS)
    with pytest.raises(SkillNotRegisteredError) as exc:
        reg.get("nope")
    assert "nope" in str(exc.value)


def test_registry_register_path(temp_skills_root: Path):
    reg = SkillRegistry(settings_obj=STUB_SETTINGS)
    path = temp_skills_root / "ml-direction" / SKILL_MANIFEST_FILENAME
    reg.register_path("ml-direction", path)
    assert "ml-direction" in reg.available()
    assert reg.get("ml-direction").id == "ml-direction"


def test_registry_default_root_points_at_service_skills_dir():
    """The default discovery root is the service's ``skills/`` dir, NOT
    ``Settings.skills_dir`` (which is the workspace-side primer location)."""
    # DEFAULT_SKILLS_ROOT resolves to <service>/skills
    expected = Path(__file__).resolve().parents[1] / "skills"
    assert DEFAULT_SKILLS_ROOT == expected
