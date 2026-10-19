"""The built-in provider/tool loop as a harness adapter.

``BuiltinHarnessAdapter`` wraps the corrected built-in loop behind the
harness contract: it is selectable by name through the registry, executes
attempts through the existing tool/output-parser machinery, and routes its
proposals through the research kernel. Its workspace instruction
convention (``CLAUDE.md``) is harness-owned data — core behavior never
depends on the filename or on any provider's tool-block shape.
"""
from __future__ import annotations

from typing import Any, Callable, Iterator, Mapping, Optional

from src.core.harness_contract import (
    ATTACH_MODE_CONTINUATION,
    ATTACH_MODE_NATIVE_RESUME,
    CAPABILITY_PAUSE,
    CAPABILITY_RESUME,
    HARNESS_CONTRACT_VERSION,
    HarnessContractError,
    HarnessIdentity,
    HarnessLifecycleError,
    HarnessProposal,
)
from src.core.research_kernel import (
    AttemptPlan,
    AttemptResult,
    ObjectiveDecision,
    decide_objective,
)

BUILTIN_HARNESS_NAME = "builtin"
BUILTIN_WORKSPACE_INSTRUCTION_FILE = "CLAUDE.md"

AttemptFn = Callable[[Mapping[str, Any], int], Mapping[str, Any]]


class BuiltinHarnessAdapter:
    """The built-in loop behind the harness contract and kernel driver."""

    def __init__(
        self,
        *,
        orchestrator: Any = None,
        attempt_fn: Optional[AttemptFn] = None,
        name: str = BUILTIN_HARNESS_NAME,
        version: str = "1.0.0",
    ) -> None:
        self._orch = orchestrator
        self._attempt_fn = attempt_fn
        self._name = name
        self._version = version
        self._next_handle = 0
        self._handles: dict[str, dict[str, Any]] = {}
        if orchestrator is not None:
            # the harness owns the workspace instruction filename
            setter = getattr(
                orchestrator, "set_workspace_instruction_filename", None
            )
            if callable(setter):
                setter(BUILTIN_WORKSPACE_INSTRUCTION_FILE)

    # -- HarnessAdapter (harness contract) ----------------------------
    def identity(self) -> HarnessIdentity:
        return {
            "name": self._name,
            "version": self._version,
            "contract_version": HARNESS_CONTRACT_VERSION,
            "permissions": {
                "stream": True,
                "cancel": True,
                "pause": True,
                "resume": True,
            },
        }

    def capabilities(self) -> frozenset[str]:
        # pause/resume drive the loop's flags; steering is not supported
        # and is refused explicitly by the SDK
        return frozenset({CAPABILITY_PAUSE, CAPABILITY_RESUME})

    def start(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        research_id = str(request.get("research_id") or "")
        handle = self._new_handle(research_id, request)
        return {"handle": handle, "mode": ATTACH_MODE_NATIVE_RESUME}

    def attach(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        mode = str(request.get("mode") or ATTACH_MODE_CONTINUATION)
        origin = request.get("origin_harness")
        if (
            mode == ATTACH_MODE_NATIVE_RESUME
            and origin not in (None, self._name)
        ):
            raise HarnessContractError(
                "cross-harness attach cannot claim native transcript resume"
            )
        handle = self._new_handle(
            str(request.get("research_id") or ""), request
        )
        return {"handle": handle, "mode": mode}

    def events(self, handle: str) -> Iterator[Mapping[str, Any]]:
        state = self._handles.get(handle)
        if state is None:
            raise HarnessLifecycleError(
                f"no open handle {handle!r} for the event stream"
            )
        return iter(state.get("events") or ())

    def cancel(self, handle: str) -> None:
        state = self._require_open(handle, "cancel")
        state["cancelled"] = True
        if self._orch is not None:
            self._orch.request_stop(state["research_id"])

    def pause(self, handle: str) -> None:
        state = self._require_open(handle, "pause")
        if self._orch is not None:
            self._orch.request_pause(state["research_id"])

    def resume(self, handle: str) -> None:
        state = self._require_open(handle, "resume")
        if self._orch is not None:
            self._orch.request_resume(state["research_id"])

    def close(self, handle: str) -> None:
        # idempotent teardown: closing an unknown or closed handle is a
        # safe no-op, never an error
        state = self._handles.pop(handle, None)
        if state is not None and self._orch is not None:
            self._orch.release_session(state["research_id"])

    # -- KernelDriver (research kernel) -------------------------------
    def run_attempt(
        self,
        plan: AttemptPlan,
        *,
        attempt_index: int,
        context: Mapping[str, Any],
    ) -> AttemptResult:
        """Execute one attempt through the built-in loop and report back.

        The attempt step is the existing tool/output-parser machinery; the
        returned value is the stable contract the kernel decides on.
        """
        if self._attempt_fn is None:
            raise HarnessContractError(
                "the built-in adapter has no attempt step bound"
            )
        raw = self._attempt_fn(context, attempt_index)
        return AttemptResult(
            iteration=int(raw.get("iteration", attempt_index)),
            outcome=str(raw.get("outcome", "completed")),
            metric=raw.get("metric"),
            metrics=dict(raw.get("metrics") or {}),
            verdict=str(raw.get("verdict", "")),
            gate_passed=bool(raw.get("gate_passed", False)),
            duplicate_of=raw.get("duplicate_of"),
            phase_id=raw.get("phase_id"),
            phase_advanced=raw.get("phase_advanced"),
        )

    def route_proposal(
        self,
        proposal: HarnessProposal,
        *,
        metric: Optional[float] = None,
        best_metric: Optional[float] = None,
        direction: str = "maximize",
    ) -> ObjectiveDecision:
        """Route a harness proposal through the kernel's decisions."""
        kind = str(proposal.get("kind") or "")
        payload = proposal.get("payload") or {}
        return decide_objective(
            verdict=str(payload.get("verdict") or kind or "proposal"),
            metric=metric,
            best_metric=best_metric,
            direction=direction,
            phase_id=payload.get("phase_id"),
            phase_advanced=payload.get("phase_advanced"),
            stop_requested=bool(payload.get("stop_requested", False)),
        )

    # -- helpers ------------------------------------------------------
    def _new_handle(
        self, research_id: str, request: Mapping[str, Any]
    ) -> str:
        self._next_handle += 1
        handle = f"builtin-h{self._next_handle}"
        self._handles[handle] = {
            "research_id": research_id,
            "request": dict(request),
            "events": list(request.get("events") or ()),
            "cancelled": False,
        }
        return handle

    def _require_open(self, handle: str, op: str) -> dict[str, Any]:
        state = self._handles.get(handle)
        if state is None:
            raise HarnessLifecycleError(
                f"{op} on unknown or closed handle {handle!r}"
            )
        return state