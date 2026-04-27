"""Development direction-signal health summaries for promotion metadata."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable


def build_development_signal_health(
    metrics_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build observable direction-signal health metrics for development promotion."""

    raw = _first_dict(
        metrics_payload.get("development_signal_health"),
        metrics_payload.get("direction_signal_health"),
        metrics_payload.get("signal_health"),
        metrics_payload.get("monitoring"),
    )
    inference = _first_dict(
        metrics_payload.get("inference_parity"),
        metrics_payload.get("inference_validation"),
        metrics_payload.get("inference"),
    )
    gates = _dict_at(metrics_payload, "gate_results")
    metrics = _dict_at(metrics_payload, "metrics")
    config = _dict_at(metrics_payload, "config")
    threshold = _first_number(
        raw.get("operating_threshold"),
        gates.get("operating_threshold"),
        config.get("operating_threshold"),
        config.get("optimal_threshold"),
    )
    threshold = 0.5 if threshold is None else threshold

    probabilities = _number_list(
        raw.get("direction_proba"),
        raw.get("probabilities"),
        raw.get("prediction_sample"),
        raw.get("direction_probability_sample"),
        metrics_payload.get("direction_proba"),
    )
    summary = _probability_summary(probabilities, threshold=threshold)
    if summary.get("signal_rate") is None:
        summary["signal_rate"] = _first_number(
            raw.get("signal_rate"),
            gates.get("operating_signal_rate"),
            metrics.get("signal_rate"),
        )
    if summary.get("probability_mean") is None:
        summary["probability_mean"] = _first_number(
            raw.get("probability_mean"),
            raw.get("mean"),
            metrics.get("probability_mean"),
        )
    if summary.get("probability_std") is None:
        summary["probability_std"] = _first_number(
            raw.get("probability_std"),
            raw.get("std"),
            metrics.get("probability_std"),
        )
    if summary.get("entropy_mean") is None:
        summary["entropy_mean"] = _first_number(
            raw.get("entropy_mean"),
            raw.get("mean_entropy"),
            metrics.get("entropy_mean"),
        )

    disagreement = _first_number(
        raw.get("base_model_disagreement_mean"),
        raw.get("base_model_disagreement"),
        raw.get("mean_base_model_disagreement"),
        metrics.get("base_model_disagreement"),
    )
    if disagreement is None:
        disagreement = _base_disagreement(raw.get("base_model_probabilities"))

    operational = {
        "feature_schema_mismatch_count": int(
            _first_number(
                raw.get("feature_schema_mismatch_count"),
                inference.get("feature_schema_mismatch_count"),
            )
            or 0
        ),
        "roster_parity_passed": _first_bool(
            raw.get("roster_parity_passed"),
            inference.get("roster_parity_passed"),
            inference.get("model_roster_parity_passed"),
        ),
        "latency_ms_p95": _first_number(
            raw.get("latency_ms_p95"),
            raw.get("p95_latency_ms"),
            inference.get("latency_ms_p95"),
            inference.get("p95_latency_ms"),
        ),
        "adapter_failure_count": int(
            _first_number(
                raw.get("adapter_failure_count"),
                raw.get("adapter_failures"),
                inference.get("adapter_failure_count"),
                inference.get("adapter_failures"),
            )
            or 0
        ),
        "rl_hold_rate": _first_number(
            raw.get("rl_hold_rate"),
            raw.get("hold_rate"),
            metrics_payload.get("rl_hold_rate"),
        ),
        "base_model_disagreement_mean": disagreement,
    }

    training = _first_dict(
        raw.get("training_distribution"),
        raw.get("training_signal_health"),
        metrics_payload.get("training_signal_health"),
    )
    drift = _build_drift(raw=raw, current=summary, training=training)
    alerts = _build_alerts(summary=summary, operational=operational, drift=drift)

    return {
        "schema_version": "development_direction_signal_health.v1",
        "source": "autoresearch_config_promoter",
        "observable": True,
        "status": "alert" if alerts else "ok",
        "metrics": summary,
        "operational": operational,
        "drift": drift,
        "alerts": alerts,
    }


def _probability_summary(
    probabilities: list[float],
    *,
    threshold: float,
) -> Dict[str, Any]:
    if not probabilities:
        return {
            "sample_count": 0,
            "probability_mean": None,
            "probability_std": None,
            "entropy_mean": None,
            "signal_rate": None,
            "operating_threshold": threshold,
        }
    count = len(probabilities)
    mean = sum(probabilities) / count
    variance = sum((value - mean) ** 2 for value in probabilities) / count
    return {
        "sample_count": count,
        "probability_mean": mean,
        "probability_std": math.sqrt(variance),
        "entropy_mean": sum(_binary_entropy(value) for value in probabilities) / count,
        "signal_rate": sum(1 for value in probabilities if value >= threshold) / count,
        "operating_threshold": threshold,
    }


