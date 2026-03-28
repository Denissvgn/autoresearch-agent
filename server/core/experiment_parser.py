"""Parse prepare.py stdout output into structured metrics."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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
