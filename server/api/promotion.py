"""Config promotion endpoints — preview and confirm pushing configs to host."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["promotion"])

_promoter = None
_store = None


def init(promoter, store):
    global _promoter, _store
    _promoter = promoter
    _store = store


class PromotionRollbackRequest(BaseModel):
    reason: str | None = None


@router.post("/research/{research_id}/promote/preview")
async def promote_preview(research_id: str):
    """Dry-run: returns what would change if the best config were promoted."""
    try:
        return await _promoter.preview(research_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/research/{research_id}/promote/confirm")
async def promote_confirm(research_id: str):
    """Write the best config to the host bind mount."""
    try:
        return await _promoter.confirm(research_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/promotions")
async def list_promotions():
    """History of all config promotions."""
    return await _store.list_promotions()


@router.post("/promotions/{model_type}/{instrument}/{timeframe}/rollback")
async def rollback_development_promotion(
    model_type: str,
    instrument: str,
    timeframe: str,
    request: PromotionRollbackRequest = PromotionRollbackRequest(),
):
    """Restore the latest development config for an instrument/timeframe."""
    try:
        return await _promoter.rollback(
            model_type=model_type,
            instrument=instrument,
            timeframe=timeframe,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
