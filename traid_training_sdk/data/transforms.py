from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


def map_rows(df, fn: Callable[[dict[str, Any]], dict[str, Any]]):
    import pandas as pd  # type: ignore

    rows = (fn(row._asdict() if hasattr(row, "_asdict") else row.to_dict()) for _, row in df.iterrows())
    return pd.DataFrame(rows)


def compose(*fns: Callable[[Any], Any]) -> Callable[[Any], Any]:
    def _inner(x: Any) -> Any:
        for fn in fns:
            x = fn(x)
        return x

    return _inner


def batch(iterable: Iterable[Any], size: int) -> Iterable[list[Any]]:
    buf: list[Any] = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf

