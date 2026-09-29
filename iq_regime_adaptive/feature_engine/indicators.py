"""
indicators.py - Quantitative Indicator Library for Binary Options Regime Engine.

Implements:
1. Wilder's True Range (TR), Average True Range (ATR), and Normalized ATR (NATR = ATR / Close * 100).
2. Bollinger Bands, Bollinger Bandwidth (BBW), Rolling Z-Score of BBW (BBW_Z), and Percentile Rank.
3. Normalized Realized Volatility (NRV), Parkinson High-Low Volatility, and Vol Shock Ratio.
4. Wilder's 14-period Directional Movement System (ADX, +DI, -DI, DI_Spread).
5. Lag-1 Return Autocorrelation (rho_1) with t-statistic.
6. Lo-MacKinlay Variance Ratio VR(q) with heteroskedasticity adjustment (Lo & MacKinlay, 1988).
7. Auxiliary technical indicators (RSI, EMA, Donchian Channels, Candle Morphology).
"""

from __future__ import annotations

from typing import Tuple, Union
import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# 1. Volatility Indicators
# -----------------------------------------------------------------------------

def compute_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Computes True Range taking into account prior close."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    # For first candle, TR is simply high - low
    tr.iloc[0] = high.iloc[0] - low.iloc[0]
    return tr


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Computes Wilder's Smoothed Average True Range (ATR).
    Uses Wilder's smoothing alpha = 1 / period.
    """
    tr = compute_true_range(high, low, close)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr


def compute_natr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Normalized Average True Range: NATR = (ATR / Close) * 100.
    Scale-invariant across different currency pairs and price levels.
    """
    atr = compute_atr(high, low, close, period=period)
    natr = (atr / (close + 1e-12)) * 100.0
    return natr


def compute_atr_ratio(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    fast_period: int = 5,
    slow_period: int = 30,
) -> pd.Series:
    """Computes ratio of fast ATR to slow ATR for volatility expansion detection."""
    atr_fast = compute_atr(high, low, close, period=fast_period)
    atr_slow = compute_atr(high, low, close, period=slow_period)
    return atr_fast / (atr_slow + 1e-12)


