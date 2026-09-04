from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...core.errors import NotAvailableSDK
from .base import EnvBuilder, RLModel


@dataclass(frozen=True)
class RLTrainingConfig:
    initial_balance: int = 10_000
    fees_bps: float = 5.0
    slippage_bps: float = 2.0
    lookback_window: int = 64
    order_latency_steps: int = 0
    reward_weights: dict[str, float] = None  # e.g., {"pnl":1.0, "risk":0.0}
    total_timesteps: int = 10_000
    seed: int = 0


class PPOAdapter:
    def __init__(self, config: RLTrainingConfig) -> None:
        self.config = config

    def train(self, env_builder: EnvBuilder) -> RLModel:
        try:
            import stable_baselines3  # type: ignore  # noqa: F401
        except Exception as exc:  # pragma: no cover
            raise NotAvailableSDK("stable_baselines3 is required for PPOAdapter") from exc
        try:
            # Import rl-trainer service adapter if available
            from services.ml.rl_trainer.src.training.train_rl_agent import train_ppo_agent  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise NotAvailableSDK("rl-trainer service not available") from exc

        # Build environment via provided builder
        env = env_builder(self.config)
        # Delegate to rl-trainer; expected to return a trained model with .predict and .save
        model = train_ppo_agent(env=env, total_timesteps=self.config.total_timesteps, seed=self.config.seed)
        return model
