"""Harness capability descriptors, provenance, and usage context.

The UI renders harness selection, capability/preflight diagnostics, and
run views from these descriptors — never from branches on a harness
name. Unsupported controls carry explicit reasons, unknown cost is
visibly unknown, and lifecycle actions stay consistent with server
authorization (operator or scoped credential).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from src.core.harness_adapter import HarnessRegistry
from src.core.harness_contract import OPTIONAL_CAPABILITIES

router = APIRouter()

_registry: Optional[HarnessRegistry] = None
_store: Any = None
_credential_key: Optional[str] = None


def build_default_registry() -> HarnessRegistry:
    """The harnesses this service hosts — registering needs no name branch."""
    from src.core.builtin_harness import BuiltinHarnessAdapter
    from src.core.claude_code_harness import ClaudeCodeHarnessAdapter
    from src.core.codex_harness import CodexHarnessAdapter

    registry = HarnessRegistry()
    registry.register(BuiltinHarnessAdapter())
    registry.register(CodexHarnessAdapter())
    registry.register(ClaudeCodeHarnessAdapter())
    return registry


def init(
    session_manager: Any,
    store: Any,
    *,
    registry: Optional[HarnessRegistry] = None,
    credential_key: Optional[str] = None,
) -> None:
    global _registry, _store, _credential_key
    _store = store
    _registry = registry or build_default_registry()
    _credential_key = credential_key


def _key() -> str:
    if _credential_key:
        return _credential_key
    from src.config import secret_value, settings

    fallback = secret_value(settings.autoresearch_api_token) or "dev-key"
    return f"agent-credential:{fallback}"


def _descriptor(adapter: Any) -> Dict[str, Any]:
    identity = dict(adapter.identity())
    capabilities = sorted(adapter.capabilities())
    preflight_fn = getattr(adapter, "preflight", None)
    if callable(preflight_fn):
        preflight = preflight_fn()
    else:
        preflight = {
            "checks": [
                {
                    "name": "identity",
                    "status": "unknown",
                    "detail": "the adapter exposes no preflight probe",
                }
            ]
        }
    unsupported = [
        {
            "capability": capability,
            "reason": (
                "not advertised by this harness; the SDK refuses it "
                "explicitly instead of substituting another operation"
            ),
        }
        for capability in sorted(OPTIONAL_CAPABILITIES - set(capabilities))
    ]
    return {
        "name": identity.get("name"),
        "version": identity.get("version"),
        "contract_version": identity.get("contract_version"),
        "interface": identity.get("interface"),
        "schema_pin": identity.get("schema_pin"),
        "capabilities": capabilities,
        "unsupported_capabilities": unsupported,
        "attach_modes": identity.get("attach_modes"),
        "resume_mode": identity.get("resume_mode"),
        "permissions": identity.get("permissions"),
        "preflight": preflight,
    }


@router.get("/harnesses")
async def list_harnesses() -> Dict[str, Any]:
    """Capability descriptors for every registered harness."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="harness registry is not initialized")
    return {
        "harnesses": [_descriptor(_registry.resolve(name)) for name in _registry.names()],
    }


@router.get("/harnesses/{name}")
async def get_harness(name: str) -> Dict[str, Any]:
    if _registry is None:
        raise HTTPException(status_code=503, detail="harness registry is not initialized")
    try:
        adapter = _registry.resolve(name)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"no harness named {name!r}"
        ) from None
    return _descriptor(adapter)


async def _viewer(request: Request) -> Dict[str, Any]:
    """The caller's effective permissions: scoped credential or operator."""
    from src.core.scoped_credentials import (
        ScopedAuthError,
        verify_scoped_credential,
    )

    header = request.headers.get("authorization") or ""
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if token:
        try:
            principal = verify_scoped_credential(token, key=_key())
        except ScopedAuthError:
            principal = None
        except Exception:
            principal = None
        if principal is not None:
            return {
                "kind": "scoped",
                "subject": getattr(principal, "subject", "scoped"),
                "permissions": sorted(getattr(principal, "permissions", ())),
            }
    return {
        "kind": "operator",
        "subject": "operator",
        "permissions": ["read", "submit", "evaluate", "lifecycle", "promote"],
    }


