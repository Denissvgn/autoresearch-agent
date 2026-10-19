"""Order totals: the fixture project's second module."""

from calc.pricing import apply_discount, line_total

TAX_RATE = 0.08


def order_total(lines, discount_percent: float = 0.0) -> float:
    """The total for an order: line totals, discount, then tax."""
    subtotal = sum(line_total(unit, qty) for unit, qty in lines)
    discounted = apply_discount(subtotal, discount_percent)
    return discounted * (1.0 + TAX_RATE)
