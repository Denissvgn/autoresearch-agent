"""P4-011 — Cross-provider parity tests for ``OpenAIProvider`` (ARC-011 R4/R5).

Pins the Chat Completions wire translation and the R5 stop-reason invariant.
Mirrors ``test_anthropic_provider.py`` (P1-002) in structure.
"""
from __future__ import annotations

import json
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    import openai  # noqa: F401
except ModuleNotFoundError:
    sys.modules["openai"] = types.SimpleNamespace(
        AsyncOpenAI=MagicMock(return_value=MagicMock()),
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )

from src.core.llm_provider import (
    Message,
    OpenAIProvider,
    ProviderCapabilities,
    StopReason,
    TextBlock,
    ToolDef,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
    _from_openai_response,
    _to_openai_messages,
    _to_openai_tools,
)


def _oai_tool_call(tc_id: str, name: str, arguments: str) -> Any:
    return types.SimpleNamespace(
        id=tc_id,
        type="function",
        function=types.SimpleNamespace(name=name, arguments=arguments),
    )


def _oai_response(
    *,
    content=None,
    tool_calls=None,
    finish_reason="stop",
    model="gpt-4o",
    prompt_tokens=10,
    completion_tokens=5,
) -> Any:
    return types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(content=content, tool_calls=tool_calls or []),
                finish_reason=finish_reason,
            )
        ],
        model=model,
        usage=types.SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
    )


