"""Tests for BatchedDataIngestClient.fetch_ohlcv (finding #9 fix).

A bare ``fetch_ohlcv(limit=N)`` must fetch only the most recent N bars via the server's
single-shot ``latest`` mode — not paginate the whole history and then ``.head(N)`` (which
returned the *oldest* N). When the server doesn't support ``latest`` it falls back to the
range walk and returns ``.tail(N)``.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

_DC_ROOT = Path(__file__).resolve().parents[1]  # libs/data_clients
if str(_DC_ROOT) not in sys.path:
    sys.path.insert(0, str(_DC_ROOT))

import pandas as pd
import pytest

from data_clients.batched_ingest_client import BatchedDataIngestClient


def _df(n: int, start: str = "2020-01-01") -> pd.DataFrame:
    ts = pd.date_range(start, periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "close": range(n)})


@pytest.mark.asyncio
async def test_limit_uses_latest_mode_and_returns_newest(monkeypatch):
    client = BatchedDataIngestClient(base_url="http://data-ingest:8000")
    src = _df(500)
    seen = {}

    async def fake_page(symbol, timeframe="15m", cursor=None, batch_size=None,
                        start_date=None, end_date=None, latest=False):
        seen["latest"] = latest
        seen["batch_size"] = batch_size
        return src.tail(batch_size).reset_index(drop=True), None, False, {"latest": True}

    async def fake_all(*a, **k):
        raise AssertionError("fetch_all must not be called on the latest fast-path")

    monkeypatch.setattr(client, "fetch_page", fake_page)
    monkeypatch.setattr(client, "fetch_all", fake_all)

    df, meta = await client.fetch_ohlcv("BTC/USDT", "15m", limit=120)

    assert seen["latest"] is True
    assert seen["batch_size"] >= 100
    assert len(df) == 120
    assert meta["mode"] == "latest"
    assert df["timestamp"].iloc[-1] == src["timestamp"].iloc[-1]  # newest, not oldest


@pytest.mark.asyncio
async def test_small_limit_clamps_batch_then_tails(monkeypatch):
    client = BatchedDataIngestClient(base_url="http://data-ingest:8000")
    src = _df(500)

    async def fake_page(symbol, timeframe="15m", cursor=None, batch_size=None,
                        start_date=None, end_date=None, latest=False):
        assert batch_size == 100  # clamped up from 50 (server requires >= 100)
        return src.tail(batch_size).reset_index(drop=True), None, False, {"latest": True}

    monkeypatch.setattr(client, "fetch_page", fake_page)
    df, _meta = await client.fetch_ohlcv("BTC/USDT", "15m", limit=50)
    assert len(df) == 50
    assert df["timestamp"].iloc[-1] == src["timestamp"].iloc[-1]


@pytest.mark.asyncio
async def test_falls_back_when_server_ignores_latest(monkeypatch):
    client = BatchedDataIngestClient(base_url="http://data-ingest:8000")
    src = _df(500)

    async def fake_page(symbol, timeframe="15m", cursor=None, batch_size=None,
                        start_date=None, end_date=None, latest=False):
        # Old server: ignores 'latest', returns the first (oldest) page, no 'latest' meta.
        return src.head(batch_size).reset_index(drop=True), "cursor", True, {"source_used": "storage"}

    async def fake_all(symbol, timeframe="15m", start_date=None, end_date=None):
        return src

    monkeypatch.setattr(client, "fetch_page", fake_page)
    monkeypatch.setattr(client, "fetch_all", fake_all)

    df, meta = await client.fetch_ohlcv("BTC/USDT", "15m", limit=120)
    assert len(df) == 120
    assert meta.get("mode") != "latest"  # fell back to the walk
    assert df["timestamp"].iloc[-1] == src["timestamp"].iloc[-1]  # tail, not head


@pytest.mark.asyncio
async def test_explicit_range_skips_latest_and_tails(monkeypatch):
    client = BatchedDataIngestClient(base_url="http://data-ingest:8000")
    src = _df(500)
    page_called = {"v": False}

    async def fake_page(*a, **k):
        page_called["v"] = True
        return pd.DataFrame(), None, False, {}

    async def fake_all(symbol, timeframe="15m", start_date=None, end_date=None):
        return src

    monkeypatch.setattr(client, "fetch_page", fake_page)
    monkeypatch.setattr(client, "fetch_all", fake_all)

    df, _meta = await client.fetch_ohlcv(
        "BTC/USDT", "15m", limit=120, start_date=datetime(2020, 1, 1),
    )
    assert page_called["v"] is False  # explicit range → no latest fast-path
    assert len(df) == 120
    assert df["timestamp"].iloc[-1] == src["timestamp"].iloc[-1]  # tail
