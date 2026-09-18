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
async def test_mock_provider_relays_governed_eval_marker(monkeypatch):
    """ARC-012 P7-011: after a governed eval prints its iteration marker, the
    next mock response relays that exact line alongside a fresh eval call
    (the marker-relay contract: backed by a run in the same turn, verbatim —
    the mock invents no metrics)."""
    from src.core.llm_provider import Message, TextBlock, ToolResultBlock, ToolUseBlock

    marker = (
        'ITERATION_RESULT: {"status":"completed","primary_metric":0.5,'
        '"server_nonce":"ab"}'
    )
    messages = [
        Message(role="assistant", content=[
            ToolUseBlock(id="t1", name="bash", input={"command": "eval"}),
        ]),
        Message(role="user", content=[
            ToolResultBlock(tool_use_id="t1", content=f"noise\n{marker}\n"),
        ]),
    ]
    p = MockProvider(eval_command="the eval command")
    response = await p.messages_create(
        model="m", system="s", messages=messages, tools=[], max_tokens=10,
    )
    text = next(b for b in response.content if isinstance(b, TextBlock))
    tool = next(b for b in response.content if isinstance(b, ToolUseBlock))
    assert marker in text.text, "the marker must be relayed verbatim"
    assert tool.input["command"] == "the eval command"
    assert response.stop_reason is StopReason.TOOL_USE


@pytest.mark.asyncio
async def test_mock_provider_relay_only_from_newest_tool_result(monkeypatch):
    """Only the most recent tool result is scanned — a stale marker from an
    earlier eval must not be re-relayed after newer tool output."""
    from src.core.llm_provider import Message, TextBlock, ToolResultBlock, ToolUseBlock

    stale = 'ITERATION_RESULT: {"status":"completed","primary_metric":0.9}'
    messages = [
        Message(role="assistant", content=[
            ToolUseBlock(id="t1", name="bash", input={"command": "eval"}),
        ]),
        Message(role="user", content=[ToolResultBlock(tool_use_id="t1", content=stale)]),
        Message(role="assistant", content=[
            ToolUseBlock(id="t2", name="bash", input={"command": "cp a b"}),
        ]),
        Message(role="user", content=[ToolResultBlock(tool_use_id="t2", content="ok")]),
    ]
    p = MockProvider()
    response = await p.messages_create(
        model="m", system="s", messages=messages, tools=[], max_tokens=10,
    )
    texts = [
        block for block in response.content if isinstance(block, TextBlock)
    ]
    assert all("ITERATION_RESULT" not in t.text for t in texts), (
        "a stale marker behind newer tool output must not be relayed"
    )


@pytest.mark.asyncio
async def test_mock_provider_honors_custom_marker_prefix(monkeypatch):
    from src.core.llm_provider import Message, TextBlock, ToolResultBlock, ToolUseBlock

    marker = 'RESULT-MARKER: {"status":"completed"}'
    messages = [
        Message(role="assistant", content=[
            ToolUseBlock(id="t1", name="bash", input={"command": "eval"}),
        ]),
        Message(role="user", content=[
            ToolResultBlock(tool_use_id="t1", content=marker),
        ]),
    ]
    p = MockProvider(marker_prefix="RESULT-MARKER:")
    response = await p.messages_create(
        model="m", system="s", messages=messages, tools=[], max_tokens=10,
    )
    text = next(b for b in response.content if isinstance(b, TextBlock))
    assert marker in text.text


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
