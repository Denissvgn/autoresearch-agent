"""Promotion policy acceptance: compiled scope graph, canonical identity, effects.

The tests cover the promotion-policy acceptance: a declared non-ML
development-to-production policy needs no fabricated ML evidence, invalid or
cyclic scope declarations are rejected at load, stale approvals cannot
promote a changed winner, history and rollback lookups separate skills and
targets by canonical identity, ambiguous legacy rollback requires explicit
reconciliation, and file/webhook effects follow the intent-acknowledgement
journal with idempotent retries and reconciliation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.config_promoter import ConfigPromoter
from src.core.promotion_approval import validate_candidate_binding
from src.core.promotion_policy import (
    SCOPE_EVIDENCE_VALIDATORS,
    ScopePolicyError,
    compile_scope_graph,
)
from src.core.results_store import ResultsStore
from tests.test_config_promoter_gate_bundle import (
    _passing_metrics,
    _write_gate_bundle_with_m7_controls,
)


class _Decl:
    def __init__(self, id, approval_required=False, prior_scopes=None, evidence=None):
        self.id = id
        self.approval_required = approval_required
        self.prior_scopes = list(prior_scopes or [])
        self.evidence = list(evidence or [])


def _non_ml_graph():
    """Synthetic non-ML development-to-production policy (no ML evidence)."""
    return compile_scope_graph([
        _Decl("development"),
        _Decl(
            "production",
            approval_required=True,
            prior_scopes=["development"],
            evidence=[],
        ),
    ])


def test_compile_scope_graph_compiles_synthetic_non_ml_graph():
    graph = _non_ml_graph()
    assert set(graph) == {"development", "production"}
    production = graph["production"]
    assert production.prior_scopes == ("development",)
    assert production.approval_required is True
    # A non-ML policy declares no domain evidence: nothing ML-shaped may be
    # demanded for its production scope.
    assert production.evidence == ()


def test_compile_scope_graph_rejects_undeclared_prior():
    with pytest.raises(ScopePolicyError, match="undeclared prior scope"):
        compile_scope_graph([
            _Decl("production", approval_required=True, prior_scopes=["paper"]),
        ])


def test_compile_scope_graph_rejects_cyclic_and_self_referential_scopes():
    with pytest.raises(ScopePolicyError, match="cyclic scope dependencies"):
        compile_scope_graph([
            _Decl("a", prior_scopes=["b"]),
            _Decl("b", prior_scopes=["a"]),
        ])
    with pytest.raises(ScopePolicyError, match="cyclic scope dependencies"):
        compile_scope_graph([_Decl("loop", prior_scopes=["loop"])])


def test_compile_scope_graph_rejects_unknown_evidence_names():
    with pytest.raises(ScopePolicyError, match="unknown evidence"):
        compile_scope_graph([
            _Decl("production", prior_scopes=[], evidence=["faked_ml_artifact"]),
        ])
    for name in SCOPE_EVIDENCE_VALIDATORS:
        graph = compile_scope_graph([_Decl("s", evidence=[name])])
        assert graph["s"].evidence == (name,)



def test_manifest_rejects_invalid_scope_graph_at_load():
    from src.core.skill_manifest import PromotionTarget

    with pytest.raises(Exception, match="cyclic scope dependencies"):
        PromotionTarget(
            primary={"kind": "file_path", "path_template": "config.yaml"},
            scopes=[
                {"id": "a", "prior_scopes": ["b"]},
                {"id": "b", "prior_scopes": ["a"]},
            ],
        )


async def _scoped_production_metadata(evidence_payload, monkeypatch, tmp_path):
    """Scoped production metadata through the real promoter path."""
    monkeypatch.setattr(
        ConfigPromoter,
        "_promotion_scope_evidence",
        lambda self, *args, **kwargs: evidence_payload,
    )
    store = ResultsStore(str(tmp_path / "promotions.sqlite"))
    await store.initialize()
    promoter = ConfigPromoter(store)
    preview = {
        "research_id": "research_1",
        "iteration": 3,
        "model_type": "direction",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "target_path": str(tmp_path / "config.yaml"),
    }
    return await promoter._build_scoped_promotion_metadata(
        preview=preview,
        session={"skill_id": "db-config-tuning", "research_id": "research_1"},
        metrics_payload={},
        scope="production",
        approval=None,
    )


@pytest.mark.asyncio
async def test_declared_non_ml_scope_requires_no_ml_evidence(monkeypatch, tmp_path):
    """A declared non-ML policy needs no fabricated ML evidence."""
    failing_ml = {
        key: {"passed": False, "fabricated": True}
        for key in SCOPE_EVIDENCE_VALIDATORS.values()
    }
    metadata = await _scoped_production_metadata(failing_ml, monkeypatch, tmp_path)
    reason_names = [
        check["reason"]
        for check in metadata["checks"]
        if check["status"] == "failed"
    ]
    ml_reasons = {f"missing_{name}" for name in SCOPE_EVIDENCE_VALIDATORS} | {
        "missing_paper_validation",
        "missing_production_gate_bundle",
        "missing_model_card",
        "missing_feature_readiness",
        "inference_reload_failed",
        "missing_canary_duration",
        "missing_live_risk_limits",
        "missing_monitoring_alerts",
        "missing_rl_oos_provenance",
        "missing_rl_economic_replay",
    }
    assert not (set(reason_names) & ml_reasons), reason_names
    assert "missing_development_promotion" in reason_names
    assert "missing_production_approval" in reason_names
    check_names = {check["name"] for check in metadata["checks"]}
    assert not (check_names & {
        "paper_validation_passed",
        "model_card_present",
        "supervised_feature_readiness",
        "inference_parity_reload_passed",
        "production_gate_bundle_loaded",
    })


@pytest.mark.asyncio
async def test_prior_promotion_lookup_separates_by_canonical_identity(tmp_path):
    """Two skills on two targets never share prior-promotion history."""
    store = ResultsStore(str(tmp_path / "promotions.sqlite"))
    await store.initialize()
    await _ensure_session(store)
    base = dict(model_type="direction", instrument="DOGE_USDT", timeframe="15m")
    await store.record_promotion(
        research_id="research_1",
        iteration=3,
        target_path="/tmp/a.yaml",
        config_yaml="agent_strategy: A\n",
        previous_yaml="agent_strategy: OLD\n",
        scope="production",
        promotion_metadata={"skill_id": "skill-a", "target_identity": "identity-a"},
        **base,
    )
    await store.record_promotion(
        research_id="research_1",
        iteration=3,
        target_path="/tmp/b.yaml",
        config_yaml="agent_strategy: B\n",
        previous_yaml="agent_strategy: OLD\n",
        scope="production",
        promotion_metadata={"skill_id": "skill-b", "target_identity": "identity-b"},
        **base,
    )
    await store.record_promotion(
        research_id="research_1",
        iteration=3,
        target_path="/tmp/legacy.yaml",
        config_yaml="agent_strategy: L\n",
        previous_yaml="agent_strategy: OLD\n",
        scope="production",
        promotion_metadata={},
        **base,
    )
    promoter = ConfigPromoter(store)
    row_a = await promoter._latest_promotion_record(
        scope="production", skill_id="skill-a", target_identity="identity-a", **base
    )
    assert row_a["promotion_metadata"]["skill_id"] == "skill-a"
    assert row_a["_identity_provenance"] == "canonical"
    row_b = await promoter._latest_promotion_record(
        scope="production", skill_id="skill-b", target_identity="identity-b", **base
    )
    assert row_b["promotion_metadata"]["skill_id"] == "skill-b"


def test_stale_approval_cannot_promote_changed_winner():
    """An approval bound to one candidate never promotes a changed winner."""
    import hashlib

    def digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    target = digest("kind|target_path")
    approval = {
        "iteration": 3,
        "config_snapshot_sha256": digest("agent_strategy: A\n"),
        "target_identity": target,
    }
    unchanged = {
        "iteration": 3,
        "config_snapshot_sha256": digest("agent_strategy: A\n"),
        "target_identity": target,
    }
    validate_candidate_binding(approval, unchanged)  # bound: accepted
    changed_winner = {
        "iteration": 4,
        "config_snapshot_sha256": digest("agent_strategy: B\n"),
        "target_identity": target,
    }
    with pytest.raises(ValueError, match="candidate mismatch"):
        validate_candidate_binding(approval, changed_winner)
    retargeted = {
        "iteration": 3,
        "config_snapshot_sha256": digest("agent_strategy: A\n"),
        "target_identity": digest("other-target"),
    }
    with pytest.raises(ValueError, match="candidate mismatch"):
        validate_candidate_binding(approval, retargeted)


async def _ensure_session(store):
    """Promotion rows require their research session (FK)."""
    if await store.get_session("research_1") is not None:
        return
    await store.create_session(
        session_id="research_1",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="fx071",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path="/tmp",
    )


async def _seed_one_promotion(store, *, metadata, tmp_path, name="config.yaml"):
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("agent_strategy: NEW\n", encoding="utf-8")
    await _ensure_session(store)
    row = await store.record_promotion(
        research_id="research_1",
        iteration=3,
        model_type="direction",
        instrument="DOGE_USDT",
        timeframe="15m",
        target_path=str(target),
        config_yaml="agent_strategy: NEW\n",
        previous_yaml="agent_strategy: OLD\n",
        scope="development",
        promotion_metadata=metadata,
    )
    return row, target


@pytest.mark.asyncio
async def test_ambiguous_legacy_rollback_requires_explicit_reconciliation(
    tmp_path, monkeypatch,
):
    from src.core import config_promoter as cp

    monkeypatch.setattr(cp.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(cp.settings, "host_configs_path", str(tmp_path / "configs"))
    store = ResultsStore(str(tmp_path / "promotions.sqlite"))
    await store.initialize()
    row, target = await _seed_one_promotion(
        store,
        metadata={},
        tmp_path=tmp_path,
        name="configs/direction/DOGE_USDT_15m.yaml",
    )
    promoter = ConfigPromoter(store)
    with pytest.raises(ValueError, match="ambiguous legacy rollback"):
        await promoter.rollback(
            model_type="direction",
            instrument="DOGE_USDT",
            timeframe="15m",
            reason="test",
        )
    resolved = await promoter.rollback(
        model_type="direction",
        instrument="DOGE_USDT",
        timeframe="15m",
        reason="test",
        reconcile_legacy=True,
    )
    assert target.read_text(encoding="utf-8") == "agent_strategy: OLD\n"
    assert resolved["promotion_id"] == row["id"]


@pytest.mark.asyncio
async def test_rollback_refuses_foreign_target_identity(tmp_path):
    store = ResultsStore(str(tmp_path / "promotions.sqlite"))
    await store.initialize()
    snapshot = tmp_path / "snapshot.yaml"
    snapshot.write_text("agent_strategy: OLD\n", encoding="utf-8")
    await _seed_one_promotion(
        store,
        metadata={
            "skill_id": "skill-b",
            "target_identity": "foreign-identity",
            "rollback_readiness": {
                "previous_config_snapshot_path": str(snapshot),
                "rollback_target": str(snapshot),
            },
        },
        tmp_path=tmp_path,
    )
    promoter = ConfigPromoter(store)
    with pytest.raises(ValueError, match="different target identity"):
        await promoter.rollback(
            model_type="direction",
            instrument="DOGE_USDT",
            timeframe="15m",
            reason="test",
        )


async def _confirm_ready_store(tmp_path, monkeypatch):
    _write_gate_bundle_with_m7_controls(tmp_path)
    from src.core import config_promoter as cp

    monkeypatch.setattr(cp.settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(cp.settings, "host_configs_path", str(tmp_path / "configs"))
    target = tmp_path / "configs" / "direction" / "DOGE_USDT_15m.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("agent_strategy: OLD\n", encoding="utf-8")
    (tmp_path / "workspace").mkdir()
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await store.create_session(
        session_id="research_1",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="fx071",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(tmp_path / "workspace"),
    )
    metrics = _passing_metrics()
    metrics.pop("rollback_target")
    await store.add_iteration(
        research_id="research_1",
        iteration=3,
        primary_metric=0.61,
        metric_name="auc",
        all_gates_passed=True,
        decision="keep",
        description="passing candidate",
        config_snapshot="agent_strategy: BALA\n",
        metrics_json=json.dumps(metrics),
        training_time_s=1.0,
    )
    return store, target


@pytest.mark.asyncio
async def test_effect_intent_is_recorded_before_the_external_write(
    tmp_path, monkeypatch,
):
    """A crash between effect and acknowledgement stays reconcilable."""
    store, target = await _confirm_ready_store(tmp_path, monkeypatch)
    original = ConfigPromoter._write_text_file
    attempts = {"count": 0}

    async def failing_write(self, path, content):
        if str(path).endswith("DOGE_USDT_15m.yaml") and "BALA" in content:
            attempts["count"] += 1
            raise OSError("fault-injected target write failure")
        return await original(self, path, content)

    monkeypatch.setattr(ConfigPromoter, "_write_text_file", failing_write)
    with pytest.raises(OSError, match="fault-injected"):
        await ConfigPromoter(store).confirm("research_1")
    assert attempts["count"] == 1
    rows = await store.list_promotions()
    assert len(rows) == 1
    effect = rows[0]["promotion_metadata"]["effect"]
    assert effect["status"] == "effect_failed"
    assert effect["idempotency_key"]
    assert effect["intent_at"]

    monkeypatch.setattr(ConfigPromoter, "_write_text_file", original)
    result = await ConfigPromoter(store).confirm("research_1")
    effect = result["promotion_metadata"]["effect"]
    assert effect["status"] == "applied"
    assert effect["acked_at"]
    assert result["id"] == rows[0]["id"]
    repeat = await ConfigPromoter(store).confirm("research_1")
    assert repeat["id"] == rows[0]["id"]
    assert repeat["promotion_metadata"]["effect"]["status"] == "applied"
    rows = await store.list_promotions()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_reconcile_promotion_effect_marks_applied_or_failed(tmp_path):
    store = ResultsStore(str(tmp_path / "promotions.sqlite"))
    await store.initialize()
    row, target = await _seed_one_promotion(
        store,
        metadata={"effect": {"status": "pending_effect", "idempotency_key": "k"}},
        tmp_path=tmp_path,
    )
    promoter = ConfigPromoter(store)
    target.write_text("agent_strategy: NEW\n", encoding="utf-8")
    reconciled = await promoter.reconcile_promotion_effect(row)
    assert reconciled["promotion_metadata"]["effect"]["status"] == "applied"
    assert reconciled["promotion_metadata"]["effect"]["reconciled_at"]
    row2, target2 = await _seed_one_promotion(
        store,
        metadata={"effect": {"status": "pending_effect", "idempotency_key": "k2"}},
        tmp_path=tmp_path,
        name="config2.yaml",
    )
    target2.write_text("agent_strategy: DIVERGED\n", encoding="utf-8")
    reconciled2 = await promoter.reconcile_promotion_effect(row2)
    assert reconciled2["promotion_metadata"]["effect"]["status"] == "effect_failed"


@pytest.mark.asyncio
async def test_fault_injected_webhook_receiver_fails_delivery_idempotently(
    monkeypatch, tmp_path,
):
    """The agent-owned receiver faults; retries carry one idempotency key."""
    import httpx

    from src.core.promotion_target import WebhookDeliveryError
    from tests.test_webhook_promotion import (
        _patch_mock_transport,
        _primary_path,
        _webhook_target,
    )

    attempts = []

    def failing_receiver(request):
        attempts.append(request)
        return httpx.Response(500, text="fault-injected receiver failure")

    _patch_mock_transport(monkeypatch, failing_receiver)
    target = _webhook_target(tmp_path, retries=1)
    primary = _primary_path(target)
    with pytest.raises(WebhookDeliveryError):
        await target.write(primary, "agent_strategy: NEW\n")
    assert len(attempts) == 2  # initial attempt + one idempotent retry
    keys = {req.headers.get("Idempotency-Key") for req in attempts}
    assert len(keys) == 1 and None not in keys
