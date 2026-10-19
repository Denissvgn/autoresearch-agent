"""Harness contract: the versioned vocabulary between kernel and harnesses.

An agent harness (the built-in loop, or any external agent runtime) drives
the research kernel through this contract. Required operations are minimal
and versioned; optional capabilities are advertised individually and
refuse explicitly when unsupported — a kill is never presented as a
successful pause, and a cross-harness continuation is never claimed as a
native transcript resume.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, TypedDict

HARNESS_CONTRACT_VERSION = "autoresearch_harness.v1"

# Optional capabilities — individually advertised, never assumed.
CAPABILITY_PAUSE = "pause"
CAPABILITY_RESUME = "resume"
CAPABILITY_STEERING = "steering"
OPTIONAL_CAPABILITIES = frozenset(
    {CAPABILITY_PAUSE, CAPABILITY_RESUME, CAPABILITY_STEERING}
)

# Attach semantics. Native resume is only honest when the SAME harness
# reopens its own session state; anything else (including a different
# harness, or the kernel's restore path) is continuation.
ATTACH_MODE_NATIVE_RESUME = "native_resume"
ATTACH_MODE_CONTINUATION = "continuation"
ATTACH_MODES = frozenset({ATTACH_MODE_NATIVE_RESUME, ATTACH_MODE_CONTINUATION})


class HarnessIdentity(TypedDict):
    """Who the adapter is and what it is allowed to do."""

    name: str
    version: str
    contract_version: str
    permissions: Mapping[str, Any]


class HarnessEvent(TypedDict, total=False):
    """One event from a harness's stream; unknown types are tolerated."""

    event_id: str
    type: str
    sequence: int
    timestamp: str
    payload: Mapping[str, Any]
    unknown: bool


class HarnessProposal(TypedDict):
    """A proposal carried across the boundary (e.g. a steering proposal)."""

    proposal_id: str
    kind: str
    target: str
    payload: Mapping[str, Any]


class HarnessErrorRecord(TypedDict):
    """A harness error surfaced as data, with honest retry semantics."""

    code: str
    message: str
    retryable: bool
    details: Mapping[str, Any]


class HarnessContractError(Exception):
    """The harness contract was violated or cannot be honored."""


class HarnessVersionError(HarnessContractError):
    """The adapter's contract version is incompatible with this SDK."""


class UnsupportedCapabilityError(HarnessContractError):
    """An optional capability was requested but is not advertised.

    Refusal is explicit: the SDK never substitutes a different operation
    (a kill is not a pause) and never silently no-ops.
    """

    def __init__(self, capability: str, adapter_name: str) -> None:
        self.capability = capability
        self.adapter_name = adapter_name
        super().__init__(
            f"harness {adapter_name!r} does not advertise the "
            f"{capability!r} capability; refusing explicitly"
        )


class HarnessRequirementError(HarnessContractError):
    """Skill/operator requirements exceed what the adapter provides."""

    def __init__(self, missing: Mapping[str, Any]) -> None:
        self.missing = dict(missing)
        super().__init__(
            f"unmet harness requirements before launch: {dict(missing)}"
        )


class HarnessLifecycleError(HarnessContractError):
    """A lifecycle operation was called out of order or after teardown."""


__all__ = [
    "ATTACH_MODE_CONTINUATION",
    "ATTACH_MODE_NATIVE_RESUME",
    "ATTACH_MODES",
    "CAPABILITY_PAUSE",
    "CAPABILITY_RESUME",
    "CAPABILITY_STEERING",
    "HARNESS_CONTRACT_VERSION",
    "OPTIONAL_CAPABILITIES",
    "HarnessContractError",
    "HarnessErrorRecord",
    "HarnessEvent",
    "HarnessIdentity",
    "HarnessLifecycleError",
    "HarnessProposal",
    "HarnessRequirementError",
    "HarnessVersionError",
    "UnsupportedCapabilityError",
]
