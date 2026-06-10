"""Structured HPO plan helpers for autoresearch sessions."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

import yaml


PLAN_SCHEMA_VERSION = "autoresearch_structured_hpo_plan.v1"
TRIAL_SCHEMA_VERSION = "autoresearch_structured_trial.v1"
CURRENT_FEATURE_LIBRARY_VERSION = "2.3.0"

DIRECTION_SCOPED_ROSTER = ["lgb", "lgb_deep", "xgb", "rf", "rf_deep"]
DIRECTION_FULL_ROSTER = [
    "lgb",
    "lgb_deep",
    "lgb_shallow",
    "lgb_dart",
    "lgb_goss",
    "xgb",
    "xgb_deep",
    "xgb_conserv",
    "rf",
    "rf_deep",
    "rf_shallow",
]
DIRECTION_HORIZON_FULL = [4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64]
DIRECTION_HORIZON_SHORT = [4, 6, 8, 12]
DIRECTION_HORIZON_MID = [12, 16, 20, 24, 32]


DIRECTION_SEARCH_SPACE: Dict[str, Any] = {
    "direction_pct_threshold": [0.0175, 0.020, 0.0225, 0.025, 0.0275],
    "deadzone_width": [0.0175, 0.020, 0.0225, 0.025, 0.0275],
    "auto_select_horizon": [True],
    "horizon_candidates": {
        "full_exp_dir_100_130": DIRECTION_HORIZON_FULL,
        "short": DIRECTION_HORIZON_SHORT,
        "mid": DIRECTION_HORIZON_MID,
    },
    "roster": {
        "scoped_tabular": DIRECTION_SCOPED_ROSTER,
        "full_tabular": DIRECTION_FULL_ROSTER,
    },
    "calibration_method": ["isotonic", "sigmoid"],
    "calibration_rejection_guard": {
        "stacking_calibration_fallback_method": ["sigmoid"],
        "stacking_calibration_fallback_min_samples": [200, 400],
    },
    "threshold_policy": {
        "threshold_strategy": ["f_beta"],
        "threshold_beta": [0.3, 0.5, 0.7],
        "max_signal_rate": [0.25, 0.35, 0.45],
    },
    "feature_library_version": [CURRENT_FEATURE_LIBRARY_VERSION],
    "feature_flags": {
        "use_shared_feature_library": [True],
        "log_feature_provenance": [True],
        "validate_feature_consistency": [True],
    },
}

VOLATILITY_SEARCH_SPACE: Dict[str, Any] = {
    "prediction_horizon": [3, 4, 6, 8, 12],
    "volatility_atr_mult": [1.25, 1.5, 2.0, 2.5, 3.0],
    "atr_mult_candidates": [[1.25, 1.5, 2.0], [2.0, 2.5, 3.0]],
    "roster": {
        "scoped_tabular": DIRECTION_SCOPED_ROSTER,
        "full_tabular": DIRECTION_FULL_ROSTER,
    },
    "calibration_method": ["isotonic", "sigmoid"],
    "threshold_policy": {
        "threshold_strategy": ["f_beta"],
        "threshold_beta": [0.5, 0.7],
    },
    "feature_library_version": [CURRENT_FEATURE_LIBRARY_VERSION],
    "feature_flags": {
        "use_shared_feature_library": [True],
        "log_feature_provenance": [True],
        "validate_feature_consistency": [True],
    },
}

# RL HPO is now server-owned via materialized planned trials (like direction /
# volatility), NOT the agent-invoked Optuna ``--hpo`` study. The search covers
# the PPO ``training:`` hyperparameters (the highest-leverage knobs the Optuna
# study targeted); reward-shaping stays fixed at the promoted baseline. Each
# entry is a dotted path into the RL train.yaml so the UI/manifest can render
# the surface; the trial patches below set the nested ``training:`` block.
RL_SEARCH_SPACE: Dict[str, Any] = {
    "training.learning_rate": [1e-4, 3e-4, 5e-4, 7e-4],
    "training.ent_coef": [0.005, 0.01, 0.02, 0.04],
    "training.clip_range": [0.10, 0.15, 0.20, 0.25, 0.30],
    "training.gamma": [0.98, 0.99, 0.995, 0.999],
    "training.n_steps": [1024, 2048, 4096],
    "training.target_kl": [None, 0.03, 0.04, 0.05, 0.08],
    # PnL-E1: hard selectivity gate (|direction_proba-0.5| abstain margin).
    # Recentred for the honest two-sided OOF (post-S1): |proba-0.5| mean 0.26,
    # so tradeable share at 0.05/0.10/0.20/0.30 = 91/82/63/43% — a real
    # selectivity curve (the old leaked signal abstained ~entirely above 0.05).
    "direction_confidence_gate": [0.0, 0.05, 0.10, 0.20, 0.30],
    # PnL-E3: turnover/holding reward shaping (raise churn penalties, drop the
    # holding penalty so confident positions can ride).
    "reward_weights.trade": [0.002, 0.010, 0.020],
    "reward_weights.flip": [0.001, 0.005, 0.010],
    "reward_weights.hold": [0.001, 0.0],
}

APPROVED_DIRECTION_KNOBS = {
    "auto_select_horizon",
    "base_model_keys",
    "calibration_method",
    "direction_pct_threshold",
    "feature_library_version",
    "horizon_candidates",
    "log_feature_provenance",
    "max_signal_rate",
    "roster_preset",
    "stacking_calibration_fallback_method",
    "stacking_calibration_fallback_min_samples",
    "stacking_calibration_method",
    "threshold_beta",
    "threshold_strategy",
    "use_shared_feature_library",
    "validate_feature_consistency",
    # DM-12 / DM-13 knobs the direction trial patches already set — were missing
    # here, so direction + enable_hpo raised "Unsupported structured HPO knob(s)"
    # and 500'd on session start.
    "sample_weight_halflife",
    "meta_model",
    "horizon_ensemble_enabled",
}

APPROVED_VOLATILITY_KNOBS = {
    "atr_mult_candidates",
    "atr_mult_sweep_enabled",
    "base_model_keys",
    "calibration_method",
    "feature_library_version",
    "log_feature_provenance",
    "prediction_horizon",
    "roster_preset",
    "threshold_beta",
    "threshold_strategy",
    "use_shared_feature_library",
    "validate_feature_consistency",
    "volatility_atr_mult",
}

# RL patches are NESTED (the RL train.yaml groups hyperparameters under
# ``training:``), unlike the flat direction/volatility patches. Only the
# ``training:`` section is searched by the server-owned HPO; the approved leaf
# knobs below are the PPO hyperparameters it may set.
# PnL-E3: ``reward_weights`` is also a nested patch section (turnover / holding
# reward shaping). Both training: and reward_weights: deep-merge into train.yaml.
RL_PATCH_SECTIONS = {"training", "reward_weights"}
# PnL-E1: top-level scalar knobs an RL patch may set alongside the sections
# (the hard selectivity gate is not a PPO hyperparameter).
RL_PATCH_TOPLEVEL_SCALARS = {"direction_confidence_gate"}
# PnL-E3: reward-weight leaf knobs the server-owned sweep may set (the rl-trainer
# merges partial overrides into the full reward_weights dict).
APPROVED_RL_REWARD_KNOBS = {
    "pnl", "risk", "dd_increment", "leverage", "flip", "trade", "hold",
    "sharpe", "confidence",
}
APPROVED_RL_TRAINING_KNOBS = {
    "learning_rate",
    "lr_end",
    "ent_coef",
    "clip_range",
    "gamma",
    "gae_lambda",
    "n_steps",
    "n_epochs",
    "batch_size",
    "target_kl",
    "max_grad_norm",
    "vf_coef",
    "delta_max",
}


def build_structured_hpo_plan(
    *,
    research_id: str,
    instrument: str,
    timeframe: str,
    model_type: str,
    quick_mode: bool,
    max_iterations: int,
    max_budget_usd: float,
    timeout_s: int,
    enable_hpo: bool,
    hpo_trials: int,
    hpo_timesteps: int,
    trading_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a bounded HPO plan for manifest, DB, API, and UI state."""

    max_trials = _bounded_trials(model_type, max_iterations, enable_hpo, hpo_trials)
    max_trials = _budget_bounded_trials(model_type, max_trials, max_budget_usd)
    search_space = _search_space(model_type, trading_mode=trading_mode)
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "research_id": research_id,
        "study_id": f"hpo_{research_id}_{model_type}",
        "model_type": model_type,
        "instrument": instrument,
        "timeframe": timeframe,
        "enabled": bool(enable_hpo),
        "status": "planned" if enable_hpo else "disabled",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "max_trials": max_trials,
        "timeout_s": timeout_s,
        "quick_mode": quick_mode,
        "budget": {
            "max_iterations": max_iterations,
            "max_budget_usd": max_budget_usd,
            "per_trial_budget_usd": _per_trial_budget_usd(model_type),
            "trial_budget_fraction": 0.5 if model_type in {"direction", "volatility"} else 0.35,
        },
        "search_space": search_space,
        "execution": _execution(model_type, hpo_timesteps),
        "trials": _planned_trials(
            research_id=research_id,
            study_id=f"hpo_{research_id}_{model_type}",
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            max_trials=max_trials,
            quick_mode=quick_mode,
            trading_mode=trading_mode,
        ),
    }
    plan["plan_hash"] = _hash(plan)
    return plan


