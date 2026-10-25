# test_behavior Module

**Path:** `tests/fixtures/refactor_project/tests/test_behavior.py`

## Description

Protected behavior tests: the fixed expected test set.

These tests are the fixture project's trusted evaluation surface. They
are protected from candidate mutation: a candidate cannot delete, skip,
or edit them to improve its result.

## Imports

| Source | Symbols |
|--------|---------|
| `calc.pricing` | `apply_discount`, `line_total` |
| `calc.totals` | `order_total` |

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
| `test_line_total_multiplies` | `()` | — | — |
| `test_line_total_zero_quantity` | `()` | — | — |
| `test_apply_discount` | `()` | — | — |
| `test_order_total_applies_discount_then_tax` | `()` | — | — |
| `test_order_total_without_discount_is_taxed` | `()` | — | — |
