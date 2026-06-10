"""EPIC A (MQ-A2/A3/A6/A7/A4) — new direction structured-HPO dimensions.

Pins:

1. MQ-A2: dc_cascade ladder variants ([8,4,2,1], [6,3,1.5], [4,2,1]) and
   dc_atr_period ∈ {7, 28} are represented in the seed roster.
2. MQ-A3: wider barrier grid — atr_barrier_mult ∈ {0.5, 3.0}, asymmetric
   triple-barrier (2,1)/(3,1)/(1,2) and tb_atr_period ∈ {7, 28} appear.
3. MQ-A6: composite-objective co-optimization seeds exist (auc_regime_weighted,
   rl_feature profile, and the combination) and only via the `composite:` block.
4. MQ-A7: feature-lane ablation seeds exist — an explicit all-lanes-off
   baseline, single-lane seeds, evidence paths for the gated lanes.
5. MQ-A4: meta-label isolation seeds exist.
6. Every seed patch passes validate_config_patch (knob surface approved).
7. Back-compat: a patch built without any new kwargs is byte-identical to the
   legacy patch shape (no stray keys → stable fingerprints).
"""
from __future__ import annotations

import json
import os
import sys
import types

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

try:  # the orchestrator imports Anthropic SDK at module load
    import anthropic  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover — only needed in slim test envs
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = _stub

from src.core.structured_hpo import (  # noqa: E402
    CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT,
    CURRENT_FEATURE_LIBRARY_VERSION,
    DIRECTION_HORIZON_FULL,
    SPECTRAL_FEATURE_EVIDENCE_REPORT,
    _direction_patch,
    _direction_trial_patches,
    validate_config_patch,
)


# --------------------------------------------------------------------------- #
# MQ-A2 — dc_cascade ladder / ATR period.
# --------------------------------------------------------------------------- #
def test_mqa2_dc_ladder_variants_in_seed_roster() -> None:
    patches = _direction_trial_patches()
    ladders = {
        tuple(p["dc_theta_atr_mults"])
        for p in patches
        if "dc_theta_atr_mults" in p
    }
    for expected in ((8.0, 4.0, 2.0, 1.0), (6.0, 3.0, 1.5), (4.0, 2.0, 1.0)):
        assert expected in ladders, (
            f"dc ladder {expected} missing — MQ-A2 seeds not wired. Found: {ladders}"
        )


def test_mqa2_dc_atr_period_band() -> None:
    patches = _direction_trial_patches()
    periods = {p["dc_atr_period"] for p in patches if "dc_atr_period" in p}
    assert {7, 28} <= periods, f"dc_atr_period band missing: {periods}"


# --------------------------------------------------------------------------- #
# MQ-A3 — wider barrier grid.
# --------------------------------------------------------------------------- #
def test_mqa3_vol_scaled_barrier_extremes() -> None:
    patches = _direction_trial_patches()
    mults = {
        p["atr_barrier_mult"]
        for p in patches
        if p.get("label_mode") == "vol_scaled"
    }
    assert {0.5, 3.0} <= mults, f"atr_barrier_mult extremes missing: {mults}"


def test_mqa3_asymmetric_triple_barrier_grid() -> None:
    patches = _direction_trial_patches()
    pairs = {
        (p["tb_pt_mult"], p["tb_sl_mult"])
        for p in patches
        if p.get("label_mode") == "triple_barrier"
    }
    for expected in ((2.0, 1.0), (3.0, 1.0), (1.0, 2.0)):
        assert expected in pairs, f"TB pair {expected} missing: {pairs}"


def test_mqa3_tb_atr_period_band() -> None:
    patches = _direction_trial_patches()
    periods = {p["tb_atr_period"] for p in patches if "tb_atr_period" in p}
    assert {7, 28} <= periods, f"tb_atr_period band missing: {periods}"


# --------------------------------------------------------------------------- #
# MQ-A6 — composite-objective co-optimization seeds.
# --------------------------------------------------------------------------- #
def test_mqa6_composite_block_seeds_present() -> None:
    patches = _direction_trial_patches()
    blocks = [p["composite"] for p in patches if "composite" in p]
    assert any(b.get("auc_regime_weighted") is True and "profile" not in b for b in blocks)
    assert any(b.get("profile") == "rl_feature" and "auc_regime_weighted" not in b for b in blocks)
    assert any(
        b.get("auc_regime_weighted") is True and b.get("profile") == "rl_feature"
        for b in blocks
    )


