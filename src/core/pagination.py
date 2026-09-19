"""Opaque keyset-cursor pagination helpers (ARC-011 P0-015..019).

Provides the cursor contract shared by the list endpoints on
``ResultsStore`` (sessions / iterations / pipelines) and the API layer.

Design: ARC-011 P0-016 (recorded in this module's docstring). The cursor is an opaque
base64url token wrapping a versioned JSON tuple ``(sort_key, tiebreak)``. The
``sort_key`` is a value that sorts the same way lexicographically / numerically
as the column indexed by the keyset (an ISO-8601 UTC timestamp ``started_at``
for sessions/pipelines, or an integer ``iteration`` for iterations). The
``tiebreak`` is a stable, unique value per row — the explicit ``id`` primary
key (the implicit ``rowid`` is not indexable in the target SQLite build, so we
use ``id``; for ``iterations`` ``id`` is the INTEGER PK ≡ rowid, for
sessions/pipelines it is the TEXT PK). The tiebreak makes ordering deterministic
when two rows share a sort key.

Decode is **fail-open**: any malformed, truncated, or wrong-version token
decodes to ``None`` so the caller treats it as page 1 rather than erroring.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

_CURSOR_VERSION = 1
CursorTuple = Tuple[Any, Any]
RowExtractor = Callable[[Mapping[str, Any]], CursorTuple]


def clamp_limit(limit: Optional[int]) -> int:
    """Clamp a caller-supplied limit to ``[1, MAX_PAGE_SIZE]``.

    ``None`` (caller omitted it) resolves to ``DEFAULT_PAGE_SIZE``. The store
    layer calls this too so it never trusts an API-layer bound.
    """

    if limit is None or limit <= 0:
        return DEFAULT_PAGE_SIZE
    if limit > MAX_PAGE_SIZE:
        return MAX_PAGE_SIZE
    return int(limit)


def encode_cursor(sort_key: Any, tiebreak: Any) -> str:
    """Encode a ``(sort_key, tiebreak)`` tuple into an opaque base64url token."""

    payload = {"v": _CURSOR_VERSION, "k": sort_key, "r": tiebreak}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: Optional[str]) -> Optional[CursorTuple]:
    """Decode an opaque cursor token.

    Returns ``(sort_key, tiebreak)`` or ``None`` for a missing / malformed /
    wrong-version token. Never raises — callers treat ``None`` as page 1.
    """

    if not token:
        return None
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8")
        payload = json.loads(decoded)
        if not isinstance(payload, dict):
            return None
        if int(payload.get("v", 0)) != _CURSOR_VERSION:
            return None
        sort_key = payload.get("k")
        tiebreak = payload.get("r")
        if sort_key is None or tiebreak is None:
            return None
        if not isinstance(tiebreak, (str, int, float)):
            return None
        return (sort_key, tiebreak)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def compute_next_cursor(
    items: Sequence[Mapping[str, Any]],
    limit: int,
    extractor: RowExtractor,
) -> Optional[str]:
    """Return the opaque cursor for the next page, or ``None`` when exhausted.

    A cursor is produced only when the page is full (``len(items) >= limit``) —
    a short final page means the collection is exhausted.
    """

    if len(items) >= limit and items:
        sort_key, tiebreak = extractor(items[-1])
        return encode_cursor(sort_key, tiebreak)
    return None


def build_cursor_page(
    items: Sequence[Mapping[str, Any]],
    limit: int,
    extractor: RowExtractor,
) -> Dict[str, Any]:
    """Build a cursor-paginated envelope ``{items, limit, next_cursor}``.

    ``next_cursor`` is derived from the last item only when the page is full
    (``len(items) >= limit``) — a short final page means the collection is
    exhausted and the cursor is ``None``.
    """

    return {
        "items": list(items),
        "limit": limit,
        "next_cursor": compute_next_cursor(items, limit, extractor),
    }