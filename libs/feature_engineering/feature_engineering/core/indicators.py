"""Technical indicator calculations for feature engineering.

This module provides pure, vectorized technical indicator calculations
that are identical across training and serving environments.
"""

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd

from ..advanced.vdmc import VDMC_FEATURE_COLUMNS, calculate_vdmc_indicators
from .config import FeatureConfig

logger = logging.getLogger(__name__)

_ADAPTIVE_FIB_LEVELS = np.asarray([0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0])


class FeatureEngineer:
    """Calculates technical indicators and features for ML models.
    
    This class provides deterministic, vectorized feature computation
    that is guaranteed to be identical in training and serving.
    
    Attributes:
        config: Feature configuration specifying which indicators to compute
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """Initialize feature engineer.
        
        Args:
            config: Feature configuration. If None, uses defaults.
        """
        self.config = config or FeatureConfig()
        
    def calculate_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all configured technical indicators.
        
        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            
        Returns:
            DataFrame with all technical indicators added
            
        Raises:
            ValueError: If required columns are missing
        """
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        logger.debug(f"Calculating features for {len(df)} rows")
        
        # Make a copy to avoid modifying original
        features_df = df.copy()
        
        # Calculate each feature group
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", pd.errors.PerformanceWarning)

            features_df = self._add_basic_features(features_df)
            features_df = self._add_moving_averages(features_df)
            features_df = self._add_momentum_indicators(features_df)
            features_df = self._add_volatility_indicators(features_df)
            features_df = self._add_volume_indicators(features_df)
            features_df = self._add_price_change_features(features_df)
            features_df = self._add_custom_features(features_df)
            features_df = self._add_regime_features(features_df)
            features_df = self._add_microstructure_features(features_df)
            features_df = self._add_advanced_microstructure_features(features_df)
            if self.config.vdmc_enabled:
                features_df = self._add_vdmc_features(features_df)
            if self.config.adaptive_levels_enabled:
                features_df = self._add_adaptive_level_features(features_df)
            # Phase 4 opt-in lanes (disabled by default → no schema change).
            if getattr(self.config, "cross_asset_features_enabled", False):
                features_df = self._add_cross_asset_features(features_df)
            # DM-7: cross-asset BTC enhanced lane (separate, additive).
            if getattr(self.config, "cross_asset_btc_enhanced_enabled", False):
                features_df = self._add_cross_asset_btc_enhanced_features(
                    features_df,
                )
            if self._funding_enabled() or self._open_interest_enabled():
                features_df = self._add_derivatives_features(features_df)
            if getattr(self.config, "directional_change_features_enabled", False):
                features_df = self._add_directional_change_features(features_df)
            if getattr(self.config, "spectral_features_enabled", False):
                features_df = self._add_spectral_features(features_df)
            if getattr(self.config, "price_path_features_enabled", False):
                features_df = self._add_price_path_features(features_df)
            features_df = self._add_temporal_features(features_df)
        
        # Defragment after column-by-column additions
        features_df = features_df.copy()

        # Clean infinite and extreme values
        features_df = self._clean_features(features_df)
        
        new_feature_count = len([c for c in features_df.columns if c not in df.columns])
        logger.debug(f"Generated {new_feature_count} technical indicators")
        
        return features_df
    
    def _add_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add basic price-derived features."""
        # Typical price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Price ranges
        df['high_low_range'] = df['high'] - df['low']
        df['open_close_range'] = abs(df['close'] - df['open'])
        
        # Body to range ratio
        df['body_range_ratio'] = df['open_close_range'] / (df['high_low_range'] + 1e-10)
        
        return df
    
    def _add_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add moving average indicators."""
        # Simple Moving Averages
        for period in self.config.sma_periods:
            df[f'sma_{period}'] = df['close'].rolling(period, min_periods=1).mean()
            df[f'close_sma_{period}_ratio'] = df['close'] / (df[f'sma_{period}'] + 1e-10)
            
        # Exponential Moving Averages
        for period in self.config.ema_periods:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
            df[f'close_ema_{period}_ratio'] = df['close'] / (df[f'ema_{period}'] + 1e-10)
            
        return df
    
    def _add_momentum_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum-based indicators."""
        # RSI calculation
        for period in self.config.rsi_periods:
            delta = df['close'].diff().astype('float64')
            gain = delta.where(delta > 0, 0.0).rolling(window=period, min_periods=1).mean()
            loss = (-delta).where(delta < 0, 0.0).rolling(window=period, min_periods=1).mean()
            rs = gain / (loss + 1e-10)
            df[f'rsi_{period}'] = 100 - (100 / (1 + rs))
            df[f'rsi_{period}_oversold'] = (df[f'rsi_{period}'] < 30).astype(int)
            df[f'rsi_{period}_overbought'] = (df[f'rsi_{period}'] > 70).astype(int)
        
        # MACD
        ema_fast = df['close'].ewm(span=self.config.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.config.macd_slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=self.config.macd_signal, adjust=False).mean()
        if getattr(self.config, "stationary_features_enabled", False):
            # Stationarity pass: MACD lines are price-scale (EMA differences
            # of price). Emit only the close-relative histogram + the binary.
            df['macd_histogram_pct'] = (macd - macd_signal) / (df['close'] + 1e-10)
        else:
            df['macd'] = macd
            df['macd_signal'] = macd_signal
            df['macd_histogram'] = macd - macd_signal
        df['macd_bullish'] = (macd > macd_signal).astype(int)

        return df
    
    def _add_volatility_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volatility-based indicators."""
        # ATR calculation
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift()).astype('float64')
        low_close = np.abs(df['low'] - df['close'].shift()).astype('float64')
        true_range = pd.DataFrame({
            'hl': high_low,
            'hc': high_close,
            'lc': low_close
        }).max(axis=1)
        df['atr'] = true_range.rolling(self.config.atr_period, min_periods=1).mean()
        df['atr_ratio'] = df['atr'] / (df['close'] + 1e-10)
        
        # Bollinger Bands
        bb_middle = df['close'].rolling(self.config.bb_period, min_periods=1).mean()
        bb_std = df['close'].rolling(self.config.bb_period, min_periods=1).std().fillna(0.0)
        df['bb_upper'] = bb_middle + (bb_std * self.config.bb_std)
        df['bb_lower'] = bb_middle - (bb_std * self.config.bb_std)
        df['bb_middle'] = bb_middle
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (bb_middle + 1e-10)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        
        # Historical volatility
        returns = df['close'].pct_change().astype('float64')
        for period in self.config.volatility_periods:
            df[f'volatility_{period}'] = returns.rolling(period, min_periods=1).std() * np.sqrt(period)
            # ML-25 Phase 2: Lagged volatility (volatility clusters)
            df[f'volatility_{period}_lag1'] = df[f'volatility_{period}'].shift(1)

        # ML-25 Phase 2: Lagged high-low ranges (range persistence)
        for lag in range(1, 4):
            df[f'high_low_range_lag{lag}'] = df['high_low_range'].shift(lag)

        # ML-25 Phase 2 V6: Residualized ATR / BB-width features
        # Subtract lagged rolling mean to extract innovation component,
        # avoiding direct label leakage from raw ATR/BB_width.
        if 'atr_ratio' in df.columns:
            atr_pred = df['atr_ratio'].rolling(5).mean().shift(1)
            df['atr_ratio_resid'] = df['atr_ratio'] - atr_pred.fillna(df['atr_ratio'].median())
        if 'bb_width' in df.columns:
            bb_pred = df['bb_width'].rolling(5).mean().shift(1)
            df['bb_width_resid'] = df['bb_width'] - bb_pred.fillna(df['bb_width'].median())

        return df
    
    def _add_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based indicators."""
        # Volume moving averages
        for period in self.config.volume_sma_periods:
            df[f'volume_sma_{period}'] = df['volume'].rolling(period, min_periods=1).mean()
            df[f'volume_ratio_{period}'] = df['volume'] / (df[f'volume_sma_{period}'] + 1e-10)
            
        # On Balance Volume
        price_change = df['close'].diff().astype('float64')
        df['obv'] = (df['volume'] * np.sign(price_change)).cumsum()

        # ML-25 Phase 2 V7: Volume-regime interaction features
        # Capture co-occurrence of volume spikes + momentum + volatility.
        if 'volume_ratio_10' in df.columns:
            returns = df['close'].pct_change()
            ret_std = returns.rolling(20).std()
            ret_zscore = returns / (ret_std + 1e-10)
            df['volume_spike_x_return_zscore'] = df['volume_ratio_10'] * ret_zscore

            for period in self.config.volatility_periods:
                vcol = f'volatility_{period}'
                if vcol in df.columns:
                    df[f'volume_ratio_10_x_{vcol}'] = df['volume_ratio_10'] * df[vcol]

        return df
    
    def _add_price_change_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price change and return features."""
        # Simple returns
        for period in self.config.price_change_periods:
            df[f'return_{period}'] = df['close'].pct_change(period)
            df[f'log_return_{period}'] = np.log(df['close'] / df['close'].shift(period))
            
        return df
    
    def _add_custom_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add custom trading-specific features."""
        # Price position within recent range
        for period in [10, 20]:
            rolling_min = df['close'].rolling(period, min_periods=1).min()
            rolling_max = df['close'].rolling(period, min_periods=1).max()
            df[f'price_position_{period}'] = (
                (df['close'] - rolling_min) / (rolling_max - rolling_min + 1e-10)
            )
            
        # Consecutive price movements
        df['price_up'] = (df['close'] > df['close'].shift(1)).astype(int)
        df['price_down'] = (df['close'] < df['close'].shift(1)).astype(int)
        
        return df

    # ------------------------------------------------------------------
    # Regime features — z-scored returns, vol ratio, VWAP distance, etc.
    # Ported from ensemble-trainer/data/feature_engineering.py for
    # train/serve parity (FEATURES-1 §4.1).
    # ------------------------------------------------------------------
    def _add_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add returns z-scores, volatility regime, and mean-reversion signals.

        These features capture short-horizon predictive signals that standard
        TA oscillators miss.  All outputs are stationary.
        """
        returns = df['close'].pct_change()

        # Returns z-scores at multiple windows
        for fast, slow in [(5, 60), (10, 120), (20, 240)]:
            mean_ret = returns.rolling(slow, min_periods=1).mean()
            std_ret = returns.rolling(slow, min_periods=1).std()
            df[f'return_zscore_{fast}_{slow}'] = (
                (returns.rolling(fast, min_periods=1).mean() - mean_ret) / (std_ret + 1e-10)
            )

        # Realized volatility ratio (short / long)
        for short_w, long_w in [(10, 60), (20, 120)]:
            vol_short = returns.rolling(short_w, min_periods=1).std()
            vol_long = returns.rolling(long_w, min_periods=1).std()
            df[f'vol_ratio_{short_w}_{long_w}'] = vol_short / (vol_long + 1e-10)

        # VWAP distance (proxy for institutional flow)
        if 'volume' in df.columns:
            atr_col = 'atr' if 'atr' in df.columns else None
            for period in [20, 60]:
                vwap = (
                    (df['close'] * df['volume']).rolling(period, min_periods=1).sum()
                    / (df['volume'].rolling(period, min_periods=1).sum() + 1e-10)
                )
                divisor = (
                    df[atr_col] + 1e-10 if atr_col
                    else df['close'].rolling(period, min_periods=1).std() + 1e-10
                )
                df[f'vwap_dist_{period}'] = (df['close'] - vwap) / divisor

        # Consecutive up/down bars
        up = (df['close'] > df['close'].shift(1)).astype(np.float64)
        df['consec_up'] = up.groupby((up != up.shift()).cumsum()).cumsum()
        down = (df['close'] < df['close'].shift(1)).astype(np.float64)
        df['consec_down'] = down.groupby((down != down.shift()).cumsum()).cumsum()

        # Upper/lower wick ratios
        full_range = df['high'] - df['low'] + 1e-10
        df['upper_wick_ratio'] = (
            (df['high'] - df[['open', 'close']].max(axis=1)) / full_range
        )
        df['lower_wick_ratio'] = (
            (df[['open', 'close']].min(axis=1) - df['low']) / full_range
        )

        return df

    # ------------------------------------------------------------------
    # Microstructure features — autocorrelation, skew/kurtosis,
    # volume-weighted returns, breakout distance, volume spikes, etc.
    # ------------------------------------------------------------------
    def _add_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add features capturing microstructure and short-horizon predictability.

        All outputs are stationary (returns-based, ratios, or bounded).
        """
        returns = df['close'].pct_change()

        # Suppress numpy "Degrees of freedom <= 0 for slice" warnings that
        # fire inside rolling autocorr / skew / kurtosis for early windows
        # with near-min_periods values.  Results are correct (NaN).
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Degrees of freedom <= 0 for slice",
                category=RuntimeWarning,
            )

            # 1. Return autocorrelation at multiple lags
            for lag in [5, 10, 20]:
                df[f'return_autocorr_{lag}'] = (
                    returns.rolling(max(lag * 3, 30), min_periods=lag + 1).apply(
                        lambda x: x.autocorr(lag=lag) if len(x) > lag else 0.0,
                        raw=False,
                    )
                )

            # 2. Return dispersion — skew and kurtosis
            for window in [20, 60]:
                df[f'return_skew_{window}'] = returns.rolling(window, min_periods=3).skew()
                df[f'return_kurt_{window}'] = returns.rolling(window, min_periods=4).kurt()

        # 3. Volume-weighted return
        if 'volume' in df.columns:
            vol_clip = df['volume'].clip(lower=1e-10)
            for window in [10, 20]:
                vw_ret = (returns * vol_clip).rolling(window, min_periods=1).sum() / (
                    vol_clip.rolling(window, min_periods=1).sum() + 1e-10
                )
                df[f'vw_return_{window}'] = vw_ret

        # 4. High/low breakout distance (normalised by ATR)
        atr = df.get('atr')
        if atr is None:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift()).astype('float64')
            low_close = np.abs(df['low'] - df['close'].shift()).astype('float64')
            true_range = pd.DataFrame({
                'hl': high_low, 'hc': high_close, 'lc': low_close
            }).max(axis=1)
            atr = true_range.rolling(14, min_periods=1).mean()

        for period in [10, 20]:
            rolling_high = df['high'].rolling(period, min_periods=1).max()
            rolling_low = df['low'].rolling(period, min_periods=1).min()
            df[f'breakout_high_dist_{period}'] = (
                (df['close'] - rolling_high) / (atr + 1e-10)
            )
            df[f'breakout_low_dist_{period}'] = (
                (df['close'] - rolling_low) / (atr + 1e-10)
            )

        # 5. Relative volume spike — current vol vs recent max
        if 'volume' in df.columns:
            for period in [10, 20]:
                vol_max = df['volume'].rolling(period, min_periods=1).max()
                df[f'volume_spike_{period}'] = df['volume'] / (vol_max + 1e-10)

        # 6. Intrabar momentum — (close-open) / ATR
        df['intrabar_momentum'] = (df['close'] - df['open']) / (atr + 1e-10)

        # 7. Range expansion ratio — current range vs recent avg range
        bar_range = df['high'] - df['low']
        for period in [10, 20]:
            avg_range = bar_range.rolling(period, min_periods=1).mean()
            df[f'range_expansion_{period}'] = bar_range / (avg_range + 1e-10)

        return df

    # ------------------------------------------------------------------
    # Advanced microstructure features — VWAP, spread proxy, order flow,
    # Kyle's lambda, Amihud illiquidity (items 8-12, parity with legacy)
    # Added in v2.1.0 (ML-39)
    # ------------------------------------------------------------------
    def _add_advanced_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add advanced microstructure features for parity with legacy feature_engineering.py.

        Items 8-12: VWAP, bid-ask spread proxy, order flow imbalance,
        Kyle's lambda, and Amihud illiquidity.
        Requires: close, high, low, volume columns.
        """
        returns = df['close'].pct_change()

        # 8. VWAP — volume-weighted average price (normalised by close)
        if 'volume' in df.columns:
            _stationary = getattr(self.config, "stationary_features_enabled", False)
            for period in [10, 20, 60]:
                vwap = (
                    (df['close'] * df['volume']).rolling(period).sum()
                    / (df['volume'].rolling(period).sum() + 1e-10)
                )
                if not _stationary:
                    # Raw VWAP is a price LEVEL — non-stationary across price
                    # regimes; the ratio below carries the signal scale-free.
                    df[f'vwap_{period}'] = vwap
                df[f'vwap_ratio_{period}'] = df['close'] / (vwap + 1e-10)

        # 9. Bid-ask spread proxy — (high - low) / close normalised by volume
        if 'volume' in df.columns:
            raw_spread = (df['high'] - df['low']) / (df['close'] + 1e-10)
            vol_clip = df['volume'].clip(lower=1e-10)
            for period in [10, 20]:
                avg_vol = vol_clip.rolling(period).mean()
                df[f'spread_proxy_{period}'] = raw_spread * (avg_vol / (vol_clip + 1e-10))
                df[f'spread_proxy_ma_{period}'] = raw_spread.rolling(period).mean()

        # 10. Order flow imbalance — cumulative signed volume vs unsigned volume
        if 'volume' in df.columns:
            signed_vol = df['volume'] * np.sign(df['close'] - df['open'])
            for period in [10, 20]:
                df[f'order_flow_imbalance_{period}'] = (
                    signed_vol.rolling(period).sum()
                    / (df['volume'].rolling(period).sum() + 1e-10)
                )

        # 11. Kyle's lambda proxy — |return| / volume (price impact)
        if 'volume' in df.columns:
            abs_ret = returns.abs()
            vol_clip = df['volume'].clip(lower=1e-10)
            for period in [10, 20]:
                kyle = (
                    abs_ret.rolling(period).mean()
                    / (vol_clip.rolling(period).mean() + 1e-10)
                ) * 1e6  # scale for numeric stability
                if getattr(self.config, "stationary_features_enabled", False):
                    # Volume units drift across instruments/eras — emit the
                    # causal trailing z-score instead of the raw magnitude.
                    df[f'kyle_lambda_z_{period}'] = self._causal_z(kyle)
                else:
                    df[f'kyle_lambda_{period}'] = kyle

        # 12. Amihud illiquidity — |return| / dollar volume
        if 'volume' in df.columns:
            abs_ret = returns.abs()
            dollar_vol = (df['close'] * df['volume']).clip(lower=1e-10)
            for period in [10, 20]:
                amihud = (
                    abs_ret.rolling(period).mean()
                    / (dollar_vol.rolling(period).mean() + 1e-10)
                ) * 1e9  # scale for numeric stability
                if getattr(self.config, "stationary_features_enabled", False):
                    df[f'amihud_illiq_z_{period}'] = self._causal_z(amihud)
                else:
                    df[f'amihud_illiq_{period}'] = amihud

        return df

    @staticmethod
    def _causal_z(series: pd.Series) -> pd.Series:
        """Trailing-window z-score (strictly causal: stats from past rows
        only, fixed window from config so semantics are versioned)."""
        from .config import STATIONARY_Z_WINDOW

        mean = series.rolling(STATIONARY_Z_WINDOW, min_periods=60).mean()
        std = series.rolling(STATIONARY_Z_WINDOW, min_periods=60).std()
        return (series - mean) / (std + 1e-10)

    # ------------------------------------------------------------------
    # Canonical VDMC wave-function features.
    # ------------------------------------------------------------------
    def _add_vdmc_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add canonical vdmc_core wave-function features."""
        vdmc_features = calculate_vdmc_indicators(
            df,
            lookback_period=self.config.vdmc_lookback_period,
            alpha=self.config.vdmc_alpha,
            beta=self.config.vdmc_beta,
            kernel_sigma=self.config.vdmc_kernel_sigma,
            smoothing_factor=self.config.vdmc_smoothing_factor,
            amplitude_scaling=self.config.vdmc_amplitude_scaling,
        )
        _stationary = getattr(self.config, "stationary_features_enabled", False)
        for name in VDMC_FEATURE_COLUMNS:
            if _stationary and name in ("vdmc_momentum", "vdmc_amplitude"):
                # These two carry raw price scale (gradient / peak-trough
                # amplitude of the smoothed PRICE series) — emit the
                # close-relative forms instead.
                df[f"{name}_rel"] = vdmc_features[name] / (df['close'] + 1e-10)
            else:
                df[name] = vdmc_features[name]
        return df

    # ------------------------------------------------------------------
    # Adaptive OHLCV level features — causal support/resistance grid.
    # ------------------------------------------------------------------
    def _directional_change_feature_columns(self) -> list[str]:
        """Deterministic DC feature column list (fixed scale count)."""
        from .config import DIRECTIONAL_CHANGE_N_SCALES

        cols: list[str] = []
        for s in range(DIRECTIONAL_CHANGE_N_SCALES):
            cols += [f"dc_dir_s{s}", f"dc_overshoot_s{s}", f"dc_bars_since_s{s}"]
        cols.append("dc_active_scale")
        return cols

    def _add_directional_change_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add causal multi-scale Directional-Change features (OHLCV-only).

        Per ATR-scaled threshold s (coarse→fine): confirmed leg direction
        (``dc_dir_s{s}``), overshoot since the last confirmed extreme
        (``dc_overshoot_s{s}``), and bars since the last reversal
        (``dc_bars_since_s{s}``). ``dc_active_scale`` counts how many scales are
        currently in a confirmed leg (higher = finer-scale activity). All causal —
        a reversal only registers after price breaches the threshold."""
        from ..directional_change import (
            dc_confirmed_state,
            theta_from_atr,
            wilder_atr,
        )
        from .config import DIRECTIONAL_CHANGE_N_SCALES

        cols = self._directional_change_feature_columns()
        if df.empty or not {"high", "low", "close"}.issubset(df.columns):
            for c in cols:
                df[c] = pd.Series(dtype=np.float64)
            return df

        n_scales = DIRECTIONAL_CHANGE_N_SCALES
        mults = list(
            getattr(self.config, "directional_change_atr_mults", [8.0, 4.0, 2.0, 1.0, 0.5])
        ) or [8.0, 4.0, 2.0, 1.0, 0.5]
        # Pad/truncate to the fixed scale count so the column set stays deterministic.
        use_mults = (mults + [mults[-1]] * n_scales)[:n_scales]
        period = int(getattr(self.config, "directional_change_atr_period", 14))

        close = df["close"].astype(float)
        atr = wilder_atr(df["high"], df["low"], close, period=period)
        close_a = close.to_numpy()
        atr_a = atr.to_numpy()

        active = np.zeros(len(df), dtype=np.float64)
        for s in range(n_scales):
            theta = theta_from_atr(close_a, atr_a, float(use_mults[s]))
            st = dc_confirmed_state(close_a, theta)
            df[f"dc_dir_s{s}"] = st["dir"]
            df[f"dc_overshoot_s{s}"] = np.clip(st["overshoot"], -5.0, 5.0)
            df[f"dc_bars_since_s{s}"] = np.clip(st["bars_since"], 0.0, 5000.0)
            active += np.abs(st["dir"])
        df["dc_active_scale"] = active
        return df

    def _spectral_feature_columns(self) -> list[str]:
        """Deterministic spectral feature column list (fixed windows)."""
        from .config import SPECTRAL_FEATURE_WINDOWS

        cols: list[str] = []
        for w in SPECTRAL_FEATURE_WINDOWS:
            cols += [
                f"spectral_entropy_{w}",
                f"spectral_centroid_{w}",
                f"spectral_flatness_{w}",
                f"freq_band_energy_low_{w}",
                f"freq_band_energy_mid_{w}",
                f"freq_band_energy_high_{w}",
                f"frequency_phase_sin_{w}",
                f"frequency_phase_cos_{w}",
            ]
        return cols

    @staticmethod
    def _rolling_spectral(logret: np.ndarray, w: int) -> dict[str, np.ndarray]:
        """Causal rolling-FFT spectral features for one window ``w`` (vectorized).

        Each output is placed at the window's ENDING bar (uses only bars ≤ t →
        no look-ahead). All outputs are bounded/stationary."""
        from numpy.lib.stride_tricks import sliding_window_view

        n = len(logret)
        keys = (
            "spectral_entropy", "spectral_centroid", "spectral_flatness",
            "freq_band_energy_low", "freq_band_energy_mid", "freq_band_energy_high",
            "frequency_phase_sin", "frequency_phase_cos",
        )
        out = {k: np.zeros(n, dtype=np.float64) for k in keys}
        if n < w:
            return out
        win = sliding_window_view(logret, w).astype(np.float64)  # (n-w+1, w)
        win = win - win.mean(axis=1, keepdims=True)               # detrend
        win = win * np.hanning(w)                                 # taper (leakage)
        spec = np.fft.rfft(win, axis=1)
        power = spec.real ** 2 + spec.imag ** 2
        power = power[:, 1:]                                      # drop DC bin
        nb = power.shape[1]
        total = power.sum(axis=1, keepdims=True)
        p = power / np.where(total > 0, total, 1.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ent = -np.sum(np.where(p > 0, p * np.log(p), 0.0), axis=1) / np.log(max(nb, 2))
            logpow = np.log(np.where(power > 0, power, 1e-12))
            geomean = np.exp(logpow.mean(axis=1))
        kidx = np.arange(1, nb + 1, dtype=np.float64)
        centroid = (p * kidx).sum(axis=1) / nb
        amean = power.mean(axis=1)
        flatness = np.where(amean > 0, geomean / amean, 0.0)
        third = max(1, nb // 3)
        low = p[:, :third].sum(axis=1)
        mid = p[:, third:2 * third].sum(axis=1)
        high = p[:, 2 * third:].sum(axis=1)
        dom = np.argmax(power, axis=1)
        dom_bin = spec[np.arange(spec.shape[0]), dom + 1]        # +1: DC dropped
        phase = np.angle(dom_bin)
        end = np.arange(w - 1, n)
        out["spectral_entropy"][end] = np.clip(ent, 0.0, 1.0)
        out["spectral_centroid"][end] = np.clip(centroid, 0.0, 1.0)
        out["spectral_flatness"][end] = np.clip(flatness, 0.0, 1.0)
        out["freq_band_energy_low"][end] = low
        out["freq_band_energy_mid"][end] = mid
        out["freq_band_energy_high"][end] = high
        out["frequency_phase_sin"][end] = np.sin(phase)
        out["frequency_phase_cos"][end] = np.cos(phase)
        return out

    def _add_spectral_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """SEMPO-inspired causal rolling-FFT spectral features over log-returns.

        Per fixed window: spectral entropy / centroid / flatness, low/mid/high
        frequency-band energy fractions, and the dominant-frequency phase
        (sin/cos). OHLCV-only and causal → train/serve parity is automatic. Gated
        behind the DPU-050 evidence path; disabled by default."""
        from .config import SPECTRAL_FEATURE_WINDOWS

        cols = self._spectral_feature_columns()
        if df.empty or "close" not in df.columns:
            for c in cols:
                df[c] = pd.Series(dtype=np.float64)
            return df
        close = df["close"].astype(float).to_numpy()
        logret = np.zeros_like(close)
        with np.errstate(divide="ignore", invalid="ignore"):
            logret[1:] = np.log(close[1:] / close[:-1])
        logret[~np.isfinite(logret)] = 0.0
        for w in SPECTRAL_FEATURE_WINDOWS:
            feats = self._rolling_spectral(logret, int(w))
            for name, arr in feats.items():
                df[f"{name}_{w}"] = arr
        return df

    def _add_price_path_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """ATR-normalized price-path lane (price_path_features.v1).

        Stationary, bounded path/volatility/drawdown context — a compact
        replacement for the raw OHLCV window in the RL ``distilled`` observation.
        Self-contained (recomputes ATR/EMA with fixed params) so the column set
        does not depend on indicator-ordering or the engine's EMA conventions.
        Strictly causal (trailing windows / past-only shifts) → train/serve
        parity is automatic. OHLCV-only; no evidence gate.
        """
        from .config import (
            PRICE_PATH_ATR_PERIOD,
            PRICE_PATH_DD_WINDOW,
            PRICE_PATH_EMA_WINDOW,
            PRICE_PATH_RETURN_PERIODS,
            PRICE_PATH_VOV_WINDOW,
            price_path_feature_columns,
        )

        cols = price_path_feature_columns()
        if df.empty or not {"high", "low", "close"}.issubset(df.columns):
            for c in cols:
                df[c] = pd.Series(dtype=np.float64)
            return df

        eps = 1e-10
        close = df["close"].astype("float64")
        high = df["high"].astype("float64")
        low = df["low"].astype("float64")

        # Self-contained ATR (trailing mean of true range).
        prev_close = close.shift()
        true_range = pd.concat(
            [
                (high - low),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(PRICE_PATH_ATR_PERIOD, min_periods=1).mean()
        ema = close.ewm(span=PRICE_PATH_EMA_WINDOW, adjust=False).mean()
        roll_max = close.rolling(PRICE_PATH_DD_WINDOW, min_periods=1).max()
        atr_pct = atr / (close + eps)

        new: dict[str, pd.Series] = {}
        for n in PRICE_PATH_RETURN_PERIODS:
            new[f"ret_{n}"] = close.pct_change(n).clip(-1.0, 1.0)
        new["atr_norm_range"] = ((high - low) / (atr + eps)).clip(0.0, 20.0)
        new["atr_pct"] = atr_pct.clip(0.0, 1.0)
        new["close_vs_ema_atr"] = ((close - ema) / (atr + eps)).clip(-10.0, 10.0)
        new["dd_from_peak_atr"] = ((close - roll_max) / (atr + eps)).clip(-20.0, 0.0)
        new["vol_of_vol"] = (
            atr_pct.rolling(PRICE_PATH_VOV_WINDOW, min_periods=2).std().clip(0.0, 1.0)
        )

        df = pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1)
        return df

    def _add_adaptive_level_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add causal Fibonacci-style adaptive support/resistance features."""

        if df.empty:
            for col in (
                "close_fib_bucket_24",
                "close_fib_bucket_96",
                "dist_to_support_24",
                "dist_to_resistance_24",
                "dist_to_support_96",
                "dist_to_resistance_96",
                "sma_local_to_long_ratio_24",
                "range_local_to_long_ratio_24",
                "ohlc_bucket_spread_24",
                "close_bucket_delta_24",
            ):
                df[col] = pd.Series(dtype=np.float64)
            return df

        contexts = {
            window: self._adaptive_level_context(df, window)
            for window in (24, 96)
        }

        for window, context in contexts.items():
            bucket = context["close_bucket"].astype(np.int16)
            df[f"close_fib_bucket_{window}"] = bucket
            df[f"dist_to_support_{window}"] = context["dist_to_support"]
            df[f"dist_to_resistance_{window}"] = context["dist_to_resistance"]

        local_range = contexts[24]["rolling_range"]
        long_range = contexts[96]["rolling_range"]
        local_sma = df["close"].rolling(24, min_periods=1).mean()
        long_sma = df["close"].rolling(96, min_periods=1).mean()
        df["sma_local_to_long_ratio_24"] = np.clip(
            local_sma / (long_sma + 1e-10), 0.0, 5.0,
        )
        df["range_local_to_long_ratio_24"] = np.clip(
            local_range / (long_range + 1e-10), 0.0, 5.0,
        )

        rolling_low = contexts[24]["rolling_low"]
        rolling_range = contexts[24]["rolling_range"]
        ohlc_buckets = pd.concat(
            [
                self._bucketize_against_levels(df[col], rolling_low, rolling_range)
                for col in ("open", "high", "low", "close")
            ],
            axis=1,
        )
        df["ohlc_bucket_spread_24"] = (
            ohlc_buckets.max(axis=1) - ohlc_buckets.min(axis=1)
        ).astype(np.int16)
        df["close_bucket_delta_24"] = (
            df["close_fib_bucket_24"].diff().fillna(0).clip(-6, 6).astype(np.int16)
        )

        return df

    def _adaptive_level_context(self, df: pd.DataFrame, window: int) -> dict[str, pd.Series]:
        rolling_high = df["high"].rolling(window, min_periods=1).max()
        rolling_low = df["low"].rolling(window, min_periods=1).min()
        rolling_range = (rolling_high - rolling_low).clip(lower=1e-10)

        bucket = self._bucketize_against_levels(df["close"], rolling_low, rolling_range)
        support_ratio = pd.Series(
            _ADAPTIVE_FIB_LEVELS[bucket.to_numpy(dtype=np.int16)],
            index=df.index,
        )
        resistance_index = np.minimum(
            bucket.to_numpy(dtype=np.int16) + 1,
            len(_ADAPTIVE_FIB_LEVELS) - 1,
        )
        resistance_ratio = pd.Series(
            _ADAPTIVE_FIB_LEVELS[resistance_index],
            index=df.index,
        )

        support_level = rolling_low + support_ratio * rolling_range
        resistance_level = rolling_low + resistance_ratio * rolling_range

        return {
            "rolling_low": rolling_low,
            "rolling_range": rolling_range,
            "close_bucket": bucket,
            "dist_to_support": np.clip(
                (df["close"] - support_level) / rolling_range,
                0.0,
                1.0,
            ),
            "dist_to_resistance": np.clip(
                (resistance_level - df["close"]) / rolling_range,
                0.0,
                1.0,
            ),
        }

    @staticmethod
    def _bucketize_against_levels(
        values: pd.Series,
        rolling_low: pd.Series,
        rolling_range: pd.Series,
    ) -> pd.Series:
        position = np.clip(
            (values - rolling_low) / (rolling_range + 1e-10),
            0.0,
            1.0,
        )
        buckets = np.searchsorted(
            _ADAPTIVE_FIB_LEVELS,
            position.to_numpy(dtype=np.float64),
            side="right",
        ) - 1
        return pd.Series(
            np.clip(buckets, 0, len(_ADAPTIVE_FIB_LEVELS) - 1).astype(np.int16),
            index=values.index,
        )

    # ------------------------------------------------------------------
    # Temporal / calendar features — hour, day-of-week, session flags
    # ------------------------------------------------------------------
    def _add_cross_asset_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Phase 4: cross-asset (BTC/ETH) lead-lag features.

        Reads OPTIONAL merged columns ``btc_close`` / ``eth_close`` (the major's
        close, aligned to this instrument's bars and supplied by the caller).
        When a major is absent the columns are still produced (zero-filled) so
        the feature SCHEMA is identical whether or not the data is present —
        train/serve parity. ``cross_asset_available`` flags real vs zero-filled.

        All outputs are stationary (returns, rolling correlations in [-1,1],
        relative-strength return differences).
        """
        returns = df['close'].pct_change()
        new_columns: dict[str, pd.Series] = {}
        any_available = False

        for major in ('btc', 'eth'):
            col = f'{major}_close'
            present = col in df.columns and df[col].notna().any()
            if present:
                any_available = True
                m_ret = df[col].astype('float64').pct_change()
            else:
                m_ret = pd.Series(0.0, index=df.index)
            # Lead-lag: the major's PAST return (shift 1) as a predictor.
            new_columns[f'{major}_ret_lag1'] = m_ret.shift(1).fillna(0.0)
            # Relative strength: this instrument's return minus the major's.
            new_columns[f'{major}_rel_strength'] = (returns - m_ret).fillna(0.0)
            # Rolling return correlation (momentum coupling); 0 when absent.
            for window in (24, 96):
                if present:
                    corr = returns.rolling(window, min_periods=max(window // 2, 2)).corr(m_ret)
                else:
                    corr = pd.Series(0.0, index=df.index)
                new_columns[f'{major}_corr_{window}'] = corr.fillna(0.0)

        new_columns['cross_asset_available'] = pd.Series(
            1.0 if any_available else 0.0, index=df.index
        )
        return df.assign(**new_columns)

    def _add_cross_asset_btc_enhanced_features(
        self, df: pd.DataFrame,
    ) -> pd.DataFrame:
        """DM-7: enhanced BTC cross-asset features.

        Backlog-specified columns:
          * ``btc_return_{1,3,5,10}`` — log-return at multiple lookbacks
            of the merged ``btc_close`` (causally aligned by the caller
            via ``merge_external_series``).
          * ``btc_volatility_zscore_{20,60}`` — rolling realised-vol
            z-score (vol normalised by its own rolling mean+std).
          * ``btc_dominance_proxy_zscore_60`` — DOGE/BTC return-ratio
            z-score over 60 bars; a proxy for BTC dominance shifts.
          * ``btc_enhanced_available`` — 1.0 when ``btc_close`` was
            present, 0.0 (zero-fill) otherwise. Mirrors the parity
            contract of ``_add_cross_asset_features``.

        All outputs are stationary, bounded under nominal market conditions,
        and zero-filled when the source is absent so the SCHEMA is
        identical with or without BTC data (train==serve parity).
        """
        new_columns: dict[str, pd.Series] = {}
        present = (
            "btc_close" in df.columns
            and df["btc_close"].notna().any()
        )
        if present:
            btc = df["btc_close"].astype("float64")
            btc_ret = btc.pct_change()
            for lag in (1, 3, 5, 10):
                # Lagged (shift) so the value is causally available at bar t.
                new_columns[f"btc_return_{lag}"] = (
                    btc.pct_change(lag).shift(1).fillna(0.0)
                )
            for window in (20, 60):
                rv = btc_ret.rolling(window, min_periods=max(window // 2, 2)).std()
                rv_mean = rv.rolling(window, min_periods=max(window // 2, 2)).mean()
                rv_std = rv.rolling(window, min_periods=max(window // 2, 2)).std()
                z = (rv - rv_mean) / (rv_std + 1e-9)
                new_columns[f"btc_volatility_zscore_{window}"] = (
                    z.replace([np.inf, -np.inf], 0.0).fillna(0.0)
                )
            # Dominance proxy: log(DOGE_close / BTC_close) z-score over 60.
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.log(
                    df["close"].astype("float64") / btc.replace(0.0, np.nan)
                )
            r_mean = ratio.rolling(60, min_periods=30).mean()
            r_std = ratio.rolling(60, min_periods=30).std()
            dom_z = (ratio - r_mean) / (r_std + 1e-9)
            new_columns["btc_dominance_proxy_zscore_60"] = (
                dom_z.replace([np.inf, -np.inf], 0.0).fillna(0.0)
            )
            available_val = 1.0
        else:
            # Zero-fill — same column set, no NaN, schema-identical.
            for lag in (1, 3, 5, 10):
                new_columns[f"btc_return_{lag}"] = pd.Series(0.0, index=df.index)
            for window in (20, 60):
                new_columns[f"btc_volatility_zscore_{window}"] = pd.Series(
                    0.0, index=df.index,
                )
            new_columns["btc_dominance_proxy_zscore_60"] = pd.Series(
                0.0, index=df.index,
            )
            available_val = 0.0
        new_columns["btc_enhanced_available"] = pd.Series(
            available_val, index=df.index,
        )
        return df.assign(**new_columns)

    def _funding_enabled(self) -> bool:
        """Funding sub-lane active: own flag OR the derivatives master."""
        return bool(
            getattr(self.config, "funding_features_enabled", False)
            or getattr(self.config, "derivatives_features_enabled", False)
        )

    def _open_interest_enabled(self) -> bool:
        """Open-interest sub-lane active: own flag OR the derivatives master."""
        return bool(
            getattr(self.config, "open_interest_features_enabled", False)
            or getattr(self.config, "derivatives_features_enabled", False)
        )

    def _add_derivatives_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Phase 4: derivatives microstructure (funding rate / open interest).

        The funding and open-interest sub-lanes are gated INDEPENDENTLY — only an
        enabled lane contributes columns, so a config can use one without the
        other (and without dead columns). Within an enabled lane the merged
        column (``funding_rate`` / ``open_interest``) is OPTIONAL: present →
        real values; absent → zero-filled with the lane's ``*_available`` flag at
        0, so the column SET is stable for a given flag combination (parity).

        Stationary outputs: funding level/sign/z-score (+ ``funding_available``),
        OI pct-change / z-score / price-divergence (+ ``open_interest_available``).
        """
        new_columns: dict[str, pd.Series] = {}

        if self._funding_enabled():
            if 'funding_rate' in df.columns and df['funding_rate'].notna().any():
                fr = df['funding_rate'].astype('float64').fillna(0.0)
                new_columns['funding_rate_level'] = fr
                new_columns['funding_rate_sign'] = fr.apply(
                    lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)
                )
                fr_mean = fr.rolling(48, min_periods=2).mean()
                fr_std = fr.rolling(48, min_periods=2).std()
                new_columns['funding_rate_zscore'] = (
                    (fr - fr_mean) / (fr_std + 1e-10)
                ).fillna(0.0)
                new_columns['funding_available'] = pd.Series(1.0, index=df.index)
            else:
                for c in ('funding_rate_level', 'funding_rate_sign', 'funding_rate_zscore'):
                    new_columns[c] = pd.Series(0.0, index=df.index)
                new_columns['funding_available'] = pd.Series(0.0, index=df.index)

        if self._open_interest_enabled():
            if 'open_interest' in df.columns and df['open_interest'].notna().any():
                oi = df['open_interest'].astype('float64')
                oi_change = oi.pct_change().replace(
                    [float('inf'), float('-inf')], 0.0
                ).fillna(0.0)
                new_columns['oi_pct_change'] = oi_change
                oi_mean = oi.rolling(96, min_periods=2).mean()
                oi_std = oi.rolling(96, min_periods=2).std()
                new_columns['oi_zscore'] = ((oi - oi_mean) / (oi_std + 1e-10)).fillna(0.0)
                # OI–price divergence: sign agreement between OI change and price return.
                price_ret = df['close'].pct_change().fillna(0.0)
                new_columns['oi_price_divergence'] = pd.Series(
                    np.sign(oi_change.to_numpy()) * np.sign(price_ret.to_numpy()),
                    index=df.index,
                )
                new_columns['open_interest_available'] = pd.Series(1.0, index=df.index)
            else:
                for c in ('oi_pct_change', 'oi_zscore', 'oi_price_divergence'):
                    new_columns[c] = pd.Series(0.0, index=df.index)
                new_columns['open_interest_available'] = pd.Series(0.0, index=df.index)

        return df.assign(**new_columns)

    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features capturing crypto market session patterns.

        Crypto markets have strong intraday seasonality tied to Asian,
        European, and US session openings/closings.  All outputs are
        bounded or cyclically encoded.
        """
        # Resolve a datetime index/column
        if isinstance(df.index, pd.DatetimeIndex):
            dt = df.index
        elif 'timestamp' in df.columns:
            dt = pd.to_datetime(df['timestamp'], utc=True)
        elif 'time' in df.columns:
            dt = pd.to_datetime(df['time'], utc=True)
        else:
            return df  # no datetime available — skip gracefully

        # Use .dt accessor for Series, direct attribute for DatetimeIndex
        _dt = dt.dt if isinstance(dt, pd.Series) else dt

        # Cyclically-encoded hour of day
        hour_frac = _dt.hour + _dt.minute / 60.0
        df['hour_sin'] = np.sin(2 * np.pi * hour_frac / 24.0)
        df['hour_cos'] = np.cos(2 * np.pi * hour_frac / 24.0)

        # Cyclically-encoded day of week
        dow = _dt.dayofweek.astype(float)
        df['dow_sin'] = np.sin(2 * np.pi * dow / 7.0)
        df['dow_cos'] = np.cos(2 * np.pi * dow / 7.0)

        # Binary session flags (UTC)
        hour = _dt.hour
        df['is_weekend'] = (dow >= 5).astype(np.float64)
        df['session_asia'] = ((hour >= 0) & (hour < 8)).astype(np.float64)
        df['session_europe'] = ((hour >= 7) & (hour < 16)).astype(np.float64)
        df['session_us'] = ((hour >= 13) & (hour < 22)).astype(np.float64)

        return df
    
    def _clean_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean features by handling infinite and extreme values.

        IMPORTANT: Only forward-fill is used (no bfill) to prevent
        future-data leakage.  Leading NaNs from warm-up periods are
        filled with zero.
        """
        # Replace infinite values with NaN
        df = df.replace([np.inf, -np.inf], np.nan)

        # Forward fill only — bfill leaks future information
        df = df.ffill()

        # Remaining NaN (warm-up / leading rows) → 0
        df = df.fillna(0.0)

        return df


def calculate_technical_indicators(
    df: pd.DataFrame, 
    config: Optional[FeatureConfig] = None
) -> pd.DataFrame:
    """Convenience function to calculate technical indicators.
    
    Args:
        df: DataFrame with OHLCV data
        config: Feature engineering configuration
        
    Returns:
        DataFrame with technical indicators added
    """
    engineer = FeatureEngineer(config)
    return engineer.calculate_all_features(df)


def compute_indicator_lookbacks(config: Optional[FeatureConfig] = None) -> dict:
    """Compute lookback/warm-up periods for each indicator.
    
    Args:
        config: Feature engineering configuration
        
    Returns:
        Dictionary mapping indicator names to lookback periods
    """
    cfg = config or FeatureConfig()
    lookbacks = {}
    
    # SMA lookbacks
    for period in cfg.sma_periods:
        lookbacks[f"sma_{period}"] = period
    
    # EMA lookbacks
    for period in cfg.ema_periods:
        lookbacks[f"ema_{period}"] = period
    
    # RSI lookbacks
    for period in cfg.rsi_periods:
        lookbacks[f"rsi_{period}"] = period
    
    # MACD lookback (use slow period as it's the longest)
    lookbacks["macd"] = cfg.macd_slow
    
    # Bollinger Bands lookback
    lookbacks[f"bollinger_{cfg.bb_period}"] = cfg.bb_period
    
    # ATR lookback
    lookbacks[f"atr_{cfg.atr_period}"] = cfg.atr_period
    
    # Volume SMA lookbacks
    for period in cfg.volume_sma_periods:
        lookbacks[f"volume_sma_{period}"] = period
    
    # Price change lookbacks
    for period in cfg.price_change_periods:
        lookbacks[f"price_change_{period}"] = period
    
    # Volatility lookbacks
    for period in cfg.volatility_periods:
        lookbacks[f"volatility_{period}"] = period
        lookbacks[f"volatility_{period}_lag1"] = period + 1  # shift(1)

    # Lagged high-low ranges
    for lag in range(1, 4):
        lookbacks[f"high_low_range_lag{lag}"] = lag

    # Residualized features (rolling(5).shift(1) → lookback=6)
    lookbacks["atr_ratio_resid"] = max(cfg.atr_period, 6)
    lookbacks["bb_width_resid"] = max(cfg.bb_period, 6)

    # Volume-regime interactions
    lookbacks["volume_spike_x_return_zscore"] = 20  # rolling(20).std()
    for period in cfg.volatility_periods:
        lookbacks[f"volume_ratio_10_x_volatility_{period}"] = max(10, period)

    # --- v2.0 feature groups ------------------------------------------------
    # Regime features: z-scores, vol ratios, VWAP distance
    lookbacks["return_zscore_5_60"] = 60
    lookbacks["return_zscore_10_120"] = 120
    lookbacks["return_zscore_20_240"] = 240
    lookbacks["vol_ratio_10_60"] = 60
    lookbacks["vol_ratio_20_120"] = 120
    lookbacks["vwap_dist_20"] = 20
    lookbacks["vwap_dist_60"] = 60
    lookbacks["consec_up"] = 1
    lookbacks["consec_down"] = 1
    lookbacks["upper_wick_ratio"] = 0
    lookbacks["lower_wick_ratio"] = 0

    # Microstructure features
    lookbacks["return_autocorr_5"] = 15
    lookbacks["return_autocorr_10"] = 30
    lookbacks["return_autocorr_20"] = 60
    lookbacks["return_skew_20"] = 20
    lookbacks["return_skew_60"] = 60
    lookbacks["return_kurt_20"] = 20
    lookbacks["return_kurt_60"] = 60
    lookbacks["vw_return_10"] = 10
    lookbacks["vw_return_20"] = 20
    lookbacks["breakout_high_dist_10"] = 10
    lookbacks["breakout_high_dist_20"] = 20
    lookbacks["breakout_low_dist_10"] = 10
    lookbacks["breakout_low_dist_20"] = 20
    lookbacks["volume_spike_10"] = 10
    lookbacks["volume_spike_20"] = 20
    lookbacks["intrabar_momentum"] = 0
    lookbacks["range_expansion_10"] = 10
    lookbacks["range_expansion_20"] = 20

    # Temporal features (no lookback needed)
    for feat in [
        "hour_sin", "hour_cos", "dow_sin", "dow_cos",
        "is_weekend", "session_asia", "session_europe", "session_us",
    ]:
        lookbacks[feat] = 0

    if cfg.adaptive_levels_enabled:
        lookbacks["close_fib_bucket_24"] = 24
        lookbacks["close_fib_bucket_96"] = 96
        lookbacks["dist_to_support_24"] = 24
        lookbacks["dist_to_resistance_24"] = 24
        lookbacks["dist_to_support_96"] = 96
        lookbacks["dist_to_resistance_96"] = 96
        lookbacks["sma_local_to_long_ratio_24"] = 96
        lookbacks["range_local_to_long_ratio_24"] = 96
        lookbacks["ohlc_bucket_spread_24"] = 24
        lookbacks["close_bucket_delta_24"] = 25

    if cfg.vdmc_enabled:
        for feat in VDMC_FEATURE_COLUMNS:
            lookbacks[feat] = cfg.vdmc_lookback_period

    return lookbacks
