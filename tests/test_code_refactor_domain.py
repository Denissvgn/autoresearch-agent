"""The code-refactor domain: real test/lint/type evidence over bundles.

Verification covers valid and invalid refactor fixtures, test deletion
and skip attempts, timeouts, dependency failures, and artifact-bound
promotion previews. Performance claims exist only with a controlled
benchmark; a required-but-unmeasured gate is rejected.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.code_evaluator import (
    CandidateBundle,
    EvalRequirements,
    apply_bundle,
    evaluate_bundle,
    is_protected,
    promotion_preview,
)

FIXTURE_PROJECT = (
    Path(__file__).resolve().parent / "fixtures" / "refactor_project"
)

EXPECTED_TESTS = (
    "test_line_total_multiplies",
    "test_line_total_zero_quantity",
    "test_apply_discount",
    "test_order_total_applies_discount_then_tax",
    "test_order_total_without_discount_is_taxed",
)

REQUIREMENTS = EvalRequirements(expected_tests=EXPECTED_TESTS)


def _bundle(candidate_id, files):
    return CandidateBundle(candidate_id=candidate_id, files=files)


def test_valid_multifile_refactor_passes_all_gates(tmp_path):
    # a behavior-preserving multi-file refactor: internals change, the
    # expected text of the protected tests is untouched
    bundle = _bundle(
        "valid-refactor",
        {
            "calc/pricing.py": (
                '"""Small pricing library: the fixture project\'s '
                'first module."""\n\n\n'
                "def line_total(unit_price: float, quantity: int) -> float:\n"
                '    """The total for one order line: unit price times '
                'quantity."""\n'
                "    total = 0.0\n"
                "    for _ in range(quantity):\n"
                "        total += unit_price\n"
                "    return total\n\n\n"
                "def apply_discount(total: float, percent: float) -> float:\n"
                '    """Apply a percentage discount to a total."""\n'
                "    factor = 1.0 - percent / 100.0\n"
                "    return total * factor\n"
            ),
            "calc/totals.py": (
                '"""Order totals: the fixture project\'s second module."""\n\n'
                "from calc.pricing import apply_discount, line_total\n\n"
                "TAX_RATE = 0.08\n\n\n"
                "def order_total(lines, discount_percent: float = 0.0)"
                " -> float:\n"
                '    """The total for an order: line totals, discount, then '
                'tax."""\n'
                "    subtotal = 0.0\n"
                "    for unit, qty in lines:\n"
                "        subtotal += line_total(unit, qty)\n"
                "    discounted = apply_discount(subtotal, discount_percent)\n"
                "    return discounted * (1.0 + TAX_RATE)\n"
            ),
        },
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, REQUIREMENTS, workdir=tmp_path / "work"
    )
    assert report.passed is True, report.as_dict()
    assert report.tests["passed"] == len(EXPECTED_TESTS)
    assert report.lint_ok is True
    assert report.type_ok is True
    assert report.exit_codes["tests"] == 0


def test_semantics_breaking_refactor_fails_even_with_expected_text(tmp_path):
    # all strings and docstrings preserved, but zero-quantity semantics
    # break: the fixed tests catch it — text needles would not
    bundle = _bundle(
        "semantics-break",
        {
            "calc/pricing.py": (
                '"""Small pricing library: the fixture project\'s '
                'first module."""\n\n\n'
                "def line_total(unit_price: float, quantity: int) -> float:\n"
                '    """The total for one order line: unit price times '
                'quantity."""\n'
                "    return unit_price * max(quantity, 1)\n\n\n"
                "def apply_discount(total: float, percent: float) -> float:\n"
                '    """Apply a percentage discount to a total."""\n'
                "    return total * (1.0 - percent / 100.0)\n"
            ),
        },
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, REQUIREMENTS, workdir=tmp_path / "work"
    )
    assert report.passed is False
    assert report.tests["failed"] >= 1
    assert any("test_line_total_zero_quantity" in f for f in report.failures)


def test_editing_test_files_cannot_improve_the_result(tmp_path):
    # deleting and skipping tests are both reverted: the expected set runs
    bundle = _bundle(
        "test-tamper",
        {
            "calc/pricing.py": (
                "def line_total(unit_price, quantity):\n"
                "    return unit_price * max(quantity, 1)\n\n\n"
                "def apply_discount(total, percent):\n"
                "    return total * (1.0 - percent / 100.0)\n"
            ),
            "tests/test_behavior.py": "def test_nothing():\n    pass\n",
            "conftest.py": "collect_ignore = ['tests/test_behavior.py']\n",
        },
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, REQUIREMENTS, workdir=tmp_path / "work"
    )
    # the protected edits were reverted, and the broken semantics still fail
    assert "tests/test_behavior.py" in report.protected_edits_reverted
    assert "conftest.py" in report.protected_edits_reverted
    assert report.passed is False
    assert report.tests["missing"] == 0
    assert report.tests["failed"] >= 1


