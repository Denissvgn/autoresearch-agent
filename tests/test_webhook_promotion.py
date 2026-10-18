"""Webhook promotion target tests (P1-3).

Covers: local provenance writes + endpoint delivery on the primary path only,
idempotency key + bearer auth, retry-then-fail-closed behavior, manifest
schema acceptance of ``kind: webhook``, runtime wiring for webhook and
registry_api kinds, and the API-layer per-session promoter selection.

ARC-012 P7-014 adds the non-ML promotion e2e through the single target
resolution site (``_promoter_for_session`` → ``promotion_target_from_manifest``):
a ``registry_api`` skill delivers to its declared endpoint (mock transport)
and records the durable ``target_descriptor``; a ``file_path`` skill writes
to its declared ``path_template``.
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
        load_skill_manifest(yaml.safe_dump(base)), host=MagicMock(),
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
        load_skill_manifest(yaml.safe_dump(base)), host=MagicMock(),
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

    promoter, skill_id = await promotion_module._promoter_for_session("res_x")
    assert isinstance(promoter, ConfigPromoter)
    assert isinstance(promoter._target, WebhookPromotionTarget)
    assert promoter._target.endpoint == "http://registry.local/api/v1/prompts"
    # ARC-012 P7-011: the session-resolved skill id rides along for
    # target_kind injection (non-ML sessions carry model_type="").
    assert skill_id == "prompt-engineering"


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
    promoter, skill_id = await promotion_module._promoter_for_session("res_x")
    assert promoter is default_promoter
    # The legacy-trio session resolves to the translated ml-* id even on the
    # fallback path (target_kind still injects from the manifest).
    assert skill_id == "ml-direction"


# ============================================================================
# ARC-012 P7-014 — non-ML promotion e2e through the API resolution site
# ============================================================================


async def _seed_completed_skill_session(
    store,
    tmp_path: Path,
    *,
    skill_id: str,
    metrics: dict,
) -> str:
    """Seed a completed non-ML session with a gates-passing best iteration
    carrying a config snapshot — the minimum a preview/confirm needs."""
    research_id = f"res_{skill_id.split('-')[0]}714"
    await store.create_session(
        session_id=research_id,
        instrument="default",
        timeframe="production",
        model_type="",
        skill_id=skill_id,
        subject_id="default",
        variant="production",
        tag="p7-014",
        quick_mode=False,
        max_iterations=1,
        max_budget_usd=5.0,
        focus_hint=None,
        workspace_path=str(tmp_path / "ws" / skill_id),
    )
    await store.add_iteration(
        research_id=research_id,
        iteration=1,
        primary_metric=metrics.get("primary_metric", 0.8),
        metric_name=metrics.get("metric_name", "composite_eval_score"),
        all_gates_passed=1,
        decision="keep",
        description="seeded gates-passing winner",
        config_snapshot=metrics["config_snapshot"],
        metrics_json=json.dumps({
            key: value for key, value in metrics.items()
            if key != "config_snapshot"
        }),
        training_time_s=1.0,
        api_cost_usd=0.0,
    )
    await store.update_session(research_id, status="completed", best_iteration=1)
    return research_id


@pytest.mark.asyncio
async def test_registry_api_skill_confirm_delivers_and_records_descriptor(
    monkeypatch, tmp_path,
):
    """P7-014 AC: a ``registry_api`` skill (prompt-engineering) promotes
    through the API resolution site — confirm delivers the best config to the
    skill's declared register endpoint (mock transport) and records the
    durable ``target_descriptor``."""
    from src.api import promotion as promotion_module
    from src.config import settings
    from src.core.results_store import ResultsStore
    from src.core.skill_registry import SkillRegistry

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"prompt_id": "p_714"})

    _patch_mock_transport(monkeypatch, handler)
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "ws"))
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "configs"))

    store = ResultsStore(str(tmp_path / "p714.sqlite"))
    await store.initialize()
    research_id = await _seed_completed_skill_session(
        store, tmp_path, skill_id="prompt-engineering",
        metrics={
            "primary_metric": 0.8,
            "metric_name": "composite_eval_score",
            "status": "completed",
            "passes_min_precision": True,
            "within_cost_budget": True,
            "training_gates_passed": True,
            "n_eval_examples": 2,
            "config_snapshot": "prompt: seeded winner\n",
        },
    )
    registry = SkillRegistry()
    registry.discover()
    monkeypatch.setattr(promotion_module, "_store", store)
    monkeypatch.setattr(promotion_module, "_registry", registry)

    promoter, skill_id = await promotion_module._promoter_for_session(research_id)
    assert skill_id == "prompt-engineering"
    preview = await promoter.preview(research_id, scope="development")
    assert preview["target_identity"]

    result = await promoter.confirm(research_id, scope="development")

    # Delivery: exactly one POST to the declared register endpoint.
    assert len(seen) == 1, seen
    assert str(seen[0].url) == "http://prompt-registry.local/api/v1/prompts"
    body = json.loads(seen[0].read())
    assert body["config"] == "prompt: seeded winner\n"

    # The durable promotion record carries the target descriptor.
    promotions = [
        row for row in await store.list_promotions()
        if row.get("research_id") == research_id
    ]
    assert promotions, "confirm must record the promotion"
    descriptor = promotions[0]["promotion_metadata"]["target_descriptor"]
    assert descriptor["kind"] == "webhook"
    assert descriptor["endpoint"] == "http://prompt-registry.local/api/v1/prompts"
    # The API layer's target_kind injection (P7-011) reports the skill's
    # declared kind, not the transport kind.
    injected = promotion_module._inject_target_kind(result, skill_id=skill_id)
    assert injected["target_kind"] == "registry_api"


@pytest.mark.asyncio
async def test_file_path_skill_confirm_writes_declared_template(
    monkeypatch, tmp_path,
):
    """P7-014 AC: a ``file_path`` skill (code-refactor) promotes to its
    declared ``path_template`` under the host-configs root — not the legacy
    ML layout."""
    from src.api import promotion as promotion_module
    from src.config import settings
    from src.core.results_store import ResultsStore
    from src.core.skill_registry import SkillRegistry

    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "ws"))
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "configs"))

    store = ResultsStore(str(tmp_path / "p714b.sqlite"))
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
            "config_snapshot": "def target():\n    return 42\n",
        },
    )
    registry = SkillRegistry()
    registry.discover()
    monkeypatch.setattr(promotion_module, "_store", store)
    monkeypatch.setattr(promotion_module, "_registry", registry)

    promoter, skill_id = await promotion_module._promoter_for_session(research_id)
    assert skill_id == "code-refactor"
    preview = await promoter.preview(research_id, scope="development")
    assert preview["target_path"].endswith(
        "configs/code-refactor/default_production.py"
    ), preview["target_path"]

    await promoter.confirm(research_id, scope="development")

    # The template renders relative to the host-configs root.
    written = next(iter((tmp_path / "configs").rglob("default_production.py")))
    assert written.read_text(encoding="utf-8") == "def target():\n    return 42\n"
    assert written.relative_to(tmp_path / "configs").as_posix() == (
        "configs/code-refactor/default_production.py"
    )
