"""Small pricing library: the fixture project's first module."""


def line_total(unit_price: float, quantity: int) -> float:
    """The total for one order line: unit price times quantity."""
    return unit_price * quantity


def apply_discount(total: float, percent: float) -> float:
    """Apply a percentage discount to a total."""
    return total * (1.0 - percent / 100.0)
