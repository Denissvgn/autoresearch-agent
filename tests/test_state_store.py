"""Structural / contract tests for the ``StateStore`` protocol (ARC-011
P1-006) and the ``SQLiteStateStore`` implementation (P1-007).

Mirrors ``tests/test_llm_provider.py`` (P1-005): these tests pin the public
surface of the protocol and guard against signature drift between the protocol
declaration and the concrete implementation. They are not behavioral tests —
behavior is covered by the existing ``ResultsStore`` suite (which now exercises
``SQLiteStateStore`` via the back-compat alias) and the X-002 parity fixtures.
"""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from src.core.results_store import ResultsStore
from src.core.state_store import SQLiteStateStore, StateStore


def test_state_store_protocol_is_typing_time_contract():
    """``StateStore`` is a ``Protocol`` and is **not** ``@runtime_checkable``.

    Mirrors the ``LLMProvider`` decision (``llm_provider.py`` docstring):
    ``isinstance`` against a ``Protocol`` only checks attribute presence (false
    confidence on signatures). This is a typing-time contract; consumers accept
    it as a typed parameter. A regression here (e.g. adding
    ``@runtime_checkable``) would signal an unintended contract change.
    """
    assert issubclass(StateStore, Protocol)
    # @runtime_checkable sets _is_runtime_protocol = True on the class.
    assert getattr(StateStore, "_is_runtime_protocol", False) is False


def test_state_store_protocol_surface_matches_sqlite_impl():
    """Every method declared on ``StateStore`` exists on ``SQLiteStateStore``.

    This is the signature-drift guard: it catches a future method rename/add on
    one side but not the other. ``connection()`` is intentionally absent from
    the protocol (it leaks ``aiosqlite.Connection``); it is asserted present on
    the impl only.
    """

    proto_methods = sorted(StateStore.__protocol_attrs__)
    assert proto_methods, "expected StateStore to declare methods"
    # The protocol mirrors 48 of the 49 public methods (connection() excluded)
    # + the 2 ARC-011 P6-003 cross-process-lock methods (session_lock,
    # bump_session_epoch).
    assert len(proto_methods) == 71, f"expected 71 protocol methods, got {len(proto_methods)}"
    assert "connection" not in proto_methods  # excluded — leaks backend type

    for name in proto_methods:
        assert hasattr(SQLiteStateStore, name), (
            f"SQLiteStateStore is missing protocol method {name!r}"
        )
        # Every protocol method is async; the impl must match (a silent
        # sync->async flip would break callers that `await` the result).
        # ``session_lock`` is an @asynccontextmanager (decorated async
        # generator) — awaited via ``async with``, not a plain coroutine.
        proto_is_coro = inspect.iscoroutinefunction(getattr(StateStore, name))
        impl_is_coro = inspect.iscoroutinefunction(getattr(SQLiteStateStore, name))
        if name == "session_lock":
            # session_lock is an @asynccontextmanager on the impl — a decorated
            # async generator (not itself an asyncgenfunction after decoration,
            # but callable + returns an async CM). Just assert presence +
            # callability; the async-CM contract is exercised by
            # test_state_machine (transition acquires it).
            assert callable(getattr(SQLiteStateStore, name)), (
                f"SQLiteStateStore.{name} must be callable"
            )
            continue
        assert proto_is_coro is impl_is_coro is True, (
            f"{name}: protocol coro={proto_is_coro}, impl coro={impl_is_coro}"
        )

    # connection() lives on the impl but not the protocol (backend-specific).
    # It's an @asynccontextmanager (decorated async generator) — present and
    # callable, but not a plain coroutine function, which is why it's excluded
    # from the protocol surface.
    assert callable(getattr(SQLiteStateStore, "connection", None))


def test_minimal_state_store_satisfies_protocol():
    """Executable documentation of the contract.

    Not ``isinstance`` (the protocol is not ``@runtime_checkable``); instead we
    assert a minimal concrete stub can be assigned the ``StateStore`` type and
    exposes a representative method with the expected runtime shape (awaitable).
    Mirrors ``test_llm_provider.test_minimal_provider_satisfies_protocol``.
    """

    class _MinimalStateStore:
        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def ping(self) -> bool:
            return True

        async def get_session(self, session_id):  # type: ignore[no-untyped-def]
            return {"session_id": session_id}

        async def add_iteration(self, **kwargs):  # type: ignore[no-untyped-def]
            return {"iteration": kwargs.get("iteration")}

        async def record_audit_event(self, **kwargs):  # type: ignore[no-untyped-def]
            return {"action": kwargs.get("action")}

    store: StateStore = _MinimalStateStore()  # typing-time assignment
    assert inspect.iscoroutinefunction(store.initialize)
    assert inspect.iscoroutinefunction(store.ping)


def test_results_store_alias_is_same_class_object():
    """The back-compat alias binds to the **same** class object, not a subclass.

    This is load-bearing: ``tests/conftest.py`` monkeypatches
    ``ResultsStore.initialize`` at the class level to track instances for
    teardown. If ``ResultsStore`` were a subclass (or a wrapper), that patch
    would not reach the instances created elsewhere as ``SQLiteStateStore``,
    silently leaking SQLite connections across tests. A regression here would
    manifest as flaky resource-exhaustion failures, so it is pinned explicitly.
    """
    assert ResultsStore is SQLiteStateStore, (
        "ResultsStore must be the same class object as SQLiteStateStore "
        "(import ... as), not a subclass or wrapper"
    )
    # Sanity: the class still carries the historical name in its qualname
    # (Python preserves the def-site name under `import ... as`).
    assert SQLiteStateStore.__name__ == "SQLiteStateStore"
