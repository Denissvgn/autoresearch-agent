"""Harness SDK: adapters, registry, capability negotiation, conformance.

The verification matrix: conforming and nonconforming fake adapters,
version mismatch, lifecycle ordering, cancelled start, cleanup, unknown
event compatibility, and the honesty rules (unsupported pause is explicit,
kill is never a successful pause, cross-harness continuation is never
claimed as native transcript resume).
"""
from __future__ import annotations

import pytest

from src.core.harness_adapter import (
    HarnessRegistry,
    request_pause,
    request_steer,
    resolve_harness_spec,
    validate_requirements,
)
from src.core.harness_conformance import FakeHarnessAdapter, run_conformance
from src.core.harness_contract import (
    ATTACH_MODE_CONTINUATION,
    ATTACH_MODE_NATIVE_RESUME,
    CAPABILITY_PAUSE,
    CAPABILITY_RESUME,
    CAPABILITY_STEERING,
    HARNESS_CONTRACT_VERSION,
    HarnessContractError,
    HarnessLifecycleError,
    HarnessRequirementError,
    HarnessVersionError,
    UnsupportedCapabilityError,
)


def test_conforming_fake_passes_the_suite():
    plain = FakeHarnessAdapter()
    assert run_conformance(plain) == []
    full = FakeHarnessAdapter(
        capabilities=frozenset(
            {CAPABILITY_PAUSE, CAPABILITY_RESUME, CAPABILITY_STEERING}
        ),
        permissions={"stream": True},
    )
    assert run_conformance(full) == []


@pytest.mark.parametrize(
    ("violation", "expected_finding"),
    [
        ("kill_as_pause", "kill presented as pause"),
        ("native_claim_on_continuation", "native transcript resume"),
        ("no_cleanup", "closed handle"),
        ("events_before_start", "unknown handle"),
    ],
)
def test_nonconforming_fakes_fail_the_specific_check(
    violation, expected_finding
):
    adapter = FakeHarnessAdapter(
        capabilities=frozenset(
            {CAPABILITY_PAUSE, CAPABILITY_RESUME, CAPABILITY_STEERING}
        ),
        violations=frozenset({violation}),
    )
    findings = run_conformance(adapter)
    assert any(expected_finding in finding for finding in findings), findings


def test_capability_lie_is_reported():
    adapter = FakeHarnessAdapter(violations=frozenset({"capability_lie"}))
    findings = run_conformance(adapter)
    assert any("raised" in finding for finding in findings), findings


def test_version_mismatch_is_refused_at_registration():
    adapter = FakeHarnessAdapter(contract_version="autoresearch_harness.v0")
    registry = HarnessRegistry()
    with pytest.raises(HarnessVersionError):
        registry.register(adapter)
    findings = run_conformance(adapter)
    assert any("registration refused" in finding for finding in findings)


def test_lifecycle_ordering_and_cleanup():
    adapter = FakeHarnessAdapter()
    # operations before start are refused
    with pytest.raises(HarnessLifecycleError):
        adapter.cancel("nope")
    started = adapter.start({"run": "r1"})
    handle = started["handle"]
    # cancelled start then close leaves nothing behind
    adapter.cancel(handle)
    adapter.close(handle)
    with pytest.raises(HarnessLifecycleError):
        list(adapter.events(handle))
    # close is idempotent teardown
    adapter.close(handle)


def test_unknown_events_are_tolerated_and_marked():
    adapter = FakeHarnessAdapter(
        events=(
            {"event_id": "e1", "type": "started", "sequence": 1,
             "timestamp": "t", "payload": {}},
            {"event_id": "e2", "type": "telepathy.bloom", "sequence": 2,
             "timestamp": "t", "payload": {"novel": True}, "unknown": True},
        )
    )
    handle = adapter.start({"run": "r"})["handle"]
    events = list(adapter.events(handle))
    assert [event["type"] for event in events] == [
        "started",
        "telepathy.bloom",
    ]
    assert events[1].get("unknown") is True
    adapter.close(handle)


