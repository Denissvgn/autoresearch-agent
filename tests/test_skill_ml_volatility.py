"""ml-volatility skill manifest-vs-transitional parity tests (ARC-011 P2-012).

Asserts that the ``ManifestSkillRuntime`` built from
``skills/ml-volatility/SKILL.yaml`` (P2-009/010) reproduces the
``VolatilitySkillRuntime`` (P1-025) outputs. Mirrors ``test_skill_ml_direction``
(P2-008); the behavioral gate is the X-002 parity suite.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.orchestrator import ResearchConfig
from src.core.skill_manifest import ResearchSkillManifest
from src.core.skill_registry import DEFAULT_SKILLS_ROOT, SkillRegistry
from src.core.skill_runtime import (
    ManifestSkillRuntime,
    VolatilitySkillRuntime,
    materialize_skill_runtime,
)


class _StubSettings:
    mlflow_tracking_uri = "http://mlflow:5000"
    mlflow_service_url = "http://mlflow-svc:8000"
    data_ingest_url = "http://ingest:9000"
    ensemble_trainer_url = "http://ens:9001"
    rl_trainer_url = "http://rl:9002"
    feature_service_url = "http://feat:9003"
    inference_service_url = "http://inf:9004"
    host_configs_path = "/mnt/host_configs"


@pytest.fixture()
def manifest() -> ResearchSkillManifest:
    return SkillRegistry(settings_obj=_StubSettings()).get("ml-volatility")


@pytest.fixture()
def manifest_runtime(manifest: ResearchSkillManifest) -> ManifestSkillRuntime:
    orch = MagicMock()
    orch._load_claude_md.return_value = "# CLAUDE"
    orch._build_prompt.return_value = "directive"
    return ManifestSkillRuntime(manifest, orch)


@pytest.fixture()
def transitional_runtime() -> VolatilitySkillRuntime:
    return VolatilitySkillRuntime(MagicMock())


def test_skill_package_exists_on_disk():
    assert (DEFAULT_SKILLS_ROOT / "ml-volatility" / "SKILL.yaml").is_file()
    assert (DEFAULT_SKILLS_ROOT / "ml-volatility" / "SKILL.md").is_file()


def test_manifest_identity(manifest: ResearchSkillManifest):
    assert manifest.id == "ml-volatility"
    assert manifest.category == "optimization"


def test_materialize_by_skill_id_returns_manifest_runtime(monkeypatch):
    import src.core.skill_registry as sreg

    reg = SkillRegistry(settings_obj=_StubSettings())
    monkeypatch.setattr(sreg, "default_registry", reg)
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m",
        model_type="volatility", skill_id="ml-volatility",
    )
    rt = materialize_skill_runtime(MagicMock(), cfg)
    assert isinstance(rt, ManifestSkillRuntime)
    assert rt.skill_id == "ml-volatility"


def test_phase_plan_matches(manifest_runtime, transitional_runtime):
    """Manifest phase_plan reproduces VOLATILITY_PHASES ids + ordering."""
    m_ids = [p["id"] for p in manifest_runtime.phase_plan()]
    t_ids = [p["id"] for p in transitional_runtime.phase_plan()]
    assert m_ids == t_ids
    expected = [
        "baseline_capture", "atr_sweep", "threshold_calibration",
        "temporal_ensemble", "calibration_replay_gates",
        "multi_seed_robustness", "inference_parity_replay", "promotion_proposal",
    ]
    assert m_ids == expected


def test_command_policy_allowed_scripts_match(manifest_runtime, transitional_runtime):
    """Volatility narrows to setup.py + resume.py + volatility/prepare.py."""
    m = set(manifest_runtime.command_policy_extension().get("allowed_scripts", []))
    t = set(transitional_runtime.command_policy_extension().get("allowed_scripts", []))
    assert m == t
    assert "scripts/autotuner/volatility/prepare.py" in m
    assert "scripts/autotuner/direction/prepare.py" not in m


def test_phase_advancement_rule_matches(manifest_runtime, transitional_runtime):
    """Volatility-specific evidence keys (atr_mult_sweep_enabled etc.)."""
    for phase_id in ("atr_sweep", "threshold_calibration", "temporal_ensemble"):
        m = manifest_runtime.phase_advancement_rule(phase_id)
        t = transitional_runtime.phase_advancement_rule(phase_id)
        assert set(m["evidence_keys"]) == set(t["evidence_keys"]), phase_id


def test_parse_iteration_delimited_kv_matches(manifest_runtime, transitional_runtime):
    sample = "---\nstatus: ok\nprimary_metric: 0.68\nall_gates_passed: true\n---\n"
    assert manifest_runtime.parse_iteration(sample) == transitional_runtime.parse_iteration(sample)


def test_parse_iteration_json_marker_matches(manifest_runtime, transitional_runtime):
    sample = 'ITERATION_RESULT: {"status":"ok","primary_metric":0.68,"all_gates_passed":true}'
    assert manifest_runtime.parse_iteration(sample) == transitional_runtime.parse_iteration(sample)


def test_output_parser_format(manifest_runtime):
    from src.core.output_parser import DelimitedKVParser
    assert isinstance(manifest_runtime.output_parser(), DelimitedKVParser)


def test_promotion_target_is_file_path(manifest_runtime):
    from src.core.promotion_target import FilePathPromotionTarget
    assert isinstance(manifest_runtime.promotion_target(), FilePathPromotionTarget)


def test_structured_hpo_disabled_by_default(manifest_runtime):
    cfg = ResearchConfig(
        id="s", instrument="BTCUSD", timeframe="5m", model_type="volatility"
    )
    assert manifest_runtime.structured_hpo_plan(cfg) is None