def test_skip_injection_is_reverted_not_counted_as_pass(tmp_path):
    bundle = _bundle(
        "skip-injection",
        {
            "tests/test_behavior.py": (
                "import pytest\n\npytestmark = pytest.mark.skip\n"
            ),
        },
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, REQUIREMENTS, workdir=tmp_path / "work"
    )
    assert report.protected_edits_reverted == ("tests/test_behavior.py",)
    # the untouched tests run and pass; a skip is never manufactured
    assert report.passed is True, report.as_dict()
    assert report.tests["skipped"] == 0
    assert report.tests["passed"] == len(EXPECTED_TESTS)


def test_timeout_is_bounded_and_attributed(tmp_path):
    bundle = _bundle(
        "hang",
        {
            "calc/pricing.py": (
                "def line_total(unit_price, quantity):\n"
                "    while True:\n"
                "        pass\n\n\n"
                "def apply_discount(total, percent):\n"
                "    return total\n"
            ),
        },
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT,
        bundle,
        REQUIREMENTS,
        workdir=tmp_path / "work",
        timeout_s=5.0,
    )
    assert report.passed is False
    assert report.exit_codes["tests"] == 124
    assert any("timeout" in f for f in report.failures)


def test_dependency_failure_is_reported(tmp_path):
    bundle = _bundle(
        "broken-import",
        {
            "calc/totals.py": (
                "import nonexistent_module_xyz\n\n\n"
                "def order_total(lines, discount_percent=0.0):\n"
                "    return 0.0\n"
            ),
        },
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, REQUIREMENTS, workdir=tmp_path / "work"
    )
    assert report.passed is False
    assert (
        report.exit_codes.get("collect") != 0
        or report.exit_codes.get("tests") != 0
    )


def test_performance_gate_requires_a_controlled_benchmark(tmp_path):
    bundle = _bundle("perf", {})
    # a required-but-unmeasured performance gate is a rejection
    required = EvalRequirements(
        expected_tests=EXPECTED_TESTS, performance_required=True
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, required, workdir=tmp_path / "work"
    )
    assert report.passed is False
    assert any("unmeasured" in f for f in report.failures)
    assert report.performance is None
    # with a controlled benchmark the gate is measured, not claimed
    measured = EvalRequirements(
        expected_tests=EXPECTED_TESTS,
        performance_required=True,
        performance_benchmark="order-total-2000",
        performance_budget_s=30.0,
    )
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, measured, workdir=tmp_path / "work"
    )
    assert report.passed is True, report.as_dict()
    assert report.performance["benchmark"] == "order-total-2000"
    assert report.performance["within_budget"] is True


def test_promotion_preview_is_bound_to_the_artifact(tmp_path):
    bundle = _bundle("promote-me", {})
    report = evaluate_bundle(
        FIXTURE_PROJECT, bundle, REQUIREMENTS, workdir=tmp_path / "work"
    )
    assert report.passed is True
    preview = promotion_preview(bundle=bundle, report=report)
    assert preview["bundle_digest"] == bundle.digest()
    assert preview["snapshot"] == "promoted exactly as evaluated"
    # a mutated bundle can never ride the earlier report
    mutated = _bundle("promote-me", {"calc/pricing.py": "x = 1\n"})
    with pytest.raises(ValueError):
        promotion_preview(bundle=mutated, report=report)
    # an unpassed evaluation never previews promotion
    broken = _bundle(
        "broken",
        {"calc/pricing.py": "def line_total(a, b):\n    raise RuntimeError\n"
                            "\n\ndef apply_discount(t, p):\n    return t\n"},
    )
    broken_report = evaluate_bundle(
        FIXTURE_PROJECT, broken, REQUIREMENTS, workdir=tmp_path / "work2"
    )
    assert broken_report.passed is False
    with pytest.raises(ValueError):
        promotion_preview(bundle=broken, report=broken_report)


def test_protected_paths_and_unsafe_targets():
    assert is_protected("tests/test_behavior.py") is True
    assert is_protected("conftest.py") is True
    assert is_protected("eval/run.py") is True
    assert is_protected("calc/pricing.py") is False
    bundle = _bundle("unsafe", {"../escape.py": "x = 1\n"})
    with pytest.raises(ValueError):
        apply_bundle(FIXTURE_PROJECT, bundle, Path("/tmp/unsafe-work"))