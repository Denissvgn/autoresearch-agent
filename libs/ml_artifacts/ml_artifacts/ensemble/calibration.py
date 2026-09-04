"""
ML-23 §11: Time-series-aware probability calibration.

Provides isotonic and sigmoid (Platt) calibration for meta-learner output
probabilities and calibration metrics (ECE, Brier score) for monitoring.

Design choices
--------------
* **Isotonic** (default for direction): non-parametric, handles the often
  non-sigmoidal probability distributions produced by stacking meta-learners.
* **Sigmoid / Platt** (default for volatility, ML-29 V5): two-parameter
  logistic transform with much lower variance on small calibration sets.
  Preferred when the meta-learner output is approximately sigmoidal.
* **Temporal calibration set**: the last ``cal_fraction`` of the OOF
  predictions (chronologically) is held out for calibration fitting.  This
  avoids look-ahead bias that would occur with random splitting.
* **Conservative fallback**: when isotonic calibration is requested but the
  temporal tail is too small for a stable non-parametric fit, a lower-variance
  sigmoid/Platt fallback may be used if enough samples remain.
* **Safety guards**: if the calibrated probabilities degrade AUC, Brier, or ECE
  beyond small tolerances on the calibration slice, the calibrator is *not
  activated* and ``transform()`` returns the original probabilities unchanged.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

logger = logging.getLogger(__name__)

__all__ = [
    "TimeSeriesCalibrator",
    "VALID_CALIBRATION_METHODS",
    "compute_binary_pit_histogram",
    "compute_calibration_metrics",
    "compute_full_validation_calibration_diagnostics",
    "compute_reliability_diagram",
    "compute_threshold_stability_by_fold",
]

# Calibration methods supported by TimeSeriesCalibrator.
#   isotonic    — non-parametric, monotone (default for direction stacking output)
#   sigmoid     — Platt scaling (2-param logistic; low variance, small cal sets)
#   temperature — single-parameter logit scaling (LogisticRegression on logit(p),
#                 no intercept → coef = 1/T); preserves AUC, only sharpens/softens
#   beta        — Beta calibration (LogisticRegression on [ln p, ln(1-p)]); flexible
#                 2-param family that handles non-sigmoidal distortions
_VALID_METHODS = ("isotonic", "sigmoid", "temperature", "beta")
# Public single source of truth for the stacking-calibrator method vocabulary —
# consumed by training_config Field constraints and StackingConfig validation so
# they cannot drift from what TimeSeriesCalibrator actually supports.
VALID_CALIBRATION_METHODS = _VALID_METHODS
_PARAMETRIC_METHODS = ("sigmoid", "temperature", "beta")
_PROBA_EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    """Numerically safe logit; clips probabilities away from {0,1}."""
    p = np.clip(np.asarray(p, dtype=np.float64), _PROBA_EPS, 1.0 - _PROBA_EPS)
    return np.log(p / (1.0 - p))


def _beta_features(p: np.ndarray) -> np.ndarray:
    """Beta-calibration design matrix [ln p, ln(1-p)]."""
    p = np.clip(np.asarray(p, dtype=np.float64), _PROBA_EPS, 1.0 - _PROBA_EPS)
    return np.column_stack([np.log(p), np.log(1.0 - p)])


class TimeSeriesCalibrator:
    """Time-series-aware probability calibration.

    Supports two calibration methods:

    - ``"isotonic"``: Non-parametric isotonic regression.  Better for
      non-sigmoidal distributions (e.g. direction model stacking output).
    - ``"sigmoid"``: Platt scaling via logistic regression.  Lower variance,
      better for small calibration sets (e.g. volatility model).

    Fits on a chronologically held-out calibration set (last *cal_fraction*
    of the OOF predictions).  Falls back to uncalibrated if calibration
    degrades AUC.

    Parameters
    ----------
    cal_fraction : float
        Fraction of the tail of the OOF array to use for calibration fitting.
        Must be in (0, 1).
    min_cal_samples : int
        Minimum number of calibration samples required.  If the calibration
        slice contains fewer samples, ``fit`` is a no-op and ``transform``
        returns probabilities unchanged unless the sigmoid fallback is
        configured and has enough samples.
    method : str
        ``"isotonic"`` or ``"sigmoid"`` (Platt scaling).
    fallback_method : str or None
        Optional fallback calibration method used only when ``method`` is
        ``"isotonic"`` and the calibration tail is too small for isotonic.
        Currently only ``"sigmoid"`` is supported.
    fallback_min_cal_samples : int
        Minimum samples required for the fallback method.
    """

    def __init__(
        self,
        cal_fraction: float = 0.2,
        min_cal_samples: int = 500,
        method: str = "isotonic",
        fallback_method: Optional[str] = "sigmoid",
        fallback_min_cal_samples: int = 200,
        max_auc_drop: float = 0.005,
        max_brier_increase: float = 0.01,
        max_ece_increase: float = 0.02,
        methods: Optional[list[str]] = None,
        objective: str = "brier",
        auc_floor: Optional[float] = None,
    ) -> None:
        if not 0.0 < cal_fraction < 1.0:
            raise ValueError(f"cal_fraction must be in (0, 1), got {cal_fraction}")
        if min_cal_samples < 1:
            raise ValueError(f"min_cal_samples must be >= 1, got {min_cal_samples}")
        if method not in _VALID_METHODS:
            raise ValueError(
                f"method must be one of {_VALID_METHODS}, got '{method}'"
            )
        if fallback_method not in (None, "sigmoid"):
            raise ValueError(
                f"fallback_method must be None or 'sigmoid', got '{fallback_method}'"
            )
        if fallback_min_cal_samples < 1:
            raise ValueError(
                "fallback_min_cal_samples must be >= 1, "
                f"got {fallback_min_cal_samples}"
            )
        if max_auc_drop < 0:
            raise ValueError(f"max_auc_drop must be >= 0, got {max_auc_drop}")
        if max_brier_increase < 0:
            raise ValueError(
                f"max_brier_increase must be >= 0, got {max_brier_increase}"
            )
        if max_ece_increase < 0:
            raise ValueError(
                f"max_ece_increase must be >= 0, got {max_ece_increase}"
            )
        # Opt-in multi-method selection (Action 1a/1b). When ``methods`` is set, fit()
        # fits every listed method PLUS the raw baseline and SELECTS the candidate
        # minimizing ``objective`` (Brier) subject to AUC >= raw_AUC - auc_floor. When
        # ``methods`` is None the calibrator keeps its legacy single-method behavior
        # with the conservative reject-on-regression guard (preserves volatility model).
        if methods is not None:
            if not methods:
                raise ValueError("methods, when provided, must be non-empty")
            for m in methods:
                if m not in _VALID_METHODS:
                    raise ValueError(
                        f"methods entries must be in {_VALID_METHODS}, got '{m}'"
                    )
        if objective not in ("brier",):
            raise ValueError(f"objective must be 'brier', got '{objective}'")
        if auc_floor is not None and auc_floor < 0:
            raise ValueError(f"auc_floor must be >= 0, got {auc_floor}")

        self.cal_fraction = cal_fraction
        self.min_cal_samples = min_cal_samples
        self.method = method
        self.fallback_method = fallback_method
        self.fallback_min_cal_samples = fallback_min_cal_samples
        self.max_auc_drop = max_auc_drop
        self.max_brier_increase = max_brier_increase
        self.max_ece_increase = max_ece_increase
        self.methods = list(methods) if methods is not None else None
        self.objective = objective
        # Default the selection AUC floor to the legacy max_auc_drop when unset.
        self.auc_floor = float(auc_floor) if auc_floor is not None else max_auc_drop
        self._calibrator: Optional[Union[IsotonicRegression, LogisticRegression]] = None
        self._is_fitted = False
        self._active_method: Optional[str] = None
        # Diagnostics populated by fit()
        self.diagnostics_: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(
        self,
        y_proba: np.ndarray,
        y_true: np.ndarray,
    ) -> "TimeSeriesCalibrator":
        """Fit calibration on the last *cal_fraction* of samples.

        Parameters
        ----------
        y_proba : array of shape (n_samples,)
            Raw meta-learner predicted probabilities (class-1 posterior).
        y_true : array of shape (n_samples,)
            Binary ground-truth labels (0 or 1).

        Returns
        -------
        self
            The fitted calibrator (or unchanged if not enough data / AUC
            would degrade).
        """
        y_proba = np.asarray(y_proba, dtype=np.float64).ravel()
        y_true = np.asarray(y_true, dtype=np.float64).ravel()
        self._calibrator = None
        self._is_fitted = False
        self._active_method = None
        self.diagnostics_ = {}

        if len(y_proba) != len(y_true):
            raise ValueError(
                f"y_proba and y_true must have the same length, "
                f"got {len(y_proba)} and {len(y_true)}"
            )

        n = len(y_proba)
        cal_start = int(n * (1.0 - self.cal_fraction))
        n_cal = n - cal_start
        fit_method = self.method
        min_required = self.min_cal_samples
        fallback_reason: Optional[str] = None

        # Action 1a/1b: in multi-method mode the parametric candidates
        # (sigmoid/temperature/beta) are stable on a few hundred samples, so gate on
        # the lower ``fallback_min_cal_samples`` floor — ``_fit_select_best`` simply
        # won't pick isotonic when the slice is too small for it (raw stays the
        # safety net). This is what lets calibration run on the small post-dead-zone
        # OOF that previously tripped the isotonic 500-sample gate every iteration.
        if self.methods:
            min_required = self.fallback_min_cal_samples
            if n_cal < min_required:
                self.diagnostics_ = {
                    "cal_method_requested": ",".join(self.methods),
                    "cal_method": "none",
                    "cal_is_fitted": 0.0,
                    "cal_selection_mode": "best_brier_under_auc_floor",
                    "cal_n_samples": float(n_cal),
                    "cal_min_samples_required": float(min_required),
                    "cal_skip_reason": "multi_method_min_cal_samples_not_met",
                }
                logger.info(
                    "Calibration skipped (multi-method): only %d samples "
                    "(need >= %d)",
                    n_cal,
                    min_required,
                )
                return self
        elif n_cal < self.min_cal_samples:
            if (
                self.method == "isotonic"
                and self.fallback_method == "sigmoid"
                and n_cal >= self.fallback_min_cal_samples
            ):
                fit_method = "sigmoid"
                min_required = self.fallback_min_cal_samples
                fallback_reason = "primary_min_cal_samples_not_met"
                logger.info(
                    "Calibration fallback: isotonic requested with %d samples "
                    "(need >= %d); trying sigmoid fallback (need >= %d)",
                    n_cal,
                    self.min_cal_samples,
                    self.fallback_min_cal_samples,
                )
            else:
                reason = (
                    "primary_and_fallback_min_cal_samples_not_met"
                    if self.method == "isotonic" and self.fallback_method
                    else "min_cal_samples_not_met"
                )
                self.diagnostics_ = {
                    "cal_method_requested": self.method,
                    "cal_method": "none",
                    "cal_is_fitted": 0.0,
                    "cal_n_samples": float(n_cal),
                    "cal_min_samples_required": float(self.min_cal_samples),
                    "cal_fallback_min_samples_required": float(
                        self.fallback_min_cal_samples
                    ),
                    "cal_skip_reason": reason,
                }
                logger.info(
                    "Calibration skipped: only %d samples available "
                    "(need >= %d)",
                    n_cal,
                    self.min_cal_samples,
                )
                return self

        cal_proba = y_proba[cal_start:]
        cal_true = y_true[cal_start:]

        # Need both classes in calibration set
        if len(np.unique(cal_true)) < 2:
            self.diagnostics_ = {
                "cal_method_requested": self.method,
                "cal_method": "none",
                "cal_is_fitted": 0.0,
                "cal_n_samples": float(n_cal),
                "cal_min_samples_required": float(min_required),
                "cal_skip_reason": "single_class_calibration_set",
            }
            logger.warning(
                "Calibration skipped: calibration set has only one class"
            )
            return self

        # Action 1a/1b: when a method list is configured, fit every candidate plus
        # the raw baseline and SELECT the lowest-Brier one that holds AUC above the
        # floor (relaxed acceptance). Otherwise keep the legacy single-method guard.
        if self.methods:
            return self._fit_select_best(
                cal_proba,
                cal_true,
                n_cal=n_cal,
                min_required=min_required,
                fallback_reason=fallback_reason,
            )

        # Fit calibrator based on method (legacy single-method path)
        calibrator, calibrated = self._fit_one_method(fit_method, cal_proba, cal_true)

        # AUC safety guard
        auc_before = float(roc_auc_score(cal_true, cal_proba))
        auc_after = float(roc_auc_score(cal_true, calibrated))
        metrics_before = compute_calibration_metrics(cal_proba, cal_true)
        metrics_after = compute_calibration_metrics(calibrated, cal_true)
        brier_before = metrics_before["brier_score"]
        brier_after = metrics_after["brier_score"]
        ece_before = metrics_before["ece"]
        ece_after = metrics_after["ece"]

        self.diagnostics_ = {
            "cal_method_requested": self.method,
            "cal_method": fit_method,
            "cal_is_fitted": 0.0,
            "cal_fallback_used": float(fit_method != self.method),
            "cal_auc_before": auc_before,
            "cal_auc_after": auc_after,
            "cal_n_samples": float(n_cal),
            "cal_min_samples_required": float(min_required),
            "cal_brier_before": brier_before,
            "cal_brier_after": brier_after,
            "cal_ece_before": ece_before,
            "cal_ece_after": ece_after,
            "cal_max_auc_drop": self.max_auc_drop,
            "cal_max_brier_increase": self.max_brier_increase,
            "cal_max_ece_increase": self.max_ece_increase,
        }
        if fallback_reason:
            self.diagnostics_["cal_fallback_reason"] = fallback_reason

        auc_passed = auc_after >= auc_before - self.max_auc_drop
        brier_passed = brier_after <= brier_before + self.max_brier_increase
        ece_passed = ece_after <= ece_before + self.max_ece_increase

        if auc_passed and brier_passed and ece_passed:
            self._calibrator = calibrator
            self._is_fitted = True
            self._active_method = fit_method
            self.diagnostics_["cal_is_fitted"] = 1.0
            logger.info(
                "Calibration fitted (%s): AUC %.4f → %.4f, "
                "Brier %.4f → %.4f, ECE %.4f → %.4f (%d cal samples)",
                fit_method,
                auc_before,
                auc_after,
                self.diagnostics_["cal_brier_before"],
                self.diagnostics_["cal_brier_after"],
                self.diagnostics_["cal_ece_before"],
                self.diagnostics_["cal_ece_after"],
                n_cal,
            )
        else:
            rejection_reasons = []
            if not auc_passed:
                rejection_reasons.append("auc_drop")
            if not brier_passed:
                rejection_reasons.append("brier_increase")
            if not ece_passed:
                rejection_reasons.append("ece_increase")
            self.diagnostics_["cal_rejection_reason"] = ",".join(rejection_reasons)
            logger.warning(
                "Calibration rejected (%s): AUC %.4f → %.4f, "
                "Brier %.4f → %.4f, ECE %.4f → %.4f. "
                "Reasons: %s. Returning uncalibrated.",
                fit_method,
                auc_before,
                auc_after,
                brier_before,
                brier_after,
                ece_before,
                ece_after,
                self.diagnostics_["cal_rejection_reason"],
            )

        return self

    def _fit_one_method(
        self,
        method: str,
        cal_proba: np.ndarray,
        cal_true: np.ndarray,
    ) -> tuple[Any, np.ndarray]:
        """Fit a single calibration method on the calibration slice and return
        ``(fitted_calibrator, calibrated_proba_on_cal_slice)``."""
        if method == "isotonic":
            calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            calibrator.fit(cal_proba, cal_true)
            calibrated = calibrator.predict(cal_proba)
        elif method == "sigmoid":
            calibrator = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
            calibrator.fit(cal_proba.reshape(-1, 1), cal_true)
            calibrated = calibrator.predict_proba(cal_proba.reshape(-1, 1))[:, 1]
        elif method == "temperature":
            # Single-parameter logit scaling: LogisticRegression on logit(p) with no
            # intercept → the learned coefficient is 1/T. Weak regularization (high C)
            # so the temperature is barely shrunk.
            calibrator = LogisticRegression(
                C=1e6, solver="lbfgs", max_iter=1000, fit_intercept=False
            )
            feats = _logit(cal_proba).reshape(-1, 1)
            calibrator.fit(feats, cal_true)
            calibrated = calibrator.predict_proba(feats)[:, 1]
        elif method == "beta":
            # Beta calibration: LogisticRegression on [ln p, ln(1-p)].
            calibrator = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
            feats = _beta_features(cal_proba)
            calibrator.fit(feats, cal_true)
            calibrated = calibrator.predict_proba(feats)[:, 1]
        else:
            raise ValueError(f"unknown calibration method '{method}'")
        return calibrator, np.asarray(calibrated, dtype=np.float64).ravel()

    def _fit_select_best(
        self,
        cal_proba: np.ndarray,
        cal_true: np.ndarray,
        *,
        n_cal: int,
        min_required: int,
        fallback_reason: Optional[str],
    ) -> "TimeSeriesCalibrator":
        """Action 1a/1b: fit every configured method plus the raw baseline and
        activate the lowest-Brier candidate that holds AUC >= raw_AUC - auc_floor.

        Raw (no calibration) is always a candidate, so calibration is activated only
        when some method strictly improves Brier under the AUC floor — this replaces
        the conservative reject-on-any-Brier-regression guard with a select-best rule.
        """
        auc_before = float(roc_auc_score(cal_true, cal_proba))
        metrics_before = compute_calibration_metrics(cal_proba, cal_true)
        brier_before = metrics_before["brier_score"]
        ece_before = metrics_before["ece"]

        # (method, calibrator_or_None, auc, brier, ece, eligible)
        candidates: list[tuple[str, Any, float, float, float, bool]] = [
            ("raw", None, auc_before, brier_before, ece_before, True)
        ]
        per_method_diag: Dict[str, Any] = {}
        for method in self.methods or []:
            try:
                calibrator, calibrated = self._fit_one_method(
                    method, cal_proba, cal_true
                )
            except Exception as exc:  # a degenerate method must not abort selection
                per_method_diag[method] = {"error": str(exc)}
                logger.warning("Calibration method %s failed: %s", method, exc)
                continue
            auc_after = float(roc_auc_score(cal_true, calibrated))
            m_after = compute_calibration_metrics(calibrated, cal_true)
            eligible = auc_after >= auc_before - self.auc_floor
            candidates.append(
                (
                    method,
                    calibrator,
                    auc_after,
                    float(m_after["brier_score"]),
                    float(m_after["ece"]),
                    eligible,
                )
            )
            per_method_diag[method] = {
                "auc": auc_after,
                "brier": float(m_after["brier_score"]),
                "ece": float(m_after["ece"]),
                "auc_floor_passed": float(eligible),
            }

        eligible_candidates = [c for c in candidates if c[5]]
        # Lowest Brier wins; ties keep the earlier entry (raw, then methods order).
        best = min(eligible_candidates, key=lambda c: c[3])
        best_method, best_calibrator, best_auc, best_brier, best_ece, _ = best

        self.diagnostics_ = {
            "cal_method_requested": ",".join(self.methods or []),
            "cal_method": best_method,
            "cal_is_fitted": 0.0,
            "cal_selection_mode": "best_brier_under_auc_floor",
            "cal_auc_before": auc_before,
            "cal_auc_after": best_auc,
            "cal_n_samples": float(n_cal),
            "cal_min_samples_required": float(min_required),
            "cal_brier_before": brier_before,
            "cal_brier_after": best_brier,
            "cal_ece_before": ece_before,
            "cal_ece_after": best_ece,
            "cal_auc_floor": self.auc_floor,
            "cal_objective": self.objective,
            "cal_candidates": per_method_diag,
        }
        if fallback_reason:
            self.diagnostics_["cal_fallback_reason"] = fallback_reason

        if best_method != "raw" and best_calibrator is not None:
            self._calibrator = best_calibrator
            self._is_fitted = True
            self._active_method = best_method
            self.diagnostics_["cal_is_fitted"] = 1.0
            self.diagnostics_["cal_fallback_used"] = float(best_method != self.method)
            logger.info(
                "Calibration selected (%s of %s): AUC %.4f → %.4f, "
                "Brier %.4f → %.4f (floor=%.4f, %d cal samples)",
                best_method,
                self.methods,
                auc_before,
                best_auc,
                brier_before,
                best_brier,
                self.auc_floor,
                n_cal,
            )
        else:
            self.diagnostics_["cal_rejection_reason"] = "raw_best_under_objective"
            logger.info(
                "Calibration not activated: raw probabilities had the lowest Brier "
                "(%.4f) among AUC-floor-passing candidates",
                brier_before,
            )
        return self

    def transform(self, y_proba: np.ndarray) -> np.ndarray:
        """Apply calibration to predicted probabilities.

        Returns the input unchanged if the calibrator was not fitted
        (insufficient data or AUC degradation guard triggered).
        """
        if not self._is_fitted or self._calibrator is None:
            return np.asarray(y_proba, dtype=np.float64).ravel()
        y_proba = np.asarray(y_proba, dtype=np.float64).ravel()
        active_method = self._resolve_active_method()
        if active_method == "isotonic":
            return self._calibrator.predict(y_proba)
        if active_method == "sigmoid":
            return self._calibrator.predict_proba(y_proba.reshape(-1, 1))[:, 1]
        if active_method == "temperature":
            return self._calibrator.predict_proba(_logit(y_proba).reshape(-1, 1))[:, 1]
        if active_method == "beta":
            return self._calibrator.predict_proba(_beta_features(y_proba))[:, 1]
        return y_proba

    def reject(self, reason: str, **diagnostics: Any) -> None:
        """Deactivate a fitted calibrator after a later validation check.

        The initial fit guard evaluates the chronological calibration tail.
        Callers may perform broader OOF validation afterwards; this method keeps
        the fit diagnostics while ensuring serialized inference artifacts fall
        back to raw probabilities.
        """
        self._calibrator = None
        self._is_fitted = False
        self._active_method = None
        self.diagnostics_["cal_is_fitted"] = 0.0
        self.diagnostics_["cal_rejection_reason"] = reason
        self.diagnostics_.update(diagnostics)

    @property
    def is_fitted(self) -> bool:
        """Whether calibration is active."""
        return self._is_fitted

    @property
    def active_method(self) -> Optional[str]:
        """The fitted method, including fallback method if one was used."""
        return self._resolve_active_method()

    def _resolve_active_method(self) -> Optional[str]:
        """Return the fitted method, tolerating older serialized calibrators."""
        if hasattr(self, "_is_fitted") and not self._is_fitted:
            return None

        active_method = getattr(self, "_active_method", None)
        if active_method in _VALID_METHODS:
            return active_method

        legacy_active_method = self.__dict__.get("active_method")
        if legacy_active_method in _VALID_METHODS:
            self._active_method = legacy_active_method
            return legacy_active_method

        diagnostics_method = getattr(self, "diagnostics_", {}).get("cal_method")
        if diagnostics_method in _VALID_METHODS:
            self._active_method = diagnostics_method
            return diagnostics_method

        if (
            getattr(self, "_is_fitted", False)
            and getattr(self, "_calibrator", None) is not None
        ):
            method = getattr(self, "method", None)
            if method in _VALID_METHODS:
                self._active_method = method
                return method
        return None


# ------------------------------------------------------------------
# Standalone metrics
# ------------------------------------------------------------------


def compute_calibration_metrics(
    y_proba: np.ndarray,
    y_true: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, float]:
    """Compute Expected Calibration Error (ECE) and Brier score.

    Parameters
    ----------
    y_proba : array of shape (n_samples,)
        Predicted probabilities.
    y_true : array of shape (n_samples,)
        Binary ground-truth labels.
    n_bins : int
        Number of equal-width bins for ECE computation.

    Returns
    -------
    dict with keys ``brier_score`` and ``ece``.
    """
    y_proba = np.asarray(y_proba, dtype=np.float64).ravel()
    y_true = np.asarray(y_true, dtype=np.float64).ravel()

    brier = float(brier_score_loss(y_true, y_proba))

    # Expected Calibration Error (ECE)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        if i == n_bins - 1:
            mask = (y_proba >= bin_edges[i]) & (y_proba <= bin_edges[i + 1])
        else:
            mask = (y_proba >= bin_edges[i]) & (y_proba < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_conf = float(y_proba[mask].mean())
        bin_acc = float(y_true[mask].mean())
        ece += mask.sum() * abs(bin_acc - bin_conf)
    ece /= len(y_proba)

    return {"brier_score": brier, "ece": float(ece)}


def compute_reliability_diagram(
    y_proba: np.ndarray,
    y_true: np.ndarray,
    n_bins: int = 10,
) -> list[dict[str, Any]]:
    """Return reliability-diagram bin data for report/MLflow artifacts."""
    y_proba = np.asarray(y_proba, dtype=np.float64).ravel()
    y_true = np.asarray(y_true, dtype=np.float64).ravel()
    if len(y_proba) != len(y_true):
        raise ValueError("y_proba and y_true must have the same length")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows: list[dict[str, Any]] = []
    n = len(y_proba)
    for i in range(n_bins):
        lower = float(bin_edges[i])
        upper = float(bin_edges[i + 1])
        if i == n_bins - 1:
            mask = (y_proba >= lower) & (y_proba <= upper)
        else:
            mask = (y_proba >= lower) & (y_proba < upper)
        count = int(mask.sum())
        if count:
            mean_predicted = float(y_proba[mask].mean())
            observed_rate = float(y_true[mask].mean())
            abs_error = float(abs(observed_rate - mean_predicted))
        else:
            mean_predicted = None
            observed_rate = None
            abs_error = None
        rows.append(
            {
                "bin_index": i,
                "lower": lower,
                "upper": upper,
                "count": count,
                "fraction": float(count / n) if n else 0.0,
                "mean_predicted": mean_predicted,
                "observed_rate": observed_rate,
                "abs_error": abs_error,
            }
        )
    return rows


def compute_binary_pit_histogram(
    y_proba: np.ndarray,
    y_true: np.ndarray,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Compute deterministic binary PIT-style histogram data.

    Binary outcomes do not have a unique non-randomized PIT.  This uses the
    midpoint of the randomized PIT interval: for class 0, ``0.5 * P(Y=0)``;
    for class 1, ``P(Y=0) + 0.5 * P(Y=1)``.
    """
    y_proba = np.asarray(y_proba, dtype=np.float64).ravel()
    y_true = np.asarray(y_true, dtype=np.float64).ravel()
    if len(y_proba) != len(y_true):
        raise ValueError("y_proba and y_true must have the same length")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    p = np.clip(y_proba, 0.0, 1.0)
    pit = np.where(y_true >= 0.5, 1.0 - 0.5 * p, 0.5 * (1.0 - p))
    counts, edges = np.histogram(pit, bins=n_bins, range=(0.0, 1.0))
    return {
        "method": "binary_midpoint_randomized_pit",
        "n_bins": int(n_bins),
        "bin_edges": [float(v) for v in edges.tolist()],
        "counts": [int(v) for v in counts.tolist()],
        "pit_mean": float(pit.mean()) if len(pit) else None,
        "pit_std": float(pit.std()) if len(pit) else None,
    }


