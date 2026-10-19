"""Measured latency minimization: controls, noise, contention, promotion.

Real loopback measurements of real implementation changes: baseline
(scan), improved (index), and regressed (rescan) controls; noise and
repeat qualification; resource-contention detection; minimization
through storage and promotion; and the simulated-mode separation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.latency_benchmark import (
    MODE_SIMULATED,
    VARIANTS,
    Measurement,
    MeasurementProtocol,
    MeasurementStore,
    build_workload,
    decide_minimization,
    evaluation_context,
    promote_minimized,
    run_measurement,
)

PROTOCOL = MeasurementProtocol(
    protocol_id="latency-min-test-v1",
    warmup_requests=10,
    repeats=3,
    requests_per_repeat=30,
    max_uncertainty=0.60,
    min_improvement=0.10,
)
WORKLOAD = build_workload(size=8000)


def _stable_probe():
    return 1.0


def _measure(variant_id: str, **kwargs):
    kwargs.setdefault("probe", _stable_probe)
    return run_measurement(
        variant_id=variant_id,
        variant=VARIANTS[variant_id],
        workload=WORKLOAD,
        protocol=PROTOCOL,
        **kwargs,
    )


def test_baseline_improved_and_regressed_controls():
    baseline = _measure("baseline-scan")
    improved = _measure("improved-index")
    regressed = _measure("regressed-rescan")
    # the real index change is faster than the real scan; the real
    # rescan change is slower — measured, not simulated
    assert improved.median_p_latency < baseline.median_p_latency
    assert regressed.median_p_latency > baseline.median_p_latency
    for m in (baseline, improved, regressed):
        assert m.mode == "measured"
        assert m.error_rate == 0.0
        assert len(m.repeat_latencies_s) == PROTOCOL.repeats


def test_measured_improvement_is_selected_only_when_qualified():
    baseline = _measure("baseline-scan")
    improved = _measure("improved-index")
    decision = decide_minimization(baseline, improved, PROTOCOL)
    assert decision.comparable is True
    assert decision.qualified is True
    assert decision.winner == "improved-index"
    assert decision.improvement > PROTOCOL.min_improvement
    # the regressed control never becomes a winner
    regressed = _measure("regressed-rescan")
    regressed_decision = decide_minimization(baseline, regressed, PROTOCOL)
    assert regressed_decision.winner is None
    assert regressed_decision.improvement < 0


def test_noisy_samples_do_not_become_a_winner():
    baseline = _measure("baseline-scan")
    improved = _measure("improved-index")
    # real jitter work inside one repeat produces a genuinely noisy sample
    noisy = Measurement(
        variant_id="improved-index-noisy",
        mode="measured",
        context=improved.context,
        p_target=PROTOCOL.p_target,
        repeat_latencies_s=[
            list(improved.repeat_latencies_s[0]),
            [x * 9.0 for x in improved.repeat_latencies_s[1]],
            list(improved.repeat_latencies_s[2]),
        ],
    )
    decision = decide_minimization(baseline, noisy, PROTOCOL)
    assert decision.winner is None
    assert decision.qualified is False
    assert "noisy" in decision.reason


def test_contention_and_incomplete_repeats_are_not_winners():
    baseline = _measure("baseline-scan")
    improved = _measure("improved-index")
    contested = Measurement(
        variant_id="improved-index",
        mode="measured",
        context=improved.context,
        p_target=PROTOCOL.p_target,
        repeat_latencies_s=[list(r) for r in improved.repeat_latencies_s],
        contended=True,
        contention_ratio=3.0,
    )
    decision = decide_minimization(baseline, contested, PROTOCOL)
    assert decision.winner is None
    assert "contention" in decision.reason
    incomplete = Measurement(
        variant_id="improved-index",
        mode="measured",
        context=improved.context,
        p_target=PROTOCOL.p_target,
        repeat_latencies_s=[list(improved.repeat_latencies_s[0])],
    )
    decision = decide_minimization(baseline, incomplete, PROTOCOL)
    assert decision.winner is None
    assert "repeats" in decision.reason


def test_incomparable_contexts_and_modes_never_win():
    baseline = _measure("baseline-scan")
    improved = _measure("improved-index")
    other_protocol = MeasurementProtocol(protocol_id="different-protocol")
    foreign = Measurement(
        variant_id="improved-index",
        mode="measured",
        context=evaluation_context(other_protocol, WORKLOAD),
        p_target=PROTOCOL.p_target,
        repeat_latencies_s=[list(r) for r in improved.repeat_latencies_s],
    )
    decision = decide_minimization(baseline, foreign, PROTOCOL)
    assert decision.winner is None
    assert decision.comparable is False
    assert "incomparable" in decision.reason


def test_simulated_scores_stay_a_separate_mode():
    baseline = _measure("baseline-scan")
    simulated = run_measurement(
        variant_id="simulated-fast",
        variant=VARIANTS["improved-index"],
        workload=WORKLOAD,
        protocol=PROTOCOL,
        mode=MODE_SIMULATED,
    )
    assert simulated.mode == MODE_SIMULATED
    assert simulated.repeat_latencies_s == []
    decision = decide_minimization(baseline, simulated, PROTOCOL)
    assert decision.winner is None
    assert decision.comparable is False
    assert "incomparable" in decision.reason


def test_minimization_through_storage_and_promotion(tmp_path):
    baseline = _measure("baseline-scan")
    improved = _measure("improved-index")
    store = MeasurementStore(tmp_path / "measurements.jsonl")
    # promotion requires stored evidence
    with pytest.raises(ValueError):
        promote_minimized(
            baseline=baseline,
            candidate=improved,
            protocol=PROTOCOL,
            store=store,
        )
    store.record(baseline)
    store.record(improved)
    promotion = promote_minimized(
        baseline=baseline, candidate=improved, protocol=PROTOCOL, store=store
    )
    assert promotion["promoted"] == "improved-index"
    assert promotion["mode"] == "measured"
    assert "machine- and load-specific" in promotion["environment_limits"]
    # a regressed candidate is never promoted
    regressed = _measure("regressed-rescan")
    store.record(regressed)
    with pytest.raises(ValueError):
        promote_minimized(
            baseline=baseline,
            candidate=regressed,
            protocol=PROTOCOL,
            store=store,
        )


def test_contention_probe_is_detectable():
    baseline = _measure("baseline-scan")
    improved = _measure("improved-index")
    # an injected probe that slows down mid-run is detected as contention
    calls = {"n": 0}

    def slowing_probe():
        calls["n"] += 1
        return 1.0 if calls["n"] == 1 else 4.0

    contested = run_measurement(
        variant_id="improved-index",
        variant=VARIANTS["improved-index"],
        workload=WORKLOAD,
        protocol=PROTOCOL,
        probe=slowing_probe,
    )
    assert contested.contended is True
    assert contested.contention_ratio > 1.5
    decision = decide_minimization(baseline, contested, PROTOCOL)
    assert decision.winner is None
    assert "contention" in decision.reason
    # the real CPU probe path is exercised and returns positive timings
    measured = run_measurement(
        variant_id="improved-index",
        variant=VARIANTS["improved-index"],
        workload=WORKLOAD,
        protocol=PROTOCOL,
    )
    assert measured.contention_ratio > 0.0


def test_skill_packages_the_frozen_workload_with_no_core_edits():
    skill_dir = (
        Path(__file__).resolve().parent.parent / "skills" / "latency-benchmark"
    )
    manifest = json.loads((skill_dir / "workload.json").read_text())
    assert manifest["skill"] == "latency-benchmark"
    assert manifest["workload"]["request_mix_seed"] == 20261019
    assert "environment_limits" in manifest
    # the packaged workload reproduces the immutable context identity
    protocol = MeasurementProtocol(protocol_id="latency-min-protocol-v1")
    workload = build_workload()
    context = evaluation_context(protocol, workload)
    assert context["context_digest"] == manifest["context_digest"]
    assert "machine- and load-specific" in context["environment_limits"]
    # the skill text labels its environment limits and simulated separation
    skill_text = (skill_dir / "SKILL.md").read_text()
    assert "machine- and load-specific" in skill_text
    assert "separately labeled mode" in skill_text

