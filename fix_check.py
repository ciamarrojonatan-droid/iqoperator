import pandas as pd
import numpy as np
from ml_filter import MLFilter, MIN_CANDLE_COUNT

def compute_all_features(d: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    d = d.copy()
    
    now = pd.Timestamp.now(tz="UTC")
    d["datetime"] = pd.to_datetime(d["time"], unit="s", utc=True)
    
    # Pre-process numeric
    for c in ("high", "low", "close", "open", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce").ffill().bfill()

    d["high"] = np.maximum(d["high"], np.maximum(d["open"], d["close"]))
    d["low"] = np.minimum(d["low"], np.minimum(d["open"], d["close"]))

    N_DC = 20
    d["dc_up_20"] = d["high"].shift(1).rolling(N_DC).max()
    d["dc_lo_20"] = d["low"].shift(1).rolling(N_DC).min()
    d["sig_df_dir"] = np.where(d["close"] > d["dc_up_20"], -1, np.where(d["close"] < d["dc_lo_20"], 1, 0))

    P_BB, MULT_BB = 20, 2.0
    bb_sma = d["close"].rolling(P_BB).mean()
    bb_std = d["close"].rolling(P_BB).std()
    d["bb_upper"] = bb_sma + MULT_BB * bb_std
    d["bb_lower"] = bb_sma - MULT_BB * bb_std
    d["sig_bb_dir"] = np.where(d["close"] > d["bb_upper"], -1, np.where(d["close"] < d["bb_lower"], 1, 0))

    d["sig_agreement"] = ((d["sig_df_dir"] == d["sig_bb_dir"]) & (d["sig_df_dir"] != 0)).astype(int)
    d["sig_confluence_dir"] = np.where((d["sig_df_dir"] == 1) & (d["sig_bb_dir"] == 1), 1,
                             np.where((d["sig_df_dir"] == -1) & (d["sig_bb_dir"] == -1), -1, 0))

    hour, dow, minute = d["datetime"].dt.hour, d["datetime"].dt.dayofweek, d["datetime"].dt.minute
    tod_min = hour * 60 + minute
    d["sin_hour"] = np.sin(2 * np.pi * hour / 24.0)
    d["cos_hour"] = np.cos(2 * np.pi * hour / 24.0)
    d["sin_dow"] = np.sin(2 * np.pi * dow / 7.0)
    d["cos_dow"] = np.cos(2 * np.pi * dow / 7.0)
    d["sin_tod"] = np.sin(2 * np.pi * tod_min / 1440.0)
    d["cos_tod"] = np.cos(2 * np.pi * tod_min / 1440.0)

    d["session_asian"] = ((hour >= 0) & (hour < 8)).astype(int)
    d["session_london"] = ((hour >= 8) & (hour < 16)).astype(int)
    d["session_ny"] = ((hour >= 13) & (hour < 21)).astype(int)
    d["session_overlap"] = ((hour >= 13) & (hour < 16)).astype(int)
    d["is_weekend"] = (dow >= 5).astype(int)

    for p in [5, 10, 20, 50]:
        sma, std = d["close"].rolling(p).mean(), d["close"].rolling(p).std()
        d[f"dist_sma_{p}"] = (d["close"] - sma) / (sma + 1e-9)
        d[f"slope_sma_{p}"] = (sma - sma.shift(1)) / (sma.shift(1) + 1e-9)
        d[f"vol_ratio_{p}"] = std / (sma + 1e-9)
        d[f"_sma_{p}"], d[f"_std_{p}"] = sma, std

    d["sma_spread_5_20"] = (d["_sma_5"] - d["_sma_20"]) / (d["_sma_20"] + 1e-9)
    d["sma_spread_10_50"] = (d["_sma_10"] - d["_sma_50"]) / (d["_sma_50"] + 1e-9)
    d["sma_spread_20_50"] = (d["_sma_20"] - d["_sma_50"]) / (d["_sma_50"] + 1e-9)

    d["vol_shock_5_50"] = d["_std_5"] / (d["_std_50"] + 1e-9)
    bb_range = d["bb_upper"] - d["bb_lower"] + 1e-9
    d["bb_width"] = bb_range / (d["_sma_20"] + 1e-9)
    d["bb_pct_b"] = (d["close"] - d["bb_lower"]) / bb_range
    d["bb_pen_upper"] = np.maximum(0.0, (d["close"] - d["bb_upper"]) / (np.abs(d["bb_upper"]) + 1e-9))
    d["bb_pen_lower"] = np.maximum(0.0, (d["bb_lower"] - d["close"]) / (np.abs(d["bb_lower"]) + 1e-9))

    for n in [10, 20, 40, 60]:
        dc_up = d["high"].shift(1).rolling(n).max()
        dc_lo = d["low"].shift(1).rolling(n).min()
        dc_mid = (dc_up + dc_lo) / 2.0
        dc_rng = dc_up - dc_lo + 1e-9
        d[f"dc_width_{n}"] = (dc_up - dc_lo) / (dc_mid + 1e-9)
        d[f"dc_pct_{n}"] = (d["close"] - dc_lo) / dc_rng
        if n in [10, 20]:
            d[f"dc_break_upper_{n}"] = np.maximum(0.0, (d["close"] - dc_up) / (np.abs(dc_up) + 1e-9))
            d[f"dc_break_lower_{n}"] = np.maximum(0.0, (dc_lo - d["close"]) / (np.abs(dc_lo) + 1e-9))

    bar_rng = np.maximum(1e-9, d["high"] - d["low"])
    d["body_ratio"] = np.clip((d["close"] - d["open"]).abs() / bar_rng, 0.0, 1.0)
    d["upper_wick_ratio"] = np.clip((d["high"] - d[["open", "close"]].max(axis=1)) / bar_rng, 0.0, 1.0)
    d["lower_wick_ratio"] = np.clip((d[["open", "close"]].min(axis=1) - d["low"]) / bar_rng, 0.0, 1.0)
    for lag in [1, 3, 5]:
        ret = d["close"].pct_change(lag)
        d[f"ret_{lag}"] = ret.replace([np.inf, -np.inf], 0.0).fillna(0.0)

    # v2 features
    delta = d["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    d["rsi_14"] = 100 - (100 / (1 + rs))
    d["rsi_14"] = d["rsi_14"].fillna(50.0)

    ema_12 = d["close"].ewm(span=12, adjust=False).mean()
    ema_26 = d["close"].ewm(span=26, adjust=False).mean()
    d["macd"] = ema_12 - ema_26
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_signal"]

    lowest_low = d["low"].rolling(14).min()
    highest_high = d["high"].rolling(14).max()
    d["stoch_k"] = 100 * (d["close"] - lowest_low) / (highest_high - lowest_low + 1e-9)
    d["stoch_d"] = d["stoch_k"].rolling(3).mean()
    d["stoch_k"] = d["stoch_k"].fillna(50.0)
    d["stoch_d"] = d["stoch_d"].fillna(50.0)

    tr1 = d["high"] - d["low"]
    tr2 = (d["high"] - d["close"].shift(1)).abs()
    tr3 = (d["low"] - d["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    d["atr_14"] = tr.rolling(14).mean().bfill()

    ema_20 = d["close"].ewm(span=20, adjust=False).mean()
    kc_upper = ema_20 + 2 * d["atr_14"]
    kc_lower = ema_20 - 2 * d["atr_14"]
    d["kc_pct"] = (d["close"] - kc_lower) / (kc_upper - kc_lower + 1e-9)

    ema_m5_sim = d["close"].ewm(span=25, adjust=False).mean()
    ema_m15_sim = d["close"].ewm(span=75, adjust=False).mean()
    d["dist_ema_m5"] = (d["close"] - ema_m5_sim) / (ema_m5_sim + 1e-9)
    d["dist_ema_m15"] = (d["close"] - ema_m15_sim) / (ema_m15_sim + 1e-9)

    vol_sum_20 = d["volume"].rolling(20).sum()
    vwap_20 = (d["close"] * d["volume"]).rolling(20).sum() / (vol_sum_20 + 1e-9)
    d["dist_vwap_20"] = (d["close"] - vwap_20) / (vwap_20 + 1e-9)
    d["dist_vwap_20"] = d["dist_vwap_20"].fillna(0.0)

    vroc_5 = d["volume"].pct_change(5).fillna(0.0)
    d["vroc_5"] = vroc_5.replace([np.inf, -np.inf], 0.0)

    d["vsa_vol_spread"] = d["volume"] / bar_rng

    d["fractal_up_conf"] = ((d["high"].shift(2) > d["high"].shift(3)) & 
                            (d["high"].shift(2) > d["high"].shift(4)) & 
                            (d["high"].shift(2) > d["high"].shift(1)) & 
                            (d["high"].shift(2) > d["high"])).astype(int)
    d["fractal_down_conf"] = ((d["low"].shift(2) < d["low"].shift(3)) & 
                              (d["low"].shift(2) < d["low"].shift(4)) & 
                              (d["low"].shift(2) < d["low"].shift(1)) & 
                              (d["low"].shift(2) < d["low"])).astype(int)

    prev_body = d["close"].shift(1) - d["open"].shift(1)
    curr_body = d["close"] - d["open"]
    d["bullish_engulfing"] = ((prev_body < 0) & (curr_body > 0) & 
                              (d["close"] > d["open"].shift(1)) & 
                              (d["open"] < d["close"].shift(1))).astype(int)
    d["bearish_engulfing"] = ((prev_body > 0) & (curr_body < 0) & 
                              (d["close"] < d["open"].shift(1)) & 
                              (d["open"] > d["close"].shift(1))).astype(int)

    mean_uw = d["upper_wick_ratio"].rolling(20).mean()
    std_uw = d["upper_wick_ratio"].rolling(20).std()
    d["wick_upper_z"] = (d["upper_wick_ratio"] - mean_uw) / (std_uw + 1e-9)
    
    mean_lw = d["lower_wick_ratio"].rolling(20).mean()
    std_lw = d["lower_wick_ratio"].rolling(20).std()
    d["wick_lower_z"] = (d["lower_wick_ratio"] - mean_lw) / (std_lw + 1e-9)

    d["wick_upper_z"] = d["wick_upper_z"].fillna(0.0)
    d["wick_lower_z"] = d["wick_lower_z"].fillna(0.0)

    return d[feature_cols].copy()

def main():
    ml = MLFilter()
    if not ml.is_loaded: return
    df = pd.read_csv("data/BTCUSDT_M15_60d.csv")
    feat = compute_all_features(df, ml.feature_cols)
    probs = ml.model.predict_proba(feat)[:, 1]
    df["prob"] = probs
    print("Probabilities distribution:")
    print(df["prob"].describe())

if __name__ == "__main__":
    main()