def _make_provider() -> OpenAIProvider:
    provider = OpenAIProvider(base_url="http://openai.invalid", api_key="k", timeout_s=10.0)
    # Override the openai module ref with a stub so classify_error's isinstance
    # checks use simple exception types (the real SDK's APIStatusError requires
    # response/body kwargs). The client itself is replaced below.
    provider._openai_mod = types.SimpleNamespace(
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    provider._client.chat.completions.create = AsyncMock()  # type: ignore[assignment]
    return provider


class TestToOpenAIMessages:
    def test_system_injected(self):
        msgs = _to_openai_messages([Message(role="user", content="hi")], "sys")
        assert msgs[0] == {"role": "system", "content": "sys"}
        assert msgs[1] == {"role": "user", "content": "hi"}

    def test_empty_system_omitted(self):
        assert _to_openai_messages([Message(role="user", content="hi")], "") == [
            {"role": "user", "content": "hi"}
        ]

    def test_assistant_with_tool_use(self):
        msgs = _to_openai_messages(
            [
                Message(
                    role="assistant",
                    content=[
                        TextBlock(text="thinking"),
                        ToolUseBlock(id="t1", name="bash", input={"command": "ls"}),
                    ],
                )
            ],
            "",
        )
        assert msgs[0]["content"] == "thinking"
        assert msgs[0]["tool_calls"][0]["function"]["name"] == "bash"
        assert json.loads(msgs[0]["tool_calls"][0]["function"]["arguments"]) == {"command": "ls"}

    def test_tool_result_becomes_tool_message(self):
        msgs = _to_openai_messages(
            [Message(role="user", content=[ToolResultBlock(tool_use_id="t1", content="ok")])],
            "",
        )
        assert msgs == [{"role": "tool", "tool_call_id": "t1", "content": "ok"}]


class TestToOpenAITools:
    def test_tool_wrapping(self):
        result = _to_openai_tools(
            [ToolDef(name="bash", description="cmd", input_schema={"type": "object"})]
        )
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "bash"


class TestFromOpenAIResponse:
    def test_text_only_end_turn(self):
        resp = _from_openai_response(_oai_response(content="hello", finish_reason="stop"))
        assert resp.stop_reason == StopReason.END_TURN
        assert resp.content == [TextBlock(text="hello")]

    def test_r5_tool_calls_force_tool_use(self):
        raw = _oai_response(
            tool_calls=[_oai_tool_call("t1", "bash", '{"command": "ls"}')],
            finish_reason="stop",
        )
        resp = _from_openai_response(raw)
        assert resp.stop_reason == StopReason.TOOL_USE
        assert isinstance(resp.content[0], ToolUseBlock)
        assert resp.content[0].input == {"command": "ls"}

    def test_length_finish_reason(self):
        assert (
            _from_openai_response(_oai_response(content="x", finish_reason="length")).stop_reason
            == StopReason.MAX_TOKENS
        )

    def test_malformed_json_degrades(self):
        raw = _oai_response(
            tool_calls=[_oai_tool_call("t1", "bash", "not-json")], finish_reason="tool_calls"
        )
        assert _from_openai_response(raw).content[0].input == {}

    def test_empty_choices(self):
        raw = types.SimpleNamespace(choices=[], model="gpt-4o", usage=None)
        assert _from_openai_response(raw).stop_reason == StopReason.OTHER


class TestMessagesCreate:
    @pytest.mark.asyncio
    async def test_end_to_end(self):
        provider = _make_provider()
        provider._client.chat.completions.create = AsyncMock(
            return_value=_oai_response(content="result", finish_reason="stop")
        )
        resp = await provider.messages_create(
            model="gpt-4o",
            system="sys",
            messages=[Message(role="user", content="hi")],
            tools=[ToolDef(name="bash", description="cmd", input_schema={"type": "object"})],
            max_tokens=100,
        )
        assert resp.stop_reason == StopReason.END_TURN
        kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["tools"][0]["type"] == "function"


class TestComplete:
    @pytest.mark.asyncio
    async def test_one_shot(self):
        provider = _make_provider()
        provider._client.chat.completions.create = AsyncMock(
            return_value=_oai_response(content="insights", finish_reason="stop")
        )
        assert (
            await provider.complete(model="gpt-4o-mini", prompt="sum", max_tokens=300) == "insights"
        )


class TestClassifyError:
    def test_timeout_transient(self):
        p = _make_provider()
        assert p.classify_error(p._openai_mod.APITimeoutError("t")).transient is True

    def test_rate_limit_transient(self):
        p = _make_provider()
        exc = p._openai_mod.APIStatusError("rl")
        exc.status_code = 429
        err = p.classify_error(exc)
        assert err.transient is True and err.status_code == 429

    def test_client_error_not_transient(self):
        p = _make_provider()
        exc = p._openai_mod.APIStatusError("br")
        exc.status_code = 400
        assert p.classify_error(exc).transient is False

    def test_generic_not_transient(self):
        assert _make_provider().classify_error(ValueError("x")).transient is False


class TestEstimateCost:
    def test_known_model(self):
        cost = _make_provider().estimate_cost("gpt-4o", Usage(input_tokens=1000, output_tokens=500))
        expected = 1000 * 5.0 / 1_000_000 + 500 * 15.0 / 1_000_000
        assert abs(cost - expected) < 1e-9

    def test_default_model(self):
        cost = _make_provider().estimate_cost(
            "unknown", Usage(input_tokens=1000, output_tokens=500)
        )
        expected = 1000 * 5.0 / 1_000_000 + 500 * 15.0 / 1_000_000
        assert abs(cost - expected) < 1e-9


class TestCapabilities:
    def test_caps(self):
        caps = _make_provider().capabilities()
        assert caps.native_tool_use is True
        assert caps.system_prompt is True
        assert caps.streaming is False
        assert caps.max_context_tokens == 128_000


class TestBuildProvider:
    def test_unknown_raises(self):
        from src.core.llm_provider import build_provider

        with pytest.raises(ValueError, match="unknown LLM provider"):
            build_provider("gemini", settings_obj=MagicMock())

    def test_openai_construction(self):
        from src.core.llm_provider import build_provider

        stub = types.SimpleNamespace(
            openai_base_url="http://oai.invalid",
            openai_api_key=None,
            openai_api_timeout_s=30,
        )
        provider = build_provider("openai", settings_obj=stub)
        assert isinstance(provider, OpenAIProvider)
        assert provider.name == "openai"
