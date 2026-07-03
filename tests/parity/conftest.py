"""pytest configuration for the ARC-011 parity suite.

Registers the ``parity`` marker so ``-m parity`` selects the suite and
``--strict-markers`` (if ever enabled) does not reject it.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "parity: golden-output parity fixtures (ARC-011 X-002)",
    )