def _best_youden_threshold(y_proba: np.ndarray, y_true: np.ndarray) -> dict[str, Any]:
    """Find a deterministic threshold that maximizes Youden's J."""
    y_proba = np.asarray(y_proba, dtype=np.float64).ravel()
    y_true = np.asarray(y_true, dtype=np.float64).ravel()
    positives = float((y_true >= 0.5).sum())
    negatives = float((y_true < 0.5).sum())
    if positives == 0 or negatives == 0 or len(y_proba) == 0:
        return {
            "threshold": None,
            "youden_j": None,
            "signal_rate": None,
            "n_samples": int(len(y_proba)),
            "skipped": True,
            "reason": "single_class_or_empty",
        }

    thresholds = np.unique(np.quantile(y_proba, np.linspace(0.0, 1.0, 101)))
    best: dict[str, Any] = {
        "threshold": float(thresholds[0]),
        "youden_j": -np.inf,
        "signal_rate": 0.0,
        "n_samples": int(len(y_proba)),
        "skipped": False,
    }
    for threshold in thresholds:
        pred = y_proba >= threshold
        tp = float(((pred) & (y_true >= 0.5)).sum())
        fp = float(((pred) & (y_true < 0.5)).sum())
        tpr = tp / positives
        fpr = fp / negatives
        score = tpr - fpr
        signal_rate = float(pred.mean())
        if score > best["youden_j"]:
            best = {
                "threshold": float(threshold),
                "youden_j": float(score),
                "signal_rate": signal_rate,
                "n_samples": int(len(y_proba)),
                "skipped": False,
            }
    return best


