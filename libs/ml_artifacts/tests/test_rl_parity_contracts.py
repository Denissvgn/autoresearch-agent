"""MQ-D2/MQ-D3 shared train/serve parity contracts (ml_artifacts.rl).

Pins:
1. The causal regime detector is genuinely causal (future bars cannot change
   past labels) and bounded (a min_history tail reproduces the full-series
   label exactly) — the two properties that make serve-time reconstruction
   possible at all.
2. Classification sanity: trend → BULL/BEAR, vol spike → STRESS, flat → CHOP;
   one-hot order is pinned to (BULL, BEAR, CHOP, STRESS).
3. The obs-spec hash covers structural fields only (volatile diagnostics are
   ignored), is key-order independent, and verify() fails on tampering.
4. The conviction-cap formula (single source for env + serving).
"""

import numpy as np
import pandas as pd

from ml_artifacts.rl.gating import confidence_gate_cap_fraction
from ml_artifacts.rl.obs_spec import compute_obs_spec_hash, verify_obs_spec_hash
from ml_artifacts.rl.regime import (
    DEFAULT_REGIME_DETECTOR_PARAMS,
    REGIME_ONEHOT_ORDER,
    detect_regimes_causal,
    last_bar_regime_onehot,
    min_history_bars,
    regime_onehot,
)


def _random_walk(n: int, seed: int = 7, scale: float = 0.002) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(100.0 * np.cumprod(1.0 + rng.normal(0.0, scale, size=n)))


# ── 1. Causality + boundedness ───────────────────────────────────────────


def test_detector_is_causal() -> None:
    closes = _random_walk(600)
    labels_full = detect_regimes_causal(closes)

    tampered = closes.copy()
    tampered.iloc[450:] = tampered.iloc[450:] * 3.0  # wild future move
    labels_tampered = detect_regimes_causal(tampered)

    # Labels strictly before the tampering point must be identical.
    assert (labels_full.iloc[:450] == labels_tampered.iloc[:450]).all()


def test_detector_is_bounded_tail_reproduces_label() -> None:
    closes = _random_walk(1500, seed=11)
    labels_full = detect_regimes_causal(closes)

    required = min_history_bars()
    tail = closes.iloc[-required:].to_numpy()
    onehot_from_tail = last_bar_regime_onehot(tail)

    assert onehot_from_tail == regime_onehot(labels_full.iloc[-1])


def test_extra_history_does_not_change_last_bar() -> None:
    closes = _random_walk(1200, seed=3)
    required = min_history_bars()
    assert last_bar_regime_onehot(closes.to_numpy()) == last_bar_regime_onehot(
        closes.to_numpy()[-required:]
    )


# ── 2. Classification sanity + one-hot order ─────────────────────────────


def test_uptrend_is_bull_and_downtrend_is_bear() -> None:
    n = 600
    up = pd.Series(100.0 * (1.0005 ** np.arange(n)))  # ≈ +5.1% per 100 bars
    down = pd.Series(100.0 * (0.9995 ** np.arange(n)))
    assert detect_regimes_causal(up).iloc[-1] == "BULL"
    assert detect_regimes_causal(down).iloc[-1] == "BEAR"
    assert last_bar_regime_onehot(up.to_numpy()) == [1.0, 0.0, 0.0, 0.0]
    assert last_bar_regime_onehot(down.to_numpy()) == [0.0, 1.0, 0.0, 0.0]


def test_flat_is_chop_and_vol_spike_is_stress() -> None:
    rng = np.random.default_rng(5)
    flat = pd.Series(100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.0005, 600)))
    assert detect_regimes_causal(flat).iloc[-1] == "CHOP"

    # Calm history, then violent alternating ±3% swings (net trend ≈ 0).
    swings = flat.copy()
    for i in range(560, 600):
        swings.iloc[i] = swings.iloc[i - 1] * (1.03 if i % 2 == 0 else 0.97)
    assert detect_regimes_causal(swings).iloc[-1] == "STRESS"


def test_onehot_order_pinned() -> None:
    assert REGIME_ONEHOT_ORDER == ("BULL", "BEAR", "CHOP", "STRESS")
    assert regime_onehot("STRESS") == [0.0, 0.0, 0.0, 1.0]
    assert regime_onehot("garbage") == [0.0, 0.0, 1.0, 0.0]  # unknown → CHOP


def test_short_history_defaults_to_chop() -> None:
    assert last_bar_regime_onehot([100.0]) == [0.0, 0.0, 1.0, 0.0]
    assert last_bar_regime_onehot([]) == [0.0, 0.0, 1.0, 0.0]


# ── 3. Obs-spec hash ─────────────────────────────────────────────────────


def _spec() -> dict:
    return {
        "feature_columns": ["open", "close", "direction_proba"],
        "features_per_timestep": 3,
        "lookback_window": 20,
        "include_margin_obs": True,
        "include_regime_obs": True,
        "base_state_features": 3,
        "margin_state_features": 4,
        "regime_state_features": 4,
        "total_obs_dim": 71,
        "normalization": {"price_cols": ["open", "close"]},
        "regime_detector": {"version": "causal_v1", **DEFAULT_REGIME_DETECTOR_PARAMS},
        "env_contract": {"direction_confidence_gate": 0.1},
    }


def test_hash_ignores_volatile_fields_and_key_order() -> None:
    a = _spec()
    b = dict(reversed(list(_spec().items())))
    b["feature_importance"] = {"close": 0.9}  # volatile diagnostic
    b["curriculum_stage"] = "C"
    assert compute_obs_spec_hash(a) == compute_obs_spec_hash(b)


def test_hash_changes_on_structural_change() -> None:
    a, b = _spec(), _spec()
    b["feature_columns"] = ["open", "close"]
    assert compute_obs_spec_hash(a) != compute_obs_spec_hash(b)
    c = _spec()
    c["env_contract"] = {"direction_confidence_gate": 0.2}
    assert compute_obs_spec_hash(a) != compute_obs_spec_hash(c)


def test_verify_roundtrip_and_tamper_detection() -> None:
    spec = _spec()
    assert verify_obs_spec_hash(spec)[0] is None  # no stamp yet

    spec["obs_spec_hash"] = compute_obs_spec_hash(spec)
    ok, stamped, recomputed = verify_obs_spec_hash(spec)
    assert ok is True and stamped == recomputed

    spec["total_obs_dim"] = 999  # tamper after stamping
    assert verify_obs_spec_hash(spec)[0] is False


# ── 4. Conviction-cap formula ────────────────────────────────────────────


def test_cap_fraction_semantics() -> None:
    import pytest

    # at/below the gate → zero cap (no adds)
    assert confidence_gate_cap_fraction(0.05, 0.10, 4.0, 1.0) == 0.0
    assert confidence_gate_cap_fraction(0.10, 0.10, 4.0, 1.0) == 0.0
    # linear in the excess margin, k-scaled
    assert confidence_gate_cap_fraction(0.15, 0.10, 4.0, 1.0) == pytest.approx(0.2)
    # kelly cap binds
    assert confidence_gate_cap_fraction(0.45, 0.10, 4.0, 0.5) == 0.5
    # gate disabled → margin itself drives the cap
    assert confidence_gate_cap_fraction(0.0, 0.0, 4.0, 1.0) == 0.0
