"""Webhook promotion target tests (P1-3).

Covers: local provenance writes + endpoint delivery on the primary path only,
idempotency key + bearer auth, retry-then-fail-closed behavior, manifest
schema acceptance of ``kind: webhook``, runtime wiring for webhook and
registry_api kinds, and the API-layer per-session promoter selection.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("PROMPT_REGISTRY_AUTH_TOKEN", "test-registry-token")

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import yaml

from src.core.promotion_target import (
    WebhookDeliveryError,
    WebhookPromotionTarget,
)
from src.core.skill_loader import load_skill_manifest
from src.core.skill_runtime import ManifestSkillRuntime, SkillConfigError

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"


def _manifest(skill_id: str):
    return load_skill_manifest(SKILLS_ROOT / skill_id / "SKILL.yaml")


def _patch_mock_transport(monkeypatch, handler) -> list[httpx.Request]:
    """Route httpx.AsyncClient through a MockTransport recording requests."""
    seen: list[httpx.Request] = []
    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient

    def _factory(**kwargs):
        kwargs.pop("app", None)
        return orig_client(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    return seen


def _webhook_target(tmp_path, **kwargs) -> WebhookPromotionTarget:
    defaults = dict(
        endpoint="http://registry.local/api/v1/prompts",
        auth_env_var="PROMPT_REGISTRY_AUTH_TOKEN",
        retries=0,
        local_root=str(tmp_path),
    )
    defaults.update(kwargs)
    return WebhookPromotionTarget(**defaults)


def _primary_path(t: WebhookPromotionTarget) -> str:
    return t.target_path(
        model_type="prompt-engineering",
        instrument="default",
        timeframe="production",
    )


@pytest.mark.asyncio
async def test_write_delivers_only_primary_path(monkeypatch, tmp_path):
    t = _webhook_target(tmp_path)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"prompt_id": "p_1"})

    _patch_mock_transport(monkeypatch, handler)
    primary = _primary_path(t)
    await t.write(primary, "prompt: hello")
    # Local provenance copy exists.
    assert Path(primary).read_text(encoding="utf-8") == "prompt: hello"
    # Delivery happened exactly once, with idempotency key + auth.
    assert len(seen) == 1
    assert seen[0].headers["Idempotency-Key"]
    assert seen[0].headers["Authorization"] == "Bearer test-registry-token"
    body = json.loads(seen[0].read())
    assert body["config"] == "prompt: hello"

    # A sidecar write must NOT trigger a second delivery.
    sidecar = t.metadata_sidecar_path(primary, 3)
    await t.write(sidecar, "{}")
    assert len(seen) == 1
    assert Path(sidecar).is_file()


@pytest.mark.asyncio
async def test_delivery_retries_then_fails_closed(monkeypatch, tmp_path):
    t = _webhook_target(tmp_path, retries=1)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="boom")

    _patch_mock_transport(monkeypatch, handler)
    with pytest.raises(WebhookDeliveryError, match="503"):
        await t.write(_primary_path(t), "prompt: x")
    assert calls["n"] == 2  # initial + one retry


@pytest.mark.asyncio
async def test_delivery_4xx_does_not_retry(monkeypatch, tmp_path):
    t = _webhook_target(tmp_path, retries=2)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, text="denied")

    _patch_mock_transport(monkeypatch, handler)
    with pytest.raises(WebhookDeliveryError, match="401"):
        await t.write(_primary_path(t), "prompt: x")
    assert calls["n"] == 1


def test_webhook_kind_accepted_by_manifest_schema():
    base = yaml.safe_load(
        (SKILLS_ROOT / "prompt-engineering" / "SKILL.yaml").read_text()
    )
    base["promotion_target"]["primary"] = {
        "kind": "webhook",
        "endpoint": "http://receiver.local/api/v1/prompts",
        "auth_secret": "RECEIVER_TOKEN",
        "timeout_s": 5.0,
        "retries": 1,
    }
    manifest = load_skill_manifest(yaml.safe_dump(base))
    assert manifest.promotion_target.primary.kind == "webhook"


def test_runtime_webhook_kind_builds_webhook_target():
    base = yaml.safe_load(
        (SKILLS_ROOT / "prompt-engineering" / "SKILL.yaml").read_text()
    )
    base["promotion_target"]["primary"] = {
        "kind": "webhook",
        "endpoint": "http://receiver.local/api/v1/prompts",
        "auth_secret": "RECEIVER_TOKEN",
    }
    rt = ManifestSkillRuntime(
        load_skill_manifest(yaml.safe_dump(base)), orchestrator=MagicMock(),
    )
    target = rt.promotion_target()
    assert isinstance(target, WebhookPromotionTarget)
    assert target.endpoint == "http://receiver.local/api/v1/prompts"
    assert target.auth_env_var == "RECEIVER_TOKEN"


def test_runtime_artifact_store_kind_still_raises_loudly():
    base = yaml.safe_load(
        (SKILLS_ROOT / "prompt-engineering" / "SKILL.yaml").read_text()
    )
    base["promotion_target"]["primary"] = {
        "kind": "artifact_store", "path_template": "artifacts/x/",
    }
    rt = ManifestSkillRuntime(
        load_skill_manifest(yaml.safe_dump(base)), orchestrator=MagicMock(),
    )
    with pytest.raises(SkillConfigError, match="artifact_store"):
        rt.promotion_target()


@pytest.mark.asyncio
async def test_api_promoter_for_session_uses_webhook_target(monkeypatch):
    from types import SimpleNamespace

    from src.api import promotion as promotion_module
    from src.core.config_promoter import ConfigPromoter

    class _Store:
        async def get_session(self, research_id):
            return {
                "id": research_id,
                "skill_id": "prompt-engineering",
                "model_type": "prompt-engineering",
            }

    primary = SimpleNamespace(
        kind="registry_api",
        endpoint="http://registry.local/api/v1/prompts",
        auth_secret="PROMPT_REGISTRY_AUTH_TOKEN",
        timeout_s=10.0,
        retries=2,
    )
    manifest = SimpleNamespace(
        promotion_target=SimpleNamespace(primary=primary),
    )

    class _Registry:
        def get(self, skill_id):
            return manifest

    default_promoter = object()
    monkeypatch.setattr(promotion_module, "_promoter", default_promoter)
    monkeypatch.setattr(promotion_module, "_store", _Store())
    monkeypatch.setattr(promotion_module, "_registry", _Registry())

    promoter = await promotion_module._promoter_for_session("res_x")
    assert isinstance(promoter, ConfigPromoter)
    assert isinstance(promoter._target, WebhookPromotionTarget)
    assert promoter._target.endpoint == "http://registry.local/api/v1/prompts"


@pytest.mark.asyncio
async def test_api_promoter_for_session_falls_back_without_endpoint(monkeypatch):
    from types import SimpleNamespace

    from src.api import promotion as promotion_module

    class _Store:
        async def get_session(self, research_id):
            return {"id": research_id, "model_type": "direction"}

    primary = SimpleNamespace(kind="registry_api", endpoint=None)
    manifest = SimpleNamespace(
        promotion_target=SimpleNamespace(primary=primary),
    )

    class _Registry:
        def get(self, skill_id):
            return manifest

    default_promoter = object()
    monkeypatch.setattr(promotion_module, "_promoter", default_promoter)
    monkeypatch.setattr(promotion_module, "_store", _Store())
    monkeypatch.setattr(promotion_module, "_registry", _Registry())
    assert await promotion_module._promoter_for_session("res_x") is default_promoter
