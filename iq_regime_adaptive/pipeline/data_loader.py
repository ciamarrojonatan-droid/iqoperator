"""
data_loader.py - Robust Historical Candle Ingestion and Normalization.

Features:
- Auto-detection and normalization of epoch seconds, epoch milliseconds, and ISO datetime strings.
- Strict OHLCV schema validation and price integrity checks (high >= low, prices > 0).
- Chronological sorting and deduplication.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union
import numpy as np
import pandas as pd


class DataValidationError(ValueError):
    """Raised when candle data fails schema or integrity validation."""
    pass


def normalize_timestamps(series: pd.Series) -> pd.Series:
    """
    Auto-detects and normalizes timestamp series to timezone-aware UTC datetime.
    
    Supports:
    - Epoch seconds (e.g., 1782123600)
    - Epoch milliseconds (e.g., 1716485400000)
    - ISO 8601 strings (e.g., "2026-06-22 10:20:00", "2026-06-22T10:20:00Z")
    """
    if series.empty:
        return pd.Series(dtype="datetime64[ns, UTC]")

    # Check if already datetime
    if pd.api.types.is_datetime64_any_dtype(series):
        if series.dt.tz is None:
            return series.dt.tz_localize("UTC")
        return series.dt.tz_convert("UTC")

    # If numeric or convertible to numeric
    numeric_series = pd.to_numeric(series, errors="coerce")
    valid_numeric_count = numeric_series.notna().sum()

    if valid_numeric_count > len(series) * 0.9:
        # Determine whether epoch milliseconds or epoch seconds based on median value
        median_val = float(numeric_series.dropna().median())
        if median_val > 1e11:  # Epoch milliseconds (e.g., > 1973 in ms)
            return pd.to_datetime(numeric_series, unit="ms", utc=True)
        else:  # Epoch seconds
            return pd.to_datetime(numeric_series, unit="s", utc=True)
    else:
        # Parse as ISO string / date formats
        return pd.to_datetime(series, utc=True)


def normalize_candles(df_raw: pd.DataFrame, timeframe_sec: Any = None) -> pd.DataFrame:
    """
    Normalizes raw candle DataFrame to canonical OHLC schema.

    - Renames: {from, time, at, open_time, timestamp, date, t, datetime -> time};
      {high, max -> high}; {low, min -> low} (plus o/h/l/c aliases for compatibility).
    - Auto-detects epoch seconds vs milliseconds via median > 1e11 => ms.
    - Sorts by time + drop_duplicates(keep=last).
    - Validates high >= max(open, close) and low <= min(open, close) WITHOUT
      filling with close: violations are set to NaN so the classifier vetos as CHAOS.
    - Returns columns [time, open, high, low, close] (+datetime when convertible,
      +volume when present for load_csv compatibility).
    - timeframe_sec is accepted for API compatibility (reserved, currently unused).
    """
    if not isinstance(df_raw, pd.DataFrame):
        raise DataValidationError("normalize_candles expects a pandas DataFrame")
    df = df_raw.copy()

    col_map = {str(c).strip().lower(): c for c in df.columns}

    # Time column: prioritize "time" for idempotency, then spec synonyms.
    time_col = None
    for cand in ["time", "from", "at", "open_time", "timestamp", "date", "t", "datetime"]:
        if cand in col_map:
            time_col = col_map[cand]
            break

    open_col = col_map.get("open", col_map.get("o"))

    high_col = None
    for cand in ["high", "max", "h"]:
        if cand in col_map:
            high_col = col_map[cand]
            break

    low_col = None
    for cand in ["low", "min", "l"]:
        if cand in col_map:
            low_col = col_map[cand]
            break

    close_col = col_map.get("close", col_map.get("c"))
    vol_col = col_map.get("volume", col_map.get("vol", col_map.get("v")))

    if not time_col:
        raise DataValidationError(
            "Missing time column (expected one of: from/time/at/open_time/timestamp/date/t/datetime)"
        )

    missing = []
    if not open_col:
        missing.append("open")
    if not high_col:
        missing.append("high")
    if not low_col:
        missing.append("low")
    if not close_col:
        missing.append("close")
    if missing:
        raise DataValidationError(f"Missing mandatory OHLC columns: {missing}")

    rename_dict = {
        time_col: "time",
        open_col: "open",
        high_col: "high",
        low_col: "low",
        close_col: "close",
    }
    if vol_col:
        rename_dict[vol_col] = "volume"
    df = df.rename(columns=rename_dict)

    # Cast OHLC to numeric (coerce; NaN preserved for CHAOS veto, no fill).
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    # Normalize timestamps (epoch s/ms autodetect via median > 1e11, else ISO).
    df["time"] = normalize_timestamps(df["time"])

    # Chronological sort (stable) + dedup keep=last.
    df = df.sort_values(by="time", kind="mergesort")
    df = df.drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)

    # Geometry validation WITHOUT filling: violations -> NaN (CHAOS veto).
    eps = 1e-7
    open_vals = df["open"].to_numpy(dtype=float)
    close_vals = df["close"].to_numpy(dtype=float)
    upper = np.maximum(open_vals, close_vals)  # NaN if either is NaN
    lower = np.minimum(open_vals, close_vals)
    upper_s = pd.Series(upper, index=df.index)
    lower_s = pd.Series(lower, index=df.index)
    high_invalid = df["high"] < (upper_s - eps)
    low_invalid = df["low"] > (lower_s + eps)
    df.loc[high_invalid.fillna(False), "high"] = np.nan
    df.loc[low_invalid.fillna(False), "low"] = np.nan

    # Datetime helper when convertible.
    if pd.api.types.is_datetime64_any_dtype(df["time"]) and df["time"].notna().any():
        if "datetime" not in df.columns:
            df["datetime"] = df["time"]

    base = ["time", "open", "high", "low", "close"]
    if "datetime" in df.columns:
        base.append("datetime")
    if "volume" in df.columns:
        base.append("volume")
    extras = [c for c in df.columns if c not in base]
    df = df[base + extras]

    return df


def validate_ohlcv(df: pd.DataFrame, strict_volume: bool = False) -> pd.DataFrame:
    """
    Validates OHLCV schema and geometric price relations.
    
    Invariants checked:
    - Required columns present: open, high, low, close
    - High >= Low
    - High >= Open and High >= Close (allowing tiny numerical tolerance 1e-8)
    - Low <= Open and Low <= Close (allowing tiny numerical tolerance 1e-8)
    - Positive finite prices (open, high, low, close > 0)
    - Non-negative volume (if volume present)
    """
    df = df.copy()
    
    # Standardize column names to lowercase
    col_map = {str(c).strip().lower(): c for c in df.columns}
    
    # Map common synonyms
    time_col = None
    for cand in ["time", "timestamp", "date", "datetime", "t"]:
        if cand in col_map:
            time_col = col_map[cand]
            break
            
    open_col = col_map.get("open", col_map.get("o"))
    high_col = col_map.get("high", col_map.get("h"))
    low_col = col_map.get("low", col_map.get("l"))
    close_col = col_map.get("close", col_map.get("c"))
    vol_col = col_map.get("volume", col_map.get("vol", col_map.get("v")))

    missing = []
    if not open_col: missing.append("open")
    if not high_col: missing.append("high")
    if not low_col: missing.append("low")
    if not close_col: missing.append("close")

    if missing:
        raise DataValidationError(f"Missing mandatory OHLC columns: {missing}")

    rename_dict = {
        open_col: "open",
        high_col: "high",
        low_col: "low",
        close_col: "close",
    }
    if time_col:
        rename_dict[time_col] = "time"
    if vol_col:
        rename_dict[vol_col] = "volume"

    df = df.rename(columns=rename_dict)

    # Cast OHLC to float
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isna().any():
            nan_cnt = df[col].isna().sum()
            raise DataValidationError(f"Column '{col}' contains {nan_cnt} non-numeric or NaN values")

    # If volume missing, fill with 0.0
    if "volume" not in df.columns:
        if strict_volume:
            raise DataValidationError("Volume column is required under strict_volume mode")
        df["volume"] = 0.0
    else:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        if (df["volume"] < 0).any():
            raise DataValidationError("Negative volume values detected")

    # Check strictly positive prices
    for col in ["open", "high", "low", "close"]:
        if (df[col] <= 0).any():
            non_pos = (df[col] <= 0).sum()
            raise DataValidationError(f"Non-positive price detected in '{col}': {non_pos} occurrences")

    # Price relations: high >= low, high >= max(open, close), low <= min(open, close)
    eps = 1e-7
    invalid_hl = df["high"] < (df["low"] - eps)
    if invalid_hl.any():
        raise DataValidationError(f"Invalid candle geometry: high < low in {invalid_hl.sum()} rows")

    invalid_ho = df["high"] < (df["open"] - eps)
    invalid_hc = df["high"] < (df["close"] - eps)
    if invalid_ho.any() or invalid_hc.any():
        raise DataValidationError("Invalid candle geometry: high < max(open, close)")

    invalid_lo = df["low"] > (df["open"] + eps)
    invalid_lc = df["low"] > (df["close"] + eps)
    if invalid_lo.any() or invalid_lc.any():
        raise DataValidationError("Invalid candle geometry: low > min(open, close)")

    return df


class DataLoader:
    """
    Ingests, validates, and normalizes historical candle CSVs.
    """

    def __init__(self, data_dir: Union[str, Path, None] = None):
        self.data_dir = Path(data_dir) if data_dir else None

    def load_csv(
        self,
        filepath: Union[str, Path],
        start_time: Any = None,
        end_time: Any = None,
        strict_volume: bool = False,
    ) -> pd.DataFrame:
        """
        Loads CSV candles, normalizes timestamps to UTC, validates OHLCV schema,
        deduplicates, and sorts chronologically.
        """
        path = Path(filepath)
        if not path.is_absolute() and self.data_dir:
            path = self.data_dir / path

        if not path.exists():
            raise FileNotFoundError(f"Historical candle file not found: {path}")

        # Read CSV
        try:
            df = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            raise DataValidationError(f"Candle CSV file is empty: {path}")

        if df.empty:
            raise DataValidationError(f"Candle CSV file is empty: {path}")

        # Canonical normalization: rename, epoch s/ms autodetect, sort,
        # dedup keep=last, geometry violations -> NaN (CHAOS veto, no fill).
        df = normalize_candles(df)

        # Preserve strict behavior for open/close: must be valid numbers.
        # high/low NaN is allowed (CHAOS veto downstream).
        for col in ("open", "close"):
            if df[col].isna().any():
                nan_cnt = int(df[col].isna().sum())
                raise DataValidationError(
                    f"Column '{col}' contains {nan_cnt} non-numeric or NaN values"
                )

        # Strictly positive prices (NaN in high/low passes through for veto).
        for col in ["open", "high", "low", "close"]:
            s = df[col]
            if bool(((s <= 0) & s.notna()).any()):
                raise DataValidationError(f"Non-positive price detected in '{col}'")

        # Volume handling (preserve current behavior).
        if "volume" not in df.columns:
            if strict_volume:
                raise DataValidationError("Volume column is required under strict_volume mode")
            df["volume"] = 0.0
        else:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
            if (df["volume"] < 0).any():
                raise DataValidationError("Negative volume values detected")

        # Filter date range if provided
        if start_time is not None:
            start_dt = pd.to_datetime(start_time, utc=True)
            df = df[df["time"] >= start_dt].reset_index(drop=True)
        if end_time is not None:
            end_dt = pd.to_datetime(end_time, utc=True)
            df = df[df["time"] <= end_dt].reset_index(drop=True)

        # Set standard column ordering
        cols = ["time", "open", "high", "low", "close", "volume"]
        existing_cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]
        df = df[existing_cols]

        return df


def load_csv(
    filepath: Union[str, Path],
    start_time: Any = None,
    end_time: Any = None,
    strict_volume: bool = False,
) -> pd.DataFrame:
    """Convenience standalone function for loading historical candle CSV."""
    loader = DataLoader()
    return loader.load_csv(
        filepath=filepath,
        start_time=start_time,
        end_time=end_time,
        strict_volume=strict_volume,
    )


# Alias for spec compliance
load_candles = load_csv

