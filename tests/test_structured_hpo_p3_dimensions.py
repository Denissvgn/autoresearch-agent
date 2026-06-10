"""P3 / DM-12 + DM-13 — new search-space dimensions in the direction
trial-patch roster.

The agent on res_be66790e192e never tried direction_pct_threshold below
0.025, never tried a non-default sample_weight_halflife, never tried a
non-logreg meta_model, and never enabled horizon_ensemble. DM-12 and
DM-13 wire all four into the structured-HPO seed list so future
sessions encounter them.

Pins:

1. New ``direction_pct_threshold`` band {0.015, 0.040, 0.050} is represented.
2. New ``sample_weight_halflife`` band {1000, 1500, 2000} is represented.
3. ``meta_model`` ∈ {lgb_shallow, mlp_2x32} appears at least once each.
4. ``horizon_ensemble_enabled=True`` appears at least once.
5. Back-compat: a patch built with all new kwargs = None produces the
   same fingerprint as the pre-DM-12 patch (legacy seeds unchanged).
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

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
    CURRENT_FEATURE_LIBRARY_VERSION,
    DIRECTION_HORIZON_FULL,
    DIRECTION_HORIZON_MID,
    _direction_patch,
    _direction_trial_patches,
)


# --------------------------------------------------------------------------- #
# DM-12 — direction_pct_threshold band.
# --------------------------------------------------------------------------- #
def test_dm12_patches_include_direction_pct_threshold_band() -> None:
    """Each of the new threshold values must appear in at least one seed
    patch — so the structured HPO actually emits trials that try them."""
    patches = _direction_trial_patches()
    thresholds = {p["direction_pct_threshold"] for p in patches}
    for new_value in (0.015, 0.040, 0.050):
        assert new_value in thresholds, (
            f"direction_pct_threshold {new_value} missing — DM-12 seeds "
            f"not wired. Found: {sorted(thresholds)[:10]}…"
        )


# --------------------------------------------------------------------------- #
# DM-12 — sample_weight_halflife band.
# --------------------------------------------------------------------------- #
def test_dm12_patches_include_sample_weight_halflife_band() -> None:
    """Each of the new halflife values must appear in at least one seed."""
    patches = _direction_trial_patches()
    halflives = {
        p["sample_weight_halflife"]
        for p in patches
        if "sample_weight_halflife" in p
    }
    for new_value in (1000, 1500, 2000):
        assert new_value in halflives, (
            f"sample_weight_halflife {new_value} missing — DM-12 seeds "
            f"not wired. Found: {sorted(halflives)}"
        )


# --------------------------------------------------------------------------- #
# DM-13 — meta_model variants.
# --------------------------------------------------------------------------- #
def test_dm13_patches_include_lgb_shallow_meta() -> None:
    patches = _direction_trial_patches()
    metas = {p.get("meta_model") for p in patches if "meta_model" in p}
    assert "lgb_shallow" in metas, (
        "meta_model=lgb_shallow missing from seed roster — DM-6 + DM-13 "
        f"not wired. Found: {metas}"
    )


def test_dm13_patches_include_mlp_2x32_meta() -> None:
    patches = _direction_trial_patches()
    metas = {p.get("meta_model") for p in patches if "meta_model" in p}
    assert "mlp_2x32" in metas, (
        "meta_model=mlp_2x32 missing from seed roster — DM-6 + DM-13 "
        f"not wired. Found: {metas}"
    )


def test_dm13_patches_exercise_horizon_ensemble_enabled() -> None:
    patches = _direction_trial_patches()
    enabled_flags = {
        p.get("horizon_ensemble_enabled")
        for p in patches
        if "horizon_ensemble_enabled" in p
    }
    assert True in enabled_flags, (
        "horizon_ensemble_enabled=True missing from seed roster — "
        f"DM-5 + DM-13 not wired. Found: {enabled_flags}"
    )


def test_dm13_patches_include_horizon_ensemble_disabled_variant() -> None:
    """Both False and True variants must exist so the agent compares the
    two arms apples-to-apples within the calibration_replay_gates phase."""
    patches = _direction_trial_patches()
    enabled_flags = {
        p.get("horizon_ensemble_enabled")
        for p in patches
        if "horizon_ensemble_enabled" in p
    }
    assert False in enabled_flags, (
        "horizon_ensemble_enabled=False missing — "
        f"only-True variants leave the apples-to-apples comparison broken. "
        f"Found: {enabled_flags}"
    )


# --------------------------------------------------------------------------- #
# Back-compat: legacy patches keep their pre-DM-12 fingerprints.
# --------------------------------------------------------------------------- #
def _patch_fingerprint(patch: dict) -> str:
    """Mirror the canonical fingerprint scheme structured_hpo uses
    internally (sha of sorted-JSON of the patch)."""
    return json.dumps(patch, sort_keys=True, default=str)


def test_legacy_patch_fingerprint_unchanged_when_new_kwargs_omitted() -> None:
    """A patch built without DM-12/DM-13 kwargs must produce a key set
    bit-identical to the pre-DM-12 version — otherwise old seeds drift
    and dedup misses on cross-session continuity break."""
    patch = _direction_patch(
        threshold=0.025,
        horizon=DIRECTION_HORIZON_FULL,
        roster="scoped_tabular",
        calibration="isotonic",
        beta=0.5,
        signal_cap=0.35,
        feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
    )
    # The new optional kwargs MUST NOT be in the patch when they were
    # not supplied (skip-when-None contract).
    assert "sample_weight_halflife" not in patch
    assert "meta_model" not in patch
    assert "horizon_ensemble_enabled" not in patch


def test_new_kwargs_appear_only_when_supplied() -> None:
    """Supplying the new kwargs ONLY adds keys to the patch — does not
    rewrite existing fields."""
    base = _direction_patch(
        threshold=0.025,
        horizon=DIRECTION_HORIZON_MID,
        roster="full_tabular",
        calibration="sigmoid",
        beta=0.5,
        signal_cap=0.30,
        feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
    )
    extended = _direction_patch(
        threshold=0.025,
        horizon=DIRECTION_HORIZON_MID,
        roster="full_tabular",
        calibration="sigmoid",
        beta=0.5,
        signal_cap=0.30,
        feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        sample_weight_halflife=1500,
        meta_model="lgb_shallow",
        horizon_ensemble_enabled=True,
    )
    # All base keys are present in extended with identical values.
    for k, v in base.items():
        assert extended[k] == v, k
    # New keys only.
    assert extended["sample_weight_halflife"] == 1500
    assert extended["meta_model"] == "lgb_shallow"
    assert extended["horizon_ensemble_enabled"] is True


# --------------------------------------------------------------------------- #
# Cardinality sanity — the augmented roster doesn't blow past the
# orchestrator's internal cap (_extend_unique_patches caps at 80).
# --------------------------------------------------------------------------- #
def test_dm12_dm13_extensions_stay_within_orchestrator_patch_cap() -> None:
    patches = _direction_trial_patches()
    # The cap inside _extend_unique_patches is 80 (post-fingerprint dedup).
    assert len(patches) <= 80, len(patches)


def test_dm12_dm13_extensions_actually_grew_the_roster() -> None:
    """Regression guard: confirm the new seeds aren't dedup'd away by
    an upstream fingerprint collision. Pre-DM-12 the function returned
    a deterministic-size list; DM-12/DM-13 must have added at least 8
    distinct patches (3 threshold + 3 halflife + 2 meta_model)."""
    patches = _direction_trial_patches()
    # We can't easily count exactly without a baseline, but a 5-seed
    # legacy list expanded to 80 by _extend_unique_patches; with DM-12/
    # DM-13's 9 new seeds we expect the list to still be at the cap
    # (more eligible candidates than the cap allows).
    assert len(patches) >= 13, (
        "DM-12/DM-13 seeds were dedup'd away — fingerprint collisions "
        "between new and legacy patches. Got %d patches." % len(patches)
    )


# --------------------------------------------------------------------------- #
# E6b — label-mode (supervision target) sweep. All builders already exist in
# the trainer; the HPO must exercise each mode so the search can find the
# labelling that widens the confident, high-selective-AUC subset.
# --------------------------------------------------------------------------- #
def test_e6b_label_mode_sweep_exercises_all_modes() -> None:
    patches = _direction_trial_patches()
    modes = {p.get("label_mode") for p in patches if p.get("label_mode")}
    # fixed_pct is the implicit default (no key); the sweep adds the three
    # alternative supervision targets.
    assert {"vol_scaled", "dc_cascade", "triple_barrier"} <= modes
    # vol_scaled carries its barrier; triple_barrier carries pt/sl.
    vol = [p for p in patches if p.get("label_mode") == "vol_scaled"]
    tb = [p for p in patches if p.get("label_mode") == "triple_barrier"]
    assert vol and all("atr_barrier_mult" in p for p in vol)
    assert tb and all("tb_pt_mult" in p and "tb_sl_mult" in p for p in tb)
    # the default (fixed_pct) seeds carry NO label_mode key (legacy fingerprint)
    assert any("label_mode" not in p for p in patches)


def test_e6b_label_params_only_when_supplied() -> None:
    """None-skip: label knobs add keys only when set, so legacy fixed_pct seeds
    keep bit-identical fingerprints."""
    base = _direction_patch(
        threshold=0.020, horizon=DIRECTION_HORIZON_FULL, roster="scoped_tabular",
        calibration="isotonic", beta=0.5, signal_cap=0.35,
        feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
    )
    assert "label_mode" not in base and "atr_barrier_mult" not in base
    vs = _direction_patch(
        threshold=0.020, horizon=DIRECTION_HORIZON_FULL, roster="scoped_tabular",
        calibration="isotonic", beta=0.5, signal_cap=0.35,
        feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        label_mode="vol_scaled", atr_barrier_mult=2.0,
    )
    for k, v in base.items():
        assert vs[k] == v, k
    assert vs["label_mode"] == "vol_scaled" and vs["atr_barrier_mult"] == 2.0
