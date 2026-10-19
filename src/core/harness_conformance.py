"""Reusable harness conformance suite and a deterministic fake adapter.

Integration authors run ``run_conformance`` against their adapter before
connecting it to the kernel. The fake adapter is deterministic and can be
built to violate exactly one rule at a time, so the suite's own checks are
specified by failing examples.
"""
from __future__ import annotations

from typing import Any, Iterator, Mapping, Optional

from src.core.harness_adapter import (
    HarnessAdapter,
    HarnessRegistry,
    request_pause,
    request_resume,
    request_steer,
)
from src.core.harness_contract import (
    ATTACH_MODE_CONTINUATION,
    ATTACH_MODE_NATIVE_RESUME,
    CAPABILITY_PAUSE,
    CAPABILITY_RESUME,
    CAPABILITY_STEERING,
    HARNESS_CONTRACT_VERSION,
    OPTIONAL_CAPABILITIES,
    HarnessContractError,
    HarnessLifecycleError,
    HarnessVersionError,
    UnsupportedCapabilityError,
)


class FakeHarnessAdapter:
    """A deterministic harness adapter for specification and testing.

    ``violations`` names the conformance rules the adapter deliberately
    breaks (see ``run_conformance``); with none it is fully conforming.
    """

    def __init__(
        self,
        *,
        name: str = "fake-harness",
        version: str = "1.0.0",
        contract_version: str = HARNESS_CONTRACT_VERSION,
        capabilities: frozenset[str] = frozenset(),
        permissions: Optional[Mapping[str, Any]] = None,
        events: tuple[Mapping[str, Any], ...] = (),
        violations: frozenset[str] = frozenset(),
    ) -> None:
        self._identity = {
            "name": name,
            "version": version,
            "contract_version": contract_version,
            "permissions": dict(permissions or {}),
        }
        self._capabilities = frozenset(capabilities)
        self._scripted = tuple(events)
        self._violations = frozenset(violations)
        self._next_handle = 0
        self._open: dict[str, dict[str, Any]] = {}
        self.log: list[str] = []

    # -- identity and capabilities ------------------------------------
    def identity(self) -> Mapping[str, Any]:
        return dict(self._identity)

    def capabilities(self) -> frozenset[str]:
        if "capability_lie" in self._violations:
            # advertises pause with no implementation behind it
            return frozenset({CAPABILITY_PAUSE})
        return self._capabilities

    def pause(self, handle: str) -> None:
        if "capability_lie" in self._violations:
            raise NotImplementedError("advertised pause has no implementation")
        self._require_open(handle, "pause")
        if "kill_as_pause" in self._violations:
            # the forbidden substitution: a kill presented as a pause —
            # the run is torn down and the pause reports success
            self.cancel(handle)
            del self._open[handle]
            self.log.append(f"pause:{handle}")
            return
        self._open[handle]["paused"] = True
        self.log.append(f"pause:{handle}")

    def resume(self, handle: str) -> None:
        self._require_open(handle, "resume")
        self._open[handle]["paused"] = False
        self.log.append(f"resume:{handle}")

    def steering(self, handle: str, proposal: Mapping[str, Any]) -> None:
        self._require_open(handle, "steer")
        self._open[handle]["steered"].append(dict(proposal))
        self.log.append(f"steer:{handle}")

    # -- required operations ------------------------------------------
    def start(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        handle = self._new_handle(request)
        self.log.append(f"start:{handle}")
        return {"handle": handle, "mode": ATTACH_MODE_NATIVE_RESUME}

    def attach(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        mode = str(request.get("mode") or ATTACH_MODE_CONTINUATION)
        origin = request.get("origin_harness")
        if (
            mode == ATTACH_MODE_NATIVE_RESUME
            and origin not in (None, self._identity["name"])
            and "native_claim_on_continuation" not in self._violations
        ):
            raise HarnessContractError(
                "cross-harness attach cannot claim native transcript resume"
            )
        if "native_claim_on_continuation" in self._violations:
            mode = ATTACH_MODE_NATIVE_RESUME
        handle = self._new_handle(request)
        self.log.append(f"attach:{handle}:{mode}")
        return {"handle": handle, "mode": mode}

    def events(self, handle: str) -> Iterator[Mapping[str, Any]]:
        if handle not in self._open:
            if "events_before_start" in self._violations:
                return iter(())
            raise HarnessLifecycleError(
                f"no open handle {handle!r} for the event stream"
            )
        return iter([dict(event) for event in self._scripted])

    def cancel(self, handle: str) -> None:
        self._require_open(handle, "cancel")
        self._open[handle]["cancelled"] = True
        self.log.append(f"cancel:{handle}")

    def close(self, handle: str) -> None:
        # idempotent teardown: closing an unknown or already-closed handle
        # is a safe no-op, never an error
        if handle in self._open and "no_cleanup" not in self._violations:
            del self._open[handle]
        self.log.append(f"close:{handle}")

    # -- helpers ------------------------------------------------------
    def _new_handle(self, request: Mapping[str, Any]) -> str:
        self._next_handle += 1
        handle = f"h{self._next_handle}"
        self._open[handle] = {
            "request": dict(request),
            "paused": False,
            "cancelled": False,
            "steered": [],
        }
        return handle

    def _require_open(self, handle: str, op: str) -> None:
        if handle not in self._open:
            raise HarnessLifecycleError(
                f"{op} on unknown or closed handle {handle!r}"
            )


# ---------------------------------------------------------------------------
# The reusable conformance suite.
# ---------------------------------------------------------------------------


def run_conformance(
    adapter: HarnessAdapter, *, start_request: Mapping[str, Any] | None = None
) -> list[str]:
    """Conformance findings for one adapter; empty means conforming.

    ``start_request`` supplies the run configuration for adapters that
    require one (process-backed harnesses); without it the generic
    contract shape is used and a refused start is a finding.
    """
    findings: list[str] = []
    identity = adapter.identity()
    name = str(identity.get("name") or "?")
    request = dict(start_request) if start_request else {"run": "conformance"}

    # identity coherence and contract version
    if identity.get("contract_version") != HARNESS_CONTRACT_VERSION:
        findings.append(
            f"{name}: contract_version {identity.get('contract_version')!r}"
            f" != {HARNESS_CONTRACT_VERSION!r}"
        )
    if not identity.get("name") or not identity.get("version"):
        findings.append(f"{name}: identity missing name/version")
    if not isinstance(identity.get("permissions"), Mapping):
        findings.append(f"{name}: permissions must be a mapping")

    # registration refuses version mismatch and capability lies at the door
    registry = HarnessRegistry()
    try:
        registry.register(adapter)
    except HarnessVersionError as exc:
        findings.append(f"{name}: registration refused: {exc}")
    except HarnessContractError as exc:
        findings.append(f"{name}: registration refused: {exc}")

    # capability advertisement
    advertised = set(adapter.capabilities())
    for capability in sorted(advertised):
        if capability not in OPTIONAL_CAPABILITIES:
            findings.append(
                f"{name}: advertises unknown capability {capability!r}"
            )
        elif not callable(getattr(adapter, capability, None)):
            findings.append(
                f"{name}: advertises {capability!r} without an implementation"
            )

    # lifecycle ordering: operations on unknown handles are refused
    try:
        list(adapter.events("never-started"))
        findings.append(f"{name}: event stream accepted an unknown handle")
    except HarnessLifecycleError:
        pass
    except Exception as exc:  # noqa: BLE001 — wrong error shape
        findings.append(f"{name}: unknown-handle events raised {exc!r}")

    def _start(tag: str):
        probe_request = dict(request)
        probe_request["run"] = tag
        try:
            return adapter.start(probe_request)
        except HarnessContractError as exc:
            findings.append(f"{name}: start refused: {exc}")
            return None

    # cancelled start and cleanup
    started = _start("conformance")
    if started is None:
        return findings
    handle = str(started.get("handle") or "")
    if not handle:
        findings.append(f"{name}: start returned no handle")
        return findings
    adapter.cancel(handle)
    adapter.close(handle)
    adapter.close(handle)  # idempotent teardown
    try:
        list(adapter.events(handle))
        findings.append(f"{name}: event stream served a closed handle")
    except HarnessLifecycleError:
        pass
    except Exception as exc:  # noqa: BLE001 — wrong error shape
        findings.append(f"{name}: closed-handle events raised {exc!r}")

    # unsupported capabilities are explicit; kill is never a pause
    started2 = _start("conformance-2")
    if started2 is None:
        return findings
    handle2 = str(started2.get("handle") or "")
    for capability, send in (
        (CAPABILITY_PAUSE, lambda: request_pause(adapter, handle2)),
        (CAPABILITY_RESUME, lambda: request_resume(adapter, handle2)),
        (
            CAPABILITY_STEERING,
            lambda: request_steer(
                adapter, handle2, {"proposal_id": "p1", "kind": "steer",
                                   "target": "run", "payload": {}}
            ),
        ),
    ):
        if capability in advertised:
            try:
                send()
            except UnsupportedCapabilityError:
                findings.append(
                    f"{name}: advertised {capability!r} refused its request"
                )
            except HarnessContractError:
                # an advertised capability may carry a documented
                # precondition (qualified resume needs a session): an
                # explicit refusal is not a lie
                pass
            except Exception as exc:  # noqa: BLE001 — misbehaving op
                findings.append(
                    f"{name}: advertised {capability!r} raised {exc!r}"
                )
        else:
            try:
                send()
                findings.append(
                    f"{name}: unadvertised {capability!r} was accepted"
                )
            except UnsupportedCapabilityError:
                pass
    # a pause must not kill the run it pauses
    if CAPABILITY_PAUSE in advertised:
        started_probe = _start("pause-probe")
        if started_probe is not None:
            probe = str(started_probe.get("handle") or "")
            try:
                request_pause(adapter, probe)
            except Exception:  # noqa: BLE001 — already reported above
                pass
            try:
                list(adapter.events(probe))
            except HarnessLifecycleError:
                findings.append(
                    f"{name}: pause terminated the run (kill presented as"
                    " pause)"
                )
            adapter.close(probe)
    adapter.close(handle2)

    # cross-harness attach never claims native transcript resume
    try:
        foreign = adapter.attach(
            {
                "run": "foreign",
                "mode": ATTACH_MODE_NATIVE_RESUME,
                "origin_harness": "some-other-harness",
            }
        )
    except HarnessContractError:
        foreign = None  # explicit refusal of a dishonest claim is honest
    if foreign is not None:
        if foreign.get("mode") == ATTACH_MODE_NATIVE_RESUME:
            findings.append(
                f"{name}: cross-harness attach claimed native transcript"
                " resume"
            )
        adapter.close(str(foreign.get("handle") or ""))
    return findings