def test_mqa6_composite_seeds_pair_with_selective_subweight() -> None:
    patches = _direction_trial_patches()
    for p in patches:
        if "composite" in p:
            assert p.get("selective_auc_subweight") == 0.50, (
                "MQ-A6 seeds must co-optimize with the selective-AUC objective"
            )


# --------------------------------------------------------------------------- #
# MQ-A7 — feature-lane ablation seeds.
# --------------------------------------------------------------------------- #
def test_mqa7_all_lanes_off_baseline_present() -> None:
    patches = _direction_trial_patches()
    fcs = [p["feature_config"] for p in patches if "feature_config" in p]
    assert any(
        not any(v for k, v in fc.items() if k.endswith("_enabled")) for fc in fcs
    ), "explicit all-lanes-off ablation baseline missing"


def test_mqa7_single_lane_seeds_present() -> None:
    patches = _direction_trial_patches()
    fcs = [p["feature_config"] for p in patches if "feature_config" in p]

    def lanes_on(fc: dict) -> set[str]:
        return {k for k, v in fc.items() if k.endswith("_enabled") and v}

    singles = {frozenset(lanes_on(fc)) for fc in fcs if len(lanes_on(fc)) == 1}
    for lane in (
        "directional_change_features_enabled",
        "vdmc_enabled",
        "adaptive_levels_enabled",
        "spectral_features_enabled",
        "cross_asset_btc_enhanced_enabled",
        "funding_features_enabled",
    ):
        assert frozenset({lane}) in singles, f"single-lane ablation seed missing: {lane}"


def test_mqa7_evidence_gated_lanes_carry_canonical_paths() -> None:
    patches = _direction_trial_patches()
    for p in patches:
        fc = p.get("feature_config") or {}
        if fc.get("spectral_features_enabled"):
            assert fc.get("spectral_evidence_report_path") == SPECTRAL_FEATURE_EVIDENCE_REPORT
        if fc.get("cross_asset_btc_enhanced_enabled"):
            assert (
                fc.get("cross_asset_btc_enhanced_evidence_report_path")
                == CROSS_ASSET_BTC_ENHANCED_EVIDENCE_REPORT
            )


# --------------------------------------------------------------------------- #
# MQ-A4 — meta-label isolation seeds.
# --------------------------------------------------------------------------- #
def test_mqa4_meta_label_seeds_present() -> None:
    patches = _direction_trial_patches()
    metas = [p for p in patches if p.get("meta_label_enabled")]
    assert len(metas) >= 2, "meta-label isolation seeds missing"
    assert any(p.get("meta_label_pt_mult") == 1.5 for p in metas)


# --------------------------------------------------------------------------- #
# Knob surface + back-compat.
# --------------------------------------------------------------------------- #
def test_every_direction_seed_passes_knob_validation() -> None:
    for patch in _direction_trial_patches():
        validate_config_patch("direction", patch)  # must not raise


def test_new_kwargs_none_preserves_legacy_fingerprint() -> None:
    legacy_keys = {
        "direction_pct_threshold", "auto_select_horizon", "horizon_candidates",
        "roster_preset", "base_model_keys", "calibration_method",
        "stacking_calibration_method", "threshold_strategy", "threshold_beta",
        "max_signal_rate", "use_shared_feature_library",
        "feature_library_version", "log_feature_provenance",
        "validate_feature_consistency",
    }
    patch = _direction_patch(
        threshold=0.020,
        horizon=DIRECTION_HORIZON_FULL,
        roster="scoped_tabular",
        calibration="isotonic",
        beta=0.5,
        signal_cap=0.35,
        feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
    )
    assert set(patch) == legacy_keys, (
        "legacy patch fingerprint changed — None-skip discipline broken: "
        f"{sorted(set(patch) ^ legacy_keys)}"
    )
    json.dumps(patch, sort_keys=True)  # must stay JSON-serializable
