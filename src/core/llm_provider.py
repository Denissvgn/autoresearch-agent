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

from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Protocol

import anthropic
import httpx

# Claude pricing constants (Sonnet 3.5 baseline) — moved here from
# ``orchestrator.py`` (P1-002). Referenced by ``AnthropicProvider.estimate_cost``
# and by the orchestrator's pre-spend budget gate + post-call accounting. The
# flat-rate model ignores cache tokens (parity with pre-refactor; per-model
# pricing is P1-003).
_CLAUDE_INPUT_USD_PER_TOKEN = 3.0 / 1_000_000
_CLAUDE_OUTPUT_USD_PER_TOKEN = 15.0 / 1_000_000
_CLAUDE_MAX_OUTPUT_TOKENS = 8192

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
    "ContentBlock",
    "ErrorClass",
    "LLMProvider",
    "Message",
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
