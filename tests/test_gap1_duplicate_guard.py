"""Gap 1 regression — server-side variant-marker injection must skip
rejected-duplicate iterations (and iters with no training_time_s).

Live evidence (``res_99469dfc1088`` iter 2, 2026-05-20 21:56 UTC):

- The agent prepared a config matching `direction_pct_threshold=0.05`,
  identical to a config trained in the prior session ``res_baf6605ce94f``.
- The orchestrator's canonical-config dedup rejected the attempt BEFORE
  prepare.py ran. iter 2 was persisted with ``status:rejected_duplicate``,
  ``decision:discard``, ``training_time_s:None``, ``duplicate_reason:"…"``.
- Gap 1's ``_record_iteration`` injection block fired anyway because the
  current config differed from baseline in a salient knob. Result:
  ``metrics_json.tabular_sweep_variant = "direction_pct_threshold=0.05"``.
- The phase plan saw the injected marker and completed ``tabular_sweeps``
  after zero genuine in-phase training — exactly the Issue 10A
  false-advancement bug, via a new path.

The fix: skip injection when ``marker.get("duplicate_reason")`` is set
or ``marker.get("training_time_s") is None`` (no training executed).
"""
from __future__ import annotations

import json
import sys
import types
from types import ModuleType
from typing import Any, Dict, cast

try:  # pragma: no cover — defensive for environments without anthropic SDK
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = cast(ModuleType, _stub)
import pytest

from src.core.orchestrator import AgentOrchestrator


def _duplicate_marker() -> Dict[str, Any]:
    """Iter 2 shape from ``res_99469dfc1088`` — rejected as a duplicate
    before prepare.py ran. Carries a config_snapshot (the agent's draft)
    but no training_time_s and a duplicate_reason string."""
    return {
        # Config differs from baseline in direction_pct_threshold — under
        # Gap 1, this WOULD trigger tabular_sweep_variant injection if the
        # guard didn't skip duplicates.
        "config_snapshot": (
            "agent_strategy: BALA\ndirection_pct_threshold: 0.05\n"
        ),
        "search_phase": "tabular_sweeps",
        "decision": "discard",
        "status": "rejected_duplicate",
        "training_time_s": None,
        "duplicate_reason": (
            "Duplicate training attempt rejected: same canonical config "
            "already exists in session res_other iteration 2."
        ),
        "primary_metric": None,
        "metric_name": "",
        "all_gates_passed": False,
        "description": "duplicate rejection",
    }


def _genuine_marker() -> Dict[str, Any]:
    """Same config but with training_time_s present and no duplicate_reason
    — a real training attempt that should receive the injected marker."""
    return {
        "config_snapshot": (
            "agent_strategy: BALA\ndirection_pct_threshold: 0.05\n"
        ),
        "search_phase": "tabular_sweeps",
        "decision": "keep",
        "training_time_s": 187.4,  # real training ran
        "primary_metric": 0.6386,
        "metric_name": "composite_direction_score",
        "all_gates_passed": True,
        "description": "genuine training",
    }


@pytest.mark.asyncio
async def test_rejected_duplicate_marker_does_not_get_variant_injected(
    replay_iterations,
) -> None:
    """The live regression from ``res_99469dfc1088`` iter 2.

    A rejected-duplicate marker carries config_snapshot but did NOT run
    training. The Gap 1 injection block must skip such iterations so the
    phase plan does not falsely advance ``tabular_sweeps``.
    """
    ctx = await replay_iterations()
    orch = AgentOrchestrator(ctx.store)

    marker = _duplicate_marker()
    await orch._record_iteration(
        ctx.session_id,
        103,  # fixture seeds up to iter 102; 103 is fresh
        marker,
        cumulative_cost=0.0,
    )

    row = await ctx.store.get_iteration(ctx.session_id, 103)
    assert row is not None, "_record_iteration must persist the rejected duplicate row"
    metrics = json.loads(row.get("metrics_json") or "{}")

    # The crux of the regression: no injected marker on a rejected duplicate.
    assert "tabular_sweep_variant" not in metrics, (
        "Gap 1 must NOT inject tabular_sweep_variant on rejected-duplicate "
        "iterations (training did not run; no genuine exploration occurred). "
        f"Got injected marker: {metrics.get('tabular_sweep_variant')!r}"
    )
    # Defensive: also verify the duplicate_reason is preserved.
    assert metrics.get("duplicate_reason"), (
        "duplicate_reason must round-trip through _record_iteration"
    )


@pytest.mark.asyncio
async def test_no_training_time_marker_does_not_get_variant_injected(
    replay_iterations,
) -> None:
    """A marker with ``training_time_s: None`` (no training ran) and no
    duplicate_reason set must STILL skip injection. The training-time check
    is a defense-in-depth guard against any path that records a marker
    without executing prepare.py (synthetic iters, pruned attempts, etc.).
    """
    ctx = await replay_iterations()
    orch = AgentOrchestrator(ctx.store)

    marker = _genuine_marker()
    marker["training_time_s"] = None  # synthetic — no training ran
    marker["decision"] = "discard"
    marker.pop("primary_metric", None)

    await orch._record_iteration(
        ctx.session_id,
        104,
        marker,
        cumulative_cost=0.0,
    )

    row = await ctx.store.get_iteration(ctx.session_id, 104)
    assert row is not None
    metrics = json.loads(row.get("metrics_json") or "{}")

    assert "tabular_sweep_variant" not in metrics, (
        "Gap 1 must NOT inject when training_time_s is None — no training "
        "executed, so the iter cannot be claiming deliberate exploration."
    )


@pytest.mark.asyncio
async def test_genuine_training_marker_receives_variant(
    replay_iterations,
) -> None:
    """Positive control: a normal training iter (training_time_s set, no
    duplicate_reason) whose config differs from baseline IS injected, so
    the regression patch hasn't gone too far.
    """
    ctx = await replay_iterations()
    orch = AgentOrchestrator(ctx.store)

    marker = _genuine_marker()
    await orch._record_iteration(
        ctx.session_id,
        105,
        marker,
        cumulative_cost=0.0,
    )

    row = await ctx.store.get_iteration(ctx.session_id, 105)
    assert row is not None
    metrics = json.loads(row.get("metrics_json") or "{}")

    # Baseline iter in the fixture (iter 85) has
    # ``direction_pct_threshold: 0.022``; the marker uses 0.05. The Gap 1
    # injector must derive ``tabular_sweep_variant`` for this iter.
    variant = metrics.get("tabular_sweep_variant")
    assert variant is not None and "direction_pct_threshold" in variant, (
        "Gap 1 must inject tabular_sweep_variant for a genuine training iter "
        "whose config differs from baseline. "
        f"Got: {variant!r}"
    )