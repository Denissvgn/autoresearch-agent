from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from ..core.errors import NotImplementedSDK
from ..instruments.symbols import Instrument, normalize_timeframe, parse_instrument
from ..indicators.vdmc_config import VDMCConfig


class Fetcher(Protocol):
    def __call__(self, *, symbol: str, timeframe: str, limit: Optional[int] = None,
                 start: Optional[str] = None, end: Optional[str] = None):  # pragma: no cover - structural protocol
        ...


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FETCHER_FACTORY_CACHE: dict[str, Optional[Callable[[Instrument], Fetcher]]] = {}


def _normalize_provider_name(provider: str) -> str:
    raw = provider.strip().lower()
    for separator in (":", "@", "/"):
        if separator in raw:
            raw = raw.split(separator, 1)[0]
    if raw.startswith("binance"):
        return "binance"
    if raw in {"cc", "crypto-compare"} or raw.startswith("cryptocompare"):
        return "cryptocompare"
    if raw.startswith("kaiko"):
        return "kaiko"
    return raw


def _bool_from_env(env_value: Optional[str]) -> Optional[bool]:
    if env_value is None:
        return None
    value = env_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _provider_enabled(provider: str) -> bool:
    env_key = f"TRAID_SDK_DATA_{provider.upper()}_ENABLED"
    enabled = _bool_from_env(os.getenv(env_key))
    return True if enabled is None else enabled


def _load_fetcher_from_env(provider: str) -> Optional[Callable[..., Any]]:
    env_key = f"TRAID_SDK_{provider.upper()}_FETCHER"
    target = os.getenv(env_key)
    if not target:
        return None
    module_name, _, attr = target.partition(":")
    if not module_name or not attr:
        return None
    try:
        module = importlib.import_module(module_name)
        candidate = getattr(module, attr)
    except Exception:
        return None
    return candidate if callable(candidate) else None


def _default_fetchers_enabled() -> bool:
    raw = os.getenv("TRAID_SDK_DATA_DEFAULT_FETCHER")
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_default_fetcher(provider: str, instrument: Instrument) -> Optional[Fetcher]:
    if not _default_fetchers_enabled():
        return None
    normalized_provider = _normalize_provider_name(provider)
    if not _provider_enabled(normalized_provider):
        return None
    factory = _get_fetcher_factory(normalized_provider)
    if factory is None:
        return None
    return factory(instrument)


def _get_fetcher_factory(provider: str) -> Optional[Callable[[Instrument], Fetcher]]:
    if provider in _FETCHER_FACTORY_CACHE:
        return _FETCHER_FACTORY_CACHE[provider]

    factory: Optional[Callable[[Instrument], Fetcher]] = None
    fetch_fn = _load_fetcher_from_env(provider)
    if fetch_fn is None:
        if provider == "binance":
            fetch_fn = _load_binance_fetcher()
        elif provider == "cryptocompare":
            fetch_fn = _load_cryptocompare_fetcher()
        elif provider == "kaiko":
            fetch_fn = _load_kaiko_fetcher()

    if fetch_fn is not None:
        factory = _wrap_fetcher_factory(provider, fetch_fn)

    _FETCHER_FACTORY_CACHE[provider] = factory
    return factory


def _wrap_fetcher_factory(provider: str, fetch_fn: Callable[..., Any]) -> Callable[[Instrument], Fetcher]:
    def _symbol(inst: Instrument) -> str:
        if provider == "cryptocompare":
            return f"{inst.base}/{inst.quote}"
        if provider == "kaiko":
            return f"{inst.base.lower()}-{inst.quote.lower()}"
        return inst.provider_symbol

    def _extra_kwargs(_: Instrument) -> dict[str, Any]:
        if provider == "kaiko":
            exchange = os.getenv("TRAID_SDK_KAIKO_EXCHANGE", "bncn")
            return {"exchange": exchange}
        return {}

    def _factory(inst: Instrument) -> Fetcher:
        def _fetcher(
            *,
            symbol: str,
            timeframe: str,
            limit: Optional[int] = None,
            start: Optional[str] = None,
            end: Optional[str] = None,
        ):
            del symbol, start, end
            kwargs: dict[str, Any] = {
                "symbol": _symbol(inst),
                "timeframe": timeframe,
            }
            if limit is not None:
                kwargs["limit"] = limit
            kwargs.update({k: v for k, v in _extra_kwargs(inst).items() if v is not None})
            return fetch_fn(**kwargs)  # type: ignore[arg-type]

        return _fetcher

    return _factory


