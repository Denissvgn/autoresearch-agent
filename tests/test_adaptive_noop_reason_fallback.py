"""Tests for adaptive_feature_noop_reason fallback logic in direction prepare.py.

When the training pipeline returns `requested: false` for adaptive_features,
the noop_reason should fall back to 'adaptive_features_unavailable' so that
the adaptive_feature_sweeps phase completes (ACCEPTED_ADAPTIVE_NOOP_REASONS).
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

# Minimal stand-alone re-implementation of just the noop_reason logic to
# unit-test the decision tree without running a full training pipeline.

def _resolve_noop_reason(
    adaptive_features: Dict[str, Any],
    results: Dict[str, Any],
) -> str:
    """Mirrors direction prepare.py extract_metrics noop_reason logic."""
    _adaptive_requested = adaptive_features.get("requested")
    return (
        adaptive_features.get("noop_reason")
        or results.get("adaptive_feature_noop_reason")
        or (
            "adaptive_features_unavailable"
            if (_adaptive_requested is False or not adaptive_features)
            else ""
        )
    )


class TestAdaptiveNoopReasonFallback:
    def test_explicit_noop_reason_wins(self):
        reason = _resolve_noop_reason(
            {"requested": False, "noop_reason": "adaptive_feature_schema_unchanged"},
            {},
        )
        assert reason == "adaptive_feature_schema_unchanged"

    def test_results_fallback_when_no_noop_reason_key(self):
        reason = _resolve_noop_reason(
            {"requested": False},
            {"adaptive_feature_noop_reason": "adaptive_not_applicable"},
        )
        assert reason == "adaptive_not_applicable"

    def test_unavailable_fallback_when_requested_false(self):
        """requested=False with no explicit noop_reason → unavailable (accepted)."""
        reason = _resolve_noop_reason({"requested": False}, {})
        assert reason == "adaptive_features_unavailable"

    def test_unavailable_fallback_when_empty_adaptive_features(self):
        """Empty adaptive_features dict → unavailable (accepted)."""
        reason = _resolve_noop_reason({}, {})
        assert reason == "adaptive_features_unavailable"

    def test_empty_string_when_requested_true_no_reason(self):
        """requested=True but no noop_reason → empty string (not a noop)."""
        reason = _resolve_noop_reason({"requested": True}, {})
        assert reason == ""

    def test_empty_string_when_requested_none_no_reason(self):
        """requested key absent → empty string (ambiguous, don't assume unavailable)."""
        reason = _resolve_noop_reason({"version": "1.0"}, {})
        assert reason == ""

    def test_unavailable_is_in_accepted_set(self):
        """Ensure the fallback value is in ACCEPTED_ADAPTIVE_NOOP_REASONS."""
        from src.core.consistency_validator import ACCEPTED_ADAPTIVE_NOOP_REASONS
        assert "adaptive_features_unavailable" in ACCEPTED_ADAPTIVE_NOOP_REASONS
