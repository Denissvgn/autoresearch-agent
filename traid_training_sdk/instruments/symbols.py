from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_TIMEFRAME_ALIASES: dict[str, str] = {
    "1min": "1m",
    "1minute": "1m",
    "5min": "5m",
    "5minutes": "5m",
    "60min": "1h",
    "1hour": "1h",
}


def normalize_timeframe(tf: str) -> str:
    v = tf.strip().lower()
    if v in _TIMEFRAME_ALIASES:
        return _TIMEFRAME_ALIASES[v]
    if re.fullmatch(r"\d+[smhd]", v):
        return v
    raise ValueError(f"Invalid timeframe: {tf}")


@dataclass(frozen=True)
class Instrument:
    exchange: Optional[str]
    base: str
    quote: str

    @property
    def canon(self) -> str:
        return f"{self.base}_{self.quote}"

    @property
    def provider_symbol(self) -> str:
        # Default provider symbol style (Binance-like: BTCUSDT)
        return f"{self.base}{self.quote}"


def parse_instrument(spec: str) -> Instrument:
    s = spec.strip()
    exchange: Optional[str] = None
    rest = s
    if ":" in s:
        exchange, rest = s.split(":", 1)
        exchange = exchange.lower()
    # Accept BTC/USDT or BTC_USDT or provider-style BTCUSDT symbols
    if "/" in rest:
        base, quote = rest.split("/", 1)
    elif "_" in rest:
        base, quote = rest.split("_", 1)
    else:
        # Assume concatenated symbol, split heuristically by common stable suffixes
        m = re.fullmatch(r"([A-Z0-9]+?)(USDT|USD|USDC|BTC|ETH|EUR|RUB|JPY)$", rest.upper())
        if not m:
            if exchange is None:
                raise ValueError(f"Ambiguous instrument: {spec}")
            raise ValueError(f"Unable to parse instrument symbol: {spec}")
        base, quote = m.group(1), m.group(2)
    return Instrument(exchange=exchange, base=base.upper(), quote=quote.upper())