def _load_binance_fetcher():
    module_names = [
        "services.data_ingest.src.loaders.binance_loader",
        "services.data_ingest.loaders.binance_loader",
    ]
    for name in module_names:
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        fetch_fn = getattr(module, "fetch_binance_ohlcv_sync", None)
        if callable(fetch_fn):
            return fetch_fn

    fallback = _PROJECT_ROOT / "services" / "data-ingest" / "src" / "loaders" / "binance_loader.py"
    if fallback.exists():
        try:
            module_name = "traid_training_sdk._binance_loader"
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, fallback)
                if spec is None or spec.loader is None:  # pragma: no cover - importlib failure
                    return None
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            fetch_fn = getattr(module, "fetch_binance_ohlcv_sync", None)
            if callable(fetch_fn):
                return fetch_fn
        except Exception:
            return None

    return None


def _load_cryptocompare_fetcher():
    module_names = [
        "services.data_ingest.src.loaders.cryptocompare_loader",
        "services.data_ingest.loaders.cryptocompare_loader",
    ]
    for name in module_names:
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        fetch_fn = getattr(module, "fetch_cryptocompare_ohlcv_sync", None)
        if callable(fetch_fn):
            return fetch_fn

    fallback = _PROJECT_ROOT / "services" / "data-ingest" / "src" / "loaders" / "cryptocompare_loader.py"
    if fallback.exists():
        try:
            module_name = "traid_training_sdk._cryptocompare_loader"
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, fallback)
                if spec is None or spec.loader is None:  # pragma: no cover
                    return None
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            fetch_fn = getattr(module, "fetch_cryptocompare_ohlcv_sync", None)
            if callable(fetch_fn):
                return fetch_fn
        except Exception:
            return None
    return None


def _load_kaiko_fetcher():
    module_names = [
        "services.data_ingest.src.loaders.kaiko_loader",
        "services.data_ingest.loaders.kaiko_loader",
    ]
    for name in module_names:
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        fetch_fn = getattr(module, "fetch_kaiko_ohlcv_sync", None)
        if callable(fetch_fn):
            return fetch_fn

    fallback = _PROJECT_ROOT / "services" / "data-ingest" / "src" / "loaders" / "kaiko_loader.py"
    if fallback.exists():
        try:
            module_name = "traid_training_sdk._kaiko_loader"
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, fallback)
                if spec is None or spec.loader is None:  # pragma: no cover
                    return None
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            fetch_fn = getattr(module, "fetch_kaiko_ohlcv_sync", None)
            if callable(fetch_fn):
                return fetch_fn
        except Exception:
            return None
    return None


def _validate_ohlcv_df(df) -> None:
    import pandas as pd  # type: ignore

    required = ["timestamp", "open", "high", "low", "close", "volume"]
    if not all(col in df.columns for col in required):
        missing = [c for c in required if c not in df.columns]
        raise ValueError(f"Missing OHLCV columns: {missing}")
    # Ensure ascending timestamps
    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError("Timestamps must be ascending")
    # Basic dtype checks
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        # Try to coerce
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="raise")


