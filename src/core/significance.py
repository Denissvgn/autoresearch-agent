"""Multi-seed mean±std significance (P2 ops defaults).

The legacy keep/discard comparison is a **fixed-epsilon point test**: a single
metric must beat the session best by ``global_stagnation_epsilon``. For a
deterministic eval that is fine; for a noisy (multi-seed) eval one sample says
nothing — the same config re-run lands ±σ around its true mean, and the agent
chases noise.

This module is the pure-statistics core: when a skill declares
``metric_schema.significance``, the orchestrator groups repeated observations
of the same config (each rerun with a different seed is a new sample — the
trial-identity hash keeps them distinct) and asks whether the candidate
config's sample mean separates from the current best config's sample mean by
``min_sigma`` standard errors of the difference (a Welch-style test without
the t-distribution — auditable arithmetic, no scipy dependency).

Design decisions (house style):

* **Population std (÷n), not sample std (÷n−1).** With 2–5 replicates the
  Bessel correction inflates σ heavily; the gate wants a *conservative*
  band, and ÷n is the wider-undercount side that still resolves at n=1
  (σ=0 → deterministic semantics below).
* **σ=0 on both sides means deterministic.** Two configs whose samples are
  each bit-stable compare by raw means (the Track-D1 inert-change
  intuition, formalized); σ=0 on ONE side falls back to the other side's σ.
* **Sparse data is inconclusive, never a verdict.** Fewer than
  ``min_samples`` on either side returns ``inconclusive`` and the caller
  falls back to the legacy epsilon comparison — significance gating must
  never *block* exploration, only sharpen it.
"""

from __future__ import annotations

from typing import Optional, Sequence

#: Verdicts: ``significant`` (candidate beats the reference), ``regression``
#: (candidate is worse), ``inconclusive`` (not enough separation or data).
SIGNIFICANT = "significant"
REGRESSION = "regression"
INCONCLUSIVE = "inconclusive"


def mean_std(values: Sequence[float]) -> tuple[float, float]:
    """Population mean and standard deviation (÷n; σ=0 for n≤1)."""
    n = len(values)
    if n == 0:
        raise ValueError("mean_std requires at least one value")
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in values) / n
    return mean, var**0.5


def significance_verdict(
    candidate: Sequence[float],
    reference: Sequence[float],
    *,
    direction: str = "higher_is_better",
    min_sigma: float = 1.0,
    min_samples: int = 2,
) -> str:
    """Compare two sample groups; one of SIGNIFICANT / REGRESSION / INCONCLUSIVE.

    ``direction`` follows the manifest's ``metric_schema.primary.direction``
    (``higher_is_better`` default; anything else is lower-is-better).
    Separation is measured in standard errors of the difference
    (``sqrt(σ²c/nc + σ²r/nr)``); a verdict requires at least ``min_sigma``
    standard errors of separation AND at least ``min_samples`` observations
    on each side.
    """
    if len(candidate) < min_samples or len(reference) < min_samples:
        return INCONCLUSIVE
    cand_mean, cand_std = mean_std(candidate)
    ref_mean, ref_std = mean_std(reference)
    diff = cand_mean - ref_mean
    if direction == "higher_is_better":
        oriented = diff
    else:
        oriented = -diff
    # Standard error of the difference (Welch, without the t-distribution).
    se = (cand_std**2 / len(candidate) + ref_std**2 / len(reference)) ** 0.5
    if se == 0.0:
        # Both sides bit-stable → deterministic eval; compare raw means.
        return SIGNIFICANT if oriented > 0 else (
            REGRESSION if oriented < 0 else INCONCLUSIVE
        )
    z = oriented / se
    if z >= min_sigma:
        return SIGNIFICANT
    if z <= -min_sigma:
        return REGRESSION
    return INCONCLUSIVE


def samples_from_rows(
    rows: Sequence[dict], *, canonical_config_hash: str
) -> list[float]:
    """Collect primary-metric samples for one config hash from iteration rows.

    Rows are ``get_iterations`` dicts; each carries ``metrics_json`` whose
    parsed object holds ``canonical_config_hash`` (written by
    ``_record_iteration`` for every trial-identity build). Malformed rows are
    skipped — statistics over partial data beats failing the decision path.
    """
    import json

    out: list[float] = []
    for row in rows:
        if row.get("primary_metric") is None:
            continue
        try:
            metrics = json.loads(row.get("metrics_json") or "{}")
        except (TypeError, ValueError):
            continue
        if metrics.get("canonical_config_hash") == canonical_config_hash:
            out.append(float(row["primary_metric"]))
    return out


def best_config_hash(
    rows: Sequence[dict], *, direction: str = "higher_is_better"
) -> Optional[str]:
    """The config hash behind the session's best recorded iteration, or None.

    Used to group the reference samples (all observations of the best
    config). Reads ``best_metric``/``best_iteration`` semantics indirectly:
    the best *row* is the kept iteration with the extreme primary metric.
    """
    best_row: Optional[dict] = None
    for row in rows:
        metric = row.get("primary_metric")
        if metric is None or row.get("decision") not in ("keep", None):
            continue
        if best_row is None:
            best_row = row
            continue
        better = (
            metric > best_row["primary_metric"]
            if direction == "higher_is_better"
            else metric < best_row["primary_metric"]
        )
        if better:
            best_row = row
    if best_row is None:
        return None
    import json

    try:
        metrics = json.loads(best_row.get("metrics_json") or "{}")
    except (TypeError, ValueError):
        return None
    return metrics.get("canonical_config_hash") or None


__all__ = [
    "INCONCLUSIVE",
    "REGRESSION",
    "SIGNIFICANT",
    "best_config_hash",
    "mean_std",
    "samples_from_rows",
    "significance_verdict",
]
