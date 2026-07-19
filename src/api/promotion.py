"""Config promotion endpoints — preview and confirm pushing configs to host."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, model_validator

from src.api.audit import record_api_audit_event
from src.api.auth import require_api_auth
from src.config import secret_value, settings

router = APIRouter(tags=["promotion"], dependencies=[Depends(require_api_auth)])

_promoter = None
_store = None
#: P3-017: skill registry injected by main.py so preview/confirm results can
#: carry ``target_kind`` from the session's skill manifest.
_registry: Any = None


def init(promoter, store, *, skill_registry: Any = None):
    """Wire the promoter, store, and optional skill registry (P3-017)."""
    global _promoter, _store, _registry
    _promoter = promoter
    _store = store
    if skill_registry is not None:
        _registry = skill_registry


def reset() -> None:
    """Clear all module globals to their uninitialised state.

    Test-only: prevents module-global state (``_promoter``/``_store``/
    ``_registry``) set by one suite from leaking into another. Production
    never un-wires a service once its lifespan has started. Mirrors the
    ``reset()`` pattern in ``ui/src/skill-plugins/registry.ts`` (same
    Phase-3 vintage).
    """
    global _promoter, _store, _registry
    _promoter = None
    _store = None
    _registry = None


async def _audit(
    request: Request,
    *,
    action: str,
    outcome: str,
    research_id: str | None = None,
    metadata: dict | None = None,
    error_message: str | None = None,
):
    return await record_api_audit_event(
        request,
        _store,
        action=action,
        outcome=outcome,
        research_id=research_id,
        metadata=metadata,
        error_message=error_message,
    )


def _inject_target_kind(result: Dict[str, Any]) -> Dict[str, Any]:
    """P3-017: add ``target_kind`` to a promotion preview/confirm result.

    Derives the promotion target kind from the session's skill manifest so the
    UI PromotionModal can branch generically (``file_path`` vs ``registry_api``
    vs ``git_branch`` …). Additive — existing fields are never overwritten.
    When the skill is unknown or the registry is not wired, defaults to
    ``file_path`` (the incumbent ML target) so behavior is unchanged for legacy
    sessions.
    """
    if not isinstance(result, dict) or result.get("target_kind"):
        return result
    skill_id = result.get("skill_id") or ""
    if not skill_id:
        model_type = result.get("model_type") or ""
        if model_type:
            from src.core.legacy_alias import model_type_to_skill_id

            skill_id = model_type_to_skill_id(model_type)
    if skill_id and _registry is not None:
        try:
            manifest = _registry.get(skill_id)
            result["target_kind"] = manifest.promotion_target.primary.kind
            return result
        except Exception:
            pass  # fall through to default
    result.setdefault("target_kind", "file_path")
    return result


class PromotionRollbackRequest(BaseModel):
    reason: str | None = None


class PromotionApproval(BaseModel):
    approver: str | None = None
    reason: str | None = None
    method: str | None = None
    signature: str | None = None
    approved: bool | None = None


class PromotionScopeRequest(BaseModel):
    scope: str = "development"
    approval: PromotionApproval | None = None

    @model_validator(mode="after")
    def _enforce_production_approval(self) -> "PromotionScopeRequest":
        """Phase 3.2: production scope requires a complete signed approval.

        A production promotion is irreversible from the operator's view —
        it overwrites the active config that live trading consumes — so we
        refuse the request unless the caller provides ``approved=True``
        plus a non-empty ``approver``, ``signature``, and ``method`` so the
        audit log has full provenance.
        """
        if (self.scope or "").lower() != "production":
            return self
        approval = self.approval
        missing: list[str] = []
        if approval is None:
            missing.append("approval")
        else:
            if approval.approved is not True:
                missing.append("approval.approved=true")
            for field_name in ("approver", "signature", "method"):
                value = getattr(approval, field_name, None)
                if not (isinstance(value, str) and value.strip()):
                    missing.append(f"approval.{field_name}")
        if missing:
            raise ValueError(
                "Production-scope promotion requires a signed approval; "
                f"missing or invalid: {', '.join(missing)}"
            )
        return self


def _approval_payload(approval: PromotionApproval | None) -> dict | None:
    if approval is None:
        return None
    if hasattr(approval, "model_dump"):
        return approval.model_dump(exclude_none=True)
    return approval.dict(exclude_none=True)


# W18 / P0-020: canonical message over which the approval HMAC signature is
# computed. The operator (or UI) signs this exact string keyed by the
# production_approval_verifier secret; the server re-derives and compares.
_PRODUCTION_APPROVAL_MESSAGE_TEMPLATE = "{research_id}:{scope}:{approver}"


def _verify_production_approval_signature(
    research_id: str,
    payload: PromotionScopeRequest,
) -> None:
    """Cryptographically verify the production approval signature (W18).

    Layered AFTER ``PromotionScopeRequest._enforce_production_approval`` which
    guarantees ``approval`` is present with non-empty ``approver``/``signature``
    for ``scope=production``. Raises ``ValueError`` on (a) verifier unset
    (fail-closed) or (b) signature mismatch, so the existing handler branch
    maps it to HTTP 400 and records an audit failure.
    """
    verifier = secret_value(settings.production_approval_verifier)
    if not verifier:
        raise ValueError(
            "production approval verifier is not configured "
            "(AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER)"
        )
    approval = payload.approval
    # The structural validator guarantees approval is present with non-empty
    # approver/signature for scope=production; this guard exists for type
    # safety and defense-in-depth (it is unreachable in normal flow).
    if approval is None or not approval.approver or not approval.signature:
        raise ValueError("production approval is missing required fields")
    message = _PRODUCTION_APPROVAL_MESSAGE_TEMPLATE.format(
        research_id=research_id,
        scope=payload.scope,
        approver=approval.approver,
    ).encode("utf-8")
    expected = hmac.new(
        verifier.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    provided = approval.signature.strip()
    if not hmac.compare_digest(expected, provided):
        raise ValueError("production approval signature rejected")


def _confirm_audit_metadata(payload: PromotionScopeRequest) -> dict[str, Any]:
    """Metadata recorded in the ``promotion.confirm`` audit event (W18 / AC #4).

    ``actor_id`` (the authenticated API caller's identity) is written
    automatically by ``record_api_audit_event``; this records the *named human
    approver* from the request body so the audit row carries full provenance.
    """
    metadata: dict[str, Any] = {"scope": payload.scope}
    if payload.approval is not None:
        metadata["approver"] = payload.approval.approver
        metadata["approval_method"] = payload.approval.method
    return metadata


@router.post("/research/{research_id}/promote/preview")
async def promote_preview(
    request: Request,
    research_id: str,
    payload: PromotionScopeRequest | None = None,
):
    """Dry-run: returns what would change if the best config were promoted."""
    payload = payload or PromotionScopeRequest()
    approval = _approval_payload(payload.approval)
    try:
        result = await _promoter.preview(
            research_id,
            scope=payload.scope,
            approval=approval,
        )
        await _audit(
            request,
            action="promotion.preview",
            outcome="success",
            research_id=research_id,
            metadata={"scope": payload.scope},
        )
        return _inject_target_kind(result)
    except ValueError as e:
        await _audit(
            request,
            action="promotion.preview",
            outcome="failure",
            research_id=research_id,
            metadata={"scope": payload.scope},
            error_message=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        await _audit(
            request,
            action="promotion.preview",
            outcome="failure",
            research_id=research_id,
            metadata={"scope": payload.scope},
            error_message=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/research/{research_id}/promote/confirm")
async def promote_confirm(
    request: Request,
    research_id: str,
    payload: PromotionScopeRequest | None = None,
):
    """Write the best config to the host bind mount."""
    payload = payload or PromotionScopeRequest()
    approval = _approval_payload(payload.approval)
    audit_metadata = _confirm_audit_metadata(payload)
    try:
        # W18 / P0-020: production-scope promotions must carry an approval
        # signature that cryptographically verifies against the configured
        # HMAC verifier. Other scopes are unaffected.
        if (payload.scope or "").lower() == "production":
            _verify_production_approval_signature(research_id, payload)
        result = await _promoter.confirm(
            research_id,
            scope=payload.scope,
            approval=approval,
        )
        await _audit(
            request,
            action="promotion.confirm",
            outcome="success",
            research_id=research_id,
            metadata=audit_metadata,
        )
        return _inject_target_kind(result)
    except ValueError as e:
        await _audit(
            request,
            action="promotion.confirm",
            outcome="failure",
            research_id=research_id,
            metadata=audit_metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        await _audit(
            request,
            action="promotion.confirm",
            outcome="failure",
            research_id=research_id,
            metadata=audit_metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        await _audit(
            request,
            action="promotion.confirm",
            outcome="failure",
            research_id=research_id,
            metadata=audit_metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/promotions")
async def list_promotions():
    """History of all config promotions."""
    return await _store.list_promotions()


@router.post("/promotions/{model_type}/{instrument}/{timeframe}/rollback")
async def rollback_development_promotion(
    http_request: Request,
    model_type: str,
    instrument: str,
    timeframe: str,
    request: PromotionRollbackRequest = PromotionRollbackRequest(),
):
    """Restore the latest development config for an instrument/timeframe."""
    metadata = {
        "model_type": model_type,
        "instrument": instrument,
        "timeframe": timeframe,
        "reason_supplied": request.reason is not None,
    }
    try:
        result = await _promoter.rollback(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            reason=request.reason,
        )
        await _audit(
            http_request,
            action="promotion.rollback",
            outcome="success",
            metadata=metadata,
        )
        return result
    except ValueError as e:
        await _audit(
            http_request,
            action="promotion.rollback",
            outcome="failure",
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
