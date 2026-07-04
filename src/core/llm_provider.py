"""``LLMProvider`` protocol + normalized value types (ARC-011 P1-001).

This module adopts the X-005 LLM-provider normalization spike §4 *verbatim*
(``docs/adr/ARC-011-llm-provider-spike.md``) as the canonical contract every
provider implementation must satisfy: ``messages_create`` (main agentic path),
``complete`` (one-shot insights/Haiku path), an optional ``stream``,
``estimate_cost`` (→ P1-003), ``capabilities`` (→ P4-009 / router P4-010), and
``classify_error`` (→ loop-owned retry, R4).

Why a separate, provider-agnostic module: today the orchestrator calls the
Anthropic SDK directly (``orchestrator.py`` ``__init__`` builds
``anthropic.AsyncAnthropic`` and ``_call_claude_with_retry`` wraps
``messages.create``). P1-002 will extract an ``AnthropicProvider``; P1-004 will
wire the orchestrator to accept any ``LLMProvider``. P1-001 only introduces the
contract — no runtime behavior changes, so the X-002 parity suite is untouched.

Design decisions recorded by the spike and baked in here:

* **Anthropic-shaped normalized types** (spike §4 note). ``ToolUseBlock.input``
  is a ``dict`` (Anthropic shape; OpenAI's JSON-string ``function.arguments``
  is parsed by the provider), ``ToolResultBlock`` is the Anthropic tool-result
  block, and ``ToolDef`` matches today's ``AGENT_TOOLS`` entries. This keeps
  P1-002 a 1:1 wrapper and preserves the parity suite.
* **Loop-owned retry (R4 / D-retry).** The protocol exposes
  ``classify_error``; the loop owns backoff + the budget-aware skip
  (``orchestrator.py`` ``_call_claude_with_retry`` becomes
  ``_call_llm_with_retry`` in P1-002). ``ErrorClass.transient`` is the signal.
* **Phase-contract enforcement is loop-level (R5 / §5).** The provider surfaces
  a normalized ``StopReason``; the loop reads ``StopReason.END_TURN`` to trigger
  phase continuation. The defensive invariant *"tool calls present ⇒
  TOOL_USE, regardless of the native finish_reason"* (Gemini can report
  ``STOP`` with function calls present) is the provider's responsibility —
  documented on ``messages_create``.
* **Not ``@runtime_checkable``.** ``isinstance`` against a ``Protocol`` only
  checks attribute presence (false confidence on signatures). This is a
  typing-time contract; consumers accept it as a typed parameter.

Three places where the spike §4 draft was incomplete (resolved here, the only
deviations from a literal copy — see inline comments):

1. The draft references ``ContentBlock`` (in ``ProviderResponse.content``) and
   ``StreamDelta`` (in ``stream()``) without defining them.
2. The draft's ``Message{role, content: list[Block]}`` does not match the live
   orchestrator, which builds messages with ``content: str`` (user prompts) and
   ``content: list[block]`` (assistant / tool-result turns).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


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
