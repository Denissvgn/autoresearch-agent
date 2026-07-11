"""Structural / contract tests for the ``OutputParser`` protocol (ARC-011
P1-010) and the ``DelimitedKVParser`` / ``JSONMarkerParser`` implementations
(P1-011 / P1-012).

Mirrors ``tests/test_state_store.py`` (P1-009) and ``tests/test_llm_provider.py``
(P1-005): these tests pin the public surface of the protocol and guard against
signature drift between the protocol declaration and the concrete
implementations. They are not behavioral tests — behavior is covered by the
existing ``experiment_parser`` suite and the X-002 parity fixtures
(``tests/parity/experiment_parser/``), which dispatch by string function name
through the ``experiment_parser`` facades that now delegate to these classes.
"""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from src.core.output_parser import (
    DelimitedKVParser,
    IterationResult,
    JSONMarkerParser,
    OutputParser,
)


def test_output_parser_protocol_is_typing_time_contract():
    """``OutputParser`` is a ``Protocol`` and is **not** ``@runtime_checkable``.

    Mirrors the ``LLMProvider`` / ``StateStore`` decisions: ``isinstance``
    against a ``Protocol`` only checks attribute presence (false confidence on
    signatures). This is a typing-time contract; consumers accept it as a typed
    parameter. A regression here (e.g. adding ``@runtime_checkable``) would
    signal an unintended contract change.
    """
    assert issubclass(OutputParser, Protocol)
    # @runtime_checkable sets _is_runtime_protocol = True on the class.
    assert getattr(OutputParser, "_is_runtime_protocol", False) is False


@pytest.mark.parametrize(
    "impl",
    [DelimitedKVParser, JSONMarkerParser],
    ids=["DelimitedKVParser", "JSONMarkerParser"],
)
def test_output_parser_impl_satisfies_protocol_surface(impl):
    """Every method declared on ``OutputParser`` exists on the impl.

    This is the signature-drift guard: it catches a future method rename/add on
    one side but not the other. Both methods are non-async (the parsers are
    pure-CPU synchronous scans).
    """
    proto_methods = sorted(OutputParser.__protocol_attrs__)
    assert proto_methods == ["parse", "parse_iteration"], (
        f"unexpected OutputParser surface: {proto_methods}"
    )

    for name in proto_methods:
        assert hasattr(impl, name), f"{impl.__name__} is missing protocol method {name!r}"
        proto_fn = inspect.getattr_static(OutputParser, name)
        impl_fn = inspect.getattr_static(impl, name)
        # Both protocol methods are non-async; the impl must match.
        assert not inspect.iscoroutinefunction(proto_fn)
        assert not inspect.iscoroutinefunction(impl_fn), (
            f"{impl.__name__}.{name}: unexpectedly async"
        )


def test_minimal_output_parser_satisfies_protocol():
    """A minimal stub with the two methods satisfies the protocol at the type
    level (structural typing — no inheritance required)."""

    class _Stub:
        def parse(self, raw_output):
            return None

        def parse_iteration(self, text, *, session_nonce=None, config_snapshot=None):
            return None

    # The protocol is typing-time; the stub structurally matches.
    assert hasattr(_Stub, "parse")
    assert hasattr(_Stub, "parse_iteration")


def test_iteration_result_is_typeddict_alias_of_flat_dict():
    """``IterationResult`` is a ``TypedDict`` alias over the flat dict shape
    ``IterationMetrics.to_dict()`` produces. It must not force a dataclass
    construction — callers keep using ``dict.get(...)`` and mutation."""

    sample: IterationResult = {
        "status": "completed",
        "primary_metric": 0.5868,
        "metric_name": "walkforward_mean_auc",
        "direction": "higher_is_better",
        "training_gates_passed": True,
        "all_gates_passed": True,
        "training_time_s": 342.1,
    }
    # TypedDict is a plain dict at runtime — .get() and mutation work.
    assert sample.get("status") == "completed"
    assert sample["primary_metric"] == 0.5868
    sample["extra_key"] = "value"  # splatted extras land at top level
    assert sample["extra_key"] == "value"


def test_delimited_kv_parser_parse_returns_flat_dict_shape():
    """``DelimitedKVParser.parse`` returns the same flat-dict shape
    ``parse_prepare_output(...).to_dict()`` produced (the seven canonical fields
    plus splatted extras). Behavioral parity is gated by the parity fixtures;
    this asserts the *shape* contract the protocol promises."""

    block = (
        "---\n"
        "status: completed\n"
        "primary_metric: 0.5868\n"
        "metric_name: walkforward_mean_auc\n"
        "direction: higher_is_better\n"
        "training_gates_passed: true\n"
        "all_gates_passed: true\n"
        "training_time_s: 342.1\n"
        "sharpe_cv: 0.18\n"
        "---\n"
    )
    result = DelimitedKVParser().parse(block)
    assert result is not None
    assert result["status"] == "completed"
    assert result["primary_metric"] == 0.5868
    assert result["training_gates_passed"] is True
    # Splatted extra (sharpe_cv) lands at the top level, matching to_dict().
    assert result["sharpe_cv"] == 0.18


def test_delimited_kv_parser_failure_status_nulls_primary_metric():
    """The FAILURE_STATUSES primary_metric nulling survives the extraction
    (load-bearing: a failed run's placeholder 0.0 must not masquerade as a
    result). Mirrors the test_rl_phase_tracing.py assertion."""

    block = (
        "---\n"
        "status: timeout\n"
        "primary_metric: 0.000000\n"
        "---\n"
    )
    result = DelimitedKVParser().parse(block)
    assert result is not None
    assert result["primary_metric"] is None


def test_json_marker_parser_parse_iteration_returns_dict_or_none():
    """``JSONMarkerParser.parse_iteration`` returns the parsed dict on a
    well-formed marker and ``None`` when no marker is present. Behavioral parity
    (scan-past-malformed, gate-alias normalization) is gated by the parity
    fixtures."""

    parser = JSONMarkerParser()
    good = 'ITERATION_RESULT: {"iteration": 1, "primary_metric": 0.5}'
    result = parser.parse_iteration(good)
    assert result is not None
    assert result["iteration"] == 1

    absent = "no marker here\njust narrative text"
    assert parser.parse_iteration(absent) is None


def test_json_marker_parser_parse_marker_is_alias_of_parse_iteration():
    """The historical ``parse_marker`` name is an alias for
    ``parse_iteration`` (the facade ``experiment_parser.parse_iteration_marker``
    delegates through it)."""
    parser = JSONMarkerParser()
    text = 'ITERATION_RESULT: {"iteration": 2}'
    assert parser.parse_marker(text) == parser.parse_iteration(text)


def test_json_marker_parser_ignores_session_nonce():
    """``parse_iteration`` accepts ``session_nonce`` for forward-compat (the P4
    anti-forgery hook) but the transitional parser ignores it — passing a nonce
    does not change the result (no nonce validation exists today)."""

    parser = JSONMarkerParser()
    text = 'ITERATION_RESULT: {"iteration": 1}'
    without = parser.parse_iteration(text)
    with_nonce = parser.parse_iteration(text, session_nonce=b"deadbeef")
    assert without == with_nonce