def _jsonable_fold_id(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value
    return str(value)


def compute_threshold_stability_by_fold(
    y_proba: np.ndarray,
    y_true: np.ndarray,
    fold_ids: np.ndarray,
) -> dict[str, Any]:
    """Compute threshold and signal-rate stability across OOF folds."""
    y_proba = np.asarray(y_proba, dtype=np.float64).ravel()
    y_true = np.asarray(y_true, dtype=np.float64).ravel()
    fold_ids = np.asarray(fold_ids).ravel()
    if not (len(y_proba) == len(y_true) == len(fold_ids)):
        raise ValueError("y_proba, y_true, and fold_ids must have the same length")

    global_threshold = _best_youden_threshold(y_proba, y_true)
    threshold_value = global_threshold.get("threshold")
    fold_rows: list[dict[str, Any]] = []
    for fold in sorted(set(fold_ids.tolist())):
        mask = fold_ids == fold
        row = _best_youden_threshold(y_proba[mask], y_true[mask])
        row["fold"] = _jsonable_fold_id(fold)
        if threshold_value is not None and mask.sum():
            row["signal_rate_at_global_threshold"] = float(
                (y_proba[mask] >= float(threshold_value)).mean()
            )
        else:
            row["signal_rate_at_global_threshold"] = None
        fold_rows.append(row)

    thresholds = [
        float(row["threshold"])
        for row in fold_rows
        if row.get("threshold") is not None and not row.get("skipped")
    ]
    signal_rates = [
        float(row["signal_rate_at_global_threshold"])
        for row in fold_rows
        if row.get("signal_rate_at_global_threshold") is not None
    ]
    threshold_mean = float(np.mean(thresholds)) if thresholds else None
    threshold_std = float(np.std(thresholds)) if thresholds else None
    signal_mean = float(np.mean(signal_rates)) if signal_rates else None
    signal_std = float(np.std(signal_rates)) if signal_rates else None
    return {
        "global_threshold": global_threshold,
        "folds": fold_rows,
        "threshold_mean": threshold_mean,
        "threshold_std": threshold_std,
        "threshold_min": float(np.min(thresholds)) if thresholds else None,
        "threshold_max": float(np.max(thresholds)) if thresholds else None,
        "threshold_cv": (
            float(threshold_std / abs(threshold_mean))
            if threshold_mean not in (None, 0.0) and threshold_std is not None
            else None
        ),
        "signal_rate_distribution": {
            "mean": signal_mean,
            "std": signal_std,
            "min": float(np.min(signal_rates)) if signal_rates else None,
            "max": float(np.max(signal_rates)) if signal_rates else None,
            "by_fold": signal_rates,
        },
    }


def _calibration_candidate_rows(diag: Dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a calibrator's per-method selection diagnostics into an ordered
    list of candidate rows for the full-validation report (I6).

    The raw (no-calibration) baseline is included first so it is visible when raw
    had the lowest Brier and won. Works for both the multi-method
    ``_fit_select_best`` path (``cal_candidates`` populated) and the legacy
    single-method path (one fitted method)."""
    rows: list[dict[str, Any]] = []
    if "cal_brier_before" in diag or "cal_auc_before" in diag:
        rows.append(
            {
                "method": "raw",
                "auc": diag.get("cal_auc_before"),
                "brier": diag.get("cal_brier_before"),
                "ece": diag.get("cal_ece_before"),
                "auc_floor_passed": True,
            }
        )
    per_method = diag.get("cal_candidates")
    if isinstance(per_method, dict) and per_method:
        for method, m in per_method.items():
            if not isinstance(m, dict):
                continue
            if "error" in m:
                rows.append({"method": method, "error": m["error"]})
                continue
            rows.append(
                {
                    "method": method,
                    "auc": m.get("auc"),
                    "brier": m.get("brier"),
                    "ece": m.get("ece"),
                    "auc_floor_passed": bool(m.get("auc_floor_passed", 0.0)),
                }
            )
    else:
        # Legacy single-method path: synthesize the one fitted method's row.
        m_name = diag.get("cal_method")
        if m_name and m_name not in ("raw", "none") and "cal_brier_after" in diag:
            rows.append(
                {
                    "method": m_name,
                    "auc": diag.get("cal_auc_after"),
                    "brier": diag.get("cal_brier_after"),
                    "ece": diag.get("cal_ece_after"),
                    "auc_floor_passed": diag.get("cal_rejection_reason") is None,
                }
            )
    return rows


def compute_full_validation_calibration_diagnostics(
    y_proba_raw: np.ndarray,
    y_true: np.ndarray,
    *,
    y_proba_calibrated: Optional[np.ndarray] = None,
    fold_ids: Optional[np.ndarray] = None,
    regime_labels: Optional[np.ndarray] = None,
    selection_diagnostics: Optional[Dict[str, Any]] = None,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Build full-validation calibration diagnostics for DPU-020.

    ``selection_diagnostics`` is the fitted ``TimeSeriesCalibrator.diagnostics_``;
    when provided it surfaces the per-method candidate scores and the reason the
    selected probability space won (I6 — auditable "why raw won")."""
    y_proba_raw = np.asarray(y_proba_raw, dtype=np.float64).ravel()
    y_true = np.asarray(y_true, dtype=np.float64).ravel()
    if len(y_proba_raw) != len(y_true):
        raise ValueError("y_proba_raw and y_true must have the same length")

    if y_proba_calibrated is not None:
        y_proba_eval = np.asarray(y_proba_calibrated, dtype=np.float64).ravel()
        if len(y_proba_eval) != len(y_true):
            raise ValueError("y_proba_calibrated and y_true must have the same length")
        probability_space = "calibrated"
    else:
        y_proba_eval = y_proba_raw
        probability_space = "raw"

    report: dict[str, Any] = {
        "version": 1,
        "n_samples": int(len(y_true)),
        "probability_space": probability_space,
        "raw": {
            "metrics": compute_calibration_metrics(y_proba_raw, y_true, n_bins=n_bins),
            "reliability_diagram": compute_reliability_diagram(
                y_proba_raw, y_true, n_bins=n_bins
            ),
            "pit_histogram": compute_binary_pit_histogram(
                y_proba_raw, y_true, n_bins=n_bins
            ),
        },
        "selected": {
            "metrics": compute_calibration_metrics(
                y_proba_eval, y_true, n_bins=n_bins
            ),
            "reliability_diagram": compute_reliability_diagram(
                y_proba_eval, y_true, n_bins=n_bins
            ),
            "pit_histogram": compute_binary_pit_histogram(
                y_proba_eval, y_true, n_bins=n_bins
            ),
        },
    }
    if y_proba_calibrated is not None:
        report["calibrated"] = report["selected"]

    # I6: surface the calibrator's per-method selection evidence so "why raw won"
    # (or which method was activated) is auditable. Purely additive — the raw /
    # selected metric blocks above are untouched. ``selection_diagnostics`` is
    # None for probes that do not run selection (e.g. the TSFM comparison).
    if isinstance(selection_diagnostics, dict) and selection_diagnostics:
        report["selected"]["method"] = selection_diagnostics.get("cal_method")
        report["candidates"] = _calibration_candidate_rows(selection_diagnostics)
        report["selection"] = {
            key: selection_diagnostics[src]
            for key, src in (
                ("mode", "cal_selection_mode"),
                ("rejection_reason", "cal_rejection_reason"),
                ("skip_reason", "cal_skip_reason"),
                ("fallback_reason", "cal_fallback_reason"),
                ("n_cal_samples", "cal_n_samples"),
                ("min_samples_required", "cal_min_samples_required"),
                ("objective", "cal_objective"),
                ("auc_floor", "cal_auc_floor"),
            )
            if src in selection_diagnostics
        }

    if fold_ids is not None:
        report["threshold_stability_by_fold"] = compute_threshold_stability_by_fold(
            y_proba_eval, y_true, fold_ids
        )
        report["signal_rate_distribution"] = report[
            "threshold_stability_by_fold"
        ]["signal_rate_distribution"]
    else:
        report["threshold_stability_by_fold"] = {
            "available": False,
            "reason": "fold_ids_absent",
        }
        report["signal_rate_distribution"] = {
            "available": False,
            "reason": "fold_ids_absent",
        }

    if regime_labels is None:
        report["per_regime_calibration"] = {
            "available": False,
            "reason": "regime_labels_absent",
        }
    else:
        regimes = np.asarray(regime_labels).ravel()
        if len(regimes) != len(y_true):
            raise ValueError("regime_labels and y_true must have the same length")
        by_regime: dict[str, Any] = {}
        for regime in sorted(set(regimes.tolist()), key=str):
            mask = regimes == regime
            if int(mask.sum()) == 0:
                continue
            by_regime[str(regime)] = {
                "n_samples": int(mask.sum()),
                "metrics": compute_calibration_metrics(
                    y_proba_eval[mask], y_true[mask], n_bins=n_bins
                ),
            }
        report["per_regime_calibration"] = {
            "available": True,
            "regimes": by_regime,
        }

    return report
