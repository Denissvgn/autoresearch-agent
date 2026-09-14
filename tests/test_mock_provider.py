"""MockProvider + demo-mode routing tests (P0-3).

Covers: the zero-credential scripted loop surface, the ``AUTORESEARCH_DEMO``
selector in ``build_provider``, and the production refusal (fail-closed).
"""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from types import SimpleNamespace

import pytest

from src.core.llm_provider import (
    MockProvider,
    StopReason,
    Usage,
    build_provider,
)


def _settings(demo: bool, environment: str = "development") -> SimpleNamespace:
    return SimpleNamespace(demo_mode=demo, environment=environment)


@pytest.mark.asyncio
async def test_mock_provider_alternates_tool_and_text():
    p = MockProvider()
    first = await p.messages_create(
        model="m", system="s", messages=[], tools=[], max_tokens=10,
    )
    assert first.stop_reason is StopReason.TOOL_USE
    assert first.content and first.content[0].name == "bash"
    second = await p.messages_create(
        model="m", system="s", messages=[], tools=[], max_tokens=10,
    )
    assert second.stop_reason is StopReason.END_TURN


@pytest.mark.asyncio
async def test_mock_provider_complete_and_cost():
    p = MockProvider()
    text = await p.complete(model="m", prompt="hi", max_tokens=10)
    assert "mock" in text.lower()
    assert p.estimate_cost("m", Usage(1000, 1000)) == 0.0


def test_build_provider_demo_mode_routes_to_mock():
    provider = build_provider("anthropic", settings_obj=_settings(demo=True))
    assert type(provider).__name__ == "MockProvider"


def test_build_provider_explicit_mock_id():
    provider = build_provider("mock", settings_obj=_settings(demo=False))
    assert type(provider).__name__ == "MockProvider"


def test_build_provider_refuses_mock_in_production():
    with pytest.raises(ValueError, match="production"):
        build_provider(
            "mock", settings_obj=_settings(demo=False, environment="production")
        )
    with pytest.raises(ValueError, match="production"):
        build_provider(
            "anthropic", settings_obj=_settings(demo=True, environment="prod")
        )


def test_build_provider_without_demo_stays_real():
    provider = build_provider(
        "anthropic",
        settings_obj=SimpleNamespace(
            demo_mode=False,
            environment="development",
            anthropic_base_url="http://anthropic.invalid",
            anthropic_auth_token="test-token",
            anthropic_api_timeout_s=5,
        ),
    )
    assert type(provider).__name__ == "AnthropicProvider"