def hpo_plan_json(plan: Dict[str, Any]) -> str:
    return json.dumps(plan, sort_keys=True)


def validate_config_patch(
    model_type: str,
    config_patch: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate a server-owned config patch against the approved knob surface."""

    if model_type == "rl":
        # RL patches are nested: top-level keys must be known sections (training:)
        # or approved top-level scalars (selectivity gate), and each leaf knob
        # within ``training:`` must be approved.
        invalid_sections = sorted(
            set(config_patch) - RL_PATCH_SECTIONS - RL_PATCH_TOPLEVEL_SCALARS
        )
        if invalid_sections:
            raise ValueError(
                "Unsupported structured HPO section(s) for rl: "
                + ", ".join(invalid_sections)
            )
        training = config_patch.get("training") or {}
        if not isinstance(training, Mapping):
            raise ValueError("rl structured HPO 'training' patch must be a mapping")
        invalid = sorted(set(training) - APPROVED_RL_TRAINING_KNOBS)
        if invalid:
            raise ValueError(
                "Unsupported structured HPO knob(s) for rl.training: "
                + ", ".join(invalid)
            )
        reward = config_patch.get("reward_weights") or {}
        if not isinstance(reward, Mapping):
            raise ValueError("rl structured HPO 'reward_weights' patch must be a mapping")
        invalid_rw = sorted(set(reward) - APPROVED_RL_REWARD_KNOBS)
        if invalid_rw:
            raise ValueError(
                "Unsupported structured HPO knob(s) for rl.reward_weights: "
                + ", ".join(invalid_rw)
            )
        return dict(config_patch)

    if model_type == "direction":
        approved = APPROVED_DIRECTION_KNOBS
    elif model_type == "volatility":
        approved = APPROVED_VOLATILITY_KNOBS
    else:
        approved = set()
    invalid = sorted(set(config_patch) - approved)
    if invalid:
        raise ValueError(
            f"Unsupported structured HPO knob(s) for {model_type}: "
            + ", ".join(invalid)
        )
    return dict(config_patch)


def _deep_merge(base: Dict[str, Any], patch: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``patch`` into ``base`` (nested dicts merged, scalars /
    lists replaced). Required for RL whose train.yaml groups knobs under nested
    sections (``training:`` etc.) — a shallow update would drop sibling keys."""
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def apply_config_patch(
    base_config: Mapping[str, Any],
    config_patch: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return a train.yaml payload with a server-owned patch applied.

    Deep-merges so nested RL sections (``training:``) keep their untouched
    sibling keys. For flat direction/volatility patches this is equivalent to a
    shallow update (their patch values are scalars/lists, never nested dicts).
    """

    patched = copy.deepcopy(dict(base_config))
    return _deep_merge(patched, dict(config_patch))


def materialize_planned_trials(
    plan: Mapping[str, Any],
    workspace_path: str | Path,
) -> List[Dict[str, Any]]:
    """Write concrete planned trial train.yaml files under the workspace."""

    workspace = Path(workspace_path)
    base_path = workspace / "train.yaml"
    if not base_path.exists():
        return []

    base_config = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    if not isinstance(base_config, dict):
        return []

    written: List[Dict[str, Any]] = []
    for trial in plan.get("trials") or []:
        trial_id = trial.get("trial_id")
        if not trial_id:
            continue
        patch = trial.get("config_patch") or {}
        validate_config_patch(str(plan.get("model_type") or ""), patch)
        trial_dir = workspace / "planned_trials" / str(trial_id)
        target = trial_dir / "train.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        patched_config = apply_config_patch(base_config, patch)
        payload = yaml.safe_dump(patched_config, sort_keys=False)
        header = (
            "# Server-owned structured HPO trial.\n"
            f"# trial_id: {trial_id}\n"
            f"# config_hash: {trial.get('config_hash', '')}\n"
        )
        target.write_text(header + payload, encoding="utf-8")
        written.append(
            {
                **dict(trial),
                "materialized_config_path": str(target),
            }
        )

    plan_path = workspace / "server_hpo_plan.json"
    plan_payload = dict(plan)
    plan_payload["materialized_at"] = datetime.now(timezone.utc).isoformat()
    plan_payload["materialized_trial_count"] = len(written)
    plan_path.write_text(
        json.dumps(plan_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return written


def _bounded_trials(
    model_type: str,
    max_iterations: int,
    enable_hpo: bool,
    requested_trials: int,
) -> int:
    if not enable_hpo:
        return 0
    if requested_trials <= 0:
        return 0
    if max_iterations <= 0:
        return 0
    # RL trials are now materialized iterations (one prepare.py run each), so
    # they must fit within the iteration budget like direction/volatility —
    # leaving headroom for the agent to interpret results / propose follow-ups.
    return min(requested_trials, max_iterations, 40)


def _budget_bounded_trials(
    model_type: str,
    max_trials: int,
    max_budget_usd: float,
) -> int:
    if max_trials <= 0:
        return 0
    per_trial = _per_trial_budget_usd(model_type)
    if per_trial <= 0:
        return max_trials
    if max_budget_usd <= 0:
        return 0
    return min(max_trials, max(1, int(max_budget_usd / per_trial)))


def _per_trial_budget_usd(model_type: str) -> float:
    if model_type in {"direction", "volatility"}:
        return 0.25
    return 0.0


def _is_long_only(trading_mode: Optional[str]) -> bool:
    """Stock mode is long-only: position never goes negative, so position-flips are
    structurally impossible — flip_count is always 0 and the reward_weights.flip
    penalty is inert.  None defaults to stock, matching the trainer/promoter default."""
    return (trading_mode or "stock").lower() == "stock"


def _search_space(
    model_type: str, *, trading_mode: Optional[str] = None
) -> Dict[str, Any]:
    if model_type == "direction":
        return DIRECTION_SEARCH_SPACE
    if model_type == "volatility":
        return VOLATILITY_SEARCH_SPACE
    if model_type == "rl":
        space = dict(RL_SEARCH_SPACE)
        if _is_long_only(trading_mode):
            # Flip penalty is inert in long-only stock mode — drop the dimension so
            # the published search space (and any trial generation) does not waste a
            # lever that cannot change the result.  Margin mode keeps it.
            space.pop("reward_weights.flip", None)
        return space
    return {}


def _planned_trials(
    *,
    research_id: str,
    study_id: str,
    instrument: str,
    timeframe: str,
    model_type: str,
    max_trials: int,
    quick_mode: bool,
    trading_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if max_trials <= 0 or model_type not in {"direction", "volatility", "rl"}:
        return []
    if model_type == "direction":
        patches = _direction_trial_patches()
    elif model_type == "volatility":
        patches = _volatility_trial_patches()
    else:
        patches = _rl_trial_patches(trading_mode=trading_mode)
    workspace = _workspace_path(instrument, timeframe, model_type)
    quick_flag = " --quick" if quick_mode else ""
    trials = []
    for index, patch in enumerate(patches[:max_trials], start=1):
        validate_config_patch(model_type, patch)
        trial_id = _trial_id(index, patch, model_type)
        train_config_path = f"{workspace}/planned_trials/{trial_id}/train.yaml"
        result_path = f"{workspace}/planned_trials/{trial_id}/results.json"
        expected_command = (
            f".venv/bin/python scripts/autotuner/{model_type}/prepare.py "
            f"--config {train_config_path}{quick_flag}"
        )
        config_hash = _hash(
            {
                "schema_version": TRIAL_SCHEMA_VERSION,
                "research_id": research_id,
                "study_id": study_id,
                "trial_id": trial_id,
                "model_type": model_type,
                "config_patch": patch,
            }
        )
        trials.append(
            {
                "schema_version": TRIAL_SCHEMA_VERSION,
                "trial_id": trial_id,
                "trial_index": index,
                "study_id": study_id,
                "search_phase": "hpo_screening",
                "config_patch": patch,
                "config_hash": config_hash,
                "expected_command": expected_command,
                "train_config_path": train_config_path,
                "result_path": result_path,
                "status": "planned",
                "mlflow_run_id": None,
                "manual_review_reason": None,
            }
        )
    return trials


def _direction_trial_patches() -> List[Dict[str, Any]]:
    seeds = [
        _direction_patch(
            threshold=0.020,
            horizon=DIRECTION_HORIZON_FULL,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
        _direction_patch(
            threshold=0.025,
            horizon=DIRECTION_HORIZON_FULL,
            roster="full_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
        _direction_patch(
            threshold=0.0225,
            horizon=DIRECTION_HORIZON_MID,
            roster="scoped_tabular",
            calibration="sigmoid",
            beta=0.7,
            signal_cap=0.25,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            fallback_min_samples=200,
        ),
        _direction_patch(
            threshold=0.0275,
            horizon=DIRECTION_HORIZON_SHORT,
            roster="full_tabular",
            calibration="sigmoid",
            beta=0.5,
            signal_cap=0.25,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            fallback_min_samples=400,
        ),
        _direction_patch(
            threshold=0.0175,
            horizon=DIRECTION_HORIZON_MID,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.3,
            signal_cap=0.45,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
        # DM-12: direction_pct_threshold band extensions. Existing seeds
        # cover ~0.020/0.025/0.0275; add 0.015/0.040/0.050 so the agent
        # explores tighter and looser dead-zones than the legacy baseline.
        _direction_patch(
            threshold=0.015,
            horizon=DIRECTION_HORIZON_MID,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.4,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
        _direction_patch(
            threshold=0.040,
            horizon=DIRECTION_HORIZON_FULL,
            roster="full_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.30,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
        _direction_patch(
            threshold=0.050,
            horizon=DIRECTION_HORIZON_FULL,
            roster="full_tabular",
            calibration="sigmoid",
            beta=0.5,
            signal_cap=0.25,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            fallback_min_samples=200,
        ),
        # DM-12: sample_weight_halflife sweep. Default left to the trainer
        # (3000 typical) for legacy seeds; these explore shorter recency
        # windows that adapt faster to regime drift.
        _direction_patch(
            threshold=0.025,
            horizon=DIRECTION_HORIZON_FULL,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            sample_weight_halflife=1000,
        ),
        _direction_patch(
            threshold=0.025,
            horizon=DIRECTION_HORIZON_FULL,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            sample_weight_halflife=1500,
        ),
        _direction_patch(
            threshold=0.025,
            horizon=DIRECTION_HORIZON_FULL,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            sample_weight_halflife=2000,
        ),
        # DM-13: meta_model variants (from DM-6) + horizon_ensemble
        # (from DM-5). The agent never tried either in res_be66 because
        # neither dimension was in the seed roster.
        _direction_patch(
            threshold=0.025,
            horizon=DIRECTION_HORIZON_FULL,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            meta_model="lgb_shallow",
            horizon_ensemble_enabled=False,
        ),
        _direction_patch(
            threshold=0.025,
            horizon=DIRECTION_HORIZON_FULL,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            meta_model="lgb_shallow",
            horizon_ensemble_enabled=True,
        ),
        _direction_patch(
            threshold=0.025,
            horizon=DIRECTION_HORIZON_FULL,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            signal_cap=0.35,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
            meta_model="mlp_2x32",
            horizon_ensemble_enabled=False,
        ),
    ]
    return _extend_unique_patches(
        seeds,
        (
            _direction_patch(
                threshold=threshold,
                horizon=horizon,
                roster=roster,
                calibration=calibration,
                beta=beta,
                signal_cap=signal_cap,
                feature_version=feature_version,
                fallback_min_samples=200 if calibration == "sigmoid" else None,
            )
            for threshold in [0.020, 0.025, 0.0225, 0.0175, 0.0275]
            for horizon in [
                DIRECTION_HORIZON_FULL,
                DIRECTION_HORIZON_SHORT,
                DIRECTION_HORIZON_MID,
            ]
            for roster in ["scoped_tabular", "full_tabular"]
            for calibration in ["isotonic", "sigmoid"]
            for beta, signal_cap in [(0.5, 0.35), (0.7, 0.25), (0.3, 0.45)]
            for feature_version in [CURRENT_FEATURE_LIBRARY_VERSION]
        )
    )


def _volatility_trial_patches() -> List[Dict[str, Any]]:
    seeds = [
        _volatility_patch(
            atr_mult=2.0,
            horizon=4,
            roster="scoped_tabular",
            calibration="isotonic",
            beta=0.5,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
        _volatility_patch(
            atr_mult=2.5,
            horizon=6,
            roster="full_tabular",
            calibration="isotonic",
            beta=0.5,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
        _volatility_patch(
            atr_mult=1.5,
            horizon=8,
            roster="scoped_tabular",
            calibration="sigmoid",
            beta=0.7,
            feature_version=CURRENT_FEATURE_LIBRARY_VERSION,
        ),
    ]
    return _extend_unique_patches(
        seeds,
        (
            _volatility_patch(
                atr_mult=atr_mult,
                horizon=horizon,
                roster=roster,
                calibration=calibration,
                beta=beta,
                feature_version=feature_version,
            )
            for atr_mult in [1.25, 1.5, 2.0, 2.5, 3.0]
            for horizon in [3, 4, 6, 8, 12]
            for roster in ["scoped_tabular", "full_tabular"]
            for calibration in ["isotonic", "sigmoid"]
            for beta in [0.5, 0.7]
            for feature_version in [CURRENT_FEATURE_LIBRARY_VERSION]
        )
    )


def _direction_patch(
    *,
    threshold: float,
    horizon: List[int],
    roster: str,
    calibration: str,
    beta: float,
    signal_cap: float,
    feature_version: str,
    fallback_min_samples: int | None = None,
    # DM-12: recency weighting. None preserves the legacy patch fingerprint
    # (no key emitted) so existing seeds still produce identical hashes.
    sample_weight_halflife: int | None = None,
    # DM-13: meta-model variants from DM-6 (lgb_shallow / mlp_2x32) and the
    # DM-5 multi-horizon ensemble toggle. Same None-skip discipline as above.
    meta_model: str | None = None,
    horizon_ensemble_enabled: bool | None = None,
) -> Dict[str, Any]:
    patch: Dict[str, Any] = {
        "direction_pct_threshold": threshold,
        "auto_select_horizon": True,
        "horizon_candidates": list(horizon),
        "roster_preset": roster,
        "base_model_keys": _roster_keys(roster),
        "calibration_method": calibration,
        "stacking_calibration_method": calibration,
        "threshold_strategy": "f_beta",
        "threshold_beta": beta,
        "max_signal_rate": signal_cap,
        "use_shared_feature_library": True,
        "feature_library_version": feature_version,
        "log_feature_provenance": True,
        "validate_feature_consistency": True,
    }
    if fallback_min_samples is not None:
        patch["stacking_calibration_fallback_method"] = "sigmoid"
        patch["stacking_calibration_fallback_min_samples"] = fallback_min_samples
    # DM-12 / DM-13 keys — only emitted when set so legacy seed fingerprints
    # remain bit-identical.
    if sample_weight_halflife is not None:
        patch["sample_weight_halflife"] = sample_weight_halflife
    if meta_model is not None:
        patch["meta_model"] = meta_model
    if horizon_ensemble_enabled is not None:
        patch["horizon_ensemble_enabled"] = bool(horizon_ensemble_enabled)
    return patch


def _volatility_patch(
    *,
    atr_mult: float,
    horizon: int,
    roster: str,
    calibration: str,
    beta: float,
    feature_version: str,
) -> Dict[str, Any]:
    return {
        "volatility_atr_mult": atr_mult,
        "atr_mult_sweep_enabled": True,
        "atr_mult_candidates": _atr_candidates(atr_mult),
        "prediction_horizon": horizon,
        "roster_preset": roster,
        "base_model_keys": _roster_keys(roster),
        "calibration_method": calibration,
        "threshold_strategy": "f_beta",
        "threshold_beta": beta,
        "use_shared_feature_library": True,
        "feature_library_version": feature_version,
        "log_feature_provenance": True,
        "validate_feature_consistency": True,
    }


# PnL-E1: a single sensible PPO baseline used for the leading selectivity sweep
# so the gate's effect on post-cost return / turnover is isolated from PPO tuning.
_RL_PPO_BASELINE = dict(lr=3e-4, ent=0.01, clip=0.20, gamma=0.99, n_steps=2048, target_kl=0.04)
# Moderate default gate applied to the PPO-search trials (E1 hypothesis: some
# selectivity helps); the leading sweep pins down the best gate independently.
_RL_DEFAULT_GATE = 0.10
# PnL-E3: turnover/holding reward-shaping profiles. ``None`` = train.yaml default
# (trade 0.002 / flip 0.001 / hold 0.001). The shaped profiles raise the churn
# penalties and drop the holding penalty so confident positions can ride. The
# rl-trainer merges these partial overrides into the full reward_weights dict.
_RL_REWARD_LOWTURN = {"trade": 0.010, "flip": 0.005, "hold": 0.0}
_RL_REWARD_LOWTURN_STRONG = {"trade": 0.020, "flip": 0.010, "hold": 0.0}


def _market_reward(reward: Dict[str, Any], trading_mode: Optional[str]) -> Dict[str, Any]:
    """Strip the inert ``flip`` term from a reward-shaping profile in long-only stock
    mode (no sign-change flips), so trials differ only by levers that can actually
    change the result.  Margin mode keeps flip (real long↔short churn)."""
    if _is_long_only(trading_mode):
        return {k: v for k, v in reward.items() if k != "flip"}
    return dict(reward)


def _rl_trial_patches(*, trading_mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Discrete trials for server-owned RL HPO (Sprint-1: E1 + E3).

    Leading ISOLATION blocks at the fixed PPO baseline so each lever's effect on
    post-cost return / turnover is isolated:
      A. PnL-E1 selectivity sweep — vary ONLY ``direction_confidence_gate``.
      B. PnL-E3 turnover-reward sweep — at the moderate gate, vary ONLY the
         reward shaping (churn penalties up, holding penalty off).
    Then a PPO grid under the combined regime (moderate gate + low-turnover
    reward), i.e. E1 and E3 applied together.

    ``trading_mode`` makes flip shaping market-aware: long-only stock mode drops the
    inert ``flip`` term (see _market_reward); margin keeps it.
    """
    lowturn = _market_reward(_RL_REWARD_LOWTURN, trading_mode)
    lowturn_strong = _market_reward(_RL_REWARD_LOWTURN_STRONG, trading_mode)
    # (A) E1 gate sweep — fixed PPO baseline, baseline reward, varying gate.
    # Recentred for the honest two-sided OOF (post-S1): {0, 0.05, 0.10, 0.20, 0.30}
    # = tradeable share 100/91/82/63/43% (real selectivity curve).
    gate_sweep = [
        _rl_patch(**_RL_PPO_BASELINE, gate=g)
        for g in [0.0, 0.05, 0.10, 0.20, 0.30]
    ]
    # (B) E3 reward sweep — fixed PPO baseline + moderate gate, varying reward
    # shaping (the baseline-reward @ gate=0.10 point is already in block A).
    reward_sweep = [
        _rl_patch(**_RL_PPO_BASELINE, gate=_RL_DEFAULT_GATE, reward=lowturn),
        _rl_patch(**_RL_PPO_BASELINE, gate=_RL_DEFAULT_GATE, reward=lowturn_strong),
    ]
    # (C) PPO search seeds under the COMBINED regime (gate + low-turnover reward).
    ppo_seeds = [
        _rl_patch(lr=1e-4, ent=0.005, clip=0.15, gamma=0.995, n_steps=2048, target_kl=0.03, gate=_RL_DEFAULT_GATE, reward=lowturn),
        _rl_patch(lr=5e-4, ent=0.02, clip=0.30, gamma=0.99, n_steps=4096, target_kl=0.05, gate=_RL_DEFAULT_GATE, reward=lowturn),
        _rl_patch(lr=3e-4, ent=0.04, clip=0.20, gamma=0.98, n_steps=1024, target_kl=0.08, gate=_RL_DEFAULT_GATE, reward=lowturn),
        _rl_patch(lr=1e-4, ent=0.01, clip=0.10, gamma=0.999, n_steps=4096, target_kl=0.03, gate=_RL_DEFAULT_GATE, reward=lowturn),
        _rl_patch(lr=7e-4, ent=0.03, clip=0.25, gamma=0.99, n_steps=2048, target_kl=0.05, gate=_RL_DEFAULT_GATE, reward=lowturn),
        _rl_patch(lr=2e-4, ent=0.015, clip=0.20, gamma=0.995, n_steps=2048, target_kl=0.04, gate=_RL_DEFAULT_GATE, reward=lowturn),
        _rl_patch(lr=5e-4, ent=0.008, clip=0.15, gamma=0.99, n_steps=1024, target_kl=None, gate=_RL_DEFAULT_GATE, reward=lowturn),
    ]
    return _extend_unique_patches(
        gate_sweep + reward_sweep + ppo_seeds,
        (
            _rl_patch(
                lr=lr, ent=ent, clip=clip, gamma=gamma, n_steps=n_steps,
                target_kl=tkl, gate=_RL_DEFAULT_GATE, reward=lowturn,
            )
            for lr in [1e-4, 3e-4, 5e-4]
            for ent in [0.005, 0.01, 0.02]
            for clip in [0.15, 0.20, 0.30]
            for gamma in [0.99, 0.995]
            for n_steps in [2048, 4096]
            for tkl in [0.03, 0.05]
        ),
    )


def _rl_patch(
    *,
    lr: float,
    ent: float,
    clip: float,
    gamma: float,
    n_steps: int,
    target_kl: float | None,
    gate: float = 0.0,
    reward: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """RL trial patch: nested ``training:`` PPO knobs + the top-level hard
    selectivity gate + optional ``reward_weights:`` shaping (E3). ``target_kl=None``
    explicitly disables the KL brake (yaml ``null``); ``gate`` is the
    |direction_proba-0.5| abstain margin; ``reward`` is a partial reward-weight
    override (merged into the full dict by the trainer)."""
    patch: Dict[str, Any] = {
        "training": {
            "learning_rate": lr,
            "ent_coef": ent,
            "clip_range": clip,
            "gamma": gamma,
            "n_steps": n_steps,
            "target_kl": target_kl,
        },
        "direction_confidence_gate": gate,
    }
    if reward is not None:
        patch["reward_weights"] = dict(reward)
    return patch


def _extend_unique_patches(
    seeds: List[Dict[str, Any]],
    generated: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    seen = {_hash({"config_patch": patch}) for patch in seeds}
    patches = list(seeds)
    for patch in generated:
        fingerprint = _hash({"config_patch": patch})
        if fingerprint in seen:
            continue
        patches.append(patch)
        seen.add(fingerprint)
        if len(patches) >= 80:
            break
    return patches


def _roster_keys(roster: str) -> List[str]:
    if roster == "full_tabular":
        return list(DIRECTION_FULL_ROSTER)
    return list(DIRECTION_SCOPED_ROSTER)


def _atr_candidates(atr_mult: float) -> List[float]:
    low = max(1.0, round(atr_mult - 0.5, 2))
    high = round(atr_mult + 0.5, 2)
    return [low, atr_mult, high]


def _trial_id(index: int, patch: Mapping[str, Any], model_type: str) -> str:
    if model_type == "direction":
        threshold = int(round(float(patch["direction_pct_threshold"]) * 10000))
        roster = str(patch["roster_preset"]).replace("_tabular", "")
        calibration = str(patch["stacking_calibration_method"])
        return f"trial_{index:03d}_dz{threshold}_{roster}_{calibration}"
    if model_type == "rl":
        training = patch.get("training") or {}
        lr = int(round(float(training.get("learning_rate", 0.0)) * 1e5))
        ent = int(round(float(training.get("ent_coef", 0.0)) * 1000))
        clip = int(round(float(training.get("clip_range", 0.0)) * 100))
        tkl = training.get("target_kl")
        kl = "off" if tkl is None else str(int(round(float(tkl) * 100)))
        gate = int(round(float(patch.get("direction_confidence_gate", 0.0)) * 100))
        rw = patch.get("reward_weights") or {}
        # PnL-E3: tag the turnover-penalty profile so reward-shaped trials are
        # distinct (baseline reward → no suffix).
        rtag = f"_t{int(round(float(rw.get('trade', 0.0)) * 1000))}" if rw else ""
        return f"trial_{index:03d}_lr{lr}_ent{ent}_clip{clip}_kl{kl}_g{gate}{rtag}"
    atr_mult = int(round(float(patch["volatility_atr_mult"]) * 100))
    horizon = int(patch["prediction_horizon"])
    calibration = str(patch["calibration_method"])
    return f"trial_{index:03d}_atr{atr_mult}_h{horizon}_{calibration}"


def _workspace_path(instrument: str, timeframe: str, model_type: str) -> str:
    instrument_underscore = instrument.replace("-", "_")
    return f"runs/autotuner/{instrument_underscore}_{timeframe}/{model_type}"


def _execution(model_type: str, hpo_timesteps: int) -> Dict[str, Any]:
    # RL is now a server-owned materialized sweep (one prepare.py run per trial),
    # the same execution model as direction/volatility — no agent-invoked Optuna
    # ``--hpo`` study. hpo_timesteps is retained for provenance only; each trial
    # uses the materialized train.yaml's total_timesteps (quick mode = 2 folds).
    if model_type == "rl":
        return {
            "mode": "agent_bounded_sweep",
            "hpo_timesteps": hpo_timesteps,
            "result_path": "server_hpo_plan.json",
            "enforced_by": "manifest_budget_and_iteration_cap",
        }
    return {
        "mode": "agent_bounded_sweep",
        "result_path": "server_hpo_plan.json",
        "enforced_by": "manifest_budget_and_iteration_cap",
    }


def _hash(plan: Dict[str, Any]) -> str:
    payload = dict(plan)
    payload.pop("plan_hash", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