def compute_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    k: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Computes Bollinger Bands (Middle SMA, Upper Band, Lower Band).
    """
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std(ddof=1)
    upper = middle + (k * std)
    lower = middle - (k * std)
    return middle, upper, lower


def compute_bollinger_bandwidth(
    close: pd.Series,
    period: int = 20,
    k: float = 2.0,
) -> pd.Series:
    """
    Bollinger Bandwidth (BBW) = (Upper - Lower) / Middle.
    """
    middle, upper, lower = compute_bollinger_bands(close, period=period, k=k)
    bbw = (upper - lower) / (middle + 1e-12)
    return bbw


def compute_bbw_zscore(bbw: pd.Series, lookback: int = 50) -> pd.Series:
    """
    Computes rolling Z-Score of Bollinger Bandwidth:
    BBW_Z = (BBW - Mean(BBW)) / Std(BBW)
    """
    rolling_mean = bbw.rolling(window=lookback, min_periods=lookback // 2).mean()
    rolling_std = bbw.rolling(window=lookback, min_periods=lookback // 2).std(ddof=1)
    z = (bbw - rolling_mean) / (rolling_std + 1e-12)
    return z


def compute_bbw_percentile(bbw: pd.Series, lookback: int = 50) -> pd.Series:
    """
    Computes rolling percentile rank of Bollinger Bandwidth in [0.0, 1.0].
    """
    def _pct_rank(window: np.ndarray) -> float:
        val = window[-1]
        if np.isnan(val):
            return np.nan
        valid = window[~np.isnan(window)]
        if len(valid) == 0:
            return 0.5
        return float(np.mean(valid <= val))

    return bbw.rolling(window=lookback, min_periods=lookback // 2).apply(_pct_rank, raw=True)


def compute_normalized_realized_volatility(
    close: pd.Series,
    short_window: int = 12,
    long_window: int = 120,
) -> pd.Series:
    """
    Normalized Realized Volatility (NRV):
    Standardizes short-term realized return volatility against long-term baseline.
    NRV = (RV_short - Mean(RV_long)) / Std(RV_long)
    """
    log_ret = np.log(close / close.shift(1))
    rv_short = log_ret.rolling(window=short_window, min_periods=short_window // 2).std(ddof=1)
    rv_mean = rv_short.rolling(window=long_window, min_periods=min(30, long_window // 2)).mean()
    rv_std = rv_short.rolling(window=long_window, min_periods=min(30, long_window // 2)).std(ddof=1)
    nrv = (rv_short - rv_mean) / (rv_std + 1e-12)
    return nrv


def compute_parkinson_volatility(
    high: pd.Series,
    low: pd.Series,
    window: int = 12,
) -> pd.Series:
    """
    Parkinson High-Low Extreme Value Volatility:
    sigma_park = sqrt( 1 / (4 * ln(2) * window) * sum( ln(H / L)^2 ) )
    Possesses ~5x higher statistical efficiency than close-to-close variance.
    """
    ratio = np.log(high / (low + 1e-12))
    ratio_sq = ratio ** 2
    factor = 1.0 / (4.0 * np.log(2.0))
    rolling_sum = ratio_sq.rolling(window=window, min_periods=window // 2).sum()
    park_vol = np.sqrt(factor * rolling_sum / window)
    return park_vol


def compute_vol_shock(
    close: pd.Series,
    fast_period: int = 5,
    slow_period: int = 50,
) -> pd.Series:
    """
    Volatility Shock Ratio: std(close, fast) / std(close, slow).
    """
    std_fast = close.rolling(window=fast_period, min_periods=fast_period).std(ddof=1)
    std_slow = close.rolling(window=slow_period, min_periods=slow_period).std(ddof=1)
    return std_fast / (std_slow + 1e-12)


# -----------------------------------------------------------------------------
# 2. Trend & Directional Indicators (ADX / DI)
# -----------------------------------------------------------------------------

def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Wilder's Directional Movement System:
    Returns (ADX, Plus_DI, Minus_DI, DI_Spread).
    """
    delta_h = high.diff()
    delta_l = -low.diff()

    plus_dm = np.where((delta_h > delta_l) & (delta_h > 0), delta_h, 0.0)
    minus_dm = np.where((delta_l > delta_h) & (delta_l > 0), delta_l, 0.0)

    tr = compute_true_range(high, low, close)

    alpha = 1.0 / period
    tr_smooth = pd.Series(tr, index=close.index).ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=close.index).ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=close.index).ewm(alpha=alpha, adjust=False).mean()

    plus_di = 100.0 * (plus_dm_smooth / (tr_smooth + 1e-12))
    minus_di = 100.0 * (minus_dm_smooth / (tr_smooth + 1e-12))

    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100.0 * (di_diff / (di_sum + 1e-12))

    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    di_spread = plus_di - minus_di

    return adx, plus_di, minus_di, di_spread


# -----------------------------------------------------------------------------
# 3. Market Memory & Statistical Structure Indicators
# -----------------------------------------------------------------------------