def _build_drift(
    *,
    raw: Dict[str, Any],
    current: Dict[str, Any],
    training: Dict[str, Any],
) -> Dict[str, Any]:
    drift = {
        "psi": _first_number(
            raw.get("psi"),
            raw.get("probability_psi"),
            raw.get("direction_probability_psi"),
        ),
        "kl_divergence": _first_number(
            raw.get("kl_divergence"),
            raw.get("kl"),
            raw.get("probability_kl"),
            raw.get("direction_probability_kl"),
        ),
        "training_distribution": training,
        "deltas": {},
    }
    delta_fields = (
        "probability_mean",
        "probability_std",
        "signal_rate",
        "entropy_mean",
    )
    for field in delta_fields:
        current_value = _first_number(current.get(field))
        training_value = _first_number(training.get(field))
        if current_value is not None and training_value is not None:
            drift["deltas"][field] = current_value - training_value
    if drift["psi"] is None or drift["kl_divergence"] is None:
        current_bins = _number_list(raw.get("probability_histogram"))
        training_bins = _number_list(training.get("probability_histogram"))
        if current_bins and training_bins and len(current_bins) == len(training_bins):
            if drift["psi"] is None:
                drift["psi"] = _psi(current_bins, training_bins)
            if drift["kl_divergence"] is None:
                drift["kl_divergence"] = _kl(current_bins, training_bins)
    return drift


def _build_alerts(
    *,
    summary: Dict[str, Any],
    operational: Dict[str, Any],
    drift: Dict[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    signal_rate = _first_number(summary.get("signal_rate"))
    if signal_rate is not None and (signal_rate <= 0.01 or signal_rate >= 0.99):
        alerts.append({"name": "signal_rate_saturated", "value": signal_rate})
    psi = _first_number(drift.get("psi"))
    if psi is not None and psi >= 0.25:
        alerts.append({"name": "probability_psi_high", "value": psi})
    kl_divergence = _first_number(drift.get("kl_divergence"))
    if kl_divergence is not None and kl_divergence >= 0.10:
        alerts.append({"name": "probability_kl_high", "value": kl_divergence})
    if operational.get("feature_schema_mismatch_count", 0) > 0:
        alerts.append(
            {
                "name": "feature_schema_mismatch",
                "value": operational["feature_schema_mismatch_count"],
            }
        )
    if operational.get("adapter_failure_count", 0) > 0:
        alerts.append(
            {
                "name": "adapter_failures",
                "value": operational["adapter_failure_count"],
            }
        )
    return alerts


def _binary_entropy(probability: float) -> float:
    probability = min(max(probability, 1e-12), 1.0 - 1e-12)
    return -(
        probability * math.log(probability)
        + (1.0 - probability) * math.log(1.0 - probability)
    )


def _base_disagreement(values: Any) -> float | None:
    rows = values if isinstance(values, list) else []
    spreads: list[float] = []
    for row in rows:
        probabilities = _number_list(row)
        if probabilities:
            spreads.append(max(probabilities) - min(probabilities))
    if not spreads:
        return None
    return sum(spreads) / len(spreads)


def _psi(current: list[float], training: list[float]) -> float:
    current_dist = _normalize_histogram(current)
    training_dist = _normalize_histogram(training)
    return sum(
        (current_value - training_value)
        * math.log(current_value / training_value)
        for current_value, training_value in zip(current_dist, training_dist)
    )


def _kl(current: list[float], training: list[float]) -> float:
    current_dist = _normalize_histogram(current)
    training_dist = _normalize_histogram(training)
    return sum(
        current_value * math.log(current_value / training_value)
        for current_value, training_value in zip(current_dist, training_dist)
    )


def _normalize_histogram(values: list[float]) -> list[float]:
    clipped = [max(value, 1e-12) for value in values]
    total = sum(clipped)
    return [value / total for value in clipped]


def _number_list(*values: Any) -> list[float]:
    for value in values:
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
            numbers: list[float] = []
            for item in value:
                number = _first_number(item)
                if number is not None and math.isfinite(number):
                    numbers.append(number)
            if numbers:
                return numbers
    return []


def _dict_at(root: Any, *path: str) -> Dict[str, Any]:
    value = root
    for key in path:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return value if isinstance(value, dict) else {}


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _first_number(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
        if isinstance(value, str):
            try:
                number = float(value)
            except ValueError:
                continue
            if math.isfinite(number):
                return number
    return None


def _first_bool(*values: Any) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
    return None
