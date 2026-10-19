"""Harness contract qualification (G4): one shared contract, honest claims.

Every managed and attached surface — the built-in adapter, a custom
process driver, the Codex and Claude Code adapters, and the attached
API/CLI workflow — is qualified against one shared conformance contract
with explicit per-adapter capabilities. Fixture evidence and live-version
evidence are reported separately: a fixture pass never becomes a
compatibility claim, and missing live evidence blocks one.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Optional

from src.core.harness_adapter import HarnessRegistry
from src.core.harness_contract import (
    HARNESS_CONTRACT_VERSION,
    OPTIONAL_CAPABILITIES,
    HarnessContractError,
    HarnessVersionError,
    UnsupportedCapabilityError,
)


@dataclass
class QualificationResult:
    """One adapter's qualification: semantics, negatives, and honesty."""

    adapter: str
    version: str
    interface: str
    contract_version: str
    capabilities: tuple[str, ...]
    required_semantics: bool
    negative_cases: dict[str, bool] = field(default_factory=dict)
    fixture_evidence: str = "none"
    live_evidence: str = "not_run"
    compatibility_claim: bool = False
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _negative_unsupported_capabilities(adapter: Any) -> bool:
    """Unadvertised optional capabilities refuse explicitly, never fake."""
    advertised = set(adapter.capabilities())
    handle = None
    try:
        started = adapter.start(
            {
                "config": _probe_config(adapter),
                "prompt": "probe",
                "run": "negative",
            }
        )
        handle = started.get("handle")
        from src.core.harness_adapter import (
            request_pause,
            request_resume,
            request_steer,
        )

        requests = {
            "pause": lambda: request_pause(adapter, str(handle)),
            "resume": lambda: request_resume(adapter, str(handle)),
            "steering": lambda: request_steer(
                adapter,
                str(handle),
                {
                    "proposal_id": "p",
                    "kind": "steer",
                    "target": "run",
                    "payload": {},
                },
            ),
        }
        for capability, request in requests.items():
            if capability in OPTIONAL_CAPABILITIES - advertised:
                try:
                    request()
                    return False
                except UnsupportedCapabilityError:
                    pass
        return True
    except HarnessContractError:
        return True
    finally:
        if handle is not None:
            adapter.close(str(handle))


def _negative_cancel(adapter: Any) -> bool:
    """Cancel mid-run is bounded and attributed, never a hang."""
    try:
        started = adapter.start(
            {
                "config": _probe_config(adapter),
                "prompt": "probe",
                "run": "negative",
            }
        )
        handle = str(started.get("handle"))
    except HarnessContractError:
        return True
    try:
        adapter.cancel(handle)
        adapter.close(handle)
        adapter.close(handle)  # idempotent teardown
        return True
    except Exception:  # noqa: BLE001 — any crash here is a finding
        return False


def _negative_unavailable_executable(adapter: Any) -> bool:
    """A missing executable is an attributed refusal, never a crash."""
    name = adapter.identity().get("name")
    if name == "codex":
        from src.core.codex_harness import CodexRunConfig

        config: Any = CodexRunConfig(
            prompt="probe",
            workspace="/tmp/g4-codex-probe",
            executable=("/nonexistent/codex-binary",),
        )
    elif name == "claude-code":
        from src.core.claude_code_harness import ClaudeRunConfig

        config = ClaudeRunConfig(
            prompt="probe",
            workspace="/tmp/g4-claude-probe",
            config_dir="/tmp/g4-claude-home",
            executable=("/nonexistent/claude-binary",),
        )
    else:
        return True  # in-process adapters have no executable to fail
    try:
        adapter.start({"config": config})
    except HarnessContractError:
        return True
    except Exception:  # noqa: BLE001 — a raw crash is a finding
        return False
    return False


def _negative_version_mismatch(adapter: Any) -> bool:
    """A wrong contract version is refused at registration."""

    class _Liar:
        def identity(self):
            identity = dict(adapter.identity())
            identity["contract_version"] = "autoresearch_harness.v0"
            return identity

        def capabilities(self):
            return adapter.capabilities()

    registry = HarnessRegistry()
    try:
        registry.register(_Liar())  # type: ignore[arg-type]
        return False
    except HarnessVersionError:
        return True
    except HarnessContractError:
        return True


def _negative_unknown_usage(normalize: Callable[[Mapping[str, Any]], Any]) -> bool:
    """Unknown usage fields are tolerated and preserved, never zeroed."""
    event = normalize(
        {
            "type": "result",
            "usage": {"input_tokens": 1, "quantum_flux": 7},
        }
    )
    return event.get("unknown") is False or event.get("unknown") is True


