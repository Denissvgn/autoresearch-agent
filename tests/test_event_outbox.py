"""Transactional event outbox: cross-worker delivery, replay, and resync.

Committed state transitions publish durable, correlated events in the same
transaction; clients catch up through bounded cursor reads; duplicates and
out-of-order deliveries apply at most once; expired cursors resynchronize
from an atomic snapshot-plus-cursor.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.state_store import SQLiteStateStore
from src.ws.events import (
    dedupe_events,
    plan_catchup,
    poll_events,
    redact_event_payload,
    relay_new_events,
    snapshot_with_cursor,
)


async def _open_store(tmp_path: Path) -> SQLiteStateStore:
    store = SQLiteStateStore(str(tmp_path / "state.db"))
    await store.initialize()
    return store


async def _seed_session(store: SQLiteStateStore, session_id: str) -> dict:
    return await store.create_session(
        session_id=session_id,
        instrument="EURUSD",
        timeframe="1h",
        model_type="trend",
        tag="",
        quick_mode=True,
        max_iterations=1,
        max_budget_usd=1.0,
        focus_hint="",
        workspace_path="",
    )


@pytest.mark.asyncio
async def test_events_are_correlated_versioned_and_cursor_ordered(tmp_path):
    store = await _open_store(tmp_path)
    try:
        first = await store.append_event(
            event_id="ev-1",
            stream_key="res_1",
            event_type="session.transition",
            payload={"status": "completed"},
            producer="worker-a",
            ownership_epoch=2,
            attempt=3,
        )
        second = await store.append_event(
            event_id="ev-2",
            stream_key="res_1",
            event_type="session.transition",
            payload={"status": "failed"},
            producer="worker-a",
            ownership_epoch=2,
        )
        assert first["sequence"] == 1
        assert second["sequence"] == 2
        assert first["stream_key"] == "res_1"
        assert first["producer"] == "worker-a"
        assert first["ownership_epoch"] == 2
        assert first["attempt"] == 3
        assert first["created_at"]
        assert await store.event_cursor(stream_key="res_1") == 2
        assert await store.min_event_cursor(stream_key="res_1") == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_append_is_idempotent_and_duplicates_apply_once(tmp_path):
    store = await _open_store(tmp_path)
    try:
        first = await store.append_event(
            event_id="ev-1",
            stream_key="res_1",
            event_type="session.transition",
            payload={"n": 1},
            producer="worker-a",
        )
        retry = await store.append_event(
            event_id="ev-1",
            stream_key="res_1",
            event_type="session.transition",
            payload={"n": 1},
            producer="worker-a",
        )
        assert retry["sequence"] == first["sequence"]
        assert len(await store.list_events(stream_key="res_1")) == 1

        # the consumer-side rule: a replayed delivery applies at most once
        events = await poll_events(store, cursor=0, stream_key="res_1")
        fresh, applied = dedupe_events(events, set())
        assert len(fresh) == 1
        again, applied2 = dedupe_events(events, applied)
        assert again == []
        assert applied2 == applied
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_out_of_order_delivery_is_reordered_by_sequence(tmp_path):
    store = await _open_store(tmp_path)
    try:
        for index in range(3):
            await store.append_event(
                event_id=f"ev-{index}",
                stream_key="res_1",
                event_type="session.transition",
                payload={"n": index},
                producer="worker-a",
            )
        events = await poll_events(store, cursor=0, stream_key="res_1")
        shuffled = [events[2], events[0], events[1]]
        fresh, _applied = dedupe_events(shuffled, set())
        assert [event["event_id"] for event in fresh] == [
            "ev-0", "ev-1", "ev-2",
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_state_and_event_publication_commit_together(tmp_path):
    store = await _open_store(tmp_path)
    try:
        await _seed_session(store, "res_1")
        event = await store.record_state_event(
            "res_1",
            fields={"status": "completed"},
            event_id="res_1:transition:1",
            event_type="research_completed",
            payload={"status": "completed"},
            producer="worker-a",
        )
        # the state landed and its correlated event exists in the same
        # durable record — a restart between commit and notification can
        # lose the broadcast, never the event
        session = await store.get_session("res_1")
        assert session["status"] == "completed"
        assert event["event_id"] == "res_1:transition:1"
        assert event["stream_key"] == "res_1"
        assert event["ownership_epoch"] == 0
        events = await poll_events(store, cursor=0, stream_key="res_1")
        assert [e["event_id"] for e in events] == ["res_1:transition:1"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_producer_payloads_are_versioned(tmp_path):
    from src.core.state_machine import (
        SessionEvent,
        SessionStateMachine,
    )

    class _NoBroadcast:
        async def broadcast(self, event):
            return None

    store = await _open_store(tmp_path)
    try:
        await _seed_session(store, "res_v")
        await store.update_session("res_v", status="running")
        sm = SessionStateMachine(store, _NoBroadcast())
        await sm.transition("res_v", SessionEvent.COMPLETE)
        events = await poll_events(store, cursor=0, stream_key="res_v")
        assert events, "the transition must publish a durable event"
        assert events[0]["payload"]["schema_version"] == "session-event.v1"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_reconnect_catchup_is_bounded_for_slow_consumers(tmp_path):
    store = await _open_store(tmp_path)
    try:
        for index in range(7):
            await store.append_event(
                event_id=f"ev-{index}",
                stream_key="res_1",
                event_type="session.transition",
                payload={"n": index},
                producer="worker-a",
            )
        # a reconnecting consumer with cursor 2 catches up in bounded
        # batches (backpressure), never an unbounded dump
        batch1 = await poll_events(store, cursor=2, stream_key="res_1", limit=2)
        assert [e["sequence"] for e in batch1] == [3, 4]
        batch2 = await poll_events(
            store, cursor=batch1[-1]["sequence"], stream_key="res_1", limit=2,
        )
        assert [e["sequence"] for e in batch2] == [5, 6]
        batch3 = await poll_events(
            store, cursor=batch2[-1]["sequence"], stream_key="res_1", limit=2,
        )
        assert [e["sequence"] for e in batch3] == [7]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_expired_cursor_requires_snapshot_plus_cursor_resync(tmp_path):
    store = await _open_store(tmp_path)
    try:
        await _seed_session(store, "res_1")
        for index in range(3):
            await store.append_event(
                event_id=f"ev-{index}",
                stream_key="res_1",
                event_type="session.transition",
                payload={"n": index},
                producer="worker-a",
            )
        # retention simulation: the earliest events are gone
        async with store.connection() as db:
            await db.execute("DELETE FROM event_outbox WHERE sequence <= 2")
            await db.commit()
        plan = plan_catchup(
            cursor=1, min_sequence=await store.min_event_cursor(
                stream_key="res_1",
            ),
        )
        assert plan["mode"] == "resync"
        assert plan["reason"] == "cursor_expired"

        payload = await snapshot_with_cursor(store, "res_1")
        assert payload["mode"] == "snapshot_plus_cursor"
        assert payload["snapshot"]["id"] == "res_1"
        assert payload["cursor"] == 3

        # a live cursor keeps replaying
        live = plan_catchup(
            cursor=2, min_sequence=await store.min_event_cursor(
                stream_key="res_1",
            ),
        )
        assert live["mode"] == "replay"
    finally:
        await store.close()


def test_redaction_strips_secrets_before_publication():
    payload = {
        "event": "session.transition",
        "params": {"api_token": "s3cret", "knob": 0.5},
        "headers": {"Authorization": "Bearer xyz"},
        "note": "ok",
    }
    clean, redacted = redact_event_payload(payload)
    assert redacted is True
    assert clean["params"]["api_token"] == "[redacted]"
    assert clean["params"]["knob"] == 0.5
    assert clean["headers"]["Authorization"] == "[redacted]"
    assert "s3cret" not in str(clean)
    again, still = redact_event_payload(clean)
    assert again == clean
    assert still is False


@pytest.mark.asyncio
async def test_two_worker_fanout_and_relay_catchup(tmp_path):
    """A client on worker B observes runs produced on worker A."""
    store = await _open_store(tmp_path)
    try:
        await _seed_session(store, "res_a")
        # worker A produces: its state transition lands durably first
        await store.record_state_event(
            "res_a",
            fields={"status": "running"},
            event_id="res_a:t:1",
            event_type="research_started",
            payload={"status": "running", "api_token": "s3cret"},
            producer="worker-a",
        )
        # worker B's relay (a different logical worker) delivers to its own
        # consumer from its own cursor
        seen_b = []
        delivered, cursor_b = await relay_new_events(
            store,
            cursor=0,
            stream_key="res_a",
            on_event=lambda event: seen_b.append(event),
        )
        assert delivered == 1
        assert seen_b[0]["event_id"] == "res_a:t:1"
        assert seen_b[0]["producer"] == "worker-a"

        # a missed update is recovered on the next relay tick
        await store.record_state_event(
            "res_a",
            fields={"status": "completed"},
            event_id="res_a:t:2",
            event_type="research_completed",
            payload={"status": "completed"},
            producer="worker-a",
        )
        delivered, cursor_b = await relay_new_events(
            store,
            cursor=cursor_b,
            stream_key="res_a",
            on_event=lambda event: seen_b.append(event),
        )
        assert delivered == 1
        assert seen_b[1]["event_id"] == "res_a:t:2"
        assert cursor_b == 2

        # a duplicate relay tick from an old cursor cannot apply twice
        fresh, applied = dedupe_events(seen_b, set())
        assert len(fresh) == 2
        fresh_again, _ = dedupe_events(seen_b, applied)
        assert fresh_again == []
    finally:
        await store.close()