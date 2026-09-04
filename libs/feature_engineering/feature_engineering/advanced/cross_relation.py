"""Canonical cross-instrument relation lane (instrument-INDEPENDENT).

Unlike the legacy ``cross_asset`` lanes (per-donor, named columns like
``btc_corr_30``), this lane expresses a target's relationships against a FIXED
reference frame so a single pooled policy reads the same feature meaning for ANY
target instrument (BTC, ETH, DOGE, …):

  * the market reference  → BTC
  * the target's donor basket → the mean return of its donor instruments

All outputs are scale-free (correlations ∈[-1,1], clipped beta, clipped
return-spreads), strictly causal (trailing rolling windows over past returns),
and degrade to 0.0 when a reference series is unavailable — so the column set is
deterministic regardless of instrument or donor availability.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

CROSS_RELATION_FEATURE_VERSION = "cross_relation.v1"
# Correlation windows (bars). Fixed so the column contract is deterministic.
CROSS_RELATION_WINDOWS = (30, 120)
_BETA_WINDOW = 120
_STRENGTH_WINDOW = 30
_EPS = 1e-12


def cross_relation_feature_columns() -> list[str]:
    """Deterministic canonical column list (fixed order = obs contract)."""
    cols = [f"rel_corr_btc_{w}" for w in CROSS_RELATION_WINDOWS]
    cols.append(f"rel_beta_btc_{_BETA_WINDOW}")
    cols.append(f"rel_strength_btc_{_STRENGTH_WINDOW}")
    cols += [f"rel_corr_donorbasket_{w}" for w in CROSS_RELATION_WINDOWS]
    cols.append(f"rel_strength_donorbasket_{_STRENGTH_WINDOW}")
    return cols


def _rolling_corr(a: pd.Series, b: pd.Series, w: int) -> pd.Series:
    c = a.rolling(w, min_periods=max(w // 2, 2)).corr(b)
    return c.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-1.0, 1.0)


def _rolling_beta(target: pd.Series, ref: pd.Series, w: int) -> pd.Series:
    cov = target.rolling(w, min_periods=max(w // 2, 2)).cov(ref)
    var = ref.rolling(w, min_periods=max(w // 2, 2)).var()
    beta = cov / (var + _EPS)
    return beta.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-5.0, 5.0)


def _rel_strength(target: pd.Series, ref: pd.Series, w: int) -> pd.Series:
    spread = (target - ref).rolling(w, min_periods=2).mean()
    return spread.fillna(0.0).clip(-0.5, 0.5)


def rank_donors_by_correlation(
    target_ret: pd.Series,
    candidate_rets: "dict[str, pd.Series]",
    *,
    k: int = 3,
    min_corr: float = 0.3,
) -> list[str]:
    """Pick the ``k`` donor instruments most return-correlated with the target.

    Data-driven donor selection for a new instrument: rank candidates by return
    correlation to the target over the shared window, keep those above
    ``min_corr``, take the top ``k``. Ties broken by symbol name for determinism.
    Returns ``[]`` when no candidate clears the threshold (caller should fall back
    to a static quote-asset peer list).
    """
    tgt = pd.to_numeric(target_ret, errors="coerce").astype("float64")
    scored: list[tuple[float, str]] = []
    for sym, ret in candidate_rets.items():
        r = pd.to_numeric(pd.Series(ret).reindex(tgt.index), errors="coerce").astype("float64")
        if r.notna().sum() < 30:
            continue
        corr = tgt.corr(r)
        if pd.notna(corr) and float(corr) >= min_corr:
            scored.append((float(corr), str(sym)))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [sym for _, sym in scored[:k]]


def compute_cross_relation_features(
    target_ret: pd.Series,
    btc_ret: Optional[pd.Series] = None,
    donor_basket_ret: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Canonical cross-relation features for ``target_ret``.

    Args:
        target_ret: target instrument bar returns (e.g. ``close.pct_change()``).
        btc_ret: BTC bar returns aligned to ``target_ret.index`` (market ref).
            ``None``/absent → all btc relation columns are 0.0.
        donor_basket_ret: mean return of the target's donor instruments, aligned.
            ``None``/absent → all donor-basket columns are 0.0.

    Returns:
        DataFrame indexed like ``target_ret`` with exactly
        :func:`cross_relation_feature_columns` columns.
    """
    idx = target_ret.index
    target_ret = pd.to_numeric(target_ret, errors="coerce").astype("float64")
    out: dict[str, pd.Series] = {}

    def _ref(series: Optional[pd.Series]) -> Optional[pd.Series]:
        if series is None:
            return None
        s = pd.to_numeric(series.reindex(idx), errors="coerce").astype("float64")
        # Treat an all-missing reference as unavailable.
        return None if s.notna().sum() < 3 else s

    btc = _ref(btc_ret)
    basket = _ref(donor_basket_ret)

    zero = pd.Series(0.0, index=idx)
    for w in CROSS_RELATION_WINDOWS:
        out[f"rel_corr_btc_{w}"] = _rolling_corr(target_ret, btc, w) if btc is not None else zero
    out[f"rel_beta_btc_{_BETA_WINDOW}"] = (
        _rolling_beta(target_ret, btc, _BETA_WINDOW) if btc is not None else zero
    )
    out[f"rel_strength_btc_{_STRENGTH_WINDOW}"] = (
        _rel_strength(target_ret, btc, _STRENGTH_WINDOW) if btc is not None else zero
    )
    for w in CROSS_RELATION_WINDOWS:
        out[f"rel_corr_donorbasket_{w}"] = (
            _rolling_corr(target_ret, basket, w) if basket is not None else zero
        )
    out[f"rel_strength_donorbasket_{_STRENGTH_WINDOW}"] = (
        _rel_strength(target_ret, basket, _STRENGTH_WINDOW) if basket is not None else zero
    )

    return pd.DataFrame({c: out[c] for c in cross_relation_feature_columns()}, index=idx)
