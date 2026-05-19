"""Issue 6 — adaptive_feature_sweeps hard-block when adaptive is not attempted.

Root cause traced in live session res_0ca02946650e:
prepare.py correctly computes `adaptive_feature_noop_reason: "adaptive_
features_unavailable"` from the trainer's `adaptive_features.requested == False`
and prints it in the `---` block. But the trainer's `results.json` writes an
explicit `adaptive_feature_noop_reason: null` at top level, and
`merge_result_payload` (the orchestrator's result-artifact enricher) blindly
overwrites the parsed value with that null. The consistency validator then
hard-blocks with `adaptive_feature_not_enabled` for what is really a
"not attempted yet" iteration.

Two fixes:
- Fix A (primary, root cause): the enricher must not nullify a marker value
  with an explicit None from results.json. Apply to both nested and
  top-level result keys.
- Fix B (defense in depth): check_adaptive_feature_sweep must treat
  `requested=False AND enabled=False AND no noop_reason` as legitimate
  "not attempted" (return None). The adaptive_feature_not_enabled blocker is
  reserved for the gaming-detection case (already covered by the
  requested=True+enabled=False branch as adaptive_feature_requested_but_inactive).
"""
from __future__ import annotations

from src.core.consistency_validator import check_adaptive_feature_sweep
from src.core.result_artifact import merge_result_payload


# --- Fix A: enricher must not nullify computed marker values --------------- #


def test_fixa_top_level_null_does_not_overwrite_marker_string():
    """The exact Issue-6 shape: prepare.py parsed
    adaptive_feature_noop_reason='adaptive_features_unavailable'; trainer's
    results.json has the key set to null. Marker must keep the parsed value.
    """
    marker = {"adaptive_feature_noop_reason": "adaptive_features_unavailable"}
    payload = {"adaptive_feature_noop_reason": None}

    merge_result_payload(marker, payload)

    assert marker["adaptive_feature_noop_reason"] == "adaptive_features_unavailable"


def test_fixa_top_level_real_value_still_overwrites():
    """Regression: a non-None artifact value still wins (existing behavior)."""
    marker = {"adaptive_feature_noop_reason": "adaptive_features_unavailable"}
    payload = {"adaptive_feature_noop_reason": "adaptive_not_applicable"}

    merge_result_payload(marker, payload)

    assert marker["adaptive_feature_noop_reason"] == "adaptive_not_applicable"


def test_fixa_top_level_marker_absent_then_null_is_harmless():
    """When the marker has no value AND the payload is None, the merge
    introduces None (harmless — there was nothing to protect). The Fix A
    invariant is narrower: NEVER overwrite a non-None marker value with None.
    """
    marker: dict = {}
    payload = {"adaptive_feature_noop_reason": None}

    merge_result_payload(marker, payload)

    # Acceptable: nothing was lost; the field simply mirrors the payload.
    assert marker.get("adaptive_feature_noop_reason") is None


def test_fixa_nested_null_does_not_overwrite_dict():
    """Nested key (e.g. adaptive_features) — explicit None in payload must
    not blow away an existing dict in the marker."""
    marker = {"adaptive_features": {"enabled": False, "requested": False}}
    payload = {"adaptive_features": None}

    merge_result_payload(marker, payload)

    assert isinstance(marker["adaptive_features"], dict)
    assert marker["adaptive_features"]["enabled"] is False


def test_fixa_nested_dict_still_deep_merges():
    """Regression: when both marker and payload have a dict for the key, the
    existing deep-merge-result-wins behavior is preserved."""
    marker = {"adaptive_features": {"enabled": False, "n_features": 90}}
    payload = {"adaptive_features": {"enabled": True, "selected_count": 3}}

    merge_result_payload(marker, payload)

    assert marker["adaptive_features"]["enabled"] is True  # result wins
    assert marker["adaptive_features"]["selected_count"] == 3
    assert marker["adaptive_features"]["n_features"] == 90  # marker-only key preserved


# --- Fix B: not-attempted is not a hard blocker --------------------------- #


def _af(**kwargs):
    """Build an adaptive_features dict resembling what direction/prepare.py emits."""
    base = {
        "enabled": False,
        "requested": False,
        "selected_count": 0,
        "selected_feature_names": [],
        "n_features": 90,
        "feature_schema_hash": "h",
        "version": "adaptive_levels.v1",
    }
    base.update(kwargs)
    return base


def test_fixb_not_requested_and_not_enabled_is_not_blocker():
    """The exact Issue-6 case: agent ran prepare.py without requesting adaptive
    features. Validator must NOT hard-block this iteration; the next-action
    nudge will steer the agent.
    """
    metrics = {"adaptive_features": _af(requested=False, enabled=False)}
    assert check_adaptive_feature_sweep(metrics) is None


def test_fixb_requested_but_not_enabled_still_blocks_gaming():
    """Regression: the gaming-detection branch must still fire when the agent
    claims adaptive features were requested but the trainer didn't enable them.
    """
    metrics = {"adaptive_features": _af(requested=True, enabled=False)}
    # The 'requested AND not enabled' branch raises adaptive_feature_requested_
    # but_inactive (this branch was already in place before Fix B).
    assert (
        check_adaptive_feature_sweep(metrics)
        == "adaptive_feature_requested_but_inactive"
    )


def test_fixb_enabled_but_no_selected_features_still_blocks():
    """Regression: enabled but selected_count<=0 still raises the
    no-selected-features blocker."""
    metrics = {"adaptive_features": _af(requested=True, enabled=True, selected_count=0)}
    assert (
        check_adaptive_feature_sweep(metrics)
        == "adaptive_feature_requested_but_no_selected_features"
    )


def test_fixb_accepted_noop_still_passes():
    """Regression: an accepted noop reason still bypasses all checks."""
    metrics = {
        "adaptive_features": _af(requested=False, enabled=False),
        "adaptive_feature_noop_reason": "adaptive_features_unavailable",
    }
    assert check_adaptive_feature_sweep(metrics) is None


def test_fixb_genuine_enabled_with_features_passes():
    """Regression: a genuine adaptive sweep (enabled + selected features) passes."""
    metrics = {
        "adaptive_features": _af(
            requested=True, enabled=True, selected_count=3,
            selected_feature_names=["a", "b", "c"],
        ),
    }
    assert check_adaptive_feature_sweep(metrics) is None
