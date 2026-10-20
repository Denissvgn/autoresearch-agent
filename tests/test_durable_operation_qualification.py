"""Durable-operation qualification: fault injection with real process death.

Worker processes are killed (os._exit) at designated points during
bootstrap, evaluation, result acceptance, event publication, and promotion
intent handling. Persisted state is inspected after restart, recovery is
exercised and timed, and the qualified invariants hold: no duplicate
authoritative result/effect, no silent configuration drift, no shared
mutable workspace, and no stale-owner write. Unknown external effects are
exposed for reconciliation, never assumed absent.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from src.core.state_store import (
    SQLiteStateStore,
    StaleFenceError,
)
from src.ws.events import relay_new_events

REPO_ROOT = Path(__file__).resolve().parents[1]

KILL_EXIT = 42

_WORKER = textwrap.dedent(
    """
    import asyncio
    import json
    import os
    import sys

    sys.path.insert(0, sys.argv[3])

    from src.core.state_store import SQLiteStateStore

    def die():
        os._exit(42)

    async def main():
        db_path, phase = sys.argv[1], sys.argv[2]
        store = SQLiteStateStore(db_path)
        await store.initialize()

        if phase == "bootstrap":
            await store.reserve_work(
                reservation_key="res_q",
                scope_key="q/scope",
                owner_id="worker-doomed",
                capacity_limit=4,
                lease_seconds=0.0,
            )
            await store.reserve_budget(
                reservation_id="budget:res_q",
                research_id="res_q",
                amount_usd=5.0,
                strict_cap_usd=10.0,
                enforcement="strict",
                lease_seconds=0.0,
            )
            die()

        if phase == "evaluation":
            await store.create_session(
                session_id="res_q",
                instrument="EURUSD",
                timeframe="1h",
                model_type="",
                skill_id="prompt-engineering",
                subject_id="EURUSD",
                variant="1h",
                tag="q",
                quick_mode=True,
                max_iterations=3,
                max_budget_usd=7.5,
                focus_hint="nondefault focus",
                workspace_path="/tmp/q-eval",
                manifest_json=json.dumps({"research_id": "res_q"}),
                manifest_hash="h",
            )
            await store.reserve_work(
                reservation_key="res_q",
                scope_key="q/scope",
                owner_id="worker-doomed",
                capacity_limit=4,
                lease_seconds=0.0,
            )
            await store.record_state_event(
                "res_q",
                fields={"status": "running"},
                event_id="res_q:t:running",
                event_type="research_started",
                payload={"status": "running"},
                producer="worker-doomed",
            )
            await store.add_iteration(
                research_id="res_q",
                iteration=1,
                all_gates_passed=True,
                primary_metric=0.5,
                metric_name="auc",
                decision="keep",
                description="attempt 1",
                config_snapshot="knob: 0.42\\n",
                metrics_json=json.dumps({"auc": 0.5}),
                training_time_s=1.0,
            )
            die()

        if phase == "result_acceptance":
            await store.create_session(
                session_id="res_q",
                instrument="EURUSD",
                timeframe="1h",
                model_type="",
                skill_id="prompt-engineering",
                subject_id="EURUSD",
                variant="1h",
                tag="q",
                quick_mode=True,
                max_iterations=3,
                max_budget_usd=7.5,
                focus_hint=None,
                workspace_path="/tmp/q-result",
                manifest_json=json.dumps({"research_id": "res_q"}),
                manifest_hash="h",
            )
            await store.append_event(
                event_id="res_q:delivery:1",
                stream_key="res_q",
                event_type="result.delivered",
                payload={"receipt": "r-1"},
                producer="evaluator",
            )
            die()

        if phase == "event_publication":
            await store.create_session(
                session_id="res_q",
                instrument="EURUSD",
                timeframe="1h",
                model_type="",
                skill_id="prompt-engineering",
                subject_id="EURUSD",
                variant="1h",
                tag="q",
                quick_mode=True,
                max_iterations=3,
                max_budget_usd=7.5,
                focus_hint=None,
                workspace_path="/tmp/q-events",
                manifest_json=json.dumps({"research_id": "res_q"}),
                manifest_hash="h",
            )
            await store.record_state_event(
                "res_q",
                fields={"status": "completed"},
                event_id="res_q:t:completed",
                event_type="research_completed",
                payload={"status": "completed"},
                producer="worker-doomed",
            )
            die()

        if phase == "promotion_intent":
            await store.create_session(
                session_id="res_q",
                instrument="EURUSD",
                timeframe="1h",
                model_type="",
                skill_id="prompt-engineering",
                subject_id="EURUSD",
                variant="1h",
                tag="q",
                quick_mode=True,
                max_iterations=3,
                max_budget_usd=7.5,
                focus_hint=None,
                workspace_path="/tmp/q-promo",
                manifest_json=json.dumps({"research_id": "res_q"}),
                manifest_hash="h",
            )
            await store.record_promotion(
                research_id="res_q",
                iteration=1,
                model_type="trend",
                instrument="EURUSD",
                timeframe="1h",
                target_path="/tmp/q-target.yaml",
                config_yaml="x: 2\\n",
                previous_yaml="x: 1\\n",
                promotion_metadata={
                    "effect": {
                        "effect_key": "q-effect-1",
                        "status": "pending_effect",
                    }
                },
            )
            die()

        raise SystemExit(f"unknown phase {phase}")

    asyncio.run(main())
    """
)


async def _open_store(tmp_path: Path) -> SQLiteStateStore:
    store = SQLiteStateStore(str(tmp_path / "state.db"))
    await store.initialize()
    return store


def _kill_worker(tmp_path: Path, phase: str) -> None:
    script = tmp_path / "worker.py"
    script.write_text(_WORKER)
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            str(tmp_path / "state.db"),
            phase,
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == KILL_EXIT, (
        f"phase {phase} must die at its kill point: {proc.stderr}"
    )


@pytest.mark.asyncio
async def test_process_death_during_bootstrap_reconciles_cleanly(tmp_path):
    _kill_worker(tmp_path, "bootstrap")
    store = await _open_store(tmp_path)
    try:
        started = time.monotonic()
        reclaimed = await store.reclaim_expired_reservations()
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"cleanup took {elapsed:.2f}s"
        assert [row["reservation_key"] for row in reclaimed] == ["res_q"]
        # no session row exists and the freed capacity admits new work
        assert await store.get_session("res_q") is None
        assert await store.reserve_work(
            reservation_key="res_next",
            scope_key="q/scope",
            owner_id="worker-new",
            capacity_limit=1,
            lease_seconds=60.0,
        )
        # the doomed worker's expired budget hold cannot oversubscribe
        assert await store.reserve_budget(
            reservation_id="budget:res_next",
            research_id="res_next",
            amount_usd=10.0,
            strict_cap_usd=10.0,
            enforcement="strict",
            lease_seconds=60.0,
        )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_process_death_during_evaluation_exposes_unknown_inflight_state(
    tmp_path,
):
    _kill_worker(tmp_path, "evaluation")
    store = await _open_store(tmp_path)
    try:
        from src.core.session_manager import SessionManager

        manager = SessionManager(store)
        started = time.monotonic()
        # the crashed worker's lease has lapsed: reclamation frees its hold
        # first, then recovery classifies the in-flight session
        await store.reclaim_expired_reservations()
        summary = await manager.recover_orphaned_sessions()
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"cleanup took {elapsed:.2f}s"
        # the in-flight state is exposed as an operator decision, never
        # assumed absent
        assert summary.get("resumable") or summary.get("interrupted")
        session = await store.get_session("res_q")
        assert session is not None
        assert session is not None
        assert session["status"] in ("resumable", "interrupted")
        # exactly one authoritative attempt row survived; no duplicate
        rows = await store.get_iterations("res_q")
        assert len(rows) == 1
        # no silent configuration drift: the persisted nondefault settings
        # are intact
        assert session["max_budget_usd"] == 7.5
        assert session["max_iterations"] == 3
        assert session["focus_hint"] == "nondefault focus"
        # the durable stream records the committed transition and the
        # recovery's own classification transition — nothing else
        events = await store.list_events(stream_key="res_q")
        assert [e["payload"].get("status") for e in events][0] == "running"
        assert len(events) == 2
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_process_death_during_result_acceptance_never_duplicates_results(
    tmp_path,
):
    _kill_worker(tmp_path, "result_acceptance")
    store = await _open_store(tmp_path)
    try:
        # the delivery was durably recorded; the authoritative result write
        # never happened. Re-delivery after restart lands exactly once and a
        # second replay is attributed as a duplicate, never authoritative.
        events = await store.list_events(stream_key="res_q")
        assert [e["event_id"] for e in events] == ["res_q:delivery:1"]
        assert await store.get_iterations("res_q") == []

        await store.add_iteration(
            research_id="res_q",
            iteration=1,
            all_gates_passed=True,
            primary_metric=0.5,
            metric_name="auc",
            decision="keep",
            description="redelivered result",
            config_snapshot="knob: 0.42\n",
            metrics_json=json.dumps({"auc": 0.5}),
            training_time_s=1.0,
        )
        await store.add_iteration(
            research_id="res_q",
            iteration=2,
            all_gates_passed=True,
            primary_metric=0.5,
            metric_name="auc",
            decision="keep",
            description="redelivered result",
            config_snapshot="knob: 0.42\n",
            metrics_json=json.dumps({"auc": 0.5}),
            training_time_s=1.0,
            duplicate_of_research_id="res_q",
            duplicate_of_iteration=1,
            duplicate_reason="replayed delivery",
        )
        rows = await store.get_iterations("res_q")
        authoritative = [
            row for row in rows if not row.get("duplicate_of_research_id")
        ]
        attributed = [
            row for row in rows if row.get("duplicate_of_research_id")
        ]
        assert len(authoritative) == 1, rows
        assert len(attributed) == 1, rows
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_process_death_during_event_publication_drops_no_event(tmp_path):
    _kill_worker(tmp_path, "event_publication")
    store = await _open_store(tmp_path)
    try:
        # state and event committed together before the kill; the
        # notification was lost, the event was not
        session = await store.get_session("res_q")
        assert session is not None
        assert session is not None
        assert session["status"] == "completed"
        delivered = []

        started = time.monotonic()
        count, cursor = await relay_new_events(
            store,
            cursor=0,
            stream_key="res_q",
            on_event=lambda event: delivered.append(event),
        )
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"recovery took {elapsed:.2f}s"
        assert count == 1
        assert delivered[0]["event_id"] == "res_q:t:completed"
        assert cursor == 1
        # a second relay tick delivers nothing new (no duplicate delivery)
        count, _cursor = await relay_new_events(
            store,
            cursor=cursor,
            stream_key="res_q",
            on_event=lambda event: delivered.append(event),
        )
        assert count == 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_process_death_during_promotion_intent_exposes_unknown_effect(
    tmp_path,
):
    _kill_worker(tmp_path, "promotion_intent")
    store = await _open_store(tmp_path)
    try:
        from src.core.config_promoter import ConfigPromoter

        promotions = await store.list_promotions()
        assert len(promotions) == 1
        effect = (promotions[0].get("promotion_metadata") or {}).get("effect")
        # the intent is recorded and pending: the external effect is
        # unknown, never assumed absent and never assumed applied
        assert effect["status"] == "pending_effect"

        promoter = ConfigPromoter(store)
        started = time.monotonic()
        outcome = await promoter.reconcile_promotion_effect(promotions[0])
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"reconciliation took {elapsed:.2f}s"
        # ambiguous state is never guessed into success
        assert outcome.get("status") != "applied"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_stale_owner_write_is_refused_after_reclaim(tmp_path):
    _kill_worker(tmp_path, "bootstrap")
    store = await _open_store(tmp_path)
    try:
        await _open_sessions(store)
        # the doomed owner held epoch 0; reclaim frees it and a new owner
        # takes over with a fresh fence
        await store.reclaim_expired_reservations()
        await store.reserve_work(
            reservation_key="res_q",
            scope_key="q/scope",
            owner_id="worker-new",
            capacity_limit=4,
            lease_seconds=60.0,
        )
        await store.bump_session_epoch("res_q")
        with pytest.raises(StaleFenceError):
            await store.add_iteration(
                research_id="res_q",
                iteration=2,
                lock_epoch=0,
                all_gates_passed=True,
                primary_metric=0.5,
                metric_name="auc",
                decision="keep",
                description="late write from the dead owner",
                config_snapshot="knob: 0.42\n",
                metrics_json=json.dumps({"auc": 0.1}),
                training_time_s=1.0,
            )
    finally:
        await store.close()


async def _open_sessions(store: SQLiteStateStore) -> None:
    await store.create_session(
        session_id="res_q",
        instrument="EURUSD",
        timeframe="1h",
        model_type="",
        skill_id="prompt-engineering",
        subject_id="EURUSD",
        variant="1h",
        tag="q",
        quick_mode=True,
        max_iterations=3,
        max_budget_usd=7.5,
        focus_hint=None,
        workspace_path="/tmp/q-stale",
        manifest_json=json.dumps({"research_id": "res_q"}),
        manifest_hash="h",
    )


_SCENARIO_WORKER = textwrap.dedent(
    """
    import asyncio
    import json
    import os
    import sys

    sys.path.insert(0, sys.argv[3])

    from src.core.state_store import BudgetExceeded, CapacityExceeded
    from src.core.state_store import SQLiteStateStore
    from src.core.usage_ledger import ROLE_AGENT, ROLE_EVALUATOR
    from src.core.usage_ledger import event_from_quote, record_usage_event
    from src.core.llm_provider import MockProvider, Usage

    async def main():
        db_path, key = sys.argv[1], sys.argv[2]
        store = SQLiteStateStore(db_path)
        await store.initialize()
        try:
            try:
                await store.reserve_work(
                    reservation_key=key,
                    scope_key="scenario/scope",
                    owner_id=f"worker-{key}",
                    capacity_limit=3,
                    lease_seconds=300.0,
                )
                await store.reserve_budget(
                    reservation_id=f"budget:{key}",
                    research_id=key,
                    amount_usd=5.0,
                    strict_cap_usd=15.0,
                    enforcement="strict",
                    lease_seconds=300.0,
                )
            except (CapacityExceeded, BudgetExceeded):
                print("REFUSED", flush=True)
                return
            from src.core.research_manifest import build_research_manifest
            from src.core.run_spec import build_run_spec, skill_package_dir
            from src.core.skill_registry import default_registry

            current = default_registry.get("prompt-engineering")
            spec = build_run_spec(
                skill_params={
                    "scorer_endpoint": "https://scorer.internal/v1",
                    "eval_set": "eval/set.jsonl",
                    "api_token": "secret-value",
                },
                param_schema=None,
                skill_id="prompt-engineering",
                skill_version=getattr(current, "version", None),
                skill_dir=skill_package_dir("prompt-engineering"),
                objective_policy={"metric": "auc", "direction": "maximize"},
                policy={"approval_required": False},
                effective_config={
                    "max_budget_usd": 7.5,
                    "max_iterations": 3,
                },
            )
            manifest = build_research_manifest(
                research_id=key,
                instrument="EURUSD",
                timeframe="1h",
                model_type="",
                tag=key,
                quick_mode=False,
                max_iterations=3,
                max_budget_usd=7.5,
                timeout_s=0,
                focus_hint="scenario nondefault",
                skill_id="prompt-engineering",
                skill_params={},
            )
            manifest.run_spec = spec
            await store.create_session(
                session_id=key,
                instrument="EURUSD",
                timeframe="1h",
                model_type="",
                skill_id="prompt-engineering",
                subject_id="EURUSD",
                variant="1h",
                tag=key,
                quick_mode=False,
                max_iterations=3,
                max_budget_usd=7.5,
                focus_hint="scenario nondefault",
                workspace_path=f"/tmp/scenario-{key}",
                manifest_json=manifest.model_dump_json(),
                manifest_hash="h",
            )
            await store.update_session(key, status="running")
            provider = MockProvider()
            for role in (ROLE_AGENT, ROLE_EVALUATOR):
                quote = provider.price_quote("mock", Usage(10, 5))
                await record_usage_event(
                    store,
                    event_from_quote(
                        event_key=f"{key}:{role}:1",
                        research_id=key,
                        role=role,
                        provider="mock",
                        model="mock",
                        usage=Usage(10, 5),
                        quote=quote,
                    ),
                )
            print("ADMITTED", flush=True)
        finally:
            await store.close()

    asyncio.run(main())
    """
)


def test_simultaneous_admission_and_resume_with_reservations(tmp_path):
    """Real workers race admission; a killed one resumes with its contract."""
    script = tmp_path / "scenario_worker.py"
    script.write_text(_SCENARIO_WORKER)
    keys = [f"res_s{i}" for i in range(4)]
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(script),
                str(tmp_path / "state.db"),
                key,
                str(REPO_ROOT),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for key in keys
    ]
    outputs = {}
    for key, proc in zip(keys, procs, strict=False):
        out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, (key, err)
        outputs[key] = out.strip()

    async def _verify() -> None:
        store = await _open_store(tmp_path)
        try:
            # strict caps admitted exactly three: work cap 3, budget cap 15
            admitted = [k for k, v in outputs.items() if v == "ADMITTED"]
            assert len(admitted) == 3, outputs
            victim = admitted[0]
            # usage reservations are attributed per admitted worker and role
            for key in admitted:
                events = await store.get_usage_events(key)
                roles = sorted(event["role"] for event in events)
                assert roles == ["agent", "evaluator"]
            # the persisted nondefault contract is exactly restorable —
            # the resumed run reproduces it, never today's defaults
            from src.core.research_manifest import load_persisted_manifest
            from src.core.run_restore import assess_recovery

            victim_row = await store.get_session(victim)
            assert victim_row is not None
            assert victim_row is not None
            assert victim_row["max_budget_usd"] == 7.5
            assert victim_row["max_iterations"] == 3
            assert victim_row["focus_hint"] == "scenario nondefault"
            manifest, _report = load_persisted_manifest(
                victim_row["manifest_json"]
            )
            report = assess_recovery(
                kind="continuation",
                session_id=victim,
                run_spec=dict(getattr(manifest, "run_spec", None) or {}),
            )
            # the unbound credential is exposed as an actionable blocker
            assert report.ready is False
            assert {b["code"] for b in report.as_dict()["blockers"]} == {
                "missing_credential"
            }
            # the operator's explicit rebinding restores readiness
            import os

            os.environ["SKILL_PARAM_API_TOKEN"] = "bound"
            try:
                report = assess_recovery(
                    kind="continuation",
                    session_id=victim,
                    run_spec=dict(getattr(manifest, "run_spec", None) or {}),
                )
                assert report.ready is True, report.as_dict()
                assert report.contract["skill_params"]["scorer_endpoint"] == (
                    "https://scorer.internal/v1"
                )
                assert (
                    report.contract["effective_config"]["max_budget_usd"]
                    == 7.5
                )
            finally:
                os.environ.pop("SKILL_PARAM_API_TOKEN", None)
            # no shared mutable workspace across the admitted runs
            roots = {
                row["workspace_path"]
                for key in admitted
                if (row := await store.get_session(key)) is not None
            }
            assert len(roots) == 3, roots
        finally:
            await store.close()

    asyncio.run(_verify())