def test_registering_a_new_adapter_needs_no_kernel_branch():
    registry = HarnessRegistry()
    novel = FakeHarnessAdapter(name="brand-new-harness")
    registry.register(novel)
    assert registry.names() == ("brand-new-harness",)
    resolved = registry.resolve("brand-new-harness")
    assert resolved.identity()["name"] == "brand-new-harness"
    with pytest.raises(HarnessContractError):
        registry.resolve("no-such-harness")


def test_unsupported_capabilities_refuse_explicitly():
    adapter = FakeHarnessAdapter()
    handle = adapter.start({"run": "r"})["handle"]
    for request in (
        lambda: request_pause(adapter, handle),
        lambda: request_steer(
            adapter, handle,
            {"proposal_id": "p", "kind": "steer", "target": "run",
             "payload": {}},
        ),
    ):
        with pytest.raises(UnsupportedCapabilityError):
            request()
    # the refusal never touched the run: no kill was substituted
    assert adapter.log == [f"start:{handle}"]
    adapter.close(handle)


def test_adapter_identity_resolves_into_the_run_spec():
    from src.core.run_spec import build_run_spec, verify_run_spec

    adapter = FakeHarnessAdapter(
        name="external-harness",
        version="2.1.0",
        permissions={"stream": True},
        capabilities=frozenset({CAPABILITY_PAUSE}),
    )
    section = resolve_harness_spec(adapter)
    assert section == {
        "name": "external-harness",
        "version": "2.1.0",
        "contract_version": HARNESS_CONTRACT_VERSION,
        "permissions": {"stream": True},
        "capabilities": ["pause"],
    }
    spec = build_run_spec(
        skill_params={"knob": 0.42},
        param_schema=None,
        skill_id="prompt-engineering",
        skill_version="1.0.0",
        skill_dir=None,
        objective_policy={"metric": "auc"},
        policy={},
        effective_config={},
        harness=section,
    )
    assert spec["harness"] == section
    assert verify_run_spec(spec) is True


def test_requirements_are_validated_before_launch():
    adapter = FakeHarnessAdapter(permissions={"stream": True})
    # an unmet capability is refused before any side effect
    with pytest.raises(HarnessRequirementError) as excinfo:
        validate_requirements(adapter, required_capabilities=["pause"])
    assert excinfo.value.missing == {"capabilities": ["pause"]}
    with pytest.raises(HarnessRequirementError) as excinfo:
        resolve_harness_spec(
            adapter,
            required_capabilities=["pause"],
            required_permissions=["promote"],
        )
    assert excinfo.value.missing == {
        "capabilities": ["pause"],
        "permissions": ["promote"],
    }
    # granted requirements resolve normally
    section = resolve_harness_spec(
        adapter, required_permissions=["stream"]
    )
    assert section["name"] == "fake-harness"
    assert adapter.log == []


def test_cross_harness_continuation_is_never_native_resume():
    adapter = FakeHarnessAdapter(name="harness-a")
    # native resume is honest for the same harness
    native = adapter.attach(
        {"run": "r", "mode": ATTACH_MODE_NATIVE_RESUME,
         "origin_harness": "harness-a"}
    )
    assert native["mode"] == ATTACH_MODE_NATIVE_RESUME
    adapter.close(native["handle"])
    # a cross-harness native claim is refused outright
    with pytest.raises(HarnessContractError):
        adapter.attach(
            {"run": "r", "mode": ATTACH_MODE_NATIVE_RESUME,
             "origin_harness": "harness-b"}
        )
    # continuation is the honest cross-harness mode
    continued = adapter.attach(
        {"run": "r", "mode": ATTACH_MODE_CONTINUATION,
         "origin_harness": "harness-b"}
    )
    assert continued["mode"] == ATTACH_MODE_CONTINUATION
    adapter.close(continued["handle"])


def test_cross_harness_native_claim_is_a_conformance_failure():
    adapter = FakeHarnessAdapter(
        name="dishonest",
        violations=frozenset({"native_claim_on_continuation"}),
    )
    findings = run_conformance(adapter)
    assert any(
        "native transcript resume" in finding for finding in findings
    ), findings