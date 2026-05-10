# PromotionScopeRequest

**Location:** `src/api/promotion.py:55`
**Bases:** `BaseModel`
**Module:** [promotion](../modules/promotion.md)

## Description

_Auto-generated from `PromotionScopeRequest` in `src/api/promotion.py`._

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `scope` | `str` | `'development'` | — |
| `approval` | `PromotionApproval | None` | `None` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `_enforce_production_approval` | `() -> 'PromotionScopeRequest'` | `@model_validator(mode='after')` | Phase 3.2: production scope requires a complete signed approval. |

## Relationships

- **imported_by**: [test_hardening_phase1_to_5](../modules/test_hardening_phase1_to_5.md)
