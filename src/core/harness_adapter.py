"""Harness adapters and registry: identity, capabilities, and run-spec pins.

A harness adapter is registered by name — the kernel holds no per-name
branches. Registration validates the adapter's contract version, identity
coherence, and that every advertised optional capability has a real
implementation. Before launch, skill/operator requirements are validated
against the adapter's advertised capabilities, and the adapter's identity,
version, and permissions resolve into the run spec.
"""
from __future__ import annotations

from typing import Any, Iterable, Iterator, Mapping, Optional, Protocol, runtime_checkable

from src.core.harness_contract import (
    ATTACH_MODES,
    CAPABILITY_PAUSE,
    CAPABILITY_RESUME,
    CAPABILITY_STEERING,
    HARNESS_CONTRACT_VERSION,
    OPTIONAL_CAPABILITIES,
    HarnessContractError,
    HarnessIdentity,
    HarnessProposal,
    HarnessRequirementError,
    HarnessVersionError,
    UnsupportedCapabilityError,
)


@runtime_checkable
class HarnessAdapter(Protocol):
    """The minimal, versioned harness surface.

    Required operations: identity, capabilities, start/attach, the event
    stream, cancel, and close. Optional operations (pause, resume, steer)
    exist only for adapters that advertise the matching capability.
    """

    def identity(self) -> HarnessIdentity: ...

    def capabilities(self) -> frozenset[str]: ...

    def start(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Begin a run; returns ``{"handle": <id>, ...}``."""
        ...

    def attach(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Rejoin a run under an explicit attach mode.

        Returns ``{"handle": <id>, "mode": <attach-mode>}`` — the mode is
        the honest label (a cross-harness rejoin is never labeled
        ``native_resume``).
        """
        ...

    def events(self, handle: str) -> Iterator[Mapping[str, Any]]: ...

    def cancel(self, handle: str) -> None: ...

    def close(self, handle: str) -> None: ...


class HarnessRegistry:
    """Name → adapter. Registering requires no kernel branch for the name."""

    def __init__(self) -> None:
        self._adapters: dict[str, HarnessAdapter] = {}

    def register(self, adapter: HarnessAdapter) -> None:
        identity = adapter.identity()
        if identity.get("contract_version") != HARNESS_CONTRACT_VERSION:
            raise HarnessVersionError(
                f"harness {identity.get('name')!r} declares contract "
                f"{identity.get('contract_version')!r}; this SDK speaks "
                f"{HARNESS_CONTRACT_VERSION!r}"
            )
        if not identity.get("name") or not identity.get("version"):
            raise HarnessContractError(
                "harness identity requires name and version"
            )
        advertised = set(adapter.capabilities())
        unknown = advertised - OPTIONAL_CAPABILITIES
        if unknown:
            raise HarnessContractError(
                f"harness {identity['name']!r} advertises unknown "
                f"capabilities: {sorted(unknown)}"
            )
        for capability in sorted(advertised):
            if not callable(getattr(adapter, capability, None)):
                raise HarnessContractError(
                    f"harness {identity['name']!r} advertises "
                    f"{capability!r} without an implementation"
                )
        self._adapters[identity["name"]] = adapter

    def resolve(self, name: str) -> HarnessAdapter:
        try:
            return self._adapters[name]
        except KeyError:
            raise HarnessContractError(
                f"no registered harness named {name!r}"
            ) from None

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def validate_requirements(
    adapter: HarnessAdapter,
    *,
    required_capabilities: Iterable[str] = (),
    required_permissions: Iterable[str] = (),
) -> None:
    """Pre-launch validation: refuse before any side effect."""
    missing: dict[str, Any] = {}
    capabilities = set(adapter.capabilities())
    absent = sorted(set(required_capabilities) - capabilities)
    if absent:
        missing["capabilities"] = absent
    permissions = adapter.identity().get("permissions") or {}
    ungranted = sorted(
        name for name in required_permissions if not permissions.get(name)
    )
    if ungranted:
        missing["permissions"] = ungranted
    if missing:
        raise HarnessRequirementError(missing)


def request_pause(adapter: HarnessAdapter, handle: str) -> None:
    """Request an optional pause — refused explicitly when unadvertised.

    The SDK never substitutes another operation: a cancel/kill is not a
    pause, and an unadvertised capability is never silently ignored.
    """
    if CAPABILITY_PAUSE not in adapter.capabilities():
        raise UnsupportedCapabilityError(
            CAPABILITY_PAUSE, adapter.identity().get("name", "?")
        )
    adapter.pause(handle)  # type: ignore[attr-defined]


def request_resume(adapter: HarnessAdapter, handle: str) -> None:
    if CAPABILITY_RESUME not in adapter.capabilities():
        raise UnsupportedCapabilityError(
            CAPABILITY_RESUME, adapter.identity().get("name", "?")
        )
    adapter.resume(handle)  # type: ignore[attr-defined]


def request_steer(
    adapter: HarnessAdapter, handle: str, proposal: Mapping[str, Any]
) -> None:
    if CAPABILITY_STEERING not in adapter.capabilities():
        raise UnsupportedCapabilityError(
            CAPABILITY_STEERING, adapter.identity().get("name", "?")
        )
    adapter.steering(handle, proposal)  # type: ignore[attr-defined]


def resolve_harness_spec(
    adapter: HarnessAdapter,
    *,
    required_capabilities: Iterable[str] = (),
    required_permissions: Iterable[str] = (),
    attach_mode: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve identity/version/permissions into a run-spec harness section.

    Requirement validation happens first: an unmet requirement is refused
    before anything is pinned or started.
    """
    validate_requirements(
        adapter,
        required_capabilities=required_capabilities,
        required_permissions=required_permissions,
    )
    identity = adapter.identity()
    if attach_mode is not None and attach_mode not in ATTACH_MODES:
        raise HarnessContractError(
            f"unknown attach mode {attach_mode!r}"
        )
    section: dict[str, Any] = {
        "name": identity["name"],
        "version": identity["version"],
        "contract_version": identity["contract_version"],
        "permissions": dict(identity.get("permissions") or {}),
        "capabilities": sorted(adapter.capabilities()),
    }
    if attach_mode is not None:
        section["attach_mode"] = attach_mode
    return section
