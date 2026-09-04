from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ...models.base import joblib_load, joblib_save


if TYPE_CHECKING:  # pragma: no cover - type-checking only
    from .trainers import RLTrainingConfig


class RLModel(Protocol):
    def learn(self, total_timesteps: int) -> "RLModel":  # pragma: no cover - protocol
        ...

    def predict(self, obs):  # pragma: no cover - protocol
        ...

    def save(self, path: str | Path) -> None:  # pragma: no cover - protocol
        ...

    @classmethod
    def load(cls, path: str | Path) -> "RLModel":  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class RLEvalResult:
    mean_reward: float
    std_reward: float
    episodes: int


@dataclass
class SimpleRLModel:
    """A trivial RL-like model for tests: linear policy over obs."""

    weights: list[float]

    def learn(self, total_timesteps: int) -> "SimpleRLModel":  # no-op
        return self

    def predict(self, obs):
        import numpy as np  # type: ignore

        x = np.asarray(obs)
        w = np.asarray(self.weights)
        out = (x * w[: x.shape[-1]]).sum(axis=-1)
        return out

    def save(self, path: str | Path) -> None:
        joblib_save({"weights": self.weights}, path)

    @classmethod
    def load(cls, path: str | Path) -> "SimpleRLModel":
        payload = joblib_load(path)
        return cls(weights=list(payload["weights"]))


class EnvBuilder(Protocol):
    def __call__(self, config: "RLTrainingConfig"):
        ...


def build_synthetic_trading_env(config: "RLTrainingConfig"):
    from types import SimpleNamespace
    import numpy as np  # type: ignore

    class SyntheticEnv:
        def __init__(self, *, seed: int):
            self.rng = np.random.default_rng(seed)
            self.observation_space = SimpleNamespace(shape=(config.lookback_window,))
            self.action_space = SimpleNamespace(n=3)
            self.steps = 0

        def reset(self):
            self.steps = 0
            return self._obs()

        def step(self, action):
            self.steps += 1
            obs = self._obs()
            reward = float(self.rng.normal(0.0, 0.1))
            done = self.steps >= config.lookback_window
            info = {}
            return obs, reward, done, info

        def _obs(self):
            return self.rng.normal(0.0, 1.0, size=config.lookback_window)

        def close(self):  # pragma: no cover - optional hook
            return None

    return SyntheticEnv(seed=config.seed)
