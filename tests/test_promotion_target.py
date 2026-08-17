"""Structural / contract tests for the ``PromotionTarget`` protocol (ARC-011
P1-015) and the ``FilePathPromotionTarget`` implementation (P1-016), plus the
P1-017 wiring of ``ConfigPromoter`` to delegate its file-write surface to the
target.

Mirrors ``tests/test_state_store.py`` (P1-009) and ``tests/test_output_parser.py``
(P1-014): these tests pin the public surface of the protocol and guard against
signature drift. The behavioral gate is the existing ``ConfigPromoter`` suite
(``test_config_promoter_gate_bundle.py`` etc.) and the X-002 parity fixture
``promotion_preview/development_scope_basic.json`` — which bakes
``target_path: "<host_configs>/instrument_configs/DOGE_USDT_15m.yaml"``, so the
path-derivation contract is locked.
"""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from src.core.config_promoter import ConfigPromoter
from src.core.promotion_target import FilePathPromotionTarget, PromotionTarget


def test_promotion_target_protocol_is_typing_time_contract():
    """``PromotionTarget`` is a ``Protocol`` and is **not** ``@runtime_checkable``.

    Mirrors the ``LLMProvider`` / ``StateStore`` / ``OutputParser`` decisions:
    ``isinstance`` against a ``Protocol`` only checks attribute presence (false
    confidence on signatures). Typing-time contract only.
    """
    assert issubclass(PromotionTarget, Protocol)
    assert getattr(PromotionTarget, "_is_runtime_protocol", False) is False


def test_promotion_target_protocol_surface_matches_impl():
    """Every method declared on ``PromotionTarget`` exists on
    ``FilePathPromotionTarget`` with matching async-ness (the signature-drift
    guard)."""

    proto_methods = sorted(PromotionTarget.__protocol_attrs__)
    assert proto_methods == [
        "extract_strategy_market",
        "metadata_sidecar_path",
        "rollback_metadata_sidecar_path",
        "rollback_snapshot_path",
        "target_path",
        "write",
    ], f"unexpected PromotionTarget surface: {proto_methods}"

    for name in proto_methods:
        assert hasattr(FilePathPromotionTarget, name), (
            f"FilePathPromotionTarget is missing protocol method {name!r}"
        )
        proto_is_coro = inspect.iscoroutinefunction(
            inspect.getattr_static(PromotionTarget, name)
        )
        impl_is_coro = inspect.iscoroutinefunction(
            inspect.getattr_static(FilePathPromotionTarget, name)
        )
        assert proto_is_coro is impl_is_coro, (
            f"{name}: protocol coro={proto_is_coro}, impl coro={impl_is_coro}"
        )
    # Only ``write`` is async; the path/derivation methods are pure sync.
    assert inspect.iscoroutinefunction(FilePathPromotionTarget.write)
    assert not inspect.iscoroutinefunction(FilePathPromotionTarget.target_path)


def test_minimal_promotion_target_satisfies_protocol():
    """A minimal stub with the six methods satisfies the protocol at the type
    level (structural typing — no inheritance required)."""

    class _Stub:
        def target_path(self, **kw):
            return ""

        def metadata_sidecar_path(self, target_path, iteration, *, scope="development"):
            return ""

        def rollback_snapshot_path(self, *, target_path, research_id, iteration):
            return ""

        def rollback_metadata_sidecar_path(self, target_path, promotion_id):
            return ""

        def extract_strategy_market(self, yaml_str):
            return "BALA", "stock"

        async def write(self, path, content):
            return None

    for name in PromotionTarget.__protocol_attrs__:
        assert hasattr(_Stub, name)


# ---------------------------------------------------------------------------
# Path-derivation parity: the new impl must produce byte-identical strings to
# what the ConfigPromoter @staticmethods produced (locked by the X-002 golden).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_type,instrument,timeframe,expected_suffix",
    [
        ("direction", "DOGE_USDT", "15m", "instrument_configs/DOGE_USDT_15m.yaml"),
        ("volatility", "BTC_USDT", "1h", "instrument_configs/BTC_USDT_1h.yaml"),
        (
            "rl",
            "ETH_USDT",
            "5m",
            "rl/ETH_USDT_5m_BALA_stock_production.yaml",
        ),
    ],
)
def test_target_path_derivation_matches_golden(
    model_type, instrument, timeframe, expected_suffix
):
    """``FilePathPromotionTarget.target_path`` reproduces the exact path string
    the parity golden bakes (``<host_configs>/<expected_suffix>``). ML-67: RL
    includes strategy + market_type in the filename."""
    target = FilePathPromotionTarget()
    result = target.target_path(
        model_type=model_type,
        instrument=instrument,
        timeframe=timeframe,
    )
    assert result.endswith(expected_suffix), f"got {result!r}"


def test_target_path_unknown_model_type_raises():
    """Unknown model_type raises ValueError (mirrors the old _get_target_path)."""
    target = FilePathPromotionTarget()
    with pytest.raises(ValueError):
        target.target_path(
            model_type="unknown",
            instrument="X",
            timeframe="1m",
        )


def test_config_promoter_target_path_delegates_to_impl():
    """``ConfigPromoter(store)._get_target_path`` (default target) produces
    the same string as ``FilePathPromotionTarget().target_path`` — the
    P1-017 delegation is behavior-identical. ARC-011 review C2-5: the helper
    is now an instance method dispatching through ``self._target`` (the
    historical @staticmethod bypassed the injected target)."""
    args = dict(model_type="direction", instrument="DOGE_USDT", timeframe="15m")
    via_promoter = ConfigPromoter(_FakeStore())._get_target_path(  # type: ignore[arg-type]
        args["model_type"], args["instrument"], args["timeframe"],
    )
    via_impl = FilePathPromotionTarget().target_path(**args)
    assert via_promoter == via_impl


