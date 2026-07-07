"""Unit tests for ``AnthropicProvider`` — the SDK boundary translator
(ARC-011 P1-002).

The provider is a thin adapter: normalized ``Message``/``ToolDef``/``system``
→ Anthropic ``messages.create`` kwargs (byte-identical to the pre-refactor
orchestrator call), and raw ``anthropic.types.Message`` → normalized
``ProviderResponse``. These tests pin the translation + the R5 stop-reason
invariant + ``classify_error`` (which backs loop-owned retry), using a fake
``AsyncAnthropic`` whose ``messages.create`` returns a canned raw response.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub the Anthropic SDK so the module imports without a real install. The
# provider only touches: AsyncAnthropic (ctor), APITimeoutError,
# APIConnectionError, InternalServerError, APIStatusError.
try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=MagicMock(return_value=MagicMock()),
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )

from src.core.llm_provider import (
    _CLAUDE_INPUT_USD_PER_TOKEN,
    _CLAUDE_OUTPUT_USD_PER_TOKEN,
    AnthropicProvider,
    ErrorClass,
    Message,
    StopReason,
    TextBlock,
    ToolDef,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
    _to_sdk_messages,
    _to_sdk_tools,
)

# ── helpers ────────────────────────────────────────────────────────────────


def _raw_block(block_type: str, **fields: Any) -> Any:
    """A fake SDK content block (attribute-access, like anthropic.types)."""
    return types.SimpleNamespace(type=block_type, **fields)


def _raw_response(
    *, content: list[Any], stop_reason: str, model: str = "claude-test",
    input_tokens: int = 10, output_tokens: int = 5,
) -> Any:
    return types.SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=types.SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens,
        ),
    )


def _make_provider() -> AnthropicProvider:
    """A provider whose client.messages.create is an AsyncMock to be configured."""
    provider = AnthropicProvider(
        base_url="http://anthropic.invalid", api_key="test-key", timeout_s=10.0,
    )
    provider._client.messages.create = AsyncMock()  # type: ignore[assignment]
    return provider


# ── _to_sdk_messages ───────────────────────────────────────────────────────


def test_to_sdk_messages_str_content():
    """A plain-string user prompt maps to the Anthropic string-content shape."""
    msgs = [Message(role="user", content="hello")]
    assert _to_sdk_messages(msgs) == [{"role": "user", "content": "hello"}]


def test_to_sdk_messages_mixed_blocks():
    """Assistant + tool-result turns map to lists of Anthropic block dicts."""
    msgs = [
        Message(role="assistant", content=[TextBlock(text="hi")]),
        Message(role="user", content=[
            ToolResultBlock(tool_use_id="t1", content="ok"),
            TextBlock(text="note"),
        ]),
    ]
    assert _to_sdk_messages(msgs) == [
        {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
            {"type": "text", "text": "note"},
        ]},
    ]


def test_to_sdk_messages_tool_use_block():
    """A tool_use request block maps to the Anthropic tool_use dict shape."""
    msgs = [Message(role="assistant", content=[
        ToolUseBlock(id="t1", name="bash", input={"command": "ls"}),
    ])]
    assert _to_sdk_messages(msgs) == [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls"}},
        ]},
    ]


# ── _to_sdk_tools ──────────────────────────────────────────────────────────


def test_to_sdk_tools_matches_agent_tools_shape():
    """ToolDef maps to the {name, description, input_schema} dicts AGENT_TOOLS used."""
    tools = [ToolDef(name="bash", description="d", input_schema={"type": "object"})]
    assert _to_sdk_tools(tools) == [
        {"name": "bash", "description": "d", "input_schema": {"type": "object"}},
    ]


# ── messages_create + _from_sdk_response ───────────────────────────────────


@pytest.mark.asyncio
async def test_messages_create_maps_text_and_tool_use_blocks():
    provider = _make_provider()
    provider._client.messages.create.return_value = _raw_response(
        content=[
            _raw_block("text", text="thinking"),
            _raw_block("tool_use", id="t1", name="bash", input={"command": "ls"}),
        ],
        stop_reason="tool_use",
    )

    resp = await provider.messages_create(
        model="claude-test", system="sys",
        messages=[Message(role="user", content="hi")],
        tools=[ToolDef(name="bash", description="d", input_schema={})],
        max_tokens=100,
    )

    # Text + tool_use blocks normalized to TextBlock / ToolUseBlock.
    assert isinstance(resp.content[0], TextBlock)
    assert resp.content[0].text == "thinking"
    assert isinstance(resp.content[1], ToolUseBlock)
    assert resp.content[1].id == "t1"
    assert resp.content[1].input == {"command": "ls"}
    # Usage + raw_model propagated.
    assert resp.usage == Usage(input_tokens=10, output_tokens=5)
    assert resp.raw_model == "claude-test"
    # The SDK call received the translated wire format.
    call_kwargs = provider._client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "sys"
    assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert call_kwargs["max_tokens"] == 100


@pytest.mark.asyncio
async def test_messages_create_r5_invariant_tool_use_overrides_end_turn():
    """R5: a tool_use block forces StopReason.TOOL_USE even if native says end_turn.

    This is the Gemini-quirk defense (Gemini reports STOP with function calls
    present); AnthropicProvider enforces it for all providers.
    """
    provider = _make_provider()
    provider._client.messages.create.return_value = _raw_response(
        content=[_raw_block("tool_use", id="t1", name="bash", input={})],
        stop_reason="end_turn",  # native says end_turn…
    )
    resp = await provider.messages_create(
        model="m", system="s", messages=[Message(role="user", content="x")],
        tools=[], max_tokens=10,
    )
    assert resp.stop_reason == StopReason.TOOL_USE  # …but tool_use wins


@pytest.mark.asyncio
async def test_messages_create_stop_reason_mapping_without_tool_use():
    provider = _make_provider()
    provider._client.messages.create.return_value = _raw_response(
        content=[_raw_block("text", text="done")],
        stop_reason="end_turn",
    )
    resp = await provider.messages_create(
        model="m", system="s", messages=[Message(role="user", content="x")],
        tools=[], max_tokens=10,
    )
    assert resp.stop_reason == StopReason.END_TURN


@pytest.mark.asyncio
async def test_messages_create_unknown_stop_reason_maps_to_other():
    provider = _make_provider()
    provider._client.messages.create.return_value = _raw_response(
        content=[_raw_block("text", text="x")],
        stop_reason="pause_turn",  # anthropic SDK 0.52 addition
    )
    resp = await provider.messages_create(
        model="m", system="s", messages=[Message(role="user", content="x")],
        tools=[], max_tokens=10,
    )
    assert resp.stop_reason == StopReason.OTHER


@pytest.mark.asyncio
async def test_messages_create_omits_unset_temperature_and_stop_sequences():
    """The orchestrator never sets temperature/stop_sequences; the wire request
    must omit them to stay byte-identical to the pre-refactor call."""
    provider = _make_provider()
    provider._client.messages.create.return_value = _raw_response(
        content=[_raw_block("text", text="x")], stop_reason="end_turn",
    )
    await provider.messages_create(
        model="m", system="s", messages=[Message(role="user", content="x")],
        tools=[], max_tokens=10,
    )
    call_kwargs = provider._client.messages.create.call_args.kwargs
    assert "temperature" not in call_kwargs
    assert "stop_sequences" not in call_kwargs


# ── complete ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_returns_joined_text():
    provider = _make_provider()
    provider._client.messages.create.return_value = _raw_response(
        content=[
            _raw_block("text", text="bullet 1"),
            _raw_block("text", text="bullet 2"),
        ],
        stop_reason="end_turn",
    )
    result = await provider.complete(model="haiku", prompt="p", max_tokens=300)
    assert result == "bullet 1bullet 2"
    call_kwargs = provider._client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "haiku"
    assert call_kwargs["max_tokens"] == 300
    # No tools, no system (orchestrator's insights call sets neither).
    assert "tools" not in call_kwargs
    assert "system" not in call_kwargs


@pytest.mark.asyncio
async def test_complete_passes_system_when_provided():
    provider = _make_provider()
    provider._client.messages.create.return_value = _raw_response(
        content=[_raw_block("text", text="x")], stop_reason="end_turn",
    )
    await provider.complete(model="m", prompt="p", max_tokens=10, system="sys")
    assert provider._client.messages.create.call_args.kwargs["system"] == "sys"


# ── classify_error ─────────────────────────────────────────────────────────


def _instance_without_init(cls: type, **attrs: Any) -> Any:
    """Construct an exception instance bypassing __init__ (sets attributes after).

    The real anthropic SDK's exception constructors require httpx.Request /
    httpx.Response objects we don't want to fabricate; classify_error only
    inspects isinstance + .status_code, so __new__ + attribute set is enough
    and is robust across SDK versions.
    """
    instance = cls.__new__(cls)
    for key, value in attrs.items():
        setattr(instance, key, value)
    return instance


def _status_error(status_code: int) -> Exception:
    import anthropic

    return _instance_without_init(anthropic.APIStatusError, status_code=status_code)


def test_classify_error_transient_connection_exceptions():
    """APITimeout/APIConnection/InternalServer are transient (no status code)."""
    import anthropic

    provider = AnthropicProvider(
        base_url="http://x", api_key="k", timeout_s=1.0,
    )
    for exc_cls in (
        anthropic.APITimeoutError, anthropic.APIConnectionError,
        anthropic.InternalServerError,
    ):
        exc = _instance_without_init(exc_cls)
        err = provider.classify_error(exc)
        assert err.transient is True
        assert err.status_code is None


def test_classify_error_transient_status_codes():
    """429/502/503/529 are transient; other statuses are not."""
    provider = AnthropicProvider(base_url="http://x", api_key="k", timeout_s=1.0)
    for code in (429, 502, 503, 529):
        err = provider.classify_error(_status_error(code))
        assert err.transient is True, f"HTTP {code} should be transient"
        assert err.status_code == code


def test_classify_error_non_transient_status_code():
    provider = AnthropicProvider(base_url="http://x", api_key="k", timeout_s=1.0)
    err = provider.classify_error(_status_error(400))
    assert err.transient is False
    assert err.status_code == 400


def test_classify_error_non_anthropic_exception_is_not_transient():
    provider = AnthropicProvider(base_url="http://x", api_key="k", timeout_s=1.0)
    err = provider.classify_error(RuntimeError("unrecoverable"))
    assert err.transient is False


# ── estimate_cost ──────────────────────────────────────────────────────────


def test_estimate_cost_flat_sonnet_baseline():
    """Cost = input*$3/M + output*$15/M (parity with pre-refactor accounting)."""
    provider = AnthropicProvider(base_url="http://x", api_key="k", timeout_s=1.0)
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    cost = provider.estimate_cost("claude-test", usage)
    assert cost == pytest.approx(
        1_000_000 * _CLAUDE_INPUT_USD_PER_TOKEN
        + 1_000_000 * _CLAUDE_OUTPUT_USD_PER_TOKEN
    )
