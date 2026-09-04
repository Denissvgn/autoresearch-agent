"""
Batched Data Ingest Client — shared library for paginated OHLCV access.

ARC-016: Replaces the per-service ad-hoc HTTP clients with a single,
well-tested library that all ML consumers share.  Supports three access
patterns:

* ``fetch_all()``      — auto-paginate, return concatenated DataFrame
* ``iter_batches()``   — async generator yielding one DataFrame per page
* ``fetch_page()``     — manual single-page fetch
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, Mapping, Optional, Tuple

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────

DEFAULT_BASE_URL: str = "http://data-ingest:8000"
DEFAULT_BATCH_SIZE: int = 10_000
DEFAULT_TIMEOUT: float = 60.0
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_BACKOFF: float = 1.0


# ── Exceptions ────────────────────────────────────────────────────

class BatchedIngestError(Exception):
    """Base exception for batched ingest client errors."""


class BatchedIngestConnectionError(BatchedIngestError):
    """Connection to data-ingest failed after all retries."""


class BatchedIngestDataNotFoundError(BatchedIngestError):
    """Requested symbol/timeframe has no data in storage."""


class BatchedIngestCursorExpiredError(BatchedIngestError):
    """Cursor expired server-side — restart pagination."""


# ── Client ────────────────────────────────────────────────────────


class BatchedDataIngestClient:
    """
    Shared, paginated HTTP client for ``POST /ohlcv/batched``.

    Provides three access patterns so each consumer can pick the best fit:

    1. **fetch_all**   — convenience wrapper; auto-paginates and returns a
       single ``pd.DataFrame``.  Still materialises the full dataset in the
       *consumer's* memory, but never in *data-ingest's* memory.
    2. **iter_batches** — async generator that yields one ``DataFrame`` per
       page.  Ideal for streaming feature computation or chunked writes.
    3. **fetch_page**  — low-level, returns ``(df, next_cursor, has_more)``
       for fully manual iteration.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        headers: Optional[Mapping[str, str]] = None,
        headers_factory: Optional[Callable[[], Mapping[str, str]]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._headers = dict(headers or {})
        self._headers_factory = headers_factory
        logger.info(
            "BatchedDataIngestClient initialised: url=%s batch=%d",
            self._base_url, self._batch_size,
        )

    # ── High-level: fetch everything ──────────────────────────────

    async def fetch_all(
        self,
        symbol: str,
        timeframe: str = "15m",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        batch_size: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Auto-paginate through all batches and return a single DataFrame.

        This still materialises the full dataset in the consumer's process
        memory, but each page request is bounded — preventing data-ingest
        from OOMing.

        Returns:
            Concatenated DataFrame of all pages (empty if no data).
        """
        chunks: list[pd.DataFrame] = []
        async for batch_df in self.iter_batches(
            symbol, timeframe, start_date, end_date, batch_size,
        ):
            chunks.append(batch_df)
        if not chunks:
            return pd.DataFrame()
        return pd.concat(chunks, ignore_index=True)

    # ── Mid-level: async generator ────────────────────────────────

    async def iter_batches(
        self,
        symbol: str,
        timeframe: str = "15m",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        batch_size: Optional[int] = None,
    ) -> AsyncGenerator[pd.DataFrame, None]:
        """
        Async generator yielding one ``pd.DataFrame`` per page.

        The consumer controls back-pressure by their iteration rate::

            async for batch in client.iter_batches("BTC/USDT", "1m"):
                features = compute_features(batch)
                save_features(features)
        """
        cursor: Optional[str] = None
        page = 0
        while True:
            page += 1
            df, next_cursor, has_more, _meta = await self.fetch_page(
                symbol=symbol,
                timeframe=timeframe,
                cursor=cursor,
                batch_size=batch_size,
                start_date=start_date,
                end_date=end_date,
            )
            if not df.empty:
                yield df
            if not has_more:
                break
            cursor = next_cursor

    # ── Low-level: single page ────────────────────────────────────

    async def fetch_page(
        self,
        symbol: str,
        timeframe: str = "15m",
        cursor: Optional[str] = None,
        batch_size: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        latest: bool = False,
    ) -> Tuple[pd.DataFrame, Optional[str], bool, Dict[str, Any]]:
        """
        Fetch a single page from ``POST /ohlcv/batched``.

        With ``latest=True`` (first-page only) the server returns the most recent
        ``batch_size`` rows in one page (no cursor) — avoiding a full-history walk.

        Returns:
            ``(data_df, next_cursor, has_more, metadata)``
        """
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "batch_size": batch_size or self._batch_size,
        }
        if cursor is not None:
            payload["cursor"] = cursor
        if start_date is not None:
            payload["start_date"] = start_date.isoformat()
        if end_date is not None:
            payload["end_date"] = end_date.isoformat()
        if latest:
            payload["latest"] = True

        resp_json = await self._request_with_retry(payload)

        # Parse response
        success = resp_json.get("success", False)
        pagination = resp_json.get("pagination", {})
        metadata = resp_json.get("metadata", {})

        if not success:
            records = resp_json.get("data")
            if not records:
                raise BatchedIngestDataNotFoundError(
                    resp_json.get("message", "No data returned")
                )

        records = resp_json.get("data") or []
        df = pd.DataFrame(records)

        # Ensure timestamp is datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        next_cursor = pagination.get("cursor")
        has_more = pagination.get("has_more", False)

        return df, next_cursor, has_more, metadata

    # ── Legacy-compatible convenience method ──────────────────────

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Drop-in replacement for the old ``DataIngestClient.fetch_ohlcv()``.

        Returns ``(DataFrame, metadata)`` — identical signature to the
        ensemble-trainer's existing client.
        """
        # Fast path: when only a row ``limit`` is requested (no explicit date range), ask
        # data-ingest for the most recent N bars in a single page instead of paginating the
        # entire history and then slicing. This avoids the O(history) over-fetch — and the
        # old ``.head(limit)`` bug, which returned the *oldest* N rows rather than the latest.
        if limit is not None and start_date is None and end_date is None:
            try:
                df, _cursor, _has_more, meta = await self.fetch_page(
                    symbol=symbol,
                    timeframe=timeframe,
                    batch_size=max(int(limit), 100),  # server requires batch_size >= 100
                    latest=True,
                )
                # Only trust the fast path if the server actually honoured "latest"
                # (older data-ingest ignores the flag → fall back to the legacy walk).
                if meta.get("latest"):
                    if not df.empty and len(df) > limit:
                        df = df.tail(limit).reset_index(drop=True)
                    return df, {
                        "source_used": "storage",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "rows_fetched": len(df),
                        "mode": "latest",
                    }
            except BatchedIngestDataNotFoundError:
                return pd.DataFrame(), {
                    "source_used": "storage", "symbol": symbol,
                    "timeframe": timeframe, "rows_fetched": 0, "mode": "latest",
                }
            except Exception as exc:  # pragma: no cover — network/server quirks
                logger.debug("latest-mode fetch failed (%s); falling back to range walk", exc)

        df = await self.fetch_all(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        metadata: Dict[str, Any] = {
            "source_used": "storage",
            "symbol": symbol,
            "timeframe": timeframe,
            "rows_fetched": len(df),
        }
        # Honour limit if caller specified one — keep the most recent N (``.tail``), not the
        # oldest (the previous ``.head`` returned stale bars from the start of history).
        if limit is not None and len(df) > limit:
            df = df.tail(limit).reset_index(drop=True)
            metadata["rows_fetched"] = limit
            metadata["truncated"] = True
        return df, metadata

    def fetch_ohlcv_sync(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Synchronous wrapper for ``fetch_ohlcv`` — for non-async callers.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.fetch_ohlcv(symbol, timeframe, limit, start_date, end_date),
                )
                return future.result()
        except RuntimeError:
            return asyncio.run(
                self.fetch_ohlcv(symbol, timeframe, limit, start_date, end_date)
            )

    # ── Internal HTTP layer ───────────────────────────────────────

    async def _request_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST to ``/ohlcv/batched`` with retries on transport errors."""
        url = f"{self._base_url}/ohlcv/batched"
        last_error: Optional[Exception] = None
        headers = self._build_headers()

        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers,
                    )

                    if response.status_code == 410:
                        raise BatchedIngestCursorExpiredError(
                            "Cursor expired server-side. Restart pagination."
                        )
                    if response.status_code == 400:
                        data = response.json()
                        raise BatchedIngestError(
                            data.get("detail", response.text)
                        )
                    if response.status_code >= 500:
                        raise BatchedIngestError(
                            f"Server error {response.status_code}: {response.text[:300]}"
                        )

                    response.raise_for_status()
                    return response.json()  # type: ignore[no-any-return]

            except (BatchedIngestCursorExpiredError, BatchedIngestDataNotFoundError):
                raise  # non-retryable
            except httpx.ConnectError as exc:
                last_error = BatchedIngestConnectionError(
                    f"Connection failed (attempt {attempt}/{self._max_retries}): {exc}"
                )
                logger.warning(str(last_error))
            except httpx.TimeoutException as exc:
                last_error = BatchedIngestConnectionError(
                    f"Timeout (attempt {attempt}/{self._max_retries}): {exc}"
                )
                logger.warning(str(last_error))
            except BatchedIngestError:
                raise
            except Exception as exc:
                last_error = BatchedIngestError(f"Unexpected error: {exc}")
                logger.warning(
                    "Attempt %d/%d failed: %s", attempt, self._max_retries, exc,
                )

            # Exponential back-off between retries
            if attempt < self._max_retries:
                import asyncio
                await asyncio.sleep(self._retry_backoff * (2 ** (attempt - 1)))

        if last_error:
            raise last_error
        raise BatchedIngestError("All retry attempts exhausted")

    def _build_headers(self) -> Dict[str, str]:
        """Build outbound request headers, including caller-provided platform headers."""
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        headers.update(self._headers)
        if self._headers_factory is not None:
            headers.update(dict(self._headers_factory() or {}))
        return headers
