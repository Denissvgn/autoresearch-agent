"""``LLMProvider`` protocol + normalized value types + ``AnthropicProvider``
(ARC-011 P1-001 / P1-002).

This module adopts the X-005 LLM-provider normalization spike §4 *verbatim*
(``docs/adr/ARC-011-llm-provider-spike.md``) as the canonical contract every
provider implementation must satisfy: ``messages_create`` (main agentic path),
``complete`` (one-shot insights/Haiku path), an optional ``stream``,
``estimate_cost`` (→ P1-003), ``capabilities`` (→ P4-009 / router P4-010), and
``classify_error`` (→ loop-owned retry, R4).

P1-002 extracts ``AnthropicProvider`` — the 1:1 SDK adapter — into this module.
The orchestrator (P1-002) consumes ``ProviderResponse`` (normalized
``StopReason``/``ContentBlock``/``Usage``) and holds its conversation as
``list[Message]``. The provider translates at the SDK boundary only, so the
Anthropic wire format is byte-identical to pre-refactor and the X-002 parity
suite is preserved.

Design decisions recorded by the spike and baked in here:

* **Anthropic-shaped normalized types** (spike §4 note). ``ToolUseBlock.input``
  is a ``dict`` (Anthropic shape; OpenAI's JSON-string ``function.arguments``
  is parsed by the provider), ``ToolResultBlock`` is the Anthropic tool-result
  block, and ``ToolDef`` matches the ``AGENT_TOOLS`` shape. This keeps
  ``AnthropicProvider`` a 1:1 wrapper and preserves the parity suite.
* **Loop-owned retry (R4 / D-retry).** The protocol exposes
  ``classify_error``; the loop owns backoff + the budget-aware skip
  (``orchestrator.py`` ``_call_llm_with_retry``). ``ErrorClass.transient`` is
  the signal. Retry does NOT live in the provider — the budget-aware skip
  depends on session wall-clock state (``remaining_budget_s``), which is loop
  policy, not provider state.
* **Phase-contract enforcement is loop-level (R5 / §5).** The provider surfaces
  a normalized ``StopReason``; the loop reads ``StopReason.END_TURN`` to trigger
  phase continuation. The defensive invariant *"tool calls present ⇒
  TOOL_USE, regardless of the native finish_reason"* (Gemini can report
  ``STOP`` with function calls present) is the provider's responsibility —
  enforced in ``AnthropicProvider._from_sdk_response``.
* **Not ``@runtime_checkable``.** ``isinstance`` against a ``Protocol`` only
  checks attribute presence (false confidence on signatures). This is a
  typing-time contract; consumers accept it as a typed parameter.

Three places where the spike §4 draft was incomplete (resolved in P1-001, the
only deviations from a literal copy — see inline comments):

1. The draft references ``ContentBlock`` (in ``ProviderResponse.content``) and
   ``StreamDelta`` (in ``stream()``) without defining them.
2. The draft's ``Message{role, content: list[Block]}`` does not match the live
   orchestrator, which builds messages with ``content: str`` (user prompts) and
   ``content: list[block]`` (assistant / tool-result turns).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional, Protocol

import anthropic
import httpx

logger = logging.getLogger(__name__)

# Claude pricing constants (Sonnet 3.5 baseline) — moved here from
# ``orchestrator.py`` (P1-002). Referenced by ``AnthropicProvider.estimate_cost``
# and by the orchestrator's pre-spend budget gate + post-call accounting. The
# flat-rate model ignores cache tokens (parity with pre-refactor; per-model
# pricing is P1-003).
_CLAUDE_INPUT_USD_PER_TOKEN = 3.0 / 1_000_000
_CLAUDE_OUTPUT_USD_PER_TOKEN = 15.0 / 1_000_000
_CLAUDE_MAX_OUTPUT_TOKENS = 8192


def estimate_session_cost(
    *,
    iterations: int,
    quick_mode: bool = False,
    input_rate: float = _CLAUDE_INPUT_USD_PER_TOKEN,
    output_rate: float = _CLAUDE_OUTPUT_USD_PER_TOKEN,
) -> dict[str, float | bool | dict[str, float | int]]:
    """Expected USD cost of one research session (P2 ops — one estimator
    shared by the API, the UI preview, and operators).

    Expected-value model, deliberately NOT the worst-case math of the
    orchestrator's pre-spend gate (that one budgets a full max-output turn at
    a 32k-input proxy so a session can never overspend; this one answers
    "what will it roughly cost"): ~3 LLM calls per iteration (propose,
    relay, occasional summary) at a session-average input size — 8k tokens
    quick mode, 24k full — and ~1.5k output tokens per call. Same flat
    Sonnet-baseline rates the post-call accounting uses, so the estimate and
    the ledger agree on pricing.
    """
    calls_per_iteration = 3
    input_tokens_per_call = 8_000 if quick_mode else 24_000
    output_tokens_per_call = 1_500
    per_iteration = calls_per_iteration * (
        input_tokens_per_call * input_rate
        + output_tokens_per_call * output_rate
    )
    total = per_iteration * max(0, iterations)
    return {
        "per_iteration_usd": round(per_iteration, 4),
        "total_usd": round(total, 2),
        "assumptions": {
            "calls_per_iteration": calls_per_iteration,
            "input_tokens_per_call": input_tokens_per_call,
            "output_tokens_per_call": output_tokens_per_call,
            "input_usd_per_mtok": input_rate * 1_000_000,
            "output_usd_per_mtok": output_rate * 1_000_000,
        },
    }

# HTTP status codes the pre-refactor ``_call_claude_with_retry`` treated as
# transient (rate-limit / overloaded / bad-gateway family). Used by
# ``AnthropicProvider.classify_error``.
_TRANSIENT_STATUS_CODES = frozenset({429, 502, 503, 529})


class StopReason(str, Enum):
    """Normalized reason the model stopped generating (R5-critical).

    Provider mapping (spike §3.3 / §5):

    * Anthropic ``end_turn`` / OpenAI ``stop`` / Gemini ``STOP`` → ``END_TURN``
    * ``tool_use`` / OpenAI ``tool_calls`` / function-calls-present → ``TOOL_USE``
    * ``max_tokens`` / OpenAI ``length`` / Gemini ``MAX_TOKENS`` → ``MAX_TOKENS``
    * ``stop_sequence`` → ``STOP_SEQUENCE``
    * anything else (``pause_turn``, ``refusal``, ``content_filter``, …) → ``OTHER``

    R5 invariant: a provider MUST return ``TOOL_USE`` whenever the response
    carries tool/function calls, even if the native ``finish_reason`` says
    ``STOP`` (Gemini quirk). The loop keys off ``END_TURN`` for phase
    continuation (``orchestrator.py`` ``run``).
    """

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    OTHER = "other"


@dataclass(frozen=True)
class Usage:
    """Token accounting for one provider call (spike §3.6).

    ``cache_read_tokens`` / ``cache_write_tokens`` default to 0 and are unused
    today (the orchestrator reads only input/output, ``orchestrator.py``
    ``run``); additive so P1-003 can capture cache-aware cost without breaking
    parity.
    """

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class TextBlock:
    """A text content block emitted by the model."""

    text: str


@dataclass(frozen=True)
class ToolUseBlock:
    """A tool-call request emitted by the model (Anthropic-shaped).

    ``input`` is a ``dict``; OpenAI's JSON-string ``function.arguments`` is
    parsed to a dict by the provider (malformed JSON fails closed as a tool
    error, never crashing the loop).
    """

    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolResultBlock:
    """A tool result fed back to the model by the loop (request-side block).

    Matches the orchestrator's existing tool-result shape
    (``{"type": "tool_result", "tool_use_id", "content": <str>}``).
    """

    tool_use_id: str
    content: str


# Completion #1: the spike draft referenced ``ContentBlock`` without defining
# it. ``ContentBlock`` is what a model *emits* (text + tool-use);
# ``ToolResultBlock`` is request-side, so it sits in ``RequestBlock`` (what a
# message's ``content`` list may carry).
ContentBlock = TextBlock | ToolUseBlock
RequestBlock = ContentBlock | ToolResultBlock


@dataclass(frozen=True)
class Message:
    """One conversation turn (spike §4, completion #2 for content shape).

    ``content`` is ``str`` for plain user prompts (the orchestrator builds the
    initial user message as a string, ``orchestrator.py`` ``run``) and
    ``list[RequestBlock]`` for assistant turns and tool-result turns. Typing it
    as the union keeps P1-002 a pass-through wrapper (parity-preserving).
    """

    role: str
    content: str | list[RequestBlock]


@dataclass(frozen=True)
class ToolDef:
    """A tool the model may call (matches today's ``AGENT_TOOLS`` entries)."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized response from ``messages_create``.

    ``stop_reason`` is the R5-critical normalized field. ``raw_model`` is the
    concrete model id actually used (for cost accounting / audit), which may
    differ from the requested alias.
    """

    content: list[ContentBlock]
    stop_reason: StopReason
    usage: Usage
    raw_model: str


@dataclass(frozen=True)
class ProviderCapabilities:
    """Static capability advertisement (→ P4-009 capabilities / P4-010 router).

    In v1 all targeted providers set ``native_tool_use=True`` and
    ``system_prompt=True``; the flags are forward-looking (e.g. a local model
    without native tool use would need a prompt-based tool-use shim).
    """

    native_tool_use: bool
    streaming: bool
    system_prompt: bool
    max_context_tokens: int


@dataclass(frozen=True)
class ErrorClass:
    """Classification of a provider exception (→ loop-owned retry, R4 / D-retry).

    ``transient`` is the retry signal the loop reads (alongside its
    budget-aware skip). ``retry_after_s`` carries a server-advised backoff when
    available (e.g. ``Retry-After``).
    """

    transient: bool
    status_code: int | None
    retry_after_s: float | None


@dataclass(frozen=True)
class StreamDelta:
    """One incremental chunk from ``stream()`` (completion #3).

    The spike declared ``stream() -> AsyncIterator[StreamDelta]`` but did not
    define ``StreamDelta``. These three fields are the minimal surface any token
    consumer needs: partial text, an optional terminal ``stop_reason`` on the
    final delta, and an optional terminal ``usage``.
    """

    text: str = ""
    stop_reason: StopReason | None = None
    usage: Usage | None = None


class LLMProvider(Protocol):
    """The provider-agnostic LLM contract (ARC-011 P1-001, X-005 spike §4).

    A concrete provider (``AnthropicProvider`` in P1-002, ``OpenAIProvider`` in
    P4-007) implements this surface. The orchestrator loop (P1-004) is wired to
    accept any ``LLMProvider`` and owns retry/backoff via ``classify_error``.
    """

    name: str
    """Provider identifier (``"anthropic"`` / ``"openai"`` / ``"gemini"``)."""

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        max_tokens: int,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> ProviderResponse:
        """Run one model turn (replaces ``messages.create``).

        Implementations MUST set ``stop_reason == TOOL_USE`` whenever the
        response carries tool/function calls, regardless of the native
        ``finish_reason`` (R5 invariant; Gemini may report ``STOP`` with
        function calls present).
        """
        ...

    async def complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
        system: str | None = None,
    ) -> str:
        """One-shot text completion (insights / Haiku path).

        Returns only the text; cost accounting for this path is added in P1-003
        (the spike §9 notes the Haiku insights call is not cost-counted today).
        """
        ...

    async def stream(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
        """Token streaming (OPTIONAL in v1; D-stream).

        Implementations MAY raise ``NotImplementedError``. No streaming
        consumer exists today; this declares the normalization target so a
        future token-streaming UI need not revise the protocol.
        """
        ...
        # Yield is what makes this an async generator in the type system; the
        # body is ``...`` per Protocol convention. (Unreachable.)
        yield StreamDelta()  # pragma: no cover

    def estimate_cost(self, model: str, usage: Usage) -> float:
        """Per-provider, per-model USD cost for a call (→ P1-003)."""
        ...

    def capabilities(self) -> ProviderCapabilities:
        """Static capability advertisement (→ P4-009 / router P4-010)."""
        ...

    def classify_error(self, exc: Exception) -> ErrorClass:
        """Classify an exception for loop-owned retry (→ R4 / D-retry).

        The loop reads ``ErrorClass.transient`` to decide whether to back off
        (combined with its budget-aware skip); providers set their SDK's
        internal retries to 0 so the loop isn't double-retrying.
        """
        ...


__all__ = [
    "AnthropicProvider",
    "build_provider",
    "ContentBlock",
    "ErrorClass",
    "LLMProvider",
    "Message",
    "OpenAIProvider",
    "ProviderCapabilities",
    "ProviderResponse",
    "RequestBlock",
    "StopReason",
    "StreamDelta",
    "TextBlock",
    "ToolDef",
    "ToolResultBlock",
    "ToolUseBlock",
    "Usage",
]


# ── Anthropic SDK adapter (P1-002) ─────────────────────────────────────────


def _to_sdk_content(blocks: list[RequestBlock]) -> list[dict[str, Any]]:
    """Translate normalized request blocks → Anthropic wire-format block dicts.

    Byte-identical to the dicts the orchestrator constructed pre-refactor
    (``TextBlock`` → ``{"type":"text","text"}``; ``ToolUseBlock`` →
    ``{"type":"tool_use","id","name","input"}``; ``ToolResultBlock`` →
    ``{"type":"tool_result","tool_use_id","content"}``).
    """
    sdk_blocks: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, TextBlock):
            sdk_blocks.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolUseBlock):
            sdk_blocks.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
        elif isinstance(block, ToolResultBlock):
            sdk_blocks.append({
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
            })
    return sdk_blocks


def _to_sdk_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Translate the normalized conversation → Anthropic ``messages`` wire format.

    ``Message.content: str`` (plain user prompts) stays a string content;
    ``Message.content: list[RequestBlock]`` (assistant / tool-result turns)
    becomes a list of block dicts. This preserves the exact shapes the
    orchestrator built before P1-002.
    """
    sdk_messages: list[dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg.content, str):
            sdk_messages.append({"role": msg.role, "content": msg.content})
        else:
            sdk_messages.append({
                "role": msg.role,
                "content": _to_sdk_content(msg.content),
            })
    return sdk_messages


def _to_sdk_tools(tools: list[ToolDef]) -> list[dict[str, Any]]:
    """Translate ``ToolDef`` → the ``{name, description, input_schema}`` dicts
    the SDK expects (the pre-refactor ``AGENT_TOOLS`` shape)."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in tools
    ]


def _from_sdk_response(raw: Any) -> ProviderResponse:
    """Translate a raw ``anthropic.types.Message`` → normalized ``ProviderResponse``.

    Enforces the R5 invariant: if any content block is a ``tool_use``, the
    normalized ``stop_reason`` is ``TOOL_USE`` regardless of the native
    ``stop_reason`` (Gemini reports ``STOP`` with function calls present;
    defensive for all providers).
    """
    content: list[ContentBlock] = []
    has_tool_use = False
    for block in getattr(raw, "content", None) or []:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            content.append(TextBlock(text=block.text))
        elif block_type == "tool_use":
            has_tool_use = True
            content.append(ToolUseBlock(
                id=block.id,
                name=block.name,
                input=dict(block.input) if not isinstance(block.input, dict) else block.input,
            ))

    if has_tool_use:
        stop_reason = StopReason.TOOL_USE
    else:
        raw_stop_reason = getattr(raw, "stop_reason", None)
        stop_reason = (
            _STOP_REASON_MAP.get(raw_stop_reason, StopReason.OTHER)
            if isinstance(raw_stop_reason, str)
            else StopReason.OTHER
        )

    raw_usage = getattr(raw, "usage", None)
    usage = Usage(
        input_tokens=getattr(raw_usage, "input_tokens", 0) or 0,
        output_tokens=getattr(raw_usage, "output_tokens", 0) or 0,
    )
    return ProviderResponse(
        content=content,
        stop_reason=stop_reason,
        usage=usage,
        raw_model=getattr(raw, "model", "") or "",
    )


_STOP_REASON_MAP: dict[str, StopReason] = {
    "end_turn": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
    "stop_sequence": StopReason.STOP_SEQUENCE,
}


class AnthropicProvider:
    """``LLMProvider`` adapter over the Anthropic SDK (ARC-011 P1-002).

    A 1:1 boundary translator: normalized ``Message``/``ToolDef``/``system``
    become Anthropic ``messages.create`` kwargs (byte-identical to the
    pre-refactor orchestrator call), and the raw ``anthropic.types.Message``
    becomes a normalized ``ProviderResponse``. The provider owns no retry —
    loop-owned retry (``orchestrator.py`` ``_call_llm_with_retry``) reads
    ``classify_error`` and decides backoff + the budget-aware skip.
    """

    name = "anthropic"

    def __init__(self, *, base_url: str, api_key: str, timeout_s: float) -> None:
        # ``connect=30.0`` mirrors the pre-refactor orchestrator construction.
        self._client = anthropic.AsyncAnthropic(
            base_url=base_url,
            api_key=api_key,
            timeout=httpx.Timeout(timeout_s, connect=30.0),
        )

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        max_tokens: int,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> ProviderResponse:
        """One model turn via ``messages.create`` (replaces the orchestrator call).

        ``temperature`` / ``stop_sequences`` are only forwarded when set — the
        orchestrator never sets them today, so the wire request is unchanged.
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "tools": _to_sdk_tools(tools),
            "messages": _to_sdk_messages(messages),
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if stop_sequences is not None:
            kwargs["stop_sequences"] = stop_sequences
        raw = await self._client.messages.create(**kwargs)
        return _from_sdk_response(raw)

    async def complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
        system: str | None = None,
    ) -> str:
        """One-shot text completion (insights / Haiku path).

        Wraps the bare ``messages.create`` the orchestrator's
        ``_extract_session_insights`` used: no tools, no retry, a single user
        message. Returns only the joined text.
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            kwargs["system"] = system
        raw = await self._client.messages.create(**kwargs)
        return "".join(
            block.text for block in raw.content if getattr(block, "type", None) == "text"
        )

    async def stream(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
        """Token streaming (OPTIONAL in v1; D-stream). Not implemented for Anthropic."""
        raise NotImplementedError(
            "AnthropicProvider.stream is not implemented (ARC-011 D-stream)"
        )
        yield StreamDelta()  # pragma: no cover — makes this an async generator

    def estimate_cost(self, model: str, usage: Usage) -> float:
        """Flat Sonnet-3.5-baseline USD cost (parity with pre-refactor accounting).

        Per-model pricing is P1-003; this preserves the cache-blind math the
        orchestrator used before P1-002.
        """
        return (
            usage.input_tokens * _CLAUDE_INPUT_USD_PER_TOKEN
            + usage.output_tokens * _CLAUDE_OUTPUT_USD_PER_TOKEN
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tool_use=True,
            streaming=False,
            system_prompt=True,
            max_context_tokens=200_000,
        )

    def classify_error(self, exc: Exception) -> ErrorClass:
        """Classify an SDK exception for loop-owned retry.

        ``transient`` mirrors the pre-refactor ``_call_claude_with_retry``
        decision: the three connection/timeout/server exception types, plus
        ``APIStatusError`` with a status code in ``_TRANSIENT_STATUS_CODES``
        (429 / 502 / 503 / 529). Everything else is non-transient.
        """
        if isinstance(
            exc,
            (
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.InternalServerError,
            ),
        ):
            return ErrorClass(transient=True, status_code=None, retry_after_s=None)
        if isinstance(exc, anthropic.APIStatusError):
            status_code = getattr(exc, "status_code", None)
            return ErrorClass(
                transient=status_code in _TRANSIENT_STATUS_CODES,
                status_code=status_code,
                retry_after_s=None,
            )
        return ErrorClass(transient=False, status_code=None, retry_after_s=None)


# ── OpenAI SDK adapter (P4-007 / P4-008) ────────────────────────────────────
#
# Implements ``LLMProvider`` over the OpenAI Chat Completions API (spike
# D-openai). System → ``role:"system"`` message; tools → ``{type:"function",
# function:{name,description,parameters}}``; tool results → ``role:"tool"``
# messages keyed by ``tool_call_id``; ``function.arguments`` JSON-parsed into
# ``ToolUseBlock.input``; R5 invariant enforced in ``_from_openai_response``;
# ``max_retries=0`` so loop-owned retry is authoritative.

_OPENAI_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (5.0 / 1_000_000, 15.0 / 1_000_000),
    "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
    "gpt-4-turbo": (10.0 / 1_000_000, 30.0 / 1_000_000),
    "gpt-4.1": (2.0 / 1_000_000, 8.0 / 1_000_000),
    "gpt-4.1-mini": (0.40 / 1_000_000, 1.60 / 1_000_000),
}
_OPENAI_DEFAULT_INPUT_USD_PER_TOKEN = 5.0 / 1_000_000
_OPENAI_DEFAULT_OUTPUT_USD_PER_TOKEN = 15.0 / 1_000_000
_OPENAI_MAX_CONTEXT_TOKENS = 128_000
_OPENAI_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

_OPENAI_STOP_REASON_MAP: dict[str, StopReason] = {
    "stop": StopReason.END_TURN,
    "tool_calls": StopReason.TOOL_USE,
    "length": StopReason.MAX_TOKENS,
    "stop_sequence": StopReason.STOP_SEQUENCE,
}


def _to_openai_messages(
    messages: list[Message], system: str,
) -> list[dict[str, Any]]:
    """Translate the normalized conversation → OpenAI Chat Completions messages.

    The Anthropic top-level ``system`` becomes a leading ``role:"system"``
    message. Assistant turns carry ``tool_calls``; tool-result turns become
    ``role:"tool"`` messages keyed by ``tool_call_id`` (one per result block).
    """
    oai_messages: list[dict[str, Any]] = []
    if system:
        oai_messages.append({"role": "system", "content": system})
    for msg in messages:
        if isinstance(msg.content, str):
            oai_messages.append({"role": msg.role, "content": msg.content})
            continue
        if msg.role == "assistant":
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    })
            entry: dict[str, Any] = {"role": "assistant"}
            if text_parts:
                entry["content"] = "".join(text_parts)
            if tool_calls:
                entry["tool_calls"] = tool_calls
            if "content" not in entry and "tool_calls" not in entry:
                entry["content"] = ""
            oai_messages.append(entry)
        else:
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    oai_messages.append({
                        "role": "tool",
                        "tool_call_id": block.tool_use_id,
                        "content": block.content,
                    })
                elif isinstance(block, TextBlock):
                    oai_messages.append({"role": msg.role, "content": block.text})
    return oai_messages


def _to_openai_tools(tools: list[ToolDef]) -> list[dict[str, Any]]:
    """Translate ``ToolDef`` → OpenAI function-tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
        for tool in tools
    ]


def _from_openai_response(raw: Any) -> ProviderResponse:
    """Translate a raw OpenAI ``ChatCompletion`` → normalized ``ProviderResponse``.

    Enforces the R5 invariant: if ``message.tool_calls`` is non-empty, the
    normalized ``stop_reason`` is ``TOOL_USE`` regardless of native
    ``finish_reason`` (spike §5).
    """
    content: list[ContentBlock] = []
    has_tool_use = False

    choices = getattr(raw, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None:
            text = getattr(message, "content", None)
            if text:
                content.append(TextBlock(text=text))
            tool_calls = getattr(message, "tool_calls", None) or []
            for tc in tool_calls:
                has_tool_use = True
                fn = getattr(tc, "function", None)
                tc_id = getattr(tc, "id", "") or ""
                name = getattr(fn, "name", "") if fn else ""
                args_str = getattr(fn, "arguments", "{}") if fn else "{}"
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else dict(args_str)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        "OpenAI tool-call arguments were not valid JSON: %s; "
                        "degrading to empty dict", args_str,
                    )
                    args = {}
                content.append(ToolUseBlock(id=tc_id, name=name, input=dict(args)))

    if has_tool_use:
        stop_reason = StopReason.TOOL_USE
    else:
        finish_reason = ""
        if choices:
            finish_reason = getattr(choices[0], "finish_reason", "") or ""
        stop_reason = (
            _OPENAI_STOP_REASON_MAP.get(finish_reason, StopReason.OTHER)
            if isinstance(finish_reason, str)
            else StopReason.OTHER
        )

    raw_usage = getattr(raw, "usage", None)
    usage = Usage(
        input_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
    )
    return ProviderResponse(
        content=content,
        stop_reason=stop_reason,
        usage=usage,
        raw_model=getattr(raw, "model", "") or "",
    )


class OpenAIProvider:
    """``LLMProvider`` adapter over the OpenAI Chat Completions API (P4-007).

    A boundary translator: normalized ``Message``/``ToolDef``/``system`` become
    ``chat.completions.create`` kwargs, and the raw ``ChatCompletion`` becomes a
    normalized ``ProviderResponse``. The provider owns no retry — loop-owned
    retry reads ``classify_error`` and decides backoff + the budget-aware skip.

    The ``openai`` SDK is imported **lazily** in ``__init__`` so this module
    imports without the package installed (tests that only exercise
    ``AnthropicProvider`` are unaffected). Constructing an ``OpenAIProvider``
    requires ``openai >= 1.0``.
    """

    name = "openai"

    def __init__(self, *, base_url: str, api_key: str, timeout_s: float) -> None:
        import openai as _openai

        self._openai_mod = _openai
        # ``max_retries=0`` — loop-owned retry is authoritative (spike D-retry).
        self._client = _openai.AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=httpx.Timeout(timeout_s, connect=30.0),
            max_retries=0,
        )

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        max_tokens: int,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> ProviderResponse:
        """One model turn via ``chat.completions.create``."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": _to_openai_messages(messages, system),
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)
        if temperature is not None:
            kwargs["temperature"] = temperature
        if stop_sequences is not None:
            kwargs["stop"] = stop_sequences
        raw = await self._client.chat.completions.create(**kwargs)
        return _from_openai_response(raw)

    async def complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
        system: str | None = None,
    ) -> str:
        """One-shot text completion (insights / Haiku path)."""
        oai_messages: list[dict[str, Any]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.append({"role": "user", "content": prompt})
        raw = await self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=oai_messages,
        )
        choices = getattr(raw, "choices", None) or []
        if choices:
            return getattr(choices[0].message, "content", None) or ""
        return ""

    async def stream(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
        """Token streaming (OPTIONAL in v1; D-stream). Not implemented for OpenAI."""
        raise NotImplementedError(
            "OpenAIProvider.stream is not implemented (ARC-011 D-stream)"
        )
        yield StreamDelta()  # pragma: no cover — makes this an async generator

    def estimate_cost(self, model: str, usage: Usage) -> float:
        """Per-model USD cost for an OpenAI call.

        Uses a per-model pricing table with a gpt-4o-class default. Cache-blind
        (parity with ``AnthropicProvider.estimate_cost``).
        """
        in_rate, out_rate = _OPENAI_PRICING.get(
            model, (_OPENAI_DEFAULT_INPUT_USD_PER_TOKEN, _OPENAI_DEFAULT_OUTPUT_USD_PER_TOKEN),
        )
        return usage.input_tokens * in_rate + usage.output_tokens * out_rate

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tool_use=True,
            streaming=False,
            system_prompt=True,
            max_context_tokens=_OPENAI_MAX_CONTEXT_TOKENS,
        )

    def classify_error(self, exc: Exception) -> ErrorClass:
        """Classify an OpenAI SDK exception for loop-owned retry.

        ``transient`` mirrors the Anthropic decision: connection/timeout/server
        errors plus HTTP status codes in ``_OPENAI_TRANSIENT_STATUS_CODES``
        (429 / 500 / 502 / 503 / 504). Everything else is non-transient.
        """
        openai = self._openai_mod
        if isinstance(
            exc,
            (
                openai.APITimeoutError,
                openai.APIConnectionError,
                openai.InternalServerError,
            ),
        ):
            return ErrorClass(transient=True, status_code=None, retry_after_s=None)
        if isinstance(exc, openai.APIStatusError):
            status_code = getattr(exc, "status_code", None)
            return ErrorClass(
                transient=status_code in _OPENAI_TRANSIENT_STATUS_CODES,
                status_code=status_code,
                retry_after_s=None,
            )
        return ErrorClass(transient=False, status_code=None, retry_after_s=None)


# ── Mock provider (P0-3 demo mode) ──────────────────────────────────────────


class MockProvider:
    """Zero-credential scripted provider for demos and CI (P0-3).

    Replays a deterministic edit-run-keep loop without any network: each
    ``messages_create`` emits one ``bash`` tool call running the skill's eval
    script, and — ARC-012 P7-011 — when the previous governed eval printed an
    iteration marker on stdout, the *next* response relays that exact marker
    line alongside a fresh eval call, exactly like a real agent (the
    marker-relay contract: a marker is honored only in a turn that itself ran
    a training command, and only the governed subprocess's verbatim output is
    trustworthy — the mock invents no metrics). ``complete`` returns a canned
    insight summary. Cost is always 0. Clearly labeled via ``name == "mock"``
    so production code can refuse it.
    """

    name = "mock"

    def __init__(
        self,
        *,
        eval_command: str = "",
        marker_prefix: str = "ITERATION_RESULT:",
    ) -> None:
        self._eval_command = eval_command or (
            ".venv/bin/python eval/run.py --prompt prompt.yaml "
            "--eval eval_set.jsonl"
        )
        self._marker_prefix = marker_prefix
        self._turn = 0

    def _last_tool_marker(self, messages: list[Message]) -> str | None:
        """The freshest iteration marker line in the most recent tool result.

        Only the newest tool-result message is scanned — the relay must be
        backed by the immediately preceding governed run, not a stale one.
        """
        for message in reversed(messages):
            content = message.content
            if not isinstance(content, list):
                continue
            found: str | None = None
            has_tool_result = False
            for block in content:
                if isinstance(block, ToolResultBlock):
                    has_tool_result = True
                    for line in block.content.splitlines():
                        if line.startswith(self._marker_prefix):
                            found = line.strip()
            if has_tool_result:
                return found
        return None

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[Message],
        tools: list[ToolDef],
        max_tokens: int,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> ProviderResponse:
        self._turn += 1
        marker = self._last_tool_marker(messages)
        if marker is not None:
            # Relay the governed eval's verbatim marker in the same response
            # that issues the next eval (the relay contract).
            return ProviderResponse(
                content=[
                    TextBlock(
                        text=(
                            "Demo eval finished — relaying its exact result.\n"
                            f"{marker}"
                        )
                    ),
                    ToolUseBlock(
                        id=f"mock-tool-{self._turn}",
                        name="bash",
                        input={"command": self._eval_command},
                    ),
                ],
                stop_reason=StopReason.TOOL_USE,
                usage=Usage(input_tokens=10, output_tokens=10),
                raw_model="mock-demo",
            )
        if self._turn % 2 == 1:
            return ProviderResponse(
                content=[
                    ToolUseBlock(
                        id=f"mock-tool-{self._turn}",
                        name="bash",
                        input={"command": self._eval_command},
                    )
                ],
                stop_reason=StopReason.TOOL_USE,
                usage=Usage(input_tokens=10, output_tokens=10),
                raw_model="mock-demo",
            )
        return ProviderResponse(
            content=[
                TextBlock(
                    text=(
                        "Demo turn complete. Check ITERATION_RESULT metrics; "
                        "vary one parameter next iteration."
                    )
                )
            ],
            stop_reason=StopReason.END_TURN,
            usage=Usage(input_tokens=10, output_tokens=10),
            raw_model="mock-demo",
        )

    async def complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
        system: str | None = None,
    ) -> str:
        return "Demo insight summary (mock provider, no LLM used)."

    async def stream(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
        raise NotImplementedError("MockProvider.stream is not implemented")
        yield StreamDelta()  # pragma: no cover — makes this an async generator

    def estimate_cost(self, model: str, usage: Usage) -> float:
        return 0.0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tool_use=True,
            streaming=False,
            system_prompt=True,
            max_context_tokens=32_000,
        )

    def classify_error(self, exc: Exception) -> ErrorClass:
        return ErrorClass(transient=False, status_code=None, retry_after_s=None)


# ── Provider router (P4-010) ─────────────────────────────────────────────────


class ProviderCapabilityMismatch(ValueError):
    """Raised (ARC-011 P4-009) when a skill manifest's required capabilities
    are not satisfied by the selected provider's ``capabilities()``.

    Fail-closed: a session whose skill demands (e.g.) native tool use but is
    routed to a provider that lacks it must be rejected at session start,
    before any LLM call — mirroring the codebase's existing fail-closed posture
    (production-approval HMAC, command policy default-deny).
    """


# Capability requirements, expressed in the same terms as ProviderCapabilities.
# Built from a skill manifest's ``LLMConfig.required_*`` fields. ``None`` means
# "the manifest does not constrain this dimension" (skip the check).
class RequiredCapabilities:
    """Subset of :class:`ProviderCapabilities` a skill demands (P4-009)."""

    def __init__(
        self,
        *,
        native_tool_use: Optional[bool] = None,
        system_prompt: Optional[bool] = None,
        max_context_tokens: Optional[int] = None,
    ) -> None:
        self.native_tool_use = native_tool_use
        self.system_prompt = system_prompt
        self.max_context_tokens = max_context_tokens

    @classmethod
    def from_llm_config(cls, llm_cfg: Any) -> "RequiredCapabilities":
        """Build from a skill manifest's ``LLMConfig`` (P4-009).

        Reads ``required_native_tool_use`` / ``required_system_prompt`` /
        ``required_max_context_tokens``. Tolerates an older manifest that
        lacks the fields (treats absent fields as unconstrained).
        """
        return cls(
            native_tool_use=getattr(llm_cfg, "required_native_tool_use", None),
            system_prompt=getattr(llm_cfg, "required_system_prompt", None),
            max_context_tokens=getattr(llm_cfg, "required_max_context_tokens", None),
        )

    def check(self, caps: ProviderCapabilities, provider_id: str) -> None:
        """Raise :class:`ProviderCapabilityMismatch` if ``caps`` is insufficient."""
        problems: list[str] = []
        if self.native_tool_use and not caps.native_tool_use:
            problems.append("native_tool_use")
        if self.system_prompt and not caps.system_prompt:
            problems.append("system_prompt")
        if (
            self.max_context_tokens is not None
            and caps.max_context_tokens < self.max_context_tokens
        ):
            problems.append(
                f"max_context_tokens (need >= {self.max_context_tokens}, "
                f"have {caps.max_context_tokens})"
            )
        if problems:
            raise ProviderCapabilityMismatch(
                f"provider {provider_id!r} does not satisfy the skill's required "
                f"capabilities: {', '.join(problems)}"
            )


def build_provider(
    provider_id: str,
    *,
    settings_obj: Any = None,
    required_capabilities: Optional[RequiredCapabilities] = None,
) -> LLMProvider:
    """Construct a ``LLMProvider`` by id (ARC-011 P4-010 router + P0-3 mock).

    Maps a skill manifest's ``llm.provider`` (``"anthropic"`` / ``"openai"`` /
    ``"mock"``) to a concrete provider instance, reading API credentials from
    ``settings``. ``"mock"`` (or ``AUTORESEARCH_DEMO=true`` with any id) yields
    a zero-credential ``MockProvider`` for demos/CI; production refuses it
    (see ``_refuse_mock_in_production``).
    """
    from src.config import secret_value

    if settings_obj is None:
        from src.config import settings as _settings

        settings_obj = _settings

    def _demo_requested() -> bool:
        raw = getattr(settings_obj, "demo_mode", False)
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in ("1", "true", "yes")

    if provider_id == "mock" or _demo_requested():
        mock = MockProvider()
        if str(getattr(settings_obj, "environment", "development")).lower() in (
            "prod",
            "production",
        ):
            raise ValueError("mock provider is refused in production")
        if required_capabilities is not None:
            required_capabilities.check(mock.capabilities(), "mock")
        return mock
    if provider_id == "anthropic":
        provider: LLMProvider = AnthropicProvider(
            base_url=settings_obj.anthropic_base_url or "https://api.anthropic.com",
            api_key=secret_value(settings_obj.anthropic_auth_token) or "",
            timeout_s=settings_obj.anthropic_api_timeout_s,
        )
    elif provider_id == "openai":
        key = getattr(settings_obj, "openai_api_key", None)
        provider = OpenAIProvider(
            base_url=settings_obj.openai_base_url or "https://api.openai.com/v1",
            api_key=secret_value(key) or "",
            timeout_s=settings_obj.openai_api_timeout_s,
        )
    else:
        raise ValueError(
            "unknown LLM provider "
            f"{provider_id!r}; expected 'anthropic', 'openai' or 'mock'"
        )

    # ARC-011 P4-009: fail-closed capability check. When the caller supplies
    # the skill's required capabilities, validate them against the provider's
    # advertisement before returning — so a mismatch fails the session at
    # start, before any LLM call. Default provider construction (orchestrator
    # init) passes no requirements and skips the check.
    if required_capabilities is not None:
        required_capabilities.check(provider.capabilities(), provider_id)
    return provider
