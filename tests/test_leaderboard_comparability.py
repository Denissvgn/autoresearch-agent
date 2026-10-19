"""Comparable-context leaderboard ranking over real storage history.

Mixed-context and >500-session fixtures expose the recent-500 bug: an
older champion must remain rankable while the API describes the ranking
as global. Incomparable and legacy contexts never merge into one
champion table; minimize/maximize parity holds; pagination windows are
explicit; and the ranking path's query plan is index-backed.
"""
from __future__ import annotations

import asyncio

from src.core.comparison_context import (
    build_comparison_context,
    describe_comparison_context,
)
from src.core.state_store import SQLiteStateStore

CTX_A = build_comparison_context(
    objective="score", units="ratio",
    pins={"scorer": "scorer-a", "dataset": "data-1"},
)
CTX_B = build_comparison_context(
    objective="score", units="ratio",
    pins={"scorer": "scorer-b", "dataset": "data-2"},
)


def _store(tmp_path, name="state.db"):
    async def _build():
        s = SQLiteStateStore(str(tmp_path / name))
        await s.initialize()
        return s

    return asyncio.run(_build())


def _seed(store, rid, metric, *, context=None, model_type="prompt-engineering"):
    async def _run():
        await store.create_session(
            session_id=rid, instrument="I", timeframe="1h",
            model_type=model_type, tag="t", quick_mode=False,
            max_iterations=3, max_budget_usd=1.0, focus_hint=None,
            workspace_path=f"/tmp/ws-{rid}", comparison_context=context,
        )
        await store.add_iteration(
            research_id=rid, iteration=1, primary_metric=metric,
            metric_name="score", all_gates_passed=True, decision="keep",
            description="d", config_snapshot="{}", metrics_json="{}",
            training_time_s=1.0,
        )

    asyncio.run(_run())


def test_mixed_contexts_never_share_a_winner(tmp_path):
    store = _store(tmp_path)
    # context B's raw score is higher, but it is NOT comparable with A
    _seed(store, "res_a1", 0.70, context=CTX_A)
    _seed(store, "res_a2", 0.60, context=CTX_A)
    _seed(store, "res_b1", 0.99, context=CTX_B)
    _seed(store, "res_legacy", 0.95)  # no recorded context

    groups = asyncio.run(
        store.rank_leaderboard_groups(
            model_types=["prompt-engineering"], direction="maximize"
        )
    )
    assert len(groups) == 3
    by_context = {g["comparison_context"]: g for g in groups}
    assert [i["id"] for i in by_context[CTX_A]["items"]] == ["res_a1", "res_a2"]
    assert [i["id"] for i in by_context[CTX_B]["items"]] == ["res_b1"]
    # the unknown/legacy group is separate — 0.95 never merges anywhere
    assert by_context[None]["comparison_context"] is None
    assert [i["id"] for i in by_context[None]["items"]] == ["res_legacy"]
    assert by_context[CTX_A]["total"] == 2
    for group in groups:
        label = describe_comparison_context(group["comparison_context"])
        if group["comparison_context"] is None:
            assert label["known"] is False
        else:
            assert label["known"] is True
            assert "scorer=" in label["label"]


def test_old_champions_survive_beyond_recent_500(tmp_path):
    from src.core.results_store import ResultsStore

    # both store access paths are the same store class; the ranking must
    # hold through either
    for store_cls, name in (
        (SQLiteStateStore, "state-a.db"),
        (ResultsStore, "state-b.db"),
    ):

        async def _build(cls=store_cls, db_name=name):
            s = cls(str(tmp_path / db_name))
            await s.initialize()
            return s

        store = asyncio.run(_build())
        # the OLDEST session is the champion; 520 newer ones bury it
        _seed(store, "res_old_champion", 0.999, context=CTX_A)
        for i in range(520):
            _seed(store, f"res_new_{i:04d}", 0.1 + i * 0.0001, context=CTX_A)
        groups = asyncio.run(
            store.rank_leaderboard_groups(
                model_types=["prompt-engineering"],
                direction="maximize",
                limit=5,
            )
        )
        assert len(groups) == 1
        group = groups[0]
        assert group["total"] == 521
        assert group["items"][0]["id"] == "res_old_champion"
        assert len(group["items"]) == 5


def test_minimize_maximize_parity(tmp_path):
    store = _store(tmp_path)
    for i, metric in enumerate((0.2, 0.5, 0.9)):
        _seed(store, f"res_{i}", metric, context=CTX_A)
    high_first = asyncio.run(
        store.rank_leaderboard_groups(
            model_types=["prompt-engineering"], direction="maximize"
        )
    )[0]["items"]
    low_first = asyncio.run(
        store.rank_leaderboard_groups(
            model_types=["prompt-engineering"], direction="minimize"
        )
    )[0]["items"]
    assert [r["id"] for r in high_first] == ["res_2", "res_1", "res_0"]
    assert [r["id"] for r in low_first] == ["res_0", "res_1", "res_2"]


def test_pagination_boundaries_are_explicit(tmp_path):
    store = _store(tmp_path)
    for i in range(5):
        _seed(store, f"res_{i}", 0.1 * i, context=CTX_A)
    window = asyncio.run(
        store.rank_leaderboard_groups(
            model_types=["prompt-engineering"], direction="maximize",
            limit=2, offset=2,
        )
    )[0]
    assert window["total"] == 5
    assert window["limit"] == 2 and window["offset"] == 2
    assert [r["id"] for r in window["items"]] == ["res_2", "res_1"]
    past_end = asyncio.run(
        store.rank_leaderboard_groups(
            model_types=["prompt-engineering"], direction="maximize",
            limit=2, offset=50,
        )
    )[0]
    assert past_end["items"] == []
    assert past_end["total"] == 5


def test_ranking_query_plan_is_index_backed(tmp_path):
    store = _store(tmp_path)
    _seed(store, "res_1", 0.5, context=CTX_A)
    plan = asyncio.run(
        store.rank_leaderboard_explain(model_types=["prompt-engineering"])
    )
    assert "idx_sessions_leaderboard" in plan


def test_context_identity_and_labels():
    pinned = build_comparison_context(
        objective="sharpe", units="ratio", subject="DOGE", variant="15m",
        pins={"dataset": "d1", "scorer": "s1", "fidelity": "tick"},
    )
    assert '"fidelity":"tick"' in pinned
    label = describe_comparison_context(pinned)
    assert label["known"] is True
    for token in ("objective=sharpe", "units=ratio", "dataset=d1",
                  "scorer=s1", "fidelity=tick", "subject=DOGE", "variant=15m"):
        assert token in label["label"]
    # unknown pins are explicit, and the unknown group never merges
    partial = build_comparison_context(objective="sharpe", units="ratio")
    assert '"scorer":"unknown"' in partial
    assert describe_comparison_context(None)["known"] is False