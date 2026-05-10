# promotion Module

**Path:** `src/api/promotion.py`

## Description

Config promotion endpoints — preview and confirm pushing configs to host.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `fastapi` | `APIRouter`, `Depends`, `HTTPException`, `Request` |
| `pydantic` | `BaseModel`, `model_validator` |
| `src.api.audit` | `record_api_audit_event` |
| `src.api.auth` | `require_api_auth` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [PromotionRollbackRequest](../entities/PromotionRollbackRequest.md) | 43 | `BaseModel` | — |
| [PromotionApproval](../entities/promotion_PromotionApproval.md) | 47 | `BaseModel` | — |
| [PromotionScopeRequest](../entities/promotion_PromotionScopeRequest.md) | 55 | `BaseModel` | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `init` | `(promoter, store)` | — | — |
| `_audit` | `*(async)* (request: Request)` | — | — |
| `_approval_payload` | `(approval: PromotionApproval | None) -> dict | None` | — | — |
| `promote_preview` | `*(async)* (request: Request, research_id: str, payload: PromotionScopeRequest | None = None)` | `@router.post('/research/{research_id}/promote/preview')` | Dry-run: returns what would change if the best config were promoted. |
| `promote_confirm` | `*(async)* (request: Request, research_id: str, payload: PromotionScopeRequest | None = None)` | `@router.post('/research/{research_id}/promote/confirm')` | Write the best config to the host bind mount. |
| `list_promotions` | `*(async)* ()` | `@router.get('/promotions')` | History of all config promotions. |
| `rollback_development_promotion` | `*(async)* (http_request: Request, model_type: str, instrument: str, timeframe: str, request: PromotionRollbackRequest = PromotionRollbackRequest(...))` | `@router.post('/promotions/{model_type}/{instrument}/{timeframe}/rollback')` | Restore the latest development config for an instrument/timeframe. |
