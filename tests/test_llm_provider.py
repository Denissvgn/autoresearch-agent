"""Structural / contract tests for the ``LLMProvider`` protocol + types
(ARC-011 P1-001) and the ``AnthropicProvider`` (P1-002).

P1-001 introduced the protocol + normalized value types; P1-002 added the
``AnthropicProvider`` SDK adapter to the same module. These tests pin the
public surface, the R5 ``StopReason`` mapping, and frozen-ness of the value
types. (P1-001's headless-import test is dropped: P1-002 intentionally made
``llm_provider`` depend on ``anthropic`` at module level for the adapter; the
transitive dependency is the same as the pre-refactor orchestrator's direct
``import anthropic``.)
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from src.core.llm_provider import (
    ErrorClass,
    LLMProvider,
    Message,
    ProviderCapabilities,
    ProviderResponse,
    StopReason,
    StreamDelta,
    TextBlock,
    ToolDef,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
)


def test_stop_reason_members_match_r5_contract():
    """``StopReason`` is the R5-critical enum the loop keys off (spike §5).

    A rename/reorder here would silently break phase-continuation when P1-004
    wires the loop to ``StopReason.END_TURN``.
    """
    assert issubclass(StopReason, str)  # (str, Enum) house style
    assert {member.name for member in StopReason} == {
        "END_TURN",
        "TOOL_USE",
        "MAX_TOKENS",
        "STOP_SEQUENCE",
        "OTHER",
    }
    # The loop reads END_TURN.value == "end_turn" (Anthropic native string).
    assert StopReason.END_TURN.value == "end_turn"
    assert StopReason.TOOL_USE.value == "tool_use"
    assert StopReason.MAX_TOKENS.value == "max_tokens"
    assert StopReason.STOP_SEQUENCE.value == "stop_sequence"
    assert StopReason.OTHER.value == "other"


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (Usage, {"input_tokens": 100, "output_tokens": 50}),
        (TextBlock, {"text": "hi"}),
        (ToolUseBlock, {"id": "t1", "name": "bash", "input": {"command": "ls"}}),
        (ToolResultBlock, {"tool_use_id": "t1", "content": "ok"}),
        (Message, {"role": "user", "content": "hello"}),
        (Message, {"role": "assistant", "content": [TextBlock(text="hi")]}),
        (ToolDef, {"name": "bash", "description": "d", "input_schema": {}}),
        (
            ProviderResponse,
            {
                "content": [TextBlock(text="x")],
                "stop_reason": StopReason.END_TURN,
                "usage": Usage(input_tokens=1, output_tokens=1),
                "raw_model": "claude-test",
            },
        ),
        (
            ProviderCapabilities,
            {"native_tool_use": True, "streaming": False,
             "system_prompt": True, "max_context_tokens": 200_000},
        ),
        (ErrorClass, {"transient": True, "status_code": 429, "retry_after_s": 30.0}),
        (StreamDelta, {"text": "partial"}),
        (StreamDelta, {}),  # all defaults
    ],
)
def test_value_types_are_frozen_and_construct_correctly(cls, kwargs):
    """Every value type is a frozen dataclass with the documented fields."""
    assert is_dataclass(cls)
    instance = cls(**kwargs)
    for key, value in kwargs.items():
        assert getattr(instance, key) == value
    # Frozen-ness is part of the contract: providers must not mutate a
    # ProviderResponse/Usage/etc. in place.
    first_field = fields(cls)[0].name
    with pytest.raises(FrozenInstanceError):
        setattr(instance, first_field, getattr(instance, first_field))


def test_minimal_provider_satisfies_protocol():
    """Executable documentation of the contract (signature-drift guard).

    Not ``isinstance`` (the protocol is not ``@runtime_checkable``); instead we
    assert a minimal concrete implementation exposes every member with the
    expected runtime shape (awaitables / async-generator / sync methods).
    """

    class _MinimalProvider:
        name = "test"

        async def messages_create(
            self, *, model, system, messages, tools, max_tokens,
            temperature=None, stop_sequences=None,
        ) -> ProviderResponse:
            return ProviderResponse(
                content=[TextBlock(text="ok")],
                stop_reason=StopReason.END_TURN,
                usage=Usage(input_tokens=1, output_tokens=1),
                raw_model=model,
            )

        async def complete(
            self, *, model, prompt, max_tokens, system=None,
        ) -> str:
            return "ok"

        async def stream(self, **kwargs):
            yield StreamDelta(text="chunk")

        def estimate_cost(self, model: str, usage: Usage) -> float:
            return 0.0

        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(
                native_tool_use=True, streaming=False,
                system_prompt=True, max_context_tokens=1,
            )

        def classify_error(self, exc: Exception) -> ErrorClass:
            return ErrorClass(transient=False, status_code=None, retry_after_s=None)

    provider: LLMProvider = _MinimalProvider()  # typing-time assignment
    assert provider.name == "test"

    assert inspect.iscoroutinefunction(provider.messages_create)
    assert inspect.iscoroutinefunction(provider.complete)
    assert inspect.isasyncgenfunction(provider.stream)
    for method_name in ("estimate_cost", "capabilities", "classify_error"):
        assert callable(getattr(provider, method_name)), method_name

    # classify_error returns the documented value type (the loop reads
    # ErrorClass.transient to decide retry).
    classification = provider.classify_error(RuntimeError("x"))
    assert isinstance(classification, ErrorClass)
    assert classification.transient is False