def compute_return_autocorrelation(
    close: pd.Series,
    window: int = 40,
    lag: int = 1,
) -> Tuple[pd.Series, pd.Series]:
    """
    Computes rolling Lag-1 Return Autocorrelation (rho_1) and its t-statistic:
    t_rho = rho_1 * sqrt(window).
    rho_1 < -0.15 indicates mean-reverting memory.
    rho_1 > +0.15 indicates persistent trending memory.
    """
    log_ret = np.log(close / close.shift(1))

    def _calc_autocorr(ret_window: np.ndarray) -> float:
        valid = ret_window[~np.isnan(ret_window)]
        if len(valid) < 10:
            return 0.0
        mean = np.mean(valid)
        cent = valid - mean
        denom = np.sum(cent ** 2)
        if denom <= 1e-12:
            return 0.0
        nom = np.sum(cent[lag:] * cent[:-lag])
        return float(nom / denom)

    rho = log_ret.rolling(window=window, min_periods=window // 2).apply(_calc_autocorr, raw=True)
    t_stat = rho * np.sqrt(window)
    return rho, t_stat


def compute_variance_ratio(
    log_prices: np.ndarray,
    q: int = 4,
) -> Tuple[float, float]:
    """
    Lo-MacKinlay Variance Ratio Test VR(q) with Heteroskedasticity Adjustment
    (Lo & MacKinlay, 1988; Campbell, Lo, MacKinlay, 1997).
    
    Returns:
    - vr: Variance ratio VR(q)
    - z_stat: Heteroskedasticity-consistent test statistic z*(q) ~ N(0, 1)
    
    Interpretation:
    - VR(q) < 0.90 (z* < -1.645): Mean reversion.
    - VR(q) > 1.10 (z* > +1.645): Trend persistence.
    - VR(q) in [0.90, 1.10]: Random walk / Brownian noise.
    """
    p = np.asarray(log_prices, dtype=float)
    W = len(p) - 1  # Number of return observations
    if W < q + 10:
        return 1.0, 0.0

    # 1. First-difference sample mean
    delta_p = p[1:] - p[:-1]
    mu = (p[-1] - p[0]) / float(W)

    # 2. 1-period variance estimator sigma_a^2 (unbiased)
    dev_1 = delta_p - mu
    sigma_a_sq = np.sum(dev_1 ** 2) / float(W - 1)

    if sigma_a_sq <= 1e-12:
        return 1.0, 0.0

    # 3. q-period variance estimator sigma_c^2
    # p[k] - p[k-q] for k from q to W
    delta_q = p[q:] - p[:-q]
    dev_q = delta_q - (q * mu)
    m = float(q * (W - q + 1) * (1.0 - (q / float(W))))
    sigma_c_sq = np.sum(dev_q ** 2) / m

    # 4. Variance Ratio (since m already includes q, sigma_c_sq is the scaled variance)
    vr = float(sigma_c_sq / sigma_a_sq)

    # 5. Heteroskedasticity-consistent variance of VR(q): V*(q)
    denom_delta = (np.sum(dev_1 ** 2)) ** 2
    if denom_delta <= 1e-14:
        return vr, 0.0

    v_star = 0.0
    for j in range(1, q):
        weight = ((2.0 * (q - j)) / float(q)) ** 2
        # delta_j = sum_{k=j+1}^W dev_1[k-1]^2 * dev_1[k-j-1]^2 / denom
        k_slice_curr = dev_1[j:]
        k_slice_lag = dev_1[:-j]
        nom_j = np.sum((k_slice_curr ** 2) * (k_slice_lag ** 2))
        delta_j = nom_j / denom_delta
        v_star += weight * delta_j

    if v_star <= 1e-14:
        z_stat = 0.0
    else:
        z_stat = float((vr - 1.0) / np.sqrt(v_star))

    return vr, z_stat


def compute_rolling_variance_ratio(
    close: pd.Series,
    window: int = 60,
    q: int = 4,
) -> Tuple[pd.Series, pd.Series]:
    """
    Computes rolling Lo-MacKinlay Variance Ratio and its z-score over rolling window.
    """
    log_close = np.log(close)

    def _calc_vr(p_window: np.ndarray) -> float:
        valid = p_window[~np.isnan(p_window)]
        if len(valid) < q + 10:
            return 1.0
        vr, _ = compute_variance_ratio(valid, q=q)
        return vr

    def _calc_z(p_window: np.ndarray) -> float:
        valid = p_window[~np.isnan(p_window)]
        if len(valid) < q + 10:
            return 0.0
        _, z = compute_variance_ratio(valid, q=q)
        return z

    vr_series = log_close.rolling(window=window + 1, min_periods=window // 2).apply(_calc_vr, raw=True)
    z_series = log_close.rolling(window=window + 1, min_periods=window // 2).apply(_calc_z, raw=True)
    return vr_series, z_series


# -----------------------------------------------------------------------------
# 4. Auxiliary Strategy Indicators
# -----------------------------------------------------------------------------

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Computes Wilder's Relative Strength Index (RSI)."""
    delta = close.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    alpha = 1.0 / period
    avg_gain = pd.Series(gain, index=close.index).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = pd.Series(loss, index=close.index).ewm(alpha=alpha, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-12)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def compute_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> Tuple[pd.Series, pd.Series]:
    """Computes Fast and Slow Stochastic %K and %D."""
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()
    k_line = 100.0 * ((close - lowest_low) / (highest_high - lowest_low + 1e-12))
    d_line = k_line.rolling(window=d_period, min_periods=d_period).mean()
    return k_line, d_line


def compute_donchian_channels(
    high: pd.Series,
    low: pd.Series,
    period: int = 20,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Computes Donchian Channel Upper, Lower, and Middle."""
    upper = high.rolling(window=period, min_periods=period).max()
    lower = low.rolling(window=period, min_periods=period).min()
    middle = (upper + lower) / 2.0
    return upper, lower, middle


def compute_ema(close: pd.Series, span: int) -> pd.Series:
    """Computes Exponential Moving Average."""
    return close.ewm(span=span, adjust=False).mean()


def compute_candle_morphology(
    open_p: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.DataFrame:
    """
    Computes candle geometric ratios:
    - total_range: high - low
    - body_ratio: abs(close - open) / (high - low + eps)
    - upper_wick_ratio: (high - max(open, close)) / (high - low + eps)
    - lower_wick_ratio: (min(open, close) - low) / (high - low + eps)
    - is_bullish: close > open
    """
    rng = high - low
    eps = 1e-12
    max_oc = np.maximum(open_p, close)
    min_oc = np.minimum(open_p, close)

    body_ratio = (close - open_p).abs() / (rng + eps)
    upper_wick_ratio = (high - max_oc) / (rng + eps)
    lower_wick_ratio = (min_oc - low) / (rng + eps)
    is_bullish = close > open_p

    return pd.DataFrame({
        "range": rng,
        "body_ratio": body_ratio,
        "upper_wick_ratio": upper_wick_ratio,
        "lower_wick_ratio": lower_wick_ratio,
        "is_bullish": is_bullish,
    }, index=close.index)


# -----------------------------------------------------------------------------
# Convenience / Spec compatibility adapters
# -----------------------------------------------------------------------------

def calculate_atr(data: Union[pd.DataFrame, pd.Series], *args, **kwargs) -> pd.Series:
    if isinstance(data, pd.DataFrame):
        return compute_atr(data["high"], data["low"], data["close"], *args, **kwargs)
    return compute_atr(data, *args, **kwargs)


def calculate_natr(data: Union[pd.DataFrame, pd.Series], *args, **kwargs) -> pd.Series:
    if isinstance(data, pd.DataFrame):
        return compute_natr(data["high"], data["low"], data["close"], *args, **kwargs)
    return compute_natr(data, *args, **kwargs)


def calculate_bbw(data: Union[pd.DataFrame, pd.Series], *args, **kwargs) -> pd.Series:
    if isinstance(data, pd.DataFrame):
        return compute_bollinger_bandwidth(data["close"], *args, **kwargs)
    return compute_bollinger_bandwidth(data, *args, **kwargs)


def calculate_adx(data: Union[pd.DataFrame, pd.Series], *args, **kwargs) -> Union[pd.DataFrame, Tuple[pd.Series, pd.Series, pd.Series, pd.Series]]:
    if isinstance(data, pd.DataFrame):
        adx, pdi, mdi, spread = compute_adx(data["high"], data["low"], data["close"], *args, **kwargs)
        return pd.DataFrame({"adx": adx, "plus_di": pdi, "minus_di": mdi, "di_spread": spread}, index=data.index)
    return compute_adx(data, *args, **kwargs)


def calculate_autocorrelation(data: Union[pd.DataFrame, pd.Series], *args, **kwargs) -> pd.Series:
    if isinstance(data, pd.DataFrame):
        return compute_return_autocorrelation(data["close"], *args, **kwargs)
    return compute_return_autocorrelation(data, *args, **kwargs)


def calculate_variance_ratio(data: Union[pd.DataFrame, pd.Series], *args, **kwargs):
    if isinstance(data, pd.DataFrame):
        return compute_variance_ratio(data["close"], *args, **kwargs)
    return compute_variance_ratio(data, *args, **kwargs)

