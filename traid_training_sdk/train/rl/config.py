from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .trainers import RLTrainingConfig


def map_training_config(params: Mapping[str, Any]) -> RLTrainingConfig:
    rw = params.get("reward_weights") or {"pnl": 1.0, "risk": 0.0, "leverage": 0.0, "flip": 0.0, "hold": 0.0}
    return RLTrainingConfig(
        initial_balance=int(params.get("initial_balance", 10_000)),
        fees_bps=float(params.get("fees_bps", 5.0)),
        slippage_bps=float(params.get("slippage_bps", 2.0)),
        lookback_window=int(params.get("lookback_window", 64)),
        order_latency_steps=int(params.get("order_latency_steps", 0)),
        reward_weights=rw,
        total_timesteps=int(params.get("total_timesteps", 10_000)),
        seed=int(params.get("seed", 0)),
    )

