"""Usage ledger: idempotent accounting with explicit cost knowledge.

Provider-specific calculations carry a versioned pricing basis; reported
usage, estimated money, billed money, and unavailable cost stay distinct;
unknown cost is never zero; retries and replays never double-charge; budget
reservations are atomic and never oversubscribe a strict known budget.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from src.core.llm_provider import (
    COST_ESTIMATED,
    COST_UNAVAILABLE,
    AnthropicProvider,
    MockProvider,
    OpenAIProvider,
    Usage,
)
from src.core.state_store import BudgetExceeded, SQLiteStateStore
from src.core.usage_ledger import (
    ROLE_AGENT,
    ROLE_EVALUATOR,
    ROLE_INSIGHT,
    event_from_quote,
    mark_billed,
    record_usage_event,
    summarize_usage,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


async def _open_store(tmp_path: Path) -> SQLiteStateStore:
    store = SQLiteStateStore(str(tmp_path / "state.db"))
    await store.initialize()
    return store


def _anthropic() -> AnthropicProvider:
    return AnthropicProvider(
        base_url="https://example.invalid", api_key="k", timeout_s=5.0,
    )


def _openai() -> OpenAIProvider:
    return OpenAIProvider(
        base_url="https://example.invalid", api_key="k", timeout_s=5.0,
    )


def test_provider_specific_calculations_with_versioned_basis():
    from src.core.llm_provider import (
        _CLAUDE_INPUT_USD_PER_TOKEN,
        _CLAUDE_OUTPUT_USD_PER_TOKEN,
    )

    usage = Usage(
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=2_000_000,
        cache_write_tokens=100_000,
        reasoning_tokens=50_000,
    )
    quote = _anthropic().price_quote("claude-test", usage)
    assert quote.status == COST_ESTIMATED
    expected = (
        1_000_000 * _CLAUDE_INPUT_USD_PER_TOKEN
        + 100_000 * _CLAUDE_OUTPUT_USD_PER_TOKEN
        + 100_000 * 1.25 * _CLAUDE_INPUT_USD_PER_TOKEN
        + 2_000_000 * 0.1 * _CLAUDE_INPUT_USD_PER_TOKEN
    )
    assert abs(quote.money_usd - expected) < 1e-9
    assert quote.basis["version"] == "anthropic-flat-sonnet.v1"
    assert quote.basis["cache_write_multiplier"] == 1.25

    openai_quote = _openai().price_quote(
        "gpt-4o", Usage(input_tokens=1_000, output_tokens=500),
    )
    expected = 1_000 * 5.0 / 1_000_000 + 500 * 15.0 / 1_000_000
    assert openai_quote.status == COST_ESTIMATED
    assert abs(openai_quote.money_usd - expected) < 1e-9
    assert openai_quote.basis["version"] == "openai-table.v1"


def test_unknown_pricing_is_unavailable_never_zero():
    quote = _openai().price_quote(
        "unknown-model", Usage(input_tokens=1_000, output_tokens=500),
    )
    assert quote.status == COST_UNAVAILABLE
    assert quote.money_usd is None

    event = event_from_quote(
        event_key="e1",
        research_id="res_1",
        role=ROLE_AGENT,
        provider="openai",
        model="unknown-model",
        usage=Usage(input_tokens=1_000, output_tokens=500),
        quote=quote,
    )
    assert event.cost_usd is None
    summary = summarize_usage([event.as_row()])
    assert summary["unavailable_events"] == 1
    assert summary["estimated_usd"] == 0.0
    assert summary["estimated_events"] == 0
    assert summary["usage"]["input_tokens"] == 1_000


def test_mock_zero_cost_is_a_real_zero():
    quote = MockProvider().price_quote("m", Usage(10, 10))
    assert quote.status == COST_ESTIMATED
    assert quote.money_usd == 0.0
    event = event_from_quote(
        event_key="e1",
        research_id="res_1",
        role=ROLE_AGENT,
        provider="mock",
        model="m",
        usage=Usage(10, 10),
        quote=quote,
    )
    summary = summarize_usage([event.as_row()])
    assert summary["estimated_events"] == 1
    assert summary["unavailable_events"] == 0
    assert summary["estimated_usd"] == 0.0


def test_evaluator_and_insight_spend_is_counted():
    events = []
    for key, role, money in (
        ("a", ROLE_AGENT, 1.5),
        ("i", ROLE_INSIGHT, 0.25),
        ("e", ROLE_EVALUATOR, 0.75),
    ):
        events.append(
            {
                "event_key": key,
                "role": role,
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "cost_status": COST_ESTIMATED,
                "cost_usd": money,
            }
        )
    summary = summarize_usage(events)
    assert summary["estimated_usd"] == 2.5
    assert summary["events_by_role"] == {
        ROLE_AGENT: 1,
        ROLE_INSIGHT: 1,
        ROLE_EVALUATOR: 1,
    }


def test_billed_money_is_distinct_from_estimates():
    quote = _anthropic().price_quote("m", Usage(100, 100))
    event = event_from_quote(
        event_key="e1",
        research_id="res_1",
        role=ROLE_AGENT,
        provider="anthropic",
        model="m",
        usage=Usage(100, 100),
        quote=quote,
    )
    billed = mark_billed(event, 0.42)
    summary = summarize_usage([event.as_row(), billed.as_row()])
    assert summary["billed_usd"] == 0.42
    assert summary["billed_events"] == 1


@pytest.mark.asyncio
async def test_retries_and_replays_do_not_double_charge(tmp_path):
    store = await _open_store(tmp_path)
    try:
        quote = _anthropic().price_quote("m", Usage(100, 100))
        event = event_from_quote(
            event_key="res_1:agent:1",
            research_id="res_1",
            role=ROLE_AGENT,
            provider="anthropic",
            model="m",
            usage=Usage(100, 100),
            quote=quote,
        )
        assert await record_usage_event(store, event) is True
        assert await record_usage_event(store, event) is False
        rows = await store.get_usage_events("res_1")
        assert len(rows) == 1
        summary = summarize_usage(rows)
        assert summary["estimated_events"] == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_strict_budget_reservations_never_oversubscribe(tmp_path):
    store = await _open_store(tmp_path)
    try:
        first = await store.reserve_budget(
            reservation_id="budget:res_a",
            research_id="res_a",
            amount_usd=60.0,
            strict_cap_usd=100.0,
            enforcement="strict",
            lease_seconds=60.0,
        )
        assert first["state"] == "reserved"
        assert first["enforcement"] == "strict"
        # an idempotent retry returns the same reservation, no second hold
        retry = await store.reserve_budget(
            reservation_id="budget:res_a",
            research_id="res_a",
            amount_usd=60.0,
            strict_cap_usd=100.0,
            enforcement="strict",
            lease_seconds=60.0,
        )
        assert retry["reservation_id"] == "budget:res_a"

        with pytest.raises(BudgetExceeded):
            await store.reserve_budget(
                reservation_id="budget:res_b",
                research_id="res_b",
                amount_usd=50.0,
                strict_cap_usd=100.0,
                enforcement="strict",
                lease_seconds=60.0,
            )
        # an aborted reservation frees its hold immediately
        assert await store.release_budget_reservation("budget:res_a") is True
        again = await store.reserve_budget(
            reservation_id="budget:res_b",
            research_id="res_b",
            amount_usd=50.0,
            strict_cap_usd=100.0,
            enforcement="strict",
            lease_seconds=60.0,
        )
        assert again["state"] == "reserved"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_advisory_limit_is_labeled_with_its_limits(tmp_path):
    store = await _open_store(tmp_path)
    try:
        row = await store.reserve_budget(
            reservation_id="budget:res_a",
            research_id="res_a",
            amount_usd=1_000.0,
            strict_cap_usd=None,
            enforcement="advisory",
            lease_seconds=60.0,
        )
        assert row["enforcement"] == "advisory"
        # no strict cap: nothing is refused, and the row never claims to be
        # a hard ceiling
        reconciled = await store.reconcile_budget_reservation(
            "budget:res_a", actual_usd=0.0,
        )
        assert reconciled["state"] == "reconciled"
        assert reconciled["actual_usd"] == 0.0

        # the advisory monetary limit is labeled with its limits: the caps
        # that actually bound the work are named, not a money ceiling
        from src.core.research_manifest import _spend_enforcement

        label = _spend_enforcement(max_iterations=7, timeout_s=3600)
        assert label["mode"] == "advisory"
        assert label["authorized_cap_usd"] is None
        assert label["enforced_by"] == "time/resource caps only"
        assert label["bounds"] == {"max_iterations": 7, "timeout_s": 3600}
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_manager_reserves_and_reconciles_budget(tmp_path, monkeypatch):
    import src.core.session_manager as session_manager_mod
    from src.core.orchestrator import ResearchConfig
    from src.core.session_manager import SessionManager

    store = await _open_store(tmp_path)
    manager = SessionManager(store)
    try:
        monkeypatch.setattr(
            session_manager_mod.settings, "authorized_spend_cap_usd", 50.0,
        )
        config = ResearchConfig(
            id="res_budget",
            instrument="EURUSD",
            timeframe="1h",
            model_type="",
            skill_id="prompt-engineering",
            skill_params={},
            subject_id="EURUSD",
            variant="1h",
            max_budget_usd=10.0,
        )
        await manager._reserve_budget(config)
        rows = await store.list_budget_reservations("res_budget")
        assert rows[0]["state"] == "reserved"
        assert rows[0]["enforcement"] == "strict"

        await manager._reconcile_budget("res_budget")
        rows = await store.list_budget_reservations("res_budget")
        assert rows[0]["state"] == "reconciled"
        assert rows[0]["actual_usd"] == 0.0
    finally:
        await store.close()


_BUDGET_WORKER = textwrap.dedent(
    """
    import asyncio
    import sys
    from pathlib import Path

    sys.path.insert(0, sys.argv[4])

    from src.core.state_store import BudgetExceeded, SQLiteStateStore

    async def main():
        db_path, key, cap, barrier = (
            sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[5],
        )
        while not Path(barrier).exists():
            await asyncio.sleep(0.002)
        store = SQLiteStateStore(db_path)
        await store.initialize()
        try:
            await store.reserve_budget(
                reservation_id=f"budget:{key}",
                research_id=key,
                amount_usd=40.0,
                strict_cap_usd=cap,
                enforcement="strict",
                lease_seconds=120.0,
            )
            print("RESERVED")
        except BudgetExceeded:
            print("REFUSED")
        finally:
            await store.close()

    asyncio.run(main())
    """
)


def test_parallel_budget_races_cannot_oversubscribe(tmp_path):
    """Real competing OS processes against one strict budget.

    Exactly the cap's worth of reservations fit; every other racer is
    refused before any work starts.
    """
    db_path = tmp_path / "shared.db"
    barrier = tmp_path / "go"
    script = tmp_path / "worker.py"
    script.write_text(_BUDGET_WORKER)
    cap = 100.0
    workers = 5
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(script),
                str(db_path),
                f"res_{i}",
                str(cap),
                str(REPO_ROOT),
                str(barrier),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(workers)
    ]
    barrier.write_text("go")
    outputs = []
    for proc in procs:
        out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err
        outputs.append(out.strip())
    assert outputs.count("RESERVED") == 2, outputs
    assert outputs.count("REFUSED") == workers - 2, outputs
