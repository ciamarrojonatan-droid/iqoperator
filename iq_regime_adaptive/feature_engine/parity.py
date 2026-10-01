"""parity.py - Closed-candle parity guard for regime classifier / signal router.

Contract enforced by this module:

- ``RegimeClassifier.classify_latest`` and ``SignalRouter.route_signal``
  assume candles are **FECHADOS** (completed). Feeding a still-forming
  (live) last bar leaks partial information (repaint) and breaks parity
  between backtest (closed bars) and live trading.
- The **caller** MUST call :func:`drop_forming_bar` on the raw OHLC
  DataFrame **before** calling the classifier/router::

      df_closed, dropped = drop_forming_bar(df_raw, timeframe_sec=60)
      out = classifier.classify_latest(df_closed)

A bar is considered *forming* when ``now - candle_open_time < timeframe_sec``,
i.e. its `[open_time, open_time + timeframe_sec)` window has not elapsed yet.
"""

from __future__ import annotations

import time as _time
from datetime import datetime, date
from typing import Any, Tuple, Union

import numpy as np
import pandas as pd

__all__ = ["is_forming", "drop_forming_bar"]


# -----------------------------------------------------------------------------
# Internal: epoch-seconds normalization
# -----------------------------------------------------------------------------

def _to_epoch_sec(value: Any) -> float:
    """Convert a single time value to epoch seconds (float).

    Accepts:
    - epoch seconds (int/float, ~1e9)
    - epoch milliseconds (~1e12), microseconds (~1e15), nanoseconds (~1e18)
    - ``datetime`` / ``date`` / ``pd.Timestamp`` / ``np.datetime64``
      (naive values are assumed UTC)
    - ISO/string datetimes parseable by ``pd.to_datetime``.
    """
    if value is None:
        return float("nan")
    # pandas / numpy NA
    try:
        if pd.isna(value):
            return float("nan")
    except (TypeError, ValueError):
        pass

    # datetime-like objects
    if isinstance(value, pd.Timestamp):
        ts = value
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return float(ts.timestamp())
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Naive -> assume UTC (avoids local-timezone shift).
            return float(pd.Timestamp(value, tz="UTC").timestamp())
        return float(value.timestamp())
    if isinstance(value, date):
        return float(pd.Timestamp(value, tz="UTC").timestamp())
    if isinstance(value, np.datetime64):
        return float(pd.Timestamp(value, tz="UTC").timestamp())

    # numeric epoch (s / ms / us / ns heuristic)
    if isinstance(value, (int, float, np.integer, np.floating)):
        v = float(value)
        av = abs(v)
        if av >= 1e17:  # nanoseconds
            return v / 1e9
        if av >= 1e14:  # microseconds
            return v / 1e6
        if av >= 1e12:  # milliseconds
            return v / 1e3
        return v

    # strings / other: try datetime parse, then numeric fallback
    try:
        ts = pd.to_datetime(value, utc=True)
        if pd.isna(ts):
            return float("nan")
        return float(ts.timestamp())
    except (ValueError, TypeError, OverflowError):
        pass
    try:
        return _to_epoch_sec(float(value))
    except (ValueError, TypeError):
        return float("nan")


def _normalize_now(now_ts: Any) -> float:
    """Normalize ``now`` to epoch seconds; ``None`` -> ``time.time()``."""
    if now_ts is None:
        return float(_time.time())
    return float(_to_epoch_sec(now_ts))


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def is_forming(
    candle_time: Any,
    timeframe_sec: Union[int, float],
    now_ts: Any = None,
) -> bool:
    """Return True if the candle opened at ``candle_time`` is still forming.

    A candle covers ``[open_time, open_time + timeframe_sec)``; it is closed
    once ``now >= open_time + timeframe_sec``.

    Args:
        candle_time: bar open time — epoch s/ms/us/ns, ``datetime``,
            ``pd.Timestamp``, ``np.datetime64`` or parseable string.
        timeframe_sec: candle duration in seconds (e.g. 60 for M1).
        now_ts: reference "now" (same accepted types as ``candle_time``);
            ``None`` uses ``time.time()``.

    Returns:
        True when ``now - open_time < timeframe_sec`` (forming/live bar),
        False when the bar window already elapsed or times are invalid.
    """
    open_sec = _to_epoch_sec(candle_time)
    now_sec = _normalize_now(now_ts)
    if np.isnan(open_sec) or np.isnan(now_sec):
        return False
    return (now_sec - open_sec) < float(timeframe_sec)


def drop_forming_bar(
    df: pd.DataFrame,
    timeframe_sec: Union[int, float],
    now_ts: Any = None,
    time_col: str = "time",
) -> Tuple[pd.DataFrame, bool]:
    """Drop the trailing forming bar so classifier/router see CLOSED candles.

    The classifier (``RegimeClassifier``) and the router (``SignalRouter``)
    assume **closed** candles. Call this helper on the raw feed **before**
    classification/routing to keep live/backtest parity and avoid repaint.

    Args:
        df: OHLC DataFrame with a time column (default ``"time"``) holding
            bar **open** times as epoch s/ms (or datetime).
        timeframe_sec: candle duration in seconds.
        now_ts: reference "now"; ``None`` uses ``time.time()``.
        time_col: name of the open-time column.

    Returns:
        ``(df_closed, descartou)`` where ``df_closed`` is ``df`` without the
        last row when it is still forming, otherwise ``df`` itself; and
        ``descartou`` flags whether a row was removed. When the time column
        is absent (or ``df`` is empty / timestamp unparseable) returns
        ``(df, False)`` unchanged.
    """
    if df is None or len(df) == 0:
        return df, False
    if time_col not in df.columns:
        return df, False
    try:
        last_time = df[time_col].iloc[-1]
    except (KeyError, IndexError):
        return df, False
    now_sec = _normalize_now(now_ts)
    open_sec = _to_epoch_sec(last_time)
    if np.isnan(open_sec) or np.isnan(now_sec):
        return df, False
    if (now_sec - open_sec) < float(timeframe_sec):
        return df.iloc[:-1].copy(), True
    return df, False
