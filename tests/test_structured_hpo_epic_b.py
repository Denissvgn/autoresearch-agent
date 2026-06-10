"""EPIC B (MQ-B1/B2) — RL structured-HPO surface extensions.

Pins:
1. MQ-B1: high-gate sweep points {0.35, 0.40, 0.50} exist and are PAIRED with
   the strongest turnover penalty (trade=0.020); search space advertises the
   extended gate list.
2. MQ-B2: confidence-sizing isolation seeds exist (k ∈ {2,4,8} at kelly 1.0 +
   one kelly 0.5 variant) at the default gate + low-turnover reward; the knobs
   validate as approved top-level scalars.
3. Back-compat: an _rl_patch without sizing kwargs is byte-identical to the
   legacy patch shape (None-skip discipline).
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
    RL_SEARCH_SPACE,
    _rl_patch,
    _rl_trial_patches,
    validate_config_patch,
)


def test_mqb1_high_gate_points_present_with_strong_turnover_penalty() -> None:
    patches = _rl_trial_patches(trading_mode="stock")
    high = {
        p["direction_confidence_gate"]: p.get("reward_weights")
        for p in patches
        if p.get("direction_confidence_gate", 0.0) > 0.30
    }
    assert set(high) == {0.35, 0.40, 0.50}, f"high-gate sweep missing: {sorted(high)}"
    for gate, reward in high.items():
        assert reward is not None and reward.get("trade") == 0.020, (
            f"gate {gate} must pair with the strongest turnover penalty, got {reward}"
        )


def test_mqb1_search_space_advertises_extended_gates() -> None:
    gates = RL_SEARCH_SPACE["direction_confidence_gate"]
    for g in (0.35, 0.40, 0.50):
        assert g in gates


def test_mqb2_sizing_isolation_seeds_present() -> None:
    patches = _rl_trial_patches(trading_mode="stock")
    sizing = [p for p in patches if p.get("confidence_sizing_enabled")]
    ks = {p["confidence_sizing_k"] for p in sizing}
    caps = {p["kelly_fraction_cap"] for p in sizing}
    assert {2.0, 4.0, 8.0} <= ks, f"sizing k sweep missing: {ks}"
    assert 0.5 in caps and 1.0 in caps, f"kelly cap variants missing: {caps}"
    for p in sizing:
        # Isolation: fixed default gate + low-turnover reward.
        assert p["direction_confidence_gate"] == 0.10
        assert p.get("reward_weights", {}).get("trade") == 0.010


def test_mqb2_sizing_knobs_validate_as_approved() -> None:
    patch = _rl_patch(
        lr=3e-4, ent=0.01, clip=0.2, gamma=0.99, n_steps=2048, target_kl=0.04,
        gate=0.10, sizing_enabled=True, sizing_k=4.0, kelly_cap=0.5,
    )
    validate_config_patch("rl", patch)  # must not raise


def test_every_rl_seed_passes_knob_validation() -> None:
    for patch in _rl_trial_patches(trading_mode="stock"):
        validate_config_patch("rl", patch)


def test_rl_patch_without_sizing_kwargs_keeps_legacy_fingerprint() -> None:
    patch = _rl_patch(
        lr=3e-4, ent=0.01, clip=0.2, gamma=0.99, n_steps=2048, target_kl=0.04,
        gate=0.10,
    )
    assert set(patch) == {"training", "direction_confidence_gate"}, (
        "legacy RL patch fingerprint changed — None-skip discipline broken"
    )
    json.dumps(patch, sort_keys=True)


def test_unknown_rl_toplevel_scalar_still_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported structured HPO section"):
        validate_config_patch("rl", {"made_up_knob": 1.0})