def _lifecycle_actions(
    descriptor: Dict[str, Any], viewer: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Supported lifecycle actions: capability- and permission-aware."""
    capabilities = set(descriptor.get("capabilities") or [])
    permissions = set(viewer.get("permissions") or [])
    actions: List[Dict[str, Any]] = []
    for action, capability, permission in (
        ("pause", "pause", "lifecycle"),
        ("resume", "resume", "lifecycle"),
        ("stop", None, "lifecycle"),
        ("promote", None, "promote"),
    ):
        if capability is not None and capability not in capabilities:
            actions.append(
                {
                    "action": action,
                    "enabled": False,
                    "reason": (
                        f"this harness does not advertise {capability!r}; "
                        "the control is refused explicitly, never substituted"
                    ),
                }
            )
        elif permission not in permissions:
            actions.append(
                {
                    "action": action,
                    "enabled": False,
                    "reason": (
                        f"the caller's credential lacks {permission!r}"
                    ),
                }
            )
        else:
            actions.append({"action": action, "enabled": True, "reason": ""})
    return actions


@router.get("/research/{research_id}/harness-context")
async def research_harness_context(
    research_id: str, request: Request
) -> Dict[str, Any]:
    """Run-bound view: harness, evidence authority, usage quality, resume."""
    if _store is None or _registry is None:
        raise HTTPException(status_code=503, detail="harnesses API is not initialized")
    viewer = await _viewer(request)

    # the harness bound to the run (recorded at creation; builtin default)
    harness_name = "builtin"
    resume_mode = "not_attached"
    candidate_context: Dict[str, Any] = {}
    try:
        events = await _store.list_events(stream_key=research_id)
    except Exception:
        events = []
    for event in events:
        payload = dict(event.get("payload") or {})
        if payload.get("harness"):
            harness_name = str(payload["harness"])
        if payload.get("attach_mode"):
            resume_mode = str(payload["attach_mode"])
        if payload.get("evaluator"):
            candidate_context["evaluator"] = payload["evaluator"]
        if payload.get("candidate_digest"):
            candidate_context["candidate_digest"] = payload["candidate_digest"]

    try:
        descriptor = _descriptor(_registry.resolve(harness_name))
    except Exception:
        descriptor = {
            "name": harness_name,
            "capabilities": [],
            "unsupported_capabilities": [
                {
                    "capability": cap,
                    "reason": "the bound harness is not registered here",
                }
                for cap in sorted(OPTIONAL_CAPABILITIES)
            ],
            "preflight": {
                "checks": [
                    {
                        "name": "identity",
                        "status": "missing",
                        "detail": f"no registered harness named {harness_name!r}",
                    }
                ]
            },
        }

    authority_counts = {
        "receipt_verified": 0,
        "nonce_only": 0,
        "unverified_imported": 0,
        "model_proposed": 0,
    }
    try:
        rows = await _store.get_iterations(research_id)
    except Exception:
        rows = []
    for row in rows:
        label = row.get("result_authority")
        if not label:
            try:
                marker = json.loads(row.get("metrics_json") or "{}")
            except Exception:
                marker = {}
            label = marker.get("result_authority")
        if not label:
            label = "model_proposed"
        authority_counts[label] = authority_counts.get(label, 0) + 1

    cost_known_usd = 0.0
    unknown_cost_events = 0
    total_events = 0
    try:
        usage_rows = await _store.get_usage_events(research_id)
    except Exception:
        usage_rows = []
    for row in usage_rows:
        total_events += 1
        cost = row.get("cost_usd")
        cost_status = row.get("cost_status")
        if cost is None or cost_status == "unavailable":
            unknown_cost_events += 1
        else:
            cost_known_usd += float(cost)

    return {
        "research_id": research_id,
        "harness": descriptor,
        "resume_mode": resume_mode,
        "evidence": {
            "authority_counts": authority_counts,
            "verified": authority_counts.get("receipt_verified", 0) > 0,
            "imported": authority_counts.get("unverified_imported", 0),
        },
        "candidate_evaluator_context": candidate_context
        or {"evaluator": None, "note": "no evaluator context recorded"},
        "usage_quality": {
            "cost_known_usd": cost_known_usd,
            "cost_unknown_events": unknown_cost_events,
            "total_usage_events": total_events,
            "cost_status": (
                ("partial" if unknown_cost_events else "known")
                if total_events
                else "unknown"
            ),
        },
        "viewer": viewer,
        "lifecycle": {"actions": _lifecycle_actions(descriptor, viewer)},
    }