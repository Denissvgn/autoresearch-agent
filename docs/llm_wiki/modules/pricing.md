# pricing Module

**Path:** `tests/fixtures/refactor_project/calc/pricing.py`

## Description

Small pricing library: the fixture project's first module.

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `line_total` | `(unit_price: float, quantity: int) -> float` | — | The total for one order line: unit price times quantity. |
| `apply_discount` | `(total: float, percent: float) -> float` | — | Apply a percentage discount to a total. |
