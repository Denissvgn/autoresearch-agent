from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from ..models.base import ModelProtocol
from ..models.sklearn import SklearnModel
from ..core.errors import NotAvailableSDK
from .rl.base import EnvBuilder
from .rl.config import map_training_config
from .rl.trainers import PPOAdapter


TaskType = Literal["regression", "classification"]


@dataclass(frozen=True)
class Candidate:
    name: str
    task: TaskType
    make_model: Callable[[dict[str, Any]], ModelProtocol]
    sample_params: Callable[[random.Random], dict[str, Any]]
    sample_feature_params: Callable[[random.Random], dict[str, Any]] = field(default_factory=lambda: lambda rng: {})


def _default_feature_space(rng: random.Random) -> dict[str, Any]:
    """Default search space for feature parameters (VDMC, etc)."""
    return {
        "lookback_period": rng.choice([10, 20, 30, 60, 90, 120]),
        "alpha": rng.choice([0.5, 1.0, 1.5, 2.0]),
        "beta": rng.choice([0.5, 1.0, 1.5, 2.0]),
    }


def _sklearn_lr_reg() -> Candidate:
    def make(params: dict[str, Any]) -> ModelProtocol:
        return SklearnModel("LinearRegression", params={})

    def space(rng: random.Random) -> dict[str, Any]:
        return {}

    return Candidate(name="sklearn:LinearRegression", task="regression", make_model=make, sample_params=space, sample_feature_params=_default_feature_space)


def _sklearn_rf_reg() -> Candidate:
    def make(params: dict[str, Any]) -> ModelProtocol:
        return SklearnModel("RandomForestRegressor", params=params)

    def space(rng: random.Random) -> dict[str, Any]:
        return {
            "n_estimators": rng.choice([50, 100, 150]),
            "max_depth": rng.choice([None, 5, 10]),
            "random_state": 0,
        }

    return Candidate(name="sklearn:RandomForestRegressor", task="regression", make_model=make, sample_params=space, sample_feature_params=_default_feature_space)


def _sklearn_logreg_cls() -> Candidate:
    def make(params: dict[str, Any]) -> ModelProtocol:
        p = {"solver": "lbfgs", "max_iter": 1000}
        p.update(params)
        return SklearnModel("LogisticRegression", params=p)

    def space(rng: random.Random) -> dict[str, Any]:
        return {"C": rng.choice([0.1, 1.0, 2.0]), "random_state": 0}

    return Candidate(name="sklearn:LogisticRegression", task="classification", make_model=make, sample_params=space, sample_feature_params=_default_feature_space)


def _sklearn_rf_cls() -> Candidate:
    def make(params: dict[str, Any]) -> ModelProtocol:
        return SklearnModel("RandomForestClassifier", params=params)

    def space(rng: random.Random) -> dict[str, Any]:
        return {
            "n_estimators": rng.choice([50, 100, 150]),
            "max_depth": rng.choice([None, 5, 10]),
            "random_state": 0,
        }

    return Candidate(name="sklearn:RandomForestClassifier", task="classification", make_model=make, sample_params=space, sample_feature_params=_default_feature_space)


def _torch_mlp_reg() -> Candidate:
    def make(params: dict[str, Any]) -> ModelProtocol:
        from ..models.torch_mlp import TorchMLPModel
        return TorchMLPModel(task="regression", **params)

    def space(rng: random.Random) -> dict[str, Any]:
        return {
            "hidden_sizes": rng.choice([[32], [64], [32, 16], [64, 32]]),
            "learning_rate": rng.choice([1e-3, 3e-4, 1e-4]),
            "epochs": rng.choice([50, 100]),
            "batch_size": rng.choice([16, 32]),
            "random_state": 0,
        }

    return Candidate(name="torch:MLPRegressor", task="regression", make_model=make, sample_params=space, sample_feature_params=_default_feature_space)


def _torch_mlp_cls() -> Candidate:
    def make(params: dict[str, Any]) -> ModelProtocol:
        from ..models.torch_mlp import TorchMLPModel
        return TorchMLPModel(task="classification", **params)

    def space(rng: random.Random) -> dict[str, Any]:
        return {
            "hidden_sizes": rng.choice([[32], [64], [32, 16], [64, 32]]),
            "learning_rate": rng.choice([1e-3, 3e-4, 1e-4]),
            "epochs": rng.choice([50, 100]),
            "batch_size": rng.choice([16, 32]),
            "random_state": 0,
        }

    return Candidate(name="torch:MLPClassifier", task="classification", make_model=make, sample_params=space, sample_feature_params=_default_feature_space)


def default_candidates(
    include: Optional[list[str]] = None,
    *,
    rl_env_builder: EnvBuilder | None = None,
    allow_classification: bool = True,
) -> list[Candidate]:
    cand = [_sklearn_lr_reg(), _sklearn_rf_reg(), _sklearn_logreg_cls(), _sklearn_rf_cls()]
    if not allow_classification:
        cand = [c for c in cand if c.task != "classification"]
    
    # Optionally add PyTorch candidates when torch is available
    try:
        import torch  # type: ignore  # noqa: F401
        torch_cands = [_torch_mlp_reg()]
        if allow_classification:
            torch_cands.append(_torch_mlp_cls())
        cand.extend(torch_cands)
    except Exception:
        # PyTorch not available, skip torch candidates
        pass
    
    # Optionally add RL candidate when deps and env builder are available
    if rl_env_builder is not None:
        try:
            import stable_baselines3  # type: ignore  # noqa: F401

            def rl_make(params: dict[str, Any]) -> ModelProtocol:
                _ = map_training_config({**params, "total_timesteps": params.get("total_timesteps", 5_000)})
                raise NotAvailableSDK(
                    "RL PPO requires runtime integration with rl-trainer; provide adapter when invoking training"
                )

            def rl_space(rng: random.Random) -> dict[str, Any]:
                return {
                    "learning_rate": rng.choice([1e-3, 3e-4, 1e-4]),
                    "n_steps": rng.choice([128, 256]),
                    "batch_size": rng.choice([64, 128]),
                    "ent_coef": rng.choice([0.0, 0.01, 0.05]),
                    "total_timesteps": 5_000,
                }

            cand.append(Candidate(name="rl:PPO", task="regression", make_model=rl_make, sample_params=rl_space))
        except Exception:
            pass
    if not include:
        return cand
    include_set = set(include)
    return [c for c in cand if c.name in include_set or c.name.split(":")[1] in include_set]
