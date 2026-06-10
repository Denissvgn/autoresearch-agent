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


def _rl_plan(*, max_iterations=12, hpo_trials=8, enable_hpo=True, trading_mode=None):
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
        trading_mode=trading_mode,
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
        # training + gate always present; reward_weights (E3) optional.
        assert {"training", "direction_confidence_gate"} <= set(patch)
        assert set(patch) <= {"training", "direction_confidence_gate", "reward_weights"}
        training = patch["training"]
        assert "learning_rate" in training
        assert "target_kl" in training
        assert trial["search_phase"] == "hpo_screening"
        assert trial["trial_id"].startswith("trial_")
        assert "scripts/autotuner/rl/prepare.py" in trial["expected_command"]
        assert "--quick" in trial["expected_command"]
        assert trial["config_hash"]


def test_rl_leading_trials_are_an_isolated_gate_sweep() -> None:
    """PnL-E1: the first 5 trials fix the PPO baseline and vary ONLY the hard
    selectivity gate, so its effect on post-cost return / turnover is isolated."""
    plan = _rl_plan(max_iterations=12, hpo_trials=12)
    lead = plan["trials"][:5]
    gates = [t["config_patch"]["direction_confidence_gate"] for t in lead]
    assert gates == [0.0, 0.05, 0.10, 0.20, 0.30]
    # PPO baseline identical across the sweep (only the gate moves)
    ppos = {tuple(sorted(t["config_patch"]["training"].items())) for t in lead}
    assert len(ppos) == 1
    # gate is encoded in the trial id
    assert lead[1]["trial_id"].endswith("_g5")
    assert lead[4]["trial_id"].endswith("_g30")


def test_rl_e3_reward_sweep_is_isolated_at_fixed_gate() -> None:
    """PnL-E3: trials 6-7 hold the PPO baseline + the moderate gate fixed and
    vary ONLY the turnover/holding reward shaping, isolating its effect. The
    default DOGE base is stock (long-only) so the inert flip term is dropped."""
    plan = _rl_plan(max_iterations=20, hpo_trials=20)  # default = stock
    block_b = plan["trials"][5:7]
    for t in block_b:
        assert t["config_patch"]["direction_confidence_gate"] == 0.10
        assert "reward_weights" in t["config_patch"]
    rws = [t["config_patch"]["reward_weights"] for t in block_b]
    assert rws[0] == {"trade": 0.010, "hold": 0.0}
    assert rws[1] == {"trade": 0.020, "hold": 0.0}
    # reward profile encoded in the trial id (by the trade penalty)
    assert block_b[0]["trial_id"].endswith("_g10_t10")
    assert block_b[1]["trial_id"].endswith("_g10_t20")


def test_rl_combined_grid_applies_gate_and_low_turnover_reward() -> None:
    """Block C (PPO grid) runs under BOTH E1 (gate) and E3 (low-turnover reward)
    — the Sprint-1 'together' regime (stock default → no inert flip term)."""
    plan = _rl_plan(max_iterations=20, hpo_trials=20)  # default = stock
    grid = plan["trials"][7:]
    assert grid, "expected PPO-grid trials beyond the isolation blocks"
    for t in grid:
        cp = t["config_patch"]
        assert cp["direction_confidence_gate"] == 0.10
        assert cp["reward_weights"] == {"trade": 0.010, "hold": 0.0}


def test_rl_stock_mode_drops_inert_flip_term() -> None:
    """Stock mode is long-only: no reward_weights patch may carry the inert flip
    term, so no two trials differ only by a knob that cannot change the result."""
    plan = _rl_plan(max_iterations=20, hpo_trials=20, trading_mode="stock")
    for t in plan["trials"]:
        rw = t["config_patch"].get("reward_weights")
        if rw is not None:
            assert "flip" not in rw, f"stock-mode trial {t['trial_id']} carries flip"
    # the published search space also drops the inert flip dimension
    assert "reward_weights.flip" not in plan["search_space"]


def test_rl_margin_mode_retains_flip_term() -> None:
    """Margin mode has real long↔short flips, so the flip term stays tunable in
    both the reward profiles and the published search space."""
    plan = _rl_plan(max_iterations=20, hpo_trials=20, trading_mode="margin")
    block_b = plan["trials"][5:7]
    rws = [t["config_patch"]["reward_weights"] for t in block_b]
    assert rws[0] == {"trade": 0.010, "flip": 0.005, "hold": 0.0}
    assert rws[1] == {"trade": 0.020, "flip": 0.010, "hold": 0.0}
    assert "reward_weights.flip" in plan["search_space"]


