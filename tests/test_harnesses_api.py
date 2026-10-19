"""Harness capability descriptors and run context: the UI's data source.

Every qualified harness is startable and inspectable without a name
branch; unsupported controls carry explicit reasons; unknown cost is
visibly unknown; lifecycle controls stay consistent with server
authorization.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.harnesses import init as init_harnesses
from src.api.harnesses import router as harnesses_router
from src.core.scoped_credentials import (
    PERM_LIFECYCLE,
    PERM_READ,
    PERM_SUBMIT,
    issue_scoped_credential,
)
from src.core.state_store import SQLiteStateStore

KEY = "test-credential-key"


@pytest.fixture
def store(tmp_path):
    async def _build():
        s = SQLiteStateStore(str(tmp_path / "state.db"))
        await s.initialize()
        return s

    return asyncio.run(_build())


@pytest.fixture
def client(store):
    app = FastAPI()
    app.include_router(harnesses_router, prefix="/api/v1")
    init_harnesses(None, store, credential_key=KEY)
    return TestClient(app)


def _token(run_id="res-ui", subject="agent-1", tenant="tenant-a", **kw):
    return issue_scoped_credential(
        subject=subject,
        run_id=run_id,
        tenant_id=tenant,
        key=KEY,
        permissions=(PERM_READ, PERM_SUBMIT, PERM_LIFECYCLE),
        **kw,
    )


def test_descriptors_cover_every_harness_without_name_branches(client):
    listing = client.get("/api/v1/harnesses")
    assert listing.status_code == 200
    harnesses_list = listing.json()["harnesses"]
    assert len(harnesses_list) >= 3
    for descriptor in harnesses_list:
        assert descriptor["contract_version"] == "autoresearch_harness.v1"
        assert isinstance(descriptor["capabilities"], list)
        checks = descriptor["preflight"]["checks"]
        assert checks and all("status" in c for c in checks)
        for entry in descriptor["unsupported_capabilities"]:
            assert entry["reason"]
        single = client.get(f"/api/v1/harnesses/{descriptor['name']}")
        assert single.status_code == 200
        assert single.json()["name"] == descriptor["name"]
    assert client.get("/api/v1/harnesses/no-such").status_code == 404


def test_unadvertised_capabilities_are_refused_not_substituted(client):
    for descriptor in client.get("/api/v1/harnesses").json()["harnesses"]:
        caps = set(descriptor["capabilities"])
        for entry in descriptor["unsupported_capabilities"]:
            assert entry["capability"] not in caps
            assert "refuses it explicitly" in entry["reason"]


def test_run_context_reports_evidence_usage_and_resume(client, store):
    async def _seed():
        await store.create_session(
            session_id="res-ui", instrument="EURUSD", timeframe="1h",
            model_type="rl", tag="t", quick_mode=False, max_iterations=3,
            max_budget_usd=5.0, focus_hint="f", workspace_path="/tmp/ws",
        )
        await store.append_event(
            event_id="ev-harness",
            stream_key="res-ui",
            event_type="agent.run.created",
            payload={
                "harness": "builtin",
                "attach_mode": "native_resume",
                "evaluator": "receipt-authoritative",
                "candidate_digest": "abc",
            },
            producer="test",
        )
        for iteration, authority in (
            (1, "receipt_verified"),
            (2, "unverified_imported"),
        ):
            await store.add_iteration(
                research_id="res-ui",
                iteration=iteration,
                primary_metric=0.5,
                metric_name="primary",
                all_gates_passed=True,
                decision="continue",
                description="d",
                config_snapshot="{}",
                metrics_json=json.dumps({"result_authority": authority}),
                training_time_s=1.0,
            )
        from src.core.llm_provider import (
            COST_UNAVAILABLE,
            Usage,
        )
        from src.core.usage_ledger import UsageEvent

        known = UsageEvent(
            event_key="u1", research_id="res-ui", role="worker",
            provider="p", model="m", usage=Usage(input_tokens=1, output_tokens=1),
            cost_status="billed", cost_usd=0.25,
        )
        unknown = UsageEvent(
            event_key="u2", research_id="res-ui", role="worker",
            provider="p", model="m", usage=Usage(input_tokens=1, output_tokens=1),
            cost_status=COST_UNAVAILABLE, cost_usd=None,
        )
        assert await store.record_usage_event(known.as_row()) is True
        assert await store.record_usage_event(unknown.as_row()) is True

    asyncio.run(_seed())
    body = client.get("/api/v1/research/res-ui/harness-context").json()
    assert body["harness"]["name"] == "builtin"
    assert body["resume_mode"] == "native_resume"
    evidence = body["evidence"]
    assert evidence["verified"] is True
    assert evidence["authority_counts"]["receipt_verified"] == 1
    assert evidence["authority_counts"]["unverified_imported"] == 1
    assert body["candidate_evaluator_context"]["candidate_digest"] == "abc"
    quality = body["usage_quality"]
    # unknown cost is visibly unknown, never summed into the known cost
    assert quality["cost_known_usd"] == 0.25
    assert quality["cost_unknown_events"] == 1
    assert quality["cost_status"] == "partial"


def test_lifecycle_actions_are_capability_and_permission_aware(client):
    operator = client.get("/api/v1/research/res-ui/harness-context").json()
    actions = {a["action"]: a for a in operator["lifecycle"]["actions"]}
    assert actions["pause"]["enabled"] is True
    assert actions["resume"]["enabled"] is True
    assert actions["stop"]["enabled"] is True

    scoped = client.get(
        "/api/v1/research/res-ui/harness-context",
        headers={"Authorization": f"Bearer {_token()}"},
    ).json()
    scoped_actions = {a["action"]: a for a in scoped["lifecycle"]["actions"]}
    # the scoped credential lacks promote: refused with a reason
    assert scoped_actions["promote"]["enabled"] is False
    assert "promote" in scoped_actions["promote"]["reason"]
    assert scoped_actions["pause"]["enabled"] is True
    assert scoped["viewer"]["kind"] == "scoped"


def test_context_for_unregistered_harness_is_honest(client, store):
    async def _seed():
        await store.create_session(
            session_id="res-foreign", instrument="EURUSD", timeframe="1h",
            model_type="rl", tag="t", quick_mode=False, max_iterations=3,
            max_budget_usd=5.0, focus_hint="f", workspace_path="/tmp/ws",
        )
        await store.append_event(
            event_id="ev-foreign",
            stream_key="res-foreign",
            event_type="agent.run.created",
            payload={"harness": "mystery-harness"},
            producer="test",
        )

    asyncio.run(_seed())
    body = client.get("/api/v1/research/res-foreign/harness-context").json()
    assert body["harness"]["name"] == "mystery-harness"
    checks = body["harness"]["preflight"]["checks"]
    assert checks[0]["status"] == "missing"
    for entry in body["harness"]["unsupported_capabilities"]:
        assert entry["reason"]
