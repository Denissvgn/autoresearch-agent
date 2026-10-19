"""Protected behavior tests: the fixed expected test set.

These tests are the fixture project's trusted evaluation surface. They
are protected from candidate mutation: a candidate cannot delete, skip,
or edit them to improve its result.
"""

from calc.pricing import apply_discount, line_total
from calc.totals import order_total


def test_line_total_multiplies():
    assert line_total(2.5, 4) == 10.0


def test_line_total_zero_quantity():
    assert line_total(2.5, 0) == 0.0


def test_apply_discount():
    assert apply_discount(100.0, 10.0) == 90.0


def test_order_total_applies_discount_then_tax():
    # (2*10 + 3*5) = 35, minus 10% = 31.5, plus 8% tax
    assert order_total([(10.0, 2), (5.0, 3)], discount_percent=10.0) == (
        35.0 * 0.9 * 1.08
    )


def test_order_total_without_discount_is_taxed():
    assert order_total([(10.0, 1)]) == 10.8