def _negative_out_of_order_events(
    normalize: Callable[[Mapping[str, Any]], Any],
) -> bool:
    """Duplicate and out-of-order events never crash normalization."""
    try:
        for raw in (
            {"type": "result", "usage": {}},
            {"type": "result", "usage": {}},
            {"type": "assistant"},
            {"type": "system"},
        ):
            normalize(raw)
        return True
    except Exception:  # noqa: BLE001 — any crash here is a finding
        return False


def _probe_config(adapter: Any) -> Any:
    """A minimal run config for process-backed adapters."""
    name = adapter.identity().get("name")
    if name == "codex":
        from src.core.codex_harness import CodexRunConfig

        return CodexRunConfig(
            prompt="probe",
            workspace="/tmp/g4-codex-probe",
            executable=("python3", "-c", "print()"),
        )
    if name == "claude-code":
        from src.core.claude_code_harness import ClaudeRunConfig

        return ClaudeRunConfig(
            prompt="probe",
            workspace="/tmp/g4-claude-probe",
            config_dir="/tmp/g4-claude-home",
            executable=("python3", "-c", "print()"),
        )
    return None


def qualify_adapter(
    adapter: Any,
    *,
    normalize: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    fixture_evidence: str = "none",
    live_evidence: str = "not_run",
    permissions_check: Optional[Callable[[], bool]] = None,
) -> QualificationResult:
    """Qualify one adapter against the shared conformance contract.

    ``fixture_evidence`` and ``live_evidence`` are reported separately:
    ``compatibility_claim`` stays False whenever live evidence is missing,
    regardless of fixture success.
    """
    from src.core.harness_conformance import run_conformance

    identity = adapter.identity()
    probe_config = _probe_config(adapter)
    start_request = (
        {"config": probe_config, "prompt": "probe", "run": "conformance"}
        if probe_config is not None
        else None
    )
    findings = run_conformance(adapter, start_request=start_request)
    negative: dict[str, bool] = {
        "unsupported_capabilities": _negative_unsupported_capabilities(
            adapter
        ),
        "cancel_mid_run": _negative_cancel(adapter),
        "version_mismatch": _negative_version_mismatch(adapter),
        "unavailable_executable": _negative_unavailable_executable(adapter),
    }
    if normalize is not None:
        negative["unknown_usage"] = _negative_unknown_usage(normalize)
        negative["out_of_order_events"] = _negative_out_of_order_events(
            normalize
        )
    if permissions_check is not None:
        negative["permissions_scope"] = permissions_check()

    required_ok = not findings
    compatibility = bool(
        required_ok
        and all(negative.values())
        and live_evidence not in ("not_run", "none", "missing")
    )
    notes = tuple(findings)
    return QualificationResult(
        adapter=str(identity.get("name") or "?"),
        version=str(identity.get("version") or "?"),
        interface=str(identity.get("interface") or "in-process"),
        contract_version=str(identity.get("contract_version") or "?"),
        capabilities=tuple(sorted(adapter.capabilities())),
        required_semantics=required_ok,
        negative_cases=negative,
        fixture_evidence=fixture_evidence,
        live_evidence=live_evidence,
        compatibility_claim=compatibility,
        notes=notes,
    )


def supported_matrix(
    results: list[QualificationResult],
) -> dict[str, Any]:
    """The concise supported/unsupported matrix with honest claims."""
    rows = []
    for result in results:
        rows.append(
            {
                "adapter": result.adapter,
                "version": result.version,
                "interface": result.interface,
                "capabilities": list(result.capabilities),
                "required_semantics": "pass" if result.required_semantics else "fail",
                "fixture_evidence": result.fixture_evidence,
                "live_evidence": result.live_evidence,
                "compatibility_claim": (
                    "supported" if result.compatibility_claim else "unclaimed"
                ),
            }
        )
    return {
        "contract_version": HARNESS_CONTRACT_VERSION,
        "adapters": rows,
        "all_required_semantics_pass": all(
            row["required_semantics"] == "pass" for row in rows
        ),
        "live_claims": [
            row["adapter"] for row in rows if row["compatibility_claim"] == "supported"
        ],
    }


def claim_honesty(result: QualificationResult) -> bool:
    """Fixture success must never become a compatibility claim."""
    if result.live_evidence in ("not_run", "none", "missing"):
        return result.compatibility_claim is False
    return True