class _FakeStore:
    pass


class _RecordingTarget:
    """Records every dispatch; returns fixed values (ARC-011 review C2-5).

    Proves the injected target is actually dispatched through, not just
    stored — the guarantee the P1-017 CHANGELOG entry claimed but no test
    previously pinned (finding H6 in the 2026-08-15 review).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.writes: list[tuple[str, str]] = []

    def target_path(self, **kwargs: object) -> str:
        self.calls.append("target_path")
        return "/recorded/target.yaml"

    def metadata_sidecar_path(self, target_path: str, iteration: int, **kw: object) -> str:
        self.calls.append("metadata_sidecar_path")
        return "/recorded/sidecar.json"

    def rollback_snapshot_path(self, **kwargs: object) -> str:
        self.calls.append("rollback_snapshot_path")
        return "/recorded/rollback.yaml"

    def rollback_metadata_sidecar_path(self, target_path: str, promotion_id: int) -> str:
        self.calls.append("rollback_metadata_sidecar_path")
        return "/recorded/rollback.json"

    def extract_strategy_market(self, yaml_str: str) -> tuple:
        self.calls.append("extract_strategy_market")
        return ("BALA", "stock")

    async def write(self, path: str, content: str) -> None:
        self.calls.append("write")
        self.writes.append((path, content))


def test_config_promoter_dispatches_through_injected_target():
    """H6/C2-5: every historical helper routes through the injected
    ``PromotionTarget``. Before the C2 fix these helpers constructed a fresh
    ``FilePathPromotionTarget()`` inline, so the injection was dead."""
    import asyncio

    target = _RecordingTarget()
    promoter = ConfigPromoter(_FakeStore(), target=target)  # type: ignore[arg-type]

    assert promoter._get_target_path("direction", "X", "15m") == "/recorded/target.yaml"
    assert promoter._metadata_sidecar_path("/any.yaml", 3) == "/recorded/sidecar.json"
    assert promoter._rollback_snapshot_path(
        target_path="/any.yaml", research_id="res_x", iteration=3,
    ) == "/recorded/rollback.yaml"
    assert promoter._rollback_metadata_sidecar_path("/any.yaml", 9) == "/recorded/rollback.json"
    assert promoter._extract_strategy_market("agent_strategy: X") == ("BALA", "stock")
    asyncio.run(promoter._write_text_file("/any.yaml", "content"))

    assert target.calls == [
        "target_path",
        "metadata_sidecar_path",
        "rollback_snapshot_path",
        "rollback_metadata_sidecar_path",
        "extract_strategy_market",
        "write",
    ]
    assert target.writes == [("/any.yaml", "content")]


def test_config_promoter_accepts_injected_target():
    """P1-017: ``ConfigPromoter`` accepts an optional ``target`` and defaults to
    ``FilePathPromotionTarget`` when omitted."""
    # Default — gets FilePathPromotionTarget.
    class _FakeStore:
        pass

    default_promoter = ConfigPromoter(_FakeStore())  # type: ignore[arg-type]
    assert isinstance(default_promoter._target, FilePathPromotionTarget)

    # Injected — keeps the provided target.
    custom = FilePathPromotionTarget()
    injected_promoter = ConfigPromoter(_FakeStore(), target=custom)  # type: ignore[arg-type]
    assert injected_promoter._target is custom


def test_metadata_sidecar_path_shape():
    """``metadata_sidecar_path`` shape: ``<name>.<scope>-promotion.iter-<N>.json``."""
    target = FilePathPromotionTarget()
    result = target.metadata_sidecar_path("/host/configs/instrument_configs/X_15m.yaml", 7)
    assert result.endswith("X_15m.yaml.development-promotion.iter-7.json")


def test_rollback_paths_shape():
    """Rollback snapshot + metadata sidecar shapes match the old statics."""
    target = FilePathPromotionTarget()
    snap = target.rollback_snapshot_path(
        target_path="/c/X_15m.yaml",
        research_id="res_abc123",
        iteration=3,
    )
    assert "development-rollback" in snap and "res_abc123" in snap and "iter-3" in snap

    meta = target.rollback_metadata_sidecar_path("/c/X_15m.yaml", 42)
    assert meta.endswith("X_15m.yaml.development-rollback.promotion-42.json")


def test_extract_strategy_market_defaults_and_parse():
    """``extract_strategy_market`` defaults to ``("BALA", "stock")`` and parses
    a real YAML config string."""
    target = FilePathPromotionTarget()
    assert target.extract_strategy_market("not yaml at all") == ("BALA", "stock")
    parsed = target.extract_strategy_market(
        "agent_strategy: AGGR\nenvironment:\n  trading_mode: margin\n"
    )
    assert parsed == ("AGGR", "margin")


@pytest.mark.asyncio
async def test_write_is_atomic_and_durable(tmp_path):
    """``write`` performs the tmp+fsync+os.replace atomic write and lands the
    content at the target path."""
    target = FilePathPromotionTarget()
    out = tmp_path / "sub" / "out.yaml"
    await target.write(str(out), "hello: world\n")
    assert out.read_text() == "hello: world\n"
