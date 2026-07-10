"""ml-direction skill manifest-vs-transitional parity tests (ARC-011 P2-008).

Asserts that the ``ManifestSkillRuntime`` built from
``skills/ml-direction/SKILL.yaml`` (P2-005/007) reproduces the
``DirectionSkillRuntime`` (P1-024) outputs across the data-driven surface:
``phase_plan``, ``command_policy_extension``, ``phase_advancement_rule``,
``parse_iteration``, parsers, identity. This is the equivalence contract that
makes the manifest-driven path a safe drop-in replacement for the transitional
runtime.

Mirrors ``test_skill_runtime_transitional.py`` (P1-028): contract tests pinning
the surface; the behavioral gate is the X-002 parity suite + the per-model-type
suites. Uses the same ``_FakeOrchestrator`` pattern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core.orchestrator import ResearchConfig
from src.core.skill_manifest import ResearchSkillManifest
from src.core.skill_registry import DEFAULT_SKILLS_ROOT, SkillRegistry
from src.core.skill_runtime import (
    DirectionSkillRuntime,
    ManifestSkillRuntime,
    materialize_skill_runtime,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StubSettings:
    """Settings stub exposing every attr the ml-direction manifest references."""

    mlflow_tracking_uri = "http://mlflow:5000"
    mlflow_service_url = "http://mlflow-svc:8000"
    data_ingest_url = "http://ingest:9000"
    ensemble_trainer_url = "http://ens:9001"
    rl_trainer_url = "http://rl:9002"
    feature_service_url = "http://feat:9003"
    host_configs_path = "/mnt/host_configs"


@pytest.fixture()
def manifest() -> ResearchSkillManifest:
    """The live ``skills/ml-direction/SKILL.yaml``, loaded + interpolated."""
    reg = SkillRegistry(settings_obj=_StubSettings())
    return reg.get("ml-direction")


@pytest.fixture()
def manifest_runtime(manifest: ResearchSkillManifest) -> ManifestSkillRuntime:
    """A ``ManifestSkillRuntime`` for ml-direction with a mock orchestrator."""
    orch = MagicMock()
    orch._load_claude_md.return_value = "# CLAUDE"
    orch._build_prompt.return_value = "directive"
    return ManifestSkillRuntime(manifest, orch)


@pytest.fixture()
def transitional_runtime() -> DirectionSkillRuntime:
    """A ``DirectionSkillRuntime`` with the same fake orchestrator shape."""
    return DirectionSkillRuntime(MagicMock())


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------


def test_skill_package_exists_on_disk():
    """P2-005/006: the live ``skills/ml-direction/`` package exists."""
    assert (DEFAULT_SKILLS_ROOT / "ml-direction" / "SKILL.yaml").is_file()
    assert (DEFAULT_SKILLS_ROOT / "ml-direction" / "SKILL.md").is_file()


def test_manifest_identity(manifest: ResearchSkillManifest):
    assert manifest.id == "ml-direction"
    assert manifest.category == "optimization"
    assert manifest.version == "1.0.0"


def test_materialize_by_skill_id_returns_manifest_runtime(monkeypatch):
    """``materialize_skill_runtime`` with ``skill_id="ml-direction"`` returns a
    ``ManifestSkillRuntime`` (not the transitional runtime)."""
    import src.core.skill_registry as sreg

    reg = SkillRegistry(settings_obj=_StubSettings())
    monkeypatch.setattr(sreg, "default_registry", reg)

    cfg = ResearchConfig(
        id="s1",
        instrument="BTCUSD",
        timeframe="5m",
        model_type="direction",
        skill_id="ml-direction",
    )
    rt = materialize_skill_runtime(MagicMock(), cfg)
    assert isinstance(rt, ManifestSkillRuntime)
    assert rt.skill_id == "ml-direction"


def test_materialize_without_skill_id_falls_back_to_transitional(monkeypatch):
    """Empty ``skill_id`` → transitional ``DirectionSkillRuntime`` (back-compat,
    per-skill reversible switchover)."""
    import src.core.skill_registry as sreg

    reg = SkillRegistry(settings_obj=_StubSettings())
    monkeypatch.setattr(sreg, "default_registry", reg)

    cfg = ResearchConfig(
        id="s2", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    rt = materialize_skill_runtime(MagicMock(), cfg)
    assert isinstance(rt, DirectionSkillRuntime)


# ---------------------------------------------------------------------------
# Equivalence: ManifestSkillRuntime reproduces DirectionSkillRuntime
# ---------------------------------------------------------------------------


def test_phase_plan_matches(manifest_runtime, transitional_runtime):
    """The manifest's phase_plan reproduces DIRECTION_PHASES' ids + ordering."""
    manifest_ids = [p["id"] for p in manifest_runtime.phase_plan()]
    transitional_ids = [p["id"] for p in transitional_runtime.phase_plan()]
    assert manifest_ids == transitional_ids
    # min/maxIterations preserved
    for mp, tp in zip(manifest_runtime.phase_plan(), transitional_runtime.phase_plan()):
        assert mp["min_iterations"] == tp["min_iterations"]
        assert mp["max_iterations"] == tp["max_iterations"]


def test_command_policy_allowed_scripts_match(manifest_runtime, transitional_runtime):
    """The manifest's allowed_scripts reproduces the transitional subset of
    ``_ALLOWED_SCRIPTS`` (setup.py + resume.py + direction/prepare.py)."""
    m = set(manifest_runtime.command_policy_extension().get("allowed_scripts", []))
    t = set(transitional_runtime.command_policy_extension().get("allowed_scripts", []))
    assert m == t
    assert "scripts/autotuner/direction/prepare.py" in m
    assert "scripts/autotuner/setup.py" in m


def test_phase_advancement_rule_matches(manifest_runtime, transitional_runtime):
    """Per-phase evidence keys from the manifest match _PHASE_ADVANCEMENT_KEYS."""
    # Pick a phase with known evidence keys.
    for phase_id in ("tabular_sweeps", "tsfm_sweeps", "calibration_replay_gates"):
        m = manifest_runtime.phase_advancement_rule(phase_id)
        t = transitional_runtime.phase_advancement_rule(phase_id)
        assert set(m["evidence_keys"]) == set(t["evidence_keys"]), phase_id


def test_parse_iteration_delimited_kv_matches(manifest_runtime, transitional_runtime):
    """Parsing a ``---`` delimited block yields identical results."""
    sample = "---\nstatus: ok\nprimary_metric: 0.7123\nall_gates_passed: true\n---\n"
    m = manifest_runtime.parse_iteration(sample)
    t = transitional_runtime.parse_iteration(sample)
    assert m == t
    assert m is not None
    assert m["status"] == "ok"


def test_parse_iteration_json_marker_matches(manifest_runtime, transitional_runtime):
    """Parsing an ``ITERATION_RESULT:`` JSON-line marker yields identical results."""
    sample = 'ITERATION_RESULT: {"status":"ok","primary_metric":0.65,"all_gates_passed":true}'
    m = manifest_runtime.parse_iteration(sample)
    t = transitional_runtime.parse_iteration(sample)
    assert m == t


def test_output_parser_format(manifest_runtime):
    """ml-direction uses the delimited_kv parser."""
    from src.core.output_parser import DelimitedKVParser

    assert isinstance(manifest_runtime.output_parser(), DelimitedKVParser)


def test_iteration_marker_parser_format(manifest_runtime):
    from src.core.output_parser import JSONMarkerParser

    assert isinstance(manifest_runtime.iteration_marker_parser(), JSONMarkerParser)


def test_parse_iteration_nonce_ignored(manifest_runtime):
    """D2: session_nonce is accepted but ignored (no nonce validation today)."""
    sample = "---\nstatus: ok\nprimary_metric: 0.5\nall_gates_passed: true\n---\n"
    without = manifest_runtime.parse_iteration(sample)
    with_nonce = manifest_runtime.parse_iteration(sample, session_nonce=b"abc")
    assert without == with_nonce


def test_promotion_target_is_file_path(manifest_runtime):
    """Development-scope promotion is a ``FilePathPromotionTarget`` (P1-015)."""
    from src.core.promotion_target import FilePathPromotionTarget

    assert isinstance(manifest_runtime.promotion_target(), FilePathPromotionTarget)


def test_preflight_checks_built_from_manifest(manifest_runtime):
    """Preflight checks are built from the manifest's preflight section
    (6 http_health entries for direction)."""
    checks = manifest_runtime.preflight_checks()
    names = [getattr(c, "name", None) for c in checks]
    # The manifest declares 6 http_health targets for ml-direction.
    assert "mlflow_tracking" in names
    assert "feature_service" in names


def test_structured_hpo_disabled_by_default(manifest_runtime):
    """structured_hpo.enabled=false in the manifest; plan is None unless
    config.enable_hpo is also true."""
    cfg = ResearchConfig(
        id="s", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    assert manifest_runtime.structured_hpo_plan(cfg) is None


def test_decision_vocabulary_success_values(manifest: ResearchSkillManifest):
    """G8: success_values declares {keep, improve, hpo_screening}."""
    assert set(manifest.decision_vocabulary.success_values) == {
        "keep",
        "improve",
        "hpo_screening",
    }


def test_metric_schema_primary(manifest: ResearchSkillManifest):
    """The primary metric is walkforward_mean_auc, higher_is_better."""
    assert manifest.metric_schema.primary.field == "primary_metric"
    assert manifest.metric_schema.primary.direction == "higher_is_better"
