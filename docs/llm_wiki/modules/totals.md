# totals Module

**Path:** `tests/fixtures/refactor_project/calc/totals.py`

## Description

Order totals: the fixture project's second module.

## Imports

| Source | Symbols |
|--------|---------|
| `calc.pricing` | `apply_discount`, `line_total` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `order_total` | `(lines, discount_percent: float = 0.0) -> float` | — | The total for an order: line totals, discount, then tax. |
