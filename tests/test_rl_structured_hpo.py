"""Server-owned RL HPO via materialized planned trials.

Option 2 from the HPO-workflow investigation: RL HPO is materialized by the
server as a bounded set of planned PPO-hyperparameter trials (one prepare.py
run each), exactly like direction/volatility — instead of the agent invoking
``prepare.py --hpo`` (which it reliably skipped). These tests cover the RL
trial generation, the nested deep-merge patch application, validation, and the
orchestrator enforcement gate.
"""
from __future__ import annotations

import yaml

from src.core.orchestrator import AgentOrchestrator, ResearchConfig
from src.core.structured_hpo import (
    apply_config_patch,
    build_structured_hpo_plan,
    materialize_planned_trials,
    validate_config_patch,
)


def _rl_plan(*, max_iterations=12, hpo_trials=8, enable_hpo=True):
    return build_structured_hpo_plan(
        research_id="res_rl_hpo",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        quick_mode=True,
        max_iterations=max_iterations,
        max_budget_usd=15.0,
        timeout_s=3600,
        enable_hpo=enable_hpo,
        hpo_trials=hpo_trials,
        hpo_timesteps=30000,
    )


# ---------------------------------------------------------------------------
# Trial generation
# ---------------------------------------------------------------------------


def test_rl_plan_materializes_trials_bounded_by_iterations() -> None:
    plan = _rl_plan(max_iterations=12, hpo_trials=8)
    assert plan["max_trials"] == 8
    assert len(plan["trials"]) == 8
    # bounded by max_iterations when smaller than the trial request
    tight = _rl_plan(max_iterations=3, hpo_trials=20)
    assert tight["max_trials"] == 3
    assert len(tight["trials"]) == 3


def test_rl_disabled_hpo_produces_no_trials() -> None:
    plan = _rl_plan(enable_hpo=False)
    assert plan["max_trials"] == 0
    assert plan["trials"] == []


def test_rl_trials_are_nested_training_patches_with_ppo_knobs() -> None:
    plan = _rl_plan()
    for trial in plan["trials"]:
        patch = trial["config_patch"]
        assert set(patch) == {"training"}
        training = patch["training"]
        assert "learning_rate" in training
        assert "target_kl" in training
        assert trial["search_phase"] == "hpo_screening"
        assert trial["trial_id"].startswith("trial_")
        assert "scripts/autotuner/rl/prepare.py" in trial["expected_command"]
        assert "--quick" in trial["expected_command"]
        assert trial["config_hash"]


def test_rl_trials_are_unique() -> None:
    plan = _rl_plan(max_iterations=40, hpo_trials=40)
    hashes = [t["config_hash"] for t in plan["trials"]]
    assert len(hashes) == len(set(hashes))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_accepts_good_rl_patch() -> None:
    validate_config_patch("rl", {"training": {"learning_rate": 3e-4, "target_kl": 0.04}})


def test_validate_rejects_unknown_rl_training_knob() -> None:
    import pytest

    with pytest.raises(ValueError, match="rl.training"):
        validate_config_patch("rl", {"training": {"bogus": 1}})


def test_validate_rejects_unknown_rl_section() -> None:
    import pytest

    with pytest.raises(ValueError, match="section"):
        validate_config_patch("rl", {"environment": {"fee_bps": 1}})


# ---------------------------------------------------------------------------
# Nested deep-merge patch application
# ---------------------------------------------------------------------------


def test_apply_patch_deep_merges_and_preserves_sibling_training_keys() -> None:
    base = {
        "training": {"total_timesteps": 500000, "seed": 42, "learning_rate": 0.001,
                     "target_kl": 0.02, "use_sde": True},
        "reward_weights": {"pnl": 1.0},
        "environment": {"trading_mode": "margin"},
    }
    patch = {"training": {"learning_rate": 0.0003, "target_kl": 0.05, "n_steps": 4096}}
    merged = apply_config_patch(base, patch)
    # patched
    assert merged["training"]["learning_rate"] == 0.0003
    assert merged["training"]["target_kl"] == 0.05
    assert merged["training"]["n_steps"] == 4096
    # siblings preserved
    assert merged["training"]["total_timesteps"] == 500000
    assert merged["training"]["seed"] == 42
    assert merged["training"]["use_sde"] is True
    # other sections untouched
    assert merged["reward_weights"] == {"pnl": 1.0}
    assert merged["environment"] == {"trading_mode": "margin"}
    # original not mutated
    assert base["training"]["learning_rate"] == 0.001


def test_materialize_rl_trials_writes_deep_merged_train_yaml(tmp_path) -> None:
    workspace = tmp_path / "rl"
    workspace.mkdir()
    (workspace / "train.yaml").write_text(
        yaml.safe_dump(
            {
                "instrument": "DOGE_USDT",
                "timeframe": "15m",
                "training": {"total_timesteps": 500000, "seed": 42,
                             "learning_rate": 0.001, "target_kl": 0.02},
                "reward_weights": {"pnl": 1.0},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    plan = _rl_plan(max_iterations=4, hpo_trials=4)
    written = materialize_planned_trials(plan, workspace)
    assert len(written) == 4
    trial = plan["trials"][0]
    trial_yaml = workspace / "planned_trials" / trial["trial_id"] / "train.yaml"
    assert trial_yaml.exists()
    payload = yaml.safe_load(trial_yaml.read_text(encoding="utf-8"))
    # PPO knobs from the patch applied
    assert payload["training"]["learning_rate"] == trial["config_patch"]["training"]["learning_rate"]
    # untouched base keys preserved by the deep merge
    assert payload["training"]["total_timesteps"] == 500000
    assert payload["training"]["seed"] == 42
    assert payload["reward_weights"] == {"pnl": 1.0}
    assert (workspace / "server_hpo_plan.json").exists()


# ---------------------------------------------------------------------------
# Orchestrator enforcement gate
# ---------------------------------------------------------------------------


def _cfg(model_type: str, enable_hpo: bool) -> ResearchConfig:
    return ResearchConfig(
        id="res_x",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type=model_type,
        tag="t",
        enable_hpo=enable_hpo,
    )


def test_structured_hpo_enforced_for_rl_with_hpo() -> None:
    assert AgentOrchestrator._structured_hpo_enforced(_cfg("rl", True)) is True
    assert AgentOrchestrator._structured_hpo_enforced(_cfg("rl", False)) is False
    assert AgentOrchestrator._structured_hpo_enforced(_cfg("direction", True)) is True
