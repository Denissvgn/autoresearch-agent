"""ml-rl skill manifest-vs-transitional parity tests (ARC-011 P2-016).

Asserts that the ``ManifestSkillRuntime`` built from ``skills/ml-rl/SKILL.yaml``
(P2-013/014) reproduces the ``RLSkillRuntime`` (P1-026) outputs, including the
HPO path. Mirrors ``test_skill_ml_direction`` (P2-008); the behavioral gate is
the X-002 parity suite (the ``legacy_rl_with_hpo.json`` fixture covers the RL
HPO session-start shape).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.orchestrator import ResearchConfig
from src.core.skill_manifest import ResearchSkillManifest
from src.core.skill_registry import DEFAULT_SKILLS_ROOT, SkillRegistry
from src.core.skill_runtime import (
    ManifestSkillRuntime,
    RLSkillRuntime,
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
    return SkillRegistry(settings_obj=_StubSettings()).get("ml-rl")


@pytest.fixture()
def manifest_runtime(manifest: ResearchSkillManifest) -> ManifestSkillRuntime:
    orch = MagicMock()
    orch._load_claude_md.return_value = "# CLAUDE"
    orch._build_prompt.return_value = "directive"
    return ManifestSkillRuntime(manifest, orch)


@pytest.fixture()
def transitional_runtime() -> RLSkillRuntime:
    return RLSkillRuntime(MagicMock())


def test_skill_package_exists_on_disk():
    assert (DEFAULT_SKILLS_ROOT / "ml-rl" / "SKILL.yaml").is_file()
    assert (DEFAULT_SKILLS_ROOT / "ml-rl" / "SKILL.md").is_file()


def test_manifest_identity(manifest: ResearchSkillManifest):
    assert manifest.id == "ml-rl"
    assert manifest.category == "optimization"


def test_materialize_by_skill_id_returns_manifest_runtime(monkeypatch):
    import src.core.skill_registry as sreg

    reg = SkillRegistry(settings_obj=_StubSettings())
    monkeypatch.setattr(sreg, "default_registry", reg)
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m",
        model_type="rl", skill_id="ml-rl",
    )
    rt = materialize_skill_runtime(MagicMock(), cfg)
    assert isinstance(rt, ManifestSkillRuntime)
    assert rt.skill_id == "ml-rl"


def test_phase_plan_matches_fallback_phases(manifest_runtime, transitional_runtime):
    """RL uses FALLBACK_PHASES (not a non-existent RL_PHASES — AC-deviation).
    The manifest reproduces the 4-phase plan: baseline_capture, hpo_screening,
    validation, promotion_proposal."""
    m_ids = [p["id"] for p in manifest_runtime.phase_plan()]
    t_ids = [p["id"] for p in transitional_runtime.phase_plan()]
    assert m_ids == t_ids
    assert m_ids == ["baseline_capture", "hpo_screening", "validation", "promotion_proposal"]


def test_command_policy_includes_rl_specific_scripts(manifest_runtime, transitional_runtime):
    """RL adds enrich_rl_dataset.py in addition to setup/resume/rl-prepare."""
    m = set(manifest_runtime.command_policy_extension().get("allowed_scripts", []))
    t = set(transitional_runtime.command_policy_extension().get("allowed_scripts", []))
    assert m == t
    assert "scripts/autotuner/rl/prepare.py" in m
    assert "scripts/autotuner/enrich_rl_dataset.py" in m


def test_validation_phase_has_rl_oos_evidence_keys(manifest):
    """The `validation` phase carries the RL_OOS_EVIDENCE_KEYS (the one place RL
    diverges — the phases.py plugin additionally requires ≥2 iterations carrying
    one of these keys; _completed_phase_ids:543-548)."""
    validation = next(p for p in manifest.phase_plan if p.id == "validation")
    for key in ("mean_oos_sharpe", "rl_profit_score", "oos_sharpe", "trading_score"):
        assert key in validation.evidence_keys


def test_param_schema_includes_rl_only_fields(manifest):
    """RL declares trading_mode/agent_strategy/initial_balance that
    direction/volatility omit."""
    props = manifest.param_schema.properties
    assert "trading_mode" in props
    assert "agent_strategy" in props
    assert "initial_balance" in props


def test_parse_iteration_delimited_kv_matches(manifest_runtime, transitional_runtime):
    sample = "---\nstatus: ok\nprimary_metric: 1.23\nall_gates_passed: true\n---\n"
    assert manifest_runtime.parse_iteration(sample) == transitional_runtime.parse_iteration(sample)


def test_parse_iteration_json_marker_matches(manifest_runtime, transitional_runtime):
    sample = 'ITERATION_RESULT: {"status":"ok","primary_metric":1.23,"all_gates_passed":true}'
    assert manifest_runtime.parse_iteration(sample) == transitional_runtime.parse_iteration(sample)


def test_output_parser_format(manifest_runtime):
    from src.core.output_parser import DelimitedKVParser
    assert isinstance(manifest_runtime.output_parser(), DelimitedKVParser)


def test_promotion_target_is_file_path(manifest_runtime):
    from src.core.promotion_target import FilePathPromotionTarget
    assert isinstance(manifest_runtime.promotion_target(), FilePathPromotionTarget)


def test_structured_hpo_disabled_by_default(manifest_runtime):
    """structured_hpo.enabled=false; plan is None unless config.enable_hpo."""
    cfg = ResearchConfig(
        id="s", instrument="BTCUSD", timeframe="5m", model_type="rl"
    )
    assert manifest_runtime.structured_hpo_plan(cfg) is None


def test_structured_hpo_enabled_when_config_opts_in(manifest_runtime, monkeypatch):
    """When config.enable_hpo=True and the manifest declares structured_hpo,
    the plan is built (delegates to build_structured_hpo_plan — RL is the primary
    HPO consumer). The legacy_rl_with_hpo parity fixture covers this path."""
    import src.core.structured_hpo as hpo

    monkeypatch.setattr(hpo, "build_structured_hpo_plan", lambda **kw: {"planned": True})
    cfg = ResearchConfig(
        id="s", instrument="BTCUSD", timeframe="5m", model_type="rl",
        enable_hpo=True, hpo_trials=10, hpo_timesteps=20000,
    )
    plan = manifest_runtime.structured_hpo_plan(cfg)
    assert plan == {"planned": True}
