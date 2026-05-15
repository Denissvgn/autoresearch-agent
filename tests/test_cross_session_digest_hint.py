"""Fix B / Fix C — cross-session iteration summary + digest sections.

Fix B-1 validates the new ResultsStore method.
Fix B-2 + C validate the new digest sections in
``build_iteration_context_digest``:

  - "Tried in prior sessions ({N} canonical configs, best={metric})"
  - "Server-side feature availability:"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.iteration_context import build_iteration_context_digest
from src.core.results_store import ResultsStore


async def _make_session(
    store: ResultsStore,
    sid: str,
    *,
    instrument: str = "DOGE_USDT",
    timeframe: str = "15m",
    model_type: str = "direction",
) -> None:
    await store.create_session(
        session_id=sid,
        instrument=instrument,
        timeframe=timeframe,
        model_type=model_type,
        tag=sid,
        workspace_path="/ws",
        max_iterations=20,
        max_budget_usd=10.0,
        quick_mode=False,
        focus_hint=None,
    )


async def _add_iter(
    store: ResultsStore,
    sid: str,
    iteration: int,
    *,
    primary_metric: float,
    canonical_config_hash: str,
    decision: str = "keep",
    metrics_extra: dict | None = None,
    config_snapshot: str = "instrument: DOGE_USDT\n",
    duplicate_reason: str | None = None,
) -> None:
    metrics: dict = {
        "primary_metric": primary_metric,
        "metric_name": "composite_direction_score",
        "training_gates_passed": True,
        "all_gates_passed": True,
    }
    if metrics_extra:
        metrics.update(metrics_extra)
    await store.add_iteration(
        research_id=sid,
        iteration=iteration,
        primary_metric=primary_metric,
        metric_name="composite_direction_score",
        all_gates_passed=True,
        decision=decision,
        description=f"{sid} iter {iteration}",
        config_snapshot=config_snapshot,
        metrics_json=json.dumps(metrics),
        training_time_s=60.0,
        canonical_config_hash=canonical_config_hash,
        duplicate_reason=duplicate_reason,
        search_phase="tabular_sweeps",
    )


# ────────────────────────────────────────────────────────────────────────
# Fix B-1 — ResultsStore.get_cross_session_iteration_summary
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_session_summary_groups_by_hash_and_excludes_current(
    tmp_path: Path,
) -> None:
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _make_session(store, "res_prior_a")
    await _make_session(store, "res_prior_b")
    await _make_session(store, "res_current")

    await _add_iter(store, "res_prior_a", 1, primary_metric=0.62, canonical_config_hash="hash-alpha")
    await _add_iter(store, "res_prior_a", 2, primary_metric=0.64, canonical_config_hash="hash-alpha")
    await _add_iter(store, "res_prior_b", 1, primary_metric=0.60, canonical_config_hash="hash-beta")
    await _add_iter(store, "res_current", 1, primary_metric=0.55, canonical_config_hash="hash-gamma")

    rows = await store.get_cross_session_iteration_summary(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        exclude_research_id="res_current",
    )

    hashes = {r["canonical_config_hash"] for r in rows}
    assert hashes == {"hash-alpha", "hash-beta"}, (
        "current session's hash must be excluded"
    )

    by_hash = {r["canonical_config_hash"]: r for r in rows}
    assert by_hash["hash-alpha"]["best_metric"] == pytest.approx(0.64)
    assert by_hash["hash-alpha"]["attempts"] == 2
    assert by_hash["hash-beta"]["best_metric"] == pytest.approx(0.60)

    # Ordering: highest best_metric first
    assert rows[0]["canonical_config_hash"] == "hash-alpha"


@pytest.mark.asyncio
async def test_cross_session_summary_skips_other_instruments(
    tmp_path: Path,
) -> None:
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _make_session(store, "res_match")
    await _make_session(store, "res_other", instrument="BTC_USDT")

    await _add_iter(store, "res_match", 1, primary_metric=0.6, canonical_config_hash="hash-x")
    await _add_iter(store, "res_other", 1, primary_metric=0.7, canonical_config_hash="hash-y")

    rows = await store.get_cross_session_iteration_summary(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        exclude_research_id=None,
    )
    hashes = {r["canonical_config_hash"] for r in rows}
    assert hashes == {"hash-x"}


@pytest.mark.asyncio
async def test_cross_session_summary_captures_noop_reasons(
    tmp_path: Path,
) -> None:
    """noop_reasons / tsfm_* columns must surface so the digest can emit
    the Fix C feature-availability hint."""
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    await _make_session(store, "res_obs")

    for i in range(1, 4):
        await _add_iter(
            store, "res_obs", i,
            primary_metric=0.5 + 0.01 * i,
            canonical_config_hash=f"hash-{i}",
            metrics_extra={
                "adaptive_feature_noop_reason": "adaptive_features_unavailable",
                "tsfm_fallback_validation": True,
            },
        )

    rows = await store.get_cross_session_iteration_summary(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        exclude_research_id="res_other",
    )
    assert any(
        (r.get("noop_reasons") or "").find("adaptive_features_unavailable") >= 0
        for r in rows
    )
    assert any(
        (r.get("tsfm_fallback_flags") or "").lower().find("1") >= 0
        or (r.get("tsfm_fallback_flags") or "").lower().find("true") >= 0
        for r in rows
    )


# ────────────────────────────────────────────────────────────────────────
# Fix B-2 — "Tried in prior sessions" digest section
# ────────────────────────────────────────────────────────────────────────


def _session_stub() -> dict:
    return {
        "id": "res_curr",
        "model_type": "direction",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "max_iterations": 30,
        "max_budget_usd": 10.0,
        "total_api_cost_usd": 0.5,
    }


def test_digest_emits_tried_in_prior_sessions_block() -> None:
    summary = [
        {
            "canonical_config_hash": "abc1234567890",
            "best_metric": 0.6443,
            "first_research_id": "res_a526a64254f4",
            "attempts": 3,
            "session_count": 2,
        },
        {
            "canonical_config_hash": "def0987654321",
            "best_metric": 0.6435,
            "first_research_id": "res_940e819faa03",
            "attempts": 2,
            "session_count": 1,
        },
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    assert "Tried in prior sessions" in digest
    assert "abc12345" in digest  # short hash
    assert "res_a526a64254f4" in digest
    assert "best=0.6443" in digest


def test_digest_omits_tried_section_when_summary_empty() -> None:
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=[],
    )
    assert "Tried in prior sessions" not in digest


def test_digest_caps_prior_session_entries_to_twelve() -> None:
    """20 distinct-signature direction configs → 20 distinct clusters →
    only 12 region lines + an omission footer."""
    summary = [
        {
            "canonical_config_hash": f"hash{i:02d}",
            "best_metric": 0.65 - i * 0.005,
            "first_research_id": f"res_{i}",
            "attempts": 1,
            "session_count": 1,
            # Distinct purge_multiplier band per row → distinct clusters
            # (bucket width 1.0, so i*2 spreads them apart).
            "sample_config_snapshot": (
                "instrument: DOGE_USDT\n"
                f"direction_pct_threshold: {0.03 + i * 0.01}\n"
                f"purge_multiplier: {1.0 + i * 2}\n"
            ),
        }
        for i in range(20)
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    region_lines = [
        line for line in digest.splitlines()
        if line.startswith("  - ") and "→ best=" in line
    ]
    assert len(region_lines) == 12, region_lines
    assert "more regions omitted" in digest
    assert "20 explored regions" in digest


# ────────────────────────────────────────────────────────────────────────
# Fix C — "Server-side feature availability" digest section
# ────────────────────────────────────────────────────────────────────────


def test_digest_emits_feature_unavailable_when_threshold_met() -> None:
    summary = [
        {
            "canonical_config_hash": f"hash{i:02d}",
            "best_metric": 0.55,
            "first_research_id": f"res_{i}",
            "attempts": 5,
            "session_count": 2,
            "noop_reasons": "adaptive_features_unavailable",
            "tsfm_adapters": "",
            "tsfm_fallback_flags": "",
        }
        for i in range(2)
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    assert "Server-side feature availability" in digest
    assert "adaptive_features: UNAVAILABLE" in digest
    assert "do NOT" in digest or "do not" in digest


def test_digest_omits_availability_below_threshold() -> None:
    summary = [
        {
            "canonical_config_hash": "hash00",
            "best_metric": 0.55,
            "first_research_id": "res_0",
            "attempts": 1,
            "session_count": 1,
            "noop_reasons": "adaptive_features_unavailable",
            "tsfm_adapters": "",
            "tsfm_fallback_flags": "",
        },
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    assert "Server-side feature availability" not in digest


def test_digest_emits_tsfm_fallback_when_no_real_adapter() -> None:
    summary = [
        {
            "canonical_config_hash": f"hash{i:02d}",
            "best_metric": 0.55,
            "first_research_id": f"res_{i}",
            "attempts": 4,
            "session_count": 2,
            "noop_reasons": "",
            "tsfm_adapters": "",
            "tsfm_fallback_flags": "true,true",
        }
        for i in range(2)
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    assert "tsfm: tabular-fallback only" in digest


# ────────────────────────────────────────────────────────────────────────
# B-1 (fixed) — discard rows must surface; duplicate_reason rows must not
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_session_summary_includes_discard_rows(
    tmp_path: Path,
) -> None:
    """Fix B-1: prior-session iterations that ended in decision='discard'
    are still real exploration attempts the agent will collide with. The
    cross-session summary MUST include them, not filter to keep-only.
    """
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _make_session(store, "res_prior")
    await _make_session(store, "res_current")

    await _add_iter(
        store, "res_prior", 1,
        primary_metric=0.62,
        canonical_config_hash="hash-keep",
        decision="keep",
    )
    await _add_iter(
        store, "res_prior", 2,
        primary_metric=0.55,
        canonical_config_hash="hash-discard-1",
        decision="discard",
    )
    await _add_iter(
        store, "res_prior", 3,
        primary_metric=0.58,
        canonical_config_hash="hash-discard-2",
        decision="discard",
    )

    rows = await store.get_cross_session_iteration_summary(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        exclude_research_id="res_current",
    )
    hashes = {r["canonical_config_hash"] for r in rows}
    assert hashes == {"hash-keep", "hash-discard-1", "hash-discard-2"}, (
        f"expected discards in summary, got: {hashes}"
    )


@pytest.mark.asyncio
async def test_cross_session_summary_excludes_duplicate_reason_rows(
    tmp_path: Path,
) -> None:
    """Fix B-1: rows where ``duplicate_reason`` is set are dedup-engine
    audit records, not real exploration. Must be excluded.
    """
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()

    await _make_session(store, "res_prior")
    await _make_session(store, "res_current")

    await _add_iter(
        store, "res_prior", 1,
        primary_metric=0.6,
        canonical_config_hash="hash-real",
        decision="keep",
    )
    # Simulate the duplicate-rejection audit record (decision=discard +
    # duplicate_reason set) that the orchestrator writes on collisions.
    await _add_iter(
        store, "res_prior", 2,
        primary_metric=0.0,
        canonical_config_hash="hash-rejected",
        decision="discard",
        duplicate_reason="canonical config already exists in session res_other",
    )

    rows = await store.get_cross_session_iteration_summary(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        exclude_research_id="res_current",
    )
    hashes = {r["canonical_config_hash"] for r in rows}
    assert hashes == {"hash-real"}, (
        f"duplicate_reason row must not surface, got: {hashes}"
    )


# ────────────────────────────────────────────────────────────────────────
# B-2 — parameter signatures from sample_config_snapshot
# ────────────────────────────────────────────────────────────────────────


def test_digest_renders_parameter_signature_when_snapshot_available() -> None:
    summary = [
        {
            "canonical_config_hash": "abc1234567890",
            "best_metric": 0.6443,
            "first_research_id": "res_a526a64254f4",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": (
                "instrument: DOGE_USDT\n"
                "timeframe: 15m\n"
                "direction_pct_threshold: 0.05\n"
                "purge_multiplier: 4.0\n"
                "horizon: 6\n"
                "roster_preset: balanced\n"
            ),
        },
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    assert "direction_pct_threshold=0.05" in digest
    assert "purge_multiplier=4" in digest
    assert "roster_preset=balanced" in digest
    assert "best=0.6443" in digest
    # Hash still printed as tie-breaker.
    assert "abc12345" in digest


def test_digest_falls_back_to_hash_when_snapshot_missing() -> None:
    summary = [
        {
            "canonical_config_hash": "noyaml1234",
            "best_metric": 0.6,
            "first_research_id": "res_x",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": None,
        },
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    assert "hash=noyaml123" in digest


def test_digest_signature_renders_list_compactly_for_rl() -> None:
    """RL salient knobs include list-valued ``net_arch_pi``."""
    summary = [
        {
            "canonical_config_hash": "rl_arch_1",
            "best_metric": 0.12,
            "first_research_id": "res_rl",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": (
                "net_arch_pi: [256, 128]\n"
                "net_arch_vf: [256, 128]\n"
                "n_envs: 4\n"
                "learning_rate: 0.0003\n"
            ),
        },
    ]
    rl_session = {
        "id": "res_rl_curr",
        "model_type": "rl",
        "instrument": "BTC_USDT",
        "timeframe": "1h",
        "max_iterations": 30,
        "max_budget_usd": 10.0,
        "total_api_cost_usd": 0.0,
    }
    digest = build_iteration_context_digest(
        session=rl_session,
        iterations=[],
        prior_session_summary=summary,
    )
    assert "net_arch_pi=[256,128]" in digest
    assert "n_envs=4" in digest
    # learning_rate=0.0003 → compact non-trailing-zero render
    assert "learning_rate=0.0003" in digest


def test_digest_signature_skips_unknown_model_type() -> None:
    """Unknown model_type → no salient-keys map → fallback to hash-only."""
    summary = [
        {
            "canonical_config_hash": "unknown_model_hash",
            "best_metric": 0.5,
            "first_research_id": "res_y",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": "direction_pct_threshold: 0.05\n",
        },
    ]
    session = {
        "id": "res_curr",
        "model_type": "regime",  # not in _SALIENT_PARAMS_BY_MODEL
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "max_iterations": 30,
        "max_budget_usd": 10.0,
    }
    digest = build_iteration_context_digest(
        session=session,
        iterations=[],
        prior_session_summary=summary,
    )
    assert "hash=unknown_m" in digest  # _short cap truncates the hash
    assert "direction_pct_threshold" not in digest


@pytest.mark.asyncio
async def test_summary_returns_sample_config_snapshot_column(
    tmp_path: Path,
) -> None:
    """End-to-end: the new ``sample_config_snapshot`` column populates
    from the iterations table so the digest can call
    ``_extract_param_signature`` on it.
    """
    store = ResultsStore(str(tmp_path / "store.db"))
    await store.initialize()
    await _make_session(store, "res_prior")
    await _make_session(store, "res_current")
    snapshot_yaml = (
        "instrument: DOGE_USDT\n"
        "direction_pct_threshold: 0.05\n"
        "purge_multiplier: 4.0\n"
    )
    await _add_iter(
        store, "res_prior", 1,
        primary_metric=0.64,
        canonical_config_hash="hash-with-snapshot",
        config_snapshot=snapshot_yaml,
    )
    rows = await store.get_cross_session_iteration_summary(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        exclude_research_id="res_current",
    )
    assert rows
    assert rows[0]["sample_config_snapshot"] == snapshot_yaml


# ────────────────────────────────────────────────────────────────────────
# Cluster-representative sampling
# ────────────────────────────────────────────────────────────────────────


def _direction_summary_row(
    idx: int,
    *,
    pct: float,
    purge: float,
    metric: float,
    rid: str | None = None,
) -> dict:
    return {
        "canonical_config_hash": f"chash{idx:03d}",
        "best_metric": metric,
        "first_research_id": rid or f"res_{idx}",
        "attempts": 1,
        "session_count": 1,
        "sample_config_snapshot": (
            "instrument: DOGE_USDT\n"
            f"direction_pct_threshold: {pct}\n"
            f"purge_multiplier: {purge}\n"
            "horizon: 6\n"
            "roster_preset: balanced\n"
        ),
    }


def test_clustering_groups_near_duplicate_configs() -> None:
    """20 configs whose direction_pct_threshold ∈ {0.050,0.051,0.052}
    (all inside one 0.01 bucket) and same purge collapse to ONE region."""
    summary = [
        _direction_summary_row(
            i, pct=0.050 + (i % 3) * 0.001, purge=4.0, metric=0.60 + i * 0.0001
        )
        for i in range(20)
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    region_lines = [
        ln for ln in digest.splitlines()
        if ln.startswith("  - ") and "→ best=" in ln
    ]
    assert len(region_lines) == 1, region_lines
    assert "1 explored regions" in digest
    assert "20 configs explored here" in region_lines[0]


def test_hybrid_selection_includes_top_and_spread() -> None:
    """40 configs spanning metric 0.50→0.65 across distinct purge bands:
    the top-5 highest-metric regions appear AND a low-band region appears
    (stride spread), total ≤ 12 region lines."""
    summary = [
        _direction_summary_row(
            i,
            pct=0.05,
            purge=1.0 + i * 2,            # distinct purge bucket per row
            metric=0.50 + i * (0.15 / 39),  # 0.50 … 0.65
        )
        for i in range(40)
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    region_lines = [
        ln for ln in digest.splitlines()
        if ln.startswith("  - ") and "→ best=" in ln
    ]
    assert len(region_lines) == 12, region_lines
    # Top region (highest metric ≈ 0.65) present.
    assert "best=0.6500" in digest
    # A low-metric-band region also surfaced via the diversity stride
    # (something well below the top-5 cluster ≈ 0.63+).
    low_metrics = [
        ln for ln in region_lines if "best=0.5" in ln or "best=0.60" in ln
    ]
    assert low_metrics, f"expected a low-band region in spread: {region_lines}"
    assert "more regions omitted" in digest


def test_unsignatured_rows_fall_back_to_hash() -> None:
    summary = [
        {
            "canonical_config_hash": "nosnap12345",
            "best_metric": 0.61,
            "first_research_id": "res_x",
            "attempts": 2,
            "session_count": 1,
            "sample_config_snapshot": None,
        },
    ]
    digest = build_iteration_context_digest(
        session=_session_stub(),
        iterations=[],
        prior_session_summary=summary,
    )
    assert "no config snapshot" in digest
    assert "hash=nosnap1234" in digest


def test_unknown_model_type_preserves_legacy_hash_render() -> None:
    summary = [
        {
            "canonical_config_hash": "regimehash999",
            "best_metric": 0.5,
            "first_research_id": "res_y",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": "direction_pct_threshold: 0.05\n",
        },
    ]
    session = {
        "id": "res_curr",
        "model_type": "regime",  # not in _SALIENT_PARAMS_BY_MODEL
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "max_iterations": 30,
        "max_budget_usd": 10.0,
    }
    digest = build_iteration_context_digest(
        session=session,
        iterations=[],
        prior_session_summary=summary,
    )
    assert "no config snapshot" in digest
    assert "hash=regimehas" in digest  # _short truncates 13-char hash
    assert "direction_pct_threshold" not in digest


def test_digest_is_deterministic() -> None:
    summary = [
        _direction_summary_row(
            i, pct=0.03 + i * 0.01, purge=1.0 + i * 2, metric=0.55 + i * 0.005
        )
        for i in range(25)
    ]
    a = build_iteration_context_digest(
        session=_session_stub(), iterations=[], prior_session_summary=summary,
    )
    b = build_iteration_context_digest(
        session=_session_stub(), iterations=[], prior_session_summary=summary,
    )
    assert a == b


def test_rl_log_bucket_groups_same_order_of_magnitude() -> None:
    rl_session = {
        "id": "res_rl",
        "model_type": "rl",
        "instrument": "BTC_USDT",
        "timeframe": "1h",
        "max_iterations": 30,
        "max_budget_usd": 10.0,
    }
    # 3e-4 and 1e-4 share log10 floor (-4) → same cluster.
    # 3e-3 has floor -3 → different cluster.
    summary = [
        {
            "canonical_config_hash": "rl_a",
            "best_metric": 0.10,
            "first_research_id": "res_a",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": "learning_rate: 0.0003\nn_envs: 4\n",
        },
        {
            "canonical_config_hash": "rl_b",
            "best_metric": 0.12,
            "first_research_id": "res_b",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": "learning_rate: 0.0001\nn_envs: 4\n",
        },
        {
            "canonical_config_hash": "rl_c",
            "best_metric": 0.08,
            "first_research_id": "res_c",
            "attempts": 1,
            "session_count": 1,
            "sample_config_snapshot": "learning_rate: 0.003\nn_envs: 4\n",
        },
    ]
    digest = build_iteration_context_digest(
        session=rl_session, iterations=[], prior_session_summary=summary,
    )
    region_lines = [
        ln for ln in digest.splitlines()
        if ln.startswith("  - ") and "→ best=" in ln
    ]
    # rl_a + rl_b collapse (log -4); rl_c separate (log -3) → 2 regions.
    assert len(region_lines) == 2, region_lines
    assert "2 explored regions" in digest


def test_empty_summary_unchanged() -> None:
    digest = build_iteration_context_digest(
        session=_session_stub(), iterations=[], prior_session_summary=[],
    )
    assert "Tried in prior sessions" not in digest
    assert "explored regions" not in digest
