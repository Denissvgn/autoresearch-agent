"""Gap 1 — server-side derivation of phase-advancement markers from
salient-knob diffs vs the baseline iter's config_snapshot.

After Issue 10A narrowed ``_PHASE_ADVANCEMENT_KEYS`` to deliberate-exploration
markers (``tabular_sweep_variant`` etc.), live evidence (``res_baf6605ce94f``)
showed the agent ignored the prompt instruction to emit those keys, falling
through to the slow >=6 cardinality fallback. ``derive_exploration_markers``
auto-injects the marker from any salient-knob diff vs baseline so the fast
key-path fires whenever the agent actually explores.
"""
from __future__ import annotations

from src.core.iteration_context import derive_exploration_markers

# --- Direction: any direction-salient knob diff → tabular_sweep_variant -- #


def test_direction_no_diff_returns_empty() -> None:
    """Baseline iter (current == baseline) yields no markers — the phase
    plan's key check sees nothing and the cardinality fallback rules.
    """
    cfg = {"direction_pct_threshold": 0.03, "roster_preset": "default"}
    assert derive_exploration_markers("direction", cfg, cfg) == {}


def test_direction_pct_threshold_diff_emits_tabular_variant() -> None:
    cur = {"direction_pct_threshold": 0.04}
    base = {"direction_pct_threshold": 0.03}
    markers = derive_exploration_markers("direction", cur, base)
    assert markers == {"tabular_sweep_variant": "direction_pct_threshold=0.04"}


def test_direction_multiple_diffs_concatenate() -> None:
    """Two salient knob diffs produce a single variant value combining
    them (so the digest can show both)."""
    cur = {"direction_pct_threshold": 0.04, "roster_preset": "v2"}
    base = {"direction_pct_threshold": 0.03, "roster_preset": "v1"}
    markers = derive_exploration_markers("direction", cur, base)
    val = markers["tabular_sweep_variant"]
    assert "direction_pct_threshold=0.04" in val
    assert "roster_preset=v2" in val
    assert "+" in val


def test_direction_non_salient_knob_diff_ignored() -> None:
    """A knob NOT in _KNOB_TO_MARKER must not produce a marker."""
    cur = {"unrelated_knob": 99}
    base = {"unrelated_knob": 1}
    assert derive_exploration_markers("direction", cur, base) == {}


def test_direction_none_current_value_treated_as_no_diff() -> None:
    """When the current config doesn't carry a knob (None), we skip it.
    Prevents false positives when prepare.py omits a default knob."""
    cur = {"direction_pct_threshold": None}
    base = {"direction_pct_threshold": 0.03}
    assert derive_exploration_markers("direction", cur, base) == {}


# --- Direction: nested feature_config lane toggles ---------------------- #


def test_direction_feature_lane_toggle_emits_tabular_variant() -> None:
    """Flipping a nested feature_config lane is a deliberate feature-set
    change → credited as a tabular_sweep_variant so the phase advances and the
    iter is not treated as a no-op/duplicate. The variant label drops the
    nesting prefix for readability."""
    cur = {"feature_config": {"directional_change_features_enabled": True}}
    base = {"feature_config": {"directional_change_features_enabled": False}}
    markers = derive_exploration_markers("direction", cur, base)
    assert markers == {"tabular_sweep_variant": "directional_change_features_enabled=True"}


def test_direction_feature_lane_absent_in_baseline_counts_as_diff() -> None:
    """Baseline omits the lane key entirely (the common case — only funding is
    set by default); enabling it should still register as a diff."""
    cur = {"feature_config": {"vdmc_enabled": True}}
    base = {"feature_config": {"funding_features_enabled": True}}
    markers = derive_exploration_markers("direction", cur, base)
    assert markers == {"tabular_sweep_variant": "vdmc_enabled=True"}


def test_direction_feature_config_unchanged_returns_empty() -> None:
    cfg = {"feature_config": {"funding_features_enabled": True, "vdmc_enabled": False}}
    assert derive_exploration_markers("direction", cfg, cfg) == {}


def test_direction_meta_model_is_no_longer_salient() -> None:
    """meta_model was pruned from the knob map: serving is Option A (best base
    learner), so the meta-stacker it controls is never served and changing it
    must not credit a phase advance."""
    cur = {"meta_model": "rf"}
    base = {"meta_model": "logreg"}
    assert derive_exploration_markers("direction", cur, base) == {}


# --- Volatility: knobs map to three distinct marker keys ---------------- #


def test_volatility_atr_diff_emits_atr_mult_sweep_enabled() -> None:
    cur = {"volatility_atr_mult": 2.5}
    base = {"volatility_atr_mult": 2.0}
    markers = derive_exploration_markers("volatility", cur, base)
    assert markers == {"atr_mult_sweep_enabled": "volatility_atr_mult=2.5"}


def test_volatility_threshold_diff_emits_threshold_attempt_id() -> None:
    cur = {"threshold_strategy": "rolling"}
    base = {"threshold_strategy": "fixed"}
    markers = derive_exploration_markers("volatility", cur, base)
    assert "threshold_calibration_attempt_id" in markers


def test_volatility_temporal_diff_emits_temporal_attempt_id() -> None:
    cur = {"sample_weight_halflife": 8000}
    base = {"sample_weight_halflife": 6000}
    markers = derive_exploration_markers("volatility", cur, base)
    assert "temporal_ensemble_attempt_id" in markers


def test_volatility_multi_family_diff_emits_three_keys() -> None:
    """An iteration that changes knobs spanning all three volatility
    sub-phases produces all three marker keys."""
    cur = {
        "volatility_atr_mult": 2.5,
        "threshold_strategy": "rolling",
        "sample_weight_halflife": 8000,
    }
    base = {
        "volatility_atr_mult": 2.0,
        "threshold_strategy": "fixed",
        "sample_weight_halflife": 6000,
    }
    markers = derive_exploration_markers("volatility", cur, base)
    assert set(markers.keys()) == {
        "atr_mult_sweep_enabled",
        "threshold_calibration_attempt_id",
        "temporal_ensemble_attempt_id",
    }


# --- Defensive paths ---------------------------------------------------- #


def test_missing_baseline_returns_empty() -> None:
    """No baseline config → no comparison possible → empty (the
    server-side wiring will fall back to letting the agent's own marker
    fire, or the cardinality fallback)."""
    assert derive_exploration_markers("direction", {"foo": 1}, None) == {}


def test_missing_current_returns_empty() -> None:
    assert derive_exploration_markers("direction", None, {"foo": 1}) == {}


def test_unknown_model_type_returns_empty() -> None:
    """RL has no entry in _KNOB_TO_MARKER today (no tabular-family phases)."""
    cur = {"learning_rate": 1e-4}
    base = {"learning_rate": 1e-5}
    assert derive_exploration_markers("rl", cur, base) == {}
