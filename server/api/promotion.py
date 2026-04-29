"""Config promotion endpoints — preview and confirm pushing configs to host."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from server.api.audit import record_api_audit_event
from server.api.auth import require_api_auth

router = APIRouter(prefix="/api", tags=["promotion"], dependencies=[Depends(require_api_auth)])

_promoter = None
_store = None


def init(promoter, store):
    global _promoter, _store
    _promoter = promoter
    _store = store


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


class PromotionRollbackRequest(BaseModel):
    reason: str | None = None


@router.post("/research/{research_id}/promote/preview")
async def promote_preview(request: Request, research_id: str):
    """Dry-run: returns what would change if the best config were promoted."""
    try:
        result = await _promoter.preview(research_id)
        await _audit(
            request,
            action="promotion.preview",
            outcome="success",
            research_id=research_id,
        )
        return result
    except ValueError as e:
        await _audit(
            request,
            action="promotion.preview",
            outcome="failure",
            research_id=research_id,
            error_message=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        await _audit(
            request,
            action="promotion.preview",
            outcome="failure",
            research_id=research_id,
            error_message=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/research/{research_id}/promote/confirm")
async def promote_confirm(request: Request, research_id: str):
    """Write the best config to the host bind mount."""
    try:
        result = await _promoter.confirm(research_id)
        await _audit(
            request,
            action="promotion.confirm",
            outcome="success",
            research_id=research_id,
        )
        return result
    except ValueError as e:
        await _audit(
            request,
            action="promotion.confirm",
            outcome="failure",
            research_id=research_id,
            error_message=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        await _audit(
            request,
            action="promotion.confirm",
            outcome="failure",
            research_id=research_id,
            error_message=str(e),
        )
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        await _audit(
            request,
            action="promotion.confirm",
            outcome="failure",
            research_id=research_id,
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