def test_rl_validate_rejects_unknown_reward_knob() -> None:
    import pytest
    validate_config_patch("rl", {"training": {}, "reward_weights": {"trade": 0.01, "hold": 0.0}})
    with pytest.raises(ValueError, match="reward_weights"):
        validate_config_patch("rl", {"training": {}, "reward_weights": {"bogus_rw": 1}})


def test_materialize_rl_trial_merges_reward_weights(tmp_path) -> None:
    workspace = tmp_path / "rl"
    workspace.mkdir()
    (workspace / "train.yaml").write_text(
        yaml.safe_dump(
            {"training": {"total_timesteps": 500000},
             "direction_confidence_gate": 0.0,
             "reward_weights": {"pnl": 1.0, "sharpe": 0.5, "trade": 0.002,
                                "flip": 0.001, "hold": 0.001}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    # margin mode keeps the flip term so the deep-merge of a partial reward
    # override (including flip) is exercised end-to-end.
    plan = _rl_plan(max_iterations=7, hpo_trials=7, trading_mode="margin")
    materialize_planned_trials(plan, workspace)
    t = plan["trials"][5]  # first E3 reward trial (lowturn)
    payload = yaml.safe_load(
        (workspace / "planned_trials" / t["trial_id"] / "train.yaml").read_text()
    )
    rw = payload["reward_weights"]
    assert rw["trade"] == 0.010 and rw["flip"] == 0.005 and rw["hold"] == 0.0
    # untouched reward keys preserved by the deep merge
    assert rw["pnl"] == 1.0 and rw["sharpe"] == 0.5


def test_rl_validate_accepts_gate_scalar_rejects_unknown_top_level() -> None:
    import pytest
    validate_config_patch("rl", {"training": {"learning_rate": 3e-4},
                                 "direction_confidence_gate": 0.1})
    with pytest.raises(ValueError, match="section"):
        validate_config_patch("rl", {"training": {}, "bogus_top": 1})


def test_materialize_rl_trial_applies_top_level_gate(tmp_path) -> None:
    workspace = tmp_path / "rl"
    workspace.mkdir()
    (workspace / "train.yaml").write_text(
        yaml.safe_dump(
            {"training": {"total_timesteps": 500000, "learning_rate": 0.001},
             "direction_confidence_gate": 0.0, "reward_weights": {"pnl": 1.0}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    plan = _rl_plan(max_iterations=5, hpo_trials=5)  # leading gate sweep
    materialize_planned_trials(plan, workspace)
    # trial 4 (index 3) is gate=0.20 in the recentred sweep
    t = plan["trials"][3]
    payload = yaml.safe_load(
        (workspace / "planned_trials" / t["trial_id"] / "train.yaml").read_text()
    )
    assert payload["direction_confidence_gate"] == 0.20
    assert payload["training"]["total_timesteps"] == 500000  # sibling preserved


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


def test_training_command_timeout_is_floored_above_agent_undersetting() -> None:
    """A prepare.py training run must not be killed below the 2h default no matter
    what timeout_s the agent sets — the guardrail that prevents losing the first
    trial of a sweep to an under-set 1800s bash timeout."""
    eff = AgentOrchestrator._effective_tool_timeout
    train_cmd = (
        "cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py "
        "--config runs/.../trial_001/train.yaml --quick"
    )
    # Agent under-sets 1800s → floored to the 2h training floor.
    assert eff({"command": train_cmd, "timeout_s": 1800}) == 7200
    # No timeout_s → default 2h.
    assert eff({"command": train_cmd}) == 7200
    # Agent sets a HIGHER value (e.g. full-mode) → honored, not lowered.
    assert eff({"command": train_cmd, "timeout_s": 10000}) == 10000
    # The legacy --hpo study path is NOT floored (different lifecycle).
    assert eff({"command": train_cmd.replace("--quick", "--hpo"),
                "timeout_s": 1800}) == 1800
    # Non-training commands keep the small 900s floor.
    assert eff({"command": "ls -la", "timeout_s": 100}) == 900
    assert eff({"command": ".venv/bin/python scripts/autotuner/enrich_rl_dataset.py",
                "timeout_s": 1800}) == 1800
