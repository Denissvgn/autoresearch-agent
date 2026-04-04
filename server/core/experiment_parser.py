"""Parse prepare.py stdout output into structured metrics."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# prepare.py outputs a --- delimited block of key: value pairs
_KV_PATTERN = re.compile(r"^\s*(\w[\w_]*)\s*:\s*(.+?)\s*$")
_ITERATION_MARKER = "ITERATION_RESULT:"


@dataclass
class IterationMetrics:
    """Parsed metrics from a single prepare.py run."""

    status: str = "unknown"
    primary_metric: Optional[float] = None
    metric_name: Optional[str] = None
    direction: str = "higher_is_better"
    all_gates_passed: bool = False
    training_time_s: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "primary_metric": self.primary_metric,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "all_gates_passed": self.all_gates_passed,
            "training_time_s": self.training_time_s,
            **self.extra,
        }


@dataclass
class HpoTrialResult:
    """A single trial from an HPO study."""

    rank: int
    trial_number: int
    composite_score: float
    params: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class HpoStudyResult:
    """Parsed HPO study output from prepare.py --hpo mode."""

    status: str = "unknown"
    n_trials: int = 0
    completed_trials: int = 0
    best_composite: Optional[float] = None
    training_time_s: Optional[float] = None
    top_trials: List[HpoTrialResult] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": "hpo_study",
            "status": self.status,
            "n_trials": self.n_trials,
            "completed_trials": self.completed_trials,
            "best_composite": self.best_composite,
            "training_time_s": self.training_time_s,
            "top_trials": [
                {
                    "rank": t.rank,
                    "trial_number": t.trial_number,
                    "composite_score": t.composite_score,
                    "params": t.params,
                    "metrics": t.metrics,
                }
                for t in self.top_trials
            ],
            **self.extra,
        }


def parse_prepare_output(stdout: str) -> IterationMetrics:
    """Parse the --- delimited key-value block from prepare.py stdout.

    Expected format:
        ---
        status:             completed
        primary_metric:     0.586800
        metric_name:        walkforward_mean_auc
        direction:          higher_is_better
        all_gates_passed:   true
        training_time_s:    342.1
        ...
    """
    metrics = IterationMetrics()

    # Find the --- delimited section
    in_block = False
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if in_block:
                break  # End of block
            in_block = True
            continue
        if not in_block:
            continue

        match = _KV_PATTERN.match(line)
        if not match:
            continue

        key, value = match.group(1), match.group(2).strip()

        if key == "status":
            metrics.status = value
        elif key == "primary_metric":
            try:
                metrics.primary_metric = float(value)
            except ValueError:
                logger.warning("Could not parse primary_metric: %s", value)
        elif key == "metric_name":
            metrics.metric_name = value
        elif key == "direction":
            metrics.direction = value
        elif key == "all_gates_passed":
            metrics.all_gates_passed = value.lower() in ("true", "1", "yes")
        elif key == "training_time_s":
            try:
                metrics.training_time_s = float(value)
            except ValueError:
                pass
        else:
            # Store any extra metrics
            try:
                metrics.extra[key] = float(value)
            except ValueError:
                metrics.extra[key] = value

    return metrics


def parse_iteration_marker(text: str) -> Optional[Dict[str, Any]]:
    """Parse an ITERATION_RESULT: JSON line from agent output.

    The agent is instructed to output:
        ITERATION_RESULT: {"iteration": N, "primary_metric": X, ...}
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_ITERATION_MARKER):
            json_str = stripped[len(_ITERATION_MARKER) :].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Failed to parse iteration marker JSON: %s", json_str)
    return None


def is_hpo_study_output(stdout: str) -> bool:
    """Quick check whether stdout contains an HPO study --- block."""
    in_block = False
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if in_block:
                return False  # end of first block without finding mode
            in_block = True
            continue
        if in_block and stripped.startswith("mode:") and "hpo_study" in stripped:
            return True
    return False


def parse_hpo_study_output(stdout: str) -> Optional[HpoStudyResult]:
    """Parse the --- delimited HPO study block from prepare.py --hpo output.

    Expected format:
        ---
        mode:               hpo_study
        status:             completed
        n_trials:           20
        completed_trials:   18
        best_composite:     0.4250
        training_time_s:    3842.1
        top_k_trials:       3
        trial_1_rank:       1
        trial_1_number:     14
        trial_1_composite:  0.4250
        trial_1_learning_rate: 0.00032
        trial_1_sharpe:     1.85
        ...
        ---
    """
    in_block = False
    kv_pairs: Dict[str, str] = {}

    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if in_block:
                break
            in_block = True
            continue
        if not in_block:
            continue
        match = _KV_PATTERN.match(line)
        if match:
            kv_pairs[match.group(1)] = match.group(2).strip()

    if kv_pairs.get("mode") != "hpo_study":
        return None

    result = HpoStudyResult()
    result.status = kv_pairs.get("status", "unknown")

    for key in ("n_trials", "completed_trials"):
        if key in kv_pairs:
            try:
                setattr(result, key, int(kv_pairs[key]))
            except ValueError:
                pass

    if "best_composite" in kv_pairs:
        try:
            result.best_composite = float(kv_pairs["best_composite"])
        except ValueError:
            pass

    if "training_time_s" in kv_pairs:
        try:
            result.training_time_s = float(kv_pairs["training_time_s"])
        except ValueError:
            pass

    # Parse top_k_trials: trial_N_* keys
    top_k = int(kv_pairs.get("top_k_trials", "0"))
    for i in range(1, top_k + 1):
        prefix = f"trial_{i}_"
        trial_keys = {
            k[len(prefix):]: v
            for k, v in kv_pairs.items()
            if k.startswith(prefix)
        }
        if not trial_keys:
            continue

        trial = HpoTrialResult(
            rank=int(trial_keys.get("rank", str(i))),
            trial_number=int(trial_keys.get("number", "0")),
            composite_score=float(trial_keys.get("composite", "0")),
        )

        # Separate params vs metrics
        _METRIC_KEYS = {
            "composite", "sharpe", "max_drawdown", "total_return",
            "win_rate", "trade_count", "avg_trade_return",
        }
        for k, v in trial_keys.items():
            if k in ("rank", "number"):
                continue
            try:
                fval = float(v)
            except ValueError:
                trial.params[k] = v
                continue
            if k in _METRIC_KEYS:
                trial.metrics[k] = fval
            else:
                trial.params[k] = fval

        result.top_trials.append(trial)

    # Stash remaining keys as extra
    _KNOWN_KEYS = {
        "mode", "status", "n_trials", "completed_trials",
        "best_composite", "training_time_s", "top_k_trials",
    }
    for k, v in kv_pairs.items():
        if k in _KNOWN_KEYS or k.startswith("trial_"):
            continue
        try:
            result.extra[k] = float(v)
        except ValueError:
            result.extra[k] = v

    return result
