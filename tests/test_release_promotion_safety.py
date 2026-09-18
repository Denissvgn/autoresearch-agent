"""Release regressions for durable remote rollback and candidate binding."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from src.core.config_promoter import ConfigPromoter
from src.core.promotion_approval import target_identity
from src.core.promotion_target import WebhookDeliveryError, WebhookPromotionTarget
from tests.test_webhook_promotion import _patch_mock_transport, _seed_completed_skill_session


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("iteration", 8),
        ("config_snapshot_sha256", "b" * 64),
        ("target_identity", "c" * 64),
    ],
)
async def test_confirmation_rejects_candidate_changed_since_approval(field, value):
    candidate = {"iteration": 7, "config_snapshot_sha256": "a" * 64, "target_identity": "d" * 64}
    store = AsyncMock()
    promoter = ConfigPromoter(store)
    promoter.preview = AsyncMock(return_value={**candidate, field: value})
    promoter._write_text_file = AsyncMock()
    with pytest.raises(ValueError, match=f"candidate mismatch: {field}"):
        await promoter.confirm("session", scope="production", approval=candidate)
    promoter._write_text_file.assert_not_awaited()
    store.record_promotion.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmation_records_exact_approved_preview(tmp_path):
    path = str(tmp_path / "config.yaml")
    preview = {
        "research_id": "session",
        "iteration": 7,
        "model_type": "prompt-engineering",
        "instrument": "default",
        "timeframe": "prod",
        "target_path": path,
        "new_config": "prompt: A",
        "current_config": None,
        "config_snapshot_sha256": hashlib.sha256(b"prompt: A").hexdigest(),
        "target_identity": target_identity({"kind": "file_path", "target_path": path}),
        "training_gates_passed": True,
        "gate_bundle_evaluation": {"passed": True},
        "consistency_report": {"passed": True},
        "quality_baseline_evaluation": {"passed": True},
        "scoped_promotion_metadata": {"promotion_allowed": True},
    }
    store = AsyncMock()
    promoter = ConfigPromoter(store)
    promoter.preview = AsyncMock(return_value=preview)
    await promoter.confirm("session", scope="production", approval=preview)
    promoter.preview.assert_awaited_once()
    assert store.record_promotion.call_args.kwargs["config_yaml"] == "prompt: A"
    assert store.record_promotion.call_args.kwargs["iteration"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_restore", [False, True])
async def test_webhook_rollback_after_restart_uses_recorded_destination(
    monkeypatch,
    tmp_path,
    fail_restore,
):
    remote = {"config": None}
    seen = []
    failed = {"restore": False}

    def handler(request):
        import json

        body = json.loads(request.content)
        seen.append((str(request.url), request.headers["Idempotency-Key"], body["config"]))
        if failed["restore"]:
            return httpx.Response(503)
        remote["config"] = body["config"]
        return httpx.Response(200, json={"ok": True})

    _patch_mock_transport(monkeypatch, handler)
    endpoint = "http://registry.local/original"
    target = WebhookPromotionTarget(endpoint=endpoint, local_root=str(tmp_path), retries=0)
    path = target.target_path(
        model_type="prompt-engineering", instrument="default", timeframe="prod"
    )
    await target.write(path, "prompt: A")
    await target.write(path, "prompt: B")
    store = AsyncMock()
    store.get_latest_development_promotion.return_value = {
        "id": 2,
        "research_id": "session",
        "iteration": 2,
        "target_path": path,
        "previous_yaml": "prompt: A",
        "promotion_metadata": {
            "target_descriptor": {
                "kind": "webhook",
                "target_path": path,
                "endpoint": endpoint,
            },
        },
    }
    # A new singleton file promoter has no in-memory primary-path cache.
    restarted = ConfigPromoter(store)
    failed["restore"] = fail_restore
    if fail_restore:
        with pytest.raises(WebhookDeliveryError):
            await restarted.rollback(
                model_type="prompt-engineering",
                instrument="default",
                timeframe="prod",
            )
        assert remote["config"] == "prompt: B"
        assert Path(path).read_text() == "prompt: B"
        store.record_promotion_rollback.assert_not_awaited()
    else:
        result = await restarted.rollback(
            model_type="prompt-engineering",
            instrument="default",
            timeframe="prod",
        )
        assert result["rolled_back"] is True
        assert remote["config"] == Path(path).read_text() == "prompt: A"
        assert seen[2][0] == endpoint
        # Restoring A gets its own key so an idempotent receiver does not
        # mistake it for the already-delivered initial A.
        assert seen[2][1] != seen[0][1]
        store.record_promotion_rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_delivery_preserves_local_provenance(monkeypatch, tmp_path):
    _patch_mock_transport(monkeypatch, lambda request: httpx.Response(503))
    target = WebhookPromotionTarget(
        endpoint="http://registry.local/", local_root=str(tmp_path), retries=0
    )
    path = target.target_path(
        model_type="prompt-engineering", instrument="default", timeframe="prod"
    )
    Path(path).parent.mkdir(parents=True)
    Path(path).write_text("prompt: A")
    with pytest.raises(WebhookDeliveryError):
        await target.write(path, "prompt: B")
    assert Path(path).read_text() == "prompt: A"


@pytest.mark.asyncio
async def test_file_path_skill_rollback_restores_promoted_template(
    monkeypatch, tmp_path,
):
    """ARC-012 P7-014: a ``file_path`` skill's rollback restores the previous
    content at the skill's declared ``path_template`` — the record carries the
    rendered target path, so a fresh promoter (post-restart shape) needs no
    in-memory state."""
    from src.api import promotion as promotion_module
    from src.config import settings
    from src.core.results_store import ResultsStore
    from src.core.skill_registry import SkillRegistry

    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "ws"))
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "configs"))

    store = ResultsStore(str(tmp_path / "rollback.sqlite"))
    await store.initialize()
    research_id = await _seed_completed_skill_session(
        store, tmp_path, skill_id="code-refactor",
        metrics={
            "primary_metric": 0.72,
            "metric_name": "composite_refactor_score",
            "status": "completed",
            "tests_pass": True,
            "no_perf_regression": True,
            "training_gates_passed": True,
            "config_snapshot": "def target():\n    return 43\n",
        },
    )
    registry = SkillRegistry()
    registry.discover()
    monkeypatch.setattr(promotion_module, "_store", store)
    monkeypatch.setattr(promotion_module, "_registry", registry)

    # Seed a previous config at the template-derived path, then promote over
    # it — the promotion records previous_yaml + the rendered target path.
    promoter, _ = await promotion_module._promoter_for_session(research_id)
    preview = await promoter.preview(research_id, scope="development")
    Path(preview["target_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(preview["target_path"]).write_text(
        "def target():\n    return 42\n", encoding="utf-8",
    )
    await promoter.confirm(research_id, scope="development")
    promoted = Path(preview["target_path"])
    assert promoted.read_text(encoding="utf-8") == "def target():\n    return 43\n"

    # A fresh promoter (no shared state) rolls back to the recorded previous
    # config at the recorded path.
    restarted = ConfigPromoter(store)
    result = await restarted.rollback(
        model_type="", instrument="default", timeframe="production",
        reason="p7-014 rollback proof",
    )
    assert result["rolled_back"] is True
    assert promoted.read_text(encoding="utf-8") == "def target():\n    return 42\n"