@dataclass(frozen=True)
class DataIngestSource:
    provider: str
    instrument: Instrument
    timeframe: str
    _start: Optional[str] = None
    _end: Optional[str] = None
    _limit: Optional[int] = None
    _fetcher: Optional[Fetcher] = None

    @staticmethod
    def from_spec(spec: str, timeframe: str, *, provider: Optional[str] = None, fetcher: Optional[Fetcher] = None) -> "DataIngestSource":
        inst = parse_instrument(spec)
        tf = normalize_timeframe(timeframe)
        prov = provider or (inst.exchange or "unknown")
        return DataIngestSource(provider=prov, instrument=inst, timeframe=tf, _fetcher=fetcher)

    def range(self, start: str, end: str) -> "DataIngestSource":
        return replace(self, _start=start, _end=end)

    def limit(self, bars: int) -> "DataIngestSource":
        return replace(self, _limit=bars)

    def to_dataframe(self):
        import pandas as pd  # type: ignore

        fetcher = self._fetcher or resolve_default_fetcher(self.provider, self.instrument)
        if fetcher is None:
            raise NotImplementedSDK("No fetcher provided; wire services/data-ingest loader in runtime")
        symbol = self.instrument.provider_symbol
        df = fetcher(symbol=symbol, timeframe=self.timeframe, limit=self._limit, start=self._start, end=self._end)
        _validate_ohlcv_df(df)
        # Enforce ascending order and trim tail to limit if needed
        df = df.sort_values("timestamp").reset_index(drop=True)
        if self._limit is not None and len(df) > self._limit:
            df = df.iloc[-self._limit :].reset_index(drop=True)
        return df


def enrich_with_vdmc(
    df, 
    *, 
    close_col: str = "close",
    config: Optional[VDMCConfig] = None,
    lookback_period: Optional[int] = None,
    alpha: Optional[float] = None,
    beta: Optional[float] = None
):
    import numpy as np  # type: ignore
    import pandas as pd  # type: ignore

    # Resolve parameters: explicit args > config > defaults
    defaults = VDMCConfig()
    cfg = config or defaults
    
    _lookback = lookback_period if lookback_period is not None else cfg.lookback_period
    _alpha = alpha if alpha is not None else cfg.alpha
    _beta = beta if beta is not None else cfg.beta

    # Simple, deterministic proxy features for VDMC-like behavior
    close = df[close_col].astype(float)
    ret = close.pct_change().fillna(0.0)
    
    # Use configured lookback for momentum (proxy for kernel smoothing)
    # Note: Real VDMC uses kernel regression, here we use rolling mean as proxy per original code
    # but now parameterized.
    momentum = ret.rolling(window=max(1, int(_lookback // 20)), min_periods=1).mean()
    
    # Amplitude calculation
    amp = (close.rolling(_lookback, min_periods=1).max() - close.rolling(_lookback, min_periods=1).min()) / close.clip(lower=1e-9)
    
    # Probabilities via logistic transform of momentum using alpha
    def _sigmoid(x: pd.Series) -> pd.Series:
        return 1 / (1 + np.exp(-_alpha * x.clip(-1, 1)))

    p_buy = _sigmoid(momentum)
    p_sell = 1 - p_buy

    out = df.copy()
    out["vdmc_p_buy"] = p_buy.astype(float)
    out["vdmc_p_sell"] = p_sell.astype(float)
    out["vdmc_wave_amplitude"] = amp.astype(float).fillna(0.0)
    out["vdmc_momentum"] = momentum.astype(float).fillna(0.0)
    return out


@dataclass(frozen=True)
class IndicatorSource:
    base_df: Optional[object] = None  # pandas.DataFrame at runtime

    def with_bars(self, df) -> "IndicatorSource":
        return replace(self, base_df=df)

    def to_dataset(self):  # returns DataFrame for now
        if self.base_df is None:
            raise ValueError("No base_df provided to IndicatorSource")
        return self.base_df

    def with_vdmc(self):
        if self.base_df is None:
            raise ValueError("No base_df provided to IndicatorSource")
        return replace(self, base_df=enrich_with_vdmc(self.base_df))
