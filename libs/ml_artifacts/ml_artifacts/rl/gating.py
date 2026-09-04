"""Trained direction-confidence gate / sizing math (MQ-D3, single source).

The RL training env (PnL-E1 hard gate + MQ-B2 conviction sizing) and the
inference serving pipeline must agree bit-for-bit on what the trained gate
permits — live behavior must match what the policy was optimized under.
Both import this module; the trained values travel to serving inside the
``env_contract`` block of ``obs_spec.json``.
"""

from __future__ import annotations


def confidence_gate_cap_fraction(
    margin: float,
    gate: float,
    sizing_k: float,
    kelly_fraction_cap: float,
) -> float:
    """MQ-B2 conviction-scaled exposure cap as a fraction of max position.

    ``clamp(k · (|p−0.5| − gate), 0, kelly_fraction_cap)`` — zero at or below
    the gate (no adds allowed), rising with conviction up to the fractional-
    Kelly cap.
    """
    effective_margin = max(0.0, float(margin) - float(gate))
    return float(min(float(sizing_k) * effective_margin, float(kelly_fraction_cap)))
