"""
engine.py - High-Fidelity Discrete Binary Options Backtesting Simulator.

Simulates cash-or-nothing digital contracts with:
1. Zero-Lookahead Causal Timing:
   Signal generated at Close_t; Entry executed at Open_{t+1} (or Close_t);
   Expiry evaluated at Close_{t+h}.
2. Payoff Asymmetry:
   CALL: Win if Close_{t+h} > EntryPrice (+payout * stake), Loss if < EntryPrice (-stake).
   PUT: Win if Close_{t+h} < EntryPrice (+payout * stake), Loss if > EntryPrice (-stake).
   PUSH: EntryPrice == Close_{t+h} -> PnL = 0 (stake refunded).
3. Anti-Martingale Capital Allocation:
   Integration with Fractional Kelly and Fixed Fractional Risk models.
4. Strict Boundary Purging & Warmup Embargo:
   Trades where t + h >= len(df) or non-eligible bars are strictly purged.
5. Circuit Breaker / Capital Kill Switch:
   Halts simulation if cumulative drawdown breaches threshold (e.g. 20%).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis
from iq_regime_adaptive.pipeline.payout_filter import (
    compute_payout_be,
    compute_wilson_lower_bound,
    compute_expected_value,
    evaluate_trade_gate,
)
from iq_regime_adaptive.pipeline.risk_allocation import (
    calculate_kelly_stake,
    calculate_fixed_stake,
)
from iq_regime_adaptive.backtest.metrics import (
    BacktestMetrics,
    compute_backtest_metrics,
)


@dataclass(frozen=True)
class TradeRecord:
    """Individual trade execution log."""
    trade_id: int
    entry_idx: int
    exit_idx: int
    entry_time: Any
    exit_time: Any
    direction: str
    entry_price: float
    exit_price: float
    result: str  # WIN, LOSS, PUSH
    payout: float
    stake: float
    pnl: float
    balance: float
    return_pct: float


@dataclass
class BacktestResult:
    """Encapsulates backtest execution outcomes, metrics, and trades."""
    trades: List[TradeRecord]
    trades_df: pd.DataFrame
    metrics: BacktestMetrics
    equity_curve: pd.Series
    initial_balance: float
    final_balance: float
    total_pnl: float
    purged_signals_count: int
    vetoed_signals_count: int
    kill_switch_triggered: bool
    hypothesis_id: str
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        # Dict-like access for backward/forward compat (ex: result['candidates']).
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)


class BacktestEngine:
    """
    Production-grade event-driven binary options backtesting engine.
    """

    def __init__(
        self,
        initial_balance: float = 1000.0,
        risk_method: str = "fractional_kelly",
        fixed_stake: float = 10.0,
        fixed_fraction: float = 0.01,
        fractional_gamma: float = 0.25,
        max_risk_cap: float = 0.02,
        min_stake: float = 1.0,
        execution_mode: str = "next_open",
        allow_concurrent: bool = True,
        kill_switch_drawdown: float = 0.20,
        enable_payout_filter: bool = True,
        prior_wins: int = 65,
        prior_n: int = 100,
    ):
        if initial_balance <= 0.0:
            raise ValueError(f"initial_balance must be positive, got {initial_balance}")
        if risk_method not in ("fractional_kelly", "fixed", "fixed_percentage"):
            raise ValueError(f"Unknown risk_method: {risk_method}")
        if execution_mode not in ("next_open", "close"):
            raise ValueError(f"Unknown execution_mode: {execution_mode}. Use 'next_open' or 'close'.")

        self.initial_balance = initial_balance
        self.risk_method = risk_method
        self.fixed_stake = fixed_stake
        self.fixed_fraction = fixed_fraction
        self.fractional_gamma = fractional_gamma
        self.max_risk_cap = max_risk_cap
        self.min_stake = min_stake
        self.execution_mode = execution_mode
        self.allow_concurrent = allow_concurrent
        self.kill_switch_drawdown = kill_switch_drawdown
        self.enable_payout_filter = enable_payout_filter
        self.prior_wins = prior_wins
        self.prior_n = prior_n

    def run(
        self,
        df: pd.DataFrame,
        hypothesis: Union[BaseHypothesis, pd.Series],
        payout: Union[float, pd.Series, str] = 0.85,
        horizon_bars: Optional[int] = None,
        warmup_bars: int = 0,
        eligible_mask: Optional[pd.Series] = None,
        blocked_hours_utc: Optional[list] = None,
        news_events: Optional[pd.DataFrame] = None,
        news_margin_min: int = 30,
        fill_prob: float = 1.0,
        slippage_ticks: float = 0,
        seed: int = 0,
    ) -> BacktestResult:
        """
        Executes binary options backtest across OHLCV dataset.

        Args:
            df: Historical price data with open, high, low, close.
            hypothesis: A BaseHypothesis instance OR precomputed signal Series.
            payout: Broker payout rate B in (0, 1]. Accepts scalar float,
                pd.Series (aligned to df.index, positional fallback when
                lengths match), or str column name in df. Resolved per-bar as
                ``payout_t`` (signal bar ``t``) for gate/stake/PnL/TradeRecord.
                Missing/NaN values fall back to a scalar (scalar itself, else
                nanmean of valid values, else 0.85).
            horizon_bars: Contract duration in candles. If None, queries hypothesis.
            warmup_bars: Number of initial bars to embargo if 'trade_eligible' column absent.
            eligible_mask: Optional extra pd.Series bool indexed like df. Combined
                (AND) with the base eligibility (``trade_eligible`` column or
                warmup embargo). ``False`` -> veto TOXIC.
            blocked_hours_utc: Optional list of int hours [0-23] (UTC) to block.
                Signal bars whose timestamp hour (UTC) is listed -> veto NEWS.
                Naive timestamps are assumed UTC.
            news_events: Optional pd.DataFrame of news events. Index as
                DatetimeIndex or one of columns
                [time, timestamp, datetime, event_time, date] is used. Any
                signal bar with min |signal_time - news_time| <=
                news_margin_min minutes -> veto NEWS.
            news_margin_min: Minutes of embargo around each news event.
            fill_prob: Fill probability in [0, 1]. Dedicated RNG
                (np.random.default_rng(seed)) draws per candidate that passed
                prior vetos; reject (vetoed, veto_code REJECT) when
                draw >= fill_prob. Default 1.0 = never reject.
            slippage_ticks: Adverse entry-price displacement in ticks, where
                1 tick = ATR value at entry bar when ``atr`` column exists,
                else 1 tick = bar range (high - low) at entry bar. Fractional
                values (e.g. 0.1) act as a fraction of that unit. CALL:
                entry += ticks * unit; PUT: entry -= ticks * unit.
                Default 0 = no slippage.
            seed: Seed for the dedicated fill RNG.

        Returns:
            BacktestResult with complete trade ledger and performance metrics.
            ``result.candidates`` (also ``result['candidates']``) holds one
            dict per CALL/PUT signal with keys
            {t, signal_bar_time, direction, payout_t, veto_code} where veto_code
            in ALLOW|PAYOUT|WILSON|TOXIC|NEWS|REJECT|PURGE.
        """
        n = len(df)
        if n < 2:
            raise ValueError(f"Dataset too short for simulation (length {n}).")

        if fill_prob < 0.0 or fill_prob > 1.0:
            raise ValueError(f"fill_prob must be in [0, 1], got {fill_prob}")

        # ---- Per-bar payout resolution (scalar | Series | column name) ----
        DEFAULT_PAYOUT_FALLBACK = 0.85
        if isinstance(payout, str):
            if payout in df.columns:
                _raw = pd.to_numeric(df[payout], errors="coerce")
                _valid = _raw.dropna()
                scalar_fallback = float(_valid.mean()) if len(_valid) else DEFAULT_PAYOUT_FALLBACK
                payout_series = pd.Series(_raw.values, index=df.index, dtype=float).fillna(scalar_fallback)
            else:
                try:
                    scalar_fallback = float(payout)
                except (TypeError, ValueError):
                    scalar_fallback = DEFAULT_PAYOUT_FALLBACK
                payout_series = pd.Series(float(scalar_fallback), index=df.index, dtype=float)
        elif isinstance(payout, pd.Series):
            if len(payout) == n and not payout.index.equals(df.index):
                try:
                    _aligned = pd.Series(payout.values, index=df.index, dtype=float)
                except (TypeError, ValueError):
                    _aligned = pd.Series(pd.to_numeric(payout.values, errors="coerce"), index=df.index, dtype=float)
            else:
                _aligned = pd.Series(pd.to_numeric(payout.reindex(df.index), errors="coerce").values, index=df.index, dtype=float)
            _valid = _aligned.dropna()
            scalar_fallback = float(_valid.mean()) if len(_valid) else DEFAULT_PAYOUT_FALLBACK
            payout_series = _aligned.fillna(scalar_fallback)
        else:
            scalar_fallback = float(payout)
            payout_series = pd.Series(float(payout), index=df.index, dtype=float)
        payout_vals = payout_series.values.astype(float)

        # Hypothesis signals: keep scalar contract for hypothesis poblar (backward-compat)
        if isinstance(hypothesis, BaseHypothesis):
            hyp_id = hypothesis.hypothesis_id
            h = horizon_bars if horizon_bars is not None else hypothesis.default_horizon_bars
            try:
                signals = hypothesis.generate_signals(df, payout=scalar_fallback)
            except TypeError:
                signals = hypothesis.generate_signals(df)
        elif isinstance(hypothesis, pd.Series):
            hyp_id = str(hypothesis.name or "CUSTOM_SIGNALS")
            h = horizon_bars if horizon_bars is not None else 1
            signals = hypothesis
        else:
            raise TypeError("hypothesis must be BaseHypothesis instance or pd.Series.")

        if h < 1:
            raise ValueError(f"horizon_bars must be >= 1, got {h}")

        # Check for pre-existing trade_eligible mask from Partitioner
        if "trade_eligible" in df.columns:
            base_eligible = df["trade_eligible"].values.astype(bool)
        else:
            base_eligible = np.ones(n, dtype=bool)
            if warmup_bars > 0:
                base_eligible[:min(warmup_bars, n)] = False

        # Extra eligible_mask param (AND-combined; False -> TOXIC)
        if eligible_mask is not None:
            try:
                if isinstance(eligible_mask, pd.Series):
                    if len(eligible_mask) == n and not eligible_mask.index.equals(df.index):
                        extra = pd.Series(eligible_mask.values, index=df.index).fillna(True).values.astype(bool)
                    else:
                        extra = eligible_mask.reindex(df.index).fillna(True).values.astype(bool)
                else:
                    extra = np.asarray(eligible_mask, dtype=bool)
                    if extra.shape[0] != n:
                        raise ValueError("eligible_mask length mismatch")
            except ValueError:
                raise
            except Exception:
                extra = np.ones(n, dtype=bool)
            base_eligible = np.logical_and(base_eligible, extra)
        eligible_arr = base_eligible

        # Blocked hours (UTC) -> NEWS
        blocked_set = set(blocked_hours_utc) if blocked_hours_utc else set()

        def _is_blocked_hour(ts: Any) -> bool:
            if not blocked_set:
                return False
            try:
                pts = pd.Timestamp(ts)
                if pts.tzinfo is not None:
                    pts = pts.tz_convert("UTC")
                # Naive assumed UTC
                return int(pts.hour) in blocked_set
            except Exception:
                return False

        # News events -> NEWS within +- news_margin_min
        news_times: List[pd.Timestamp] = []
        if news_events is not None and len(news_events):
            try:
                if isinstance(news_events.index, pd.DatetimeIndex) and len(news_events.index):
                    _cand = list(news_events.index)
                else:
                    _col = None
                    for c in ("time", "timestamp", "datetime", "event_time", "date"):
                        if c in news_events.columns:
                            _col = c
                            break
                    _cand = list(news_events[_col]) if _col is not None else list(news_events.index)
                for nt in _cand:
                    try:
                        if pd.isna(nt):
                            continue
                        news_times.append(pd.Timestamp(nt))
                    except Exception:
                        continue
            except Exception:
                news_times = []

        def _is_news_blocked(sig_time: Any) -> bool:
            if not news_times or news_margin_min is None or news_margin_min < 0:
                return False
            try:
                st = pd.Timestamp(sig_time)
            except Exception:
                return False
            for nt in news_times:
                try:
                    # Tolerate tz-aware vs naive by comparing in UTC-naive space
                    a = st.tz_convert("UTC").tz_localize(None) if getattr(st, "tzinfo", None) is not None else st
                    b = nt.tz_convert("UTC").tz_localize(None) if getattr(nt, "tzinfo", None) is not None else nt
                    if abs((a - b).total_seconds()) / 60.0 <= float(news_margin_min):
                        return True
                except Exception:
                    continue
            return False

        rng = np.random.default_rng(seed)

        has_atr = "atr" in df.columns
        atr_vals = pd.to_numeric(df["atr"], errors="coerce").values.astype(float) if has_atr else None
        high_vals = pd.to_numeric(df["high"], errors="coerce").values.astype(float) if "high" in df.columns else None
        low_vals = pd.to_numeric(df["low"], errors="coerce").values.astype(float) if "low" in df.columns else None

        balance = float(self.initial_balance)
        peak_balance = balance
        trades: List[TradeRecord] = []
        candidates: List[Dict[str, Any]] = []
        purged_count = 0
        vetoed_count = 0
        kill_switch_triggered = False

        close_prices = df["close"].values
        open_prices = df["open"].values
        timestamps = df.index

        trade_counter = 0
        last_exit_idx = -1

        wins_so_far = 0
        losses_so_far = 0

        # Equity tracking
        equity_times = [timestamps[0]]
        equity_values = [balance]

        for t in range(n):
            # Check Circuit Breaker / Capital Kill Switch
            drawdown_from_initial = (self.initial_balance - balance) / self.initial_balance
            if drawdown_from_initial >= self.kill_switch_drawdown:
                kill_switch_triggered = True
                break

            sig = str(signals.iloc[t]).upper()
            if sig not in (MarketSignal.CALL.value, MarketSignal.PUT.value):
                continue

            payout_t = float(payout_vals[t])
            sig_time = timestamps[t]
            veto_code: Optional[str] = None

            # 1. Eligibility / warmup embargo -> TOXIC
            if not bool(eligible_arr[t]):
                veto_code = "TOXIC"
                vetoed_count += 1
                candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": veto_code})
                continue

            # 2. Toxic-session NEWS vetos (blocked hours / news proximity)
            if _is_blocked_hour(sig_time) or _is_news_blocked(sig_time):
                veto_code = "NEWS"
                vetoed_count += 1
                candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": veto_code})
                continue

            # 3. Execution Bar & Purging Invariant
            if self.execution_mode == "next_open":
                entry_idx = t + 1
                exit_idx = t + h
            else:
                entry_idx = t
                exit_idx = t + h

            # Concurrency veto counts as PURGE (overlap with open contract)
            if not self.allow_concurrent and t < last_exit_idx:
                veto_code = "PURGE"
                vetoed_count += 1
                candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": veto_code})
                continue

            # Strict Boundary Purge: cannot resolve beyond dataset boundary
            if exit_idx >= n or entry_idx >= n:
                veto_code = "PURGE"
                purged_count += 1
                candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": veto_code})
                continue

            # 4. Payout and EV Gating -> PAYOUT (nominal EV) vs WILSON (conservative)
            if self.enable_payout_filter and (wins_so_far + losses_so_far >= 20):
                gate = evaluate_trade_gate(wins_so_far, wins_so_far + losses_so_far, payout_t)
                if not gate.allow_trade:
                    try:
                        nominal_ev = compute_expected_value(float(wins_so_far) / float(wins_so_far + losses_so_far), payout_t)
                    except Exception:
                        nominal_ev = -1.0
                    veto_code = "PAYOUT" if nominal_ev <= 0.0 else "WILSON"
                    vetoed_count += 1
                    candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": veto_code})
                    continue

            # 5. Stake Allocation (Zero Martingale Invariant) -> PAYOUT on sizing failure
            stake = self._allocate_stake(balance, payout_t, wins_so_far, wins_so_far + losses_so_far)
            if stake < self.min_stake or stake > balance:
                veto_code = "PAYOUT"
                vetoed_count += 1
                candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": veto_code})
                continue

            # 6. Fill draw -> REJECT
            if fill_prob < 1.0:
                if rng.random() >= fill_prob:
                    veto_code = "REJECT"
                    vetoed_count += 1
                    candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": veto_code})
                    continue

            # 7. Trade Execution & Outcome Resolution (with adverse slippage)
            entry_price = float(open_prices[entry_idx] if self.execution_mode == "next_open" else close_prices[entry_idx])
            if slippage_ticks:
                unit = 0.0
                if atr_vals is not None:
                    try:
                        unit = float(atr_vals[entry_idx])
                    except Exception:
                        unit = 0.0
                if not np.isfinite(unit) or unit == 0.0:
                    try:
                        if high_vals is not None and low_vals is not None:
                            unit = float(high_vals[entry_idx] - low_vals[entry_idx])
                    except Exception:
                        unit = 0.0
                if np.isfinite(unit) and unit != 0.0:
                    offset = float(slippage_ticks) * float(unit)
                    if sig == MarketSignal.CALL.value:
                        entry_price += offset
                    else:
                        entry_price -= offset
            exit_price = float(close_prices[exit_idx])

            entry_time = timestamps[entry_idx]
            exit_time = timestamps[exit_idx]

            if sig == MarketSignal.CALL.value:
                if exit_price > entry_price:
                    result = "WIN"
                    pnl = stake * payout_t
                    wins_so_far += 1
                elif exit_price < entry_price:
                    result = "LOSS"
                    pnl = -stake
                    losses_so_far += 1
                else:
                    result = "PUSH"
                    pnl = 0.0
            else:  # PUT
                if exit_price < entry_price:
                    result = "WIN"
                    pnl = stake * payout_t
                    wins_so_far += 1
                elif exit_price > entry_price:
                    result = "LOSS"
                    pnl = -stake
                    losses_so_far += 1
                else:
                    result = "PUSH"
                    pnl = 0.0

            balance += pnl
            peak_balance = max(peak_balance, balance)
            trade_counter += 1
            last_exit_idx = exit_idx

            rec = TradeRecord(
                trade_id=trade_counter,
                entry_idx=entry_idx,
                exit_idx=exit_idx,
                entry_time=entry_time,
                exit_time=exit_time,
                direction=sig,
                entry_price=entry_price,
                exit_price=exit_price,
                result=result,
                payout=payout_t,
                stake=stake,
                pnl=pnl,
                balance=balance,
                return_pct=(balance - self.initial_balance) / self.initial_balance,
            )
            trades.append(rec)
            equity_times.append(exit_time)
            equity_values.append(balance)
            candidates.append({"t": int(t), "signal_bar_time": sig_time, "direction": sig, "payout_t": payout_t, "veto_code": "ALLOW"})

        # Build DataFrames
        if trades:
            trades_df = pd.DataFrame([asdict(t) for t in trades])
            equity_curve = pd.Series(equity_values, index=equity_times, name="equity")
        else:
            trades_df = pd.DataFrame(columns=[
                "trade_id", "entry_idx", "exit_idx", "entry_time", "exit_time",
                "direction", "entry_price", "exit_price", "result", "payout",
                "stake", "pnl", "balance", "return_pct"
            ])
            equity_curve = pd.Series([self.initial_balance], index=[timestamps[0]], name="equity")

        try:
            metrics_payout = float(np.nanmean(payout_vals)) if len(payout_vals) else float(scalar_fallback)
        except Exception:
            metrics_payout = float(scalar_fallback)
        metrics = compute_backtest_metrics(
            trades_df=trades_df,
            initial_balance=self.initial_balance,
            payout=metrics_payout,
        )

        return BacktestResult(
            trades=trades,
            trades_df=trades_df,
            metrics=metrics,
            equity_curve=equity_curve,
            initial_balance=self.initial_balance,
            final_balance=balance,
            total_pnl=balance - self.initial_balance,
            purged_signals_count=purged_count,
            vetoed_signals_count=vetoed_count,
            kill_switch_triggered=kill_switch_triggered,
            hypothesis_id=hyp_id,
            candidates=candidates,
        )

    def _allocate_stake(
        self,
        balance: float,
        payout: float,
        sample_wins: int,
        sample_n: int,
    ) -> float:
        """
        Determines position stake using anti-martingale methods.
        Guarantees that losses never increase position sizing.
        """
        if self.risk_method == "fractional_kelly":
            # If not enough samples yet, use calibrated hypothesis prior
            eff_wins = sample_wins if sample_n >= 20 else self.prior_wins
            eff_n = sample_n if sample_n >= 20 else self.prior_n
            alloc = calculate_kelly_stake(
                balance=balance,
                payout=payout,
                sample_wins=eff_wins,
                sample_n=eff_n,
                fractional_gamma=self.fractional_gamma,
                max_risk_cap=self.max_risk_cap,
                min_stake=self.min_stake,
            )
            return alloc.stake

        elif self.risk_method == "fixed_percentage":
            stake = balance * min(self.fixed_fraction, self.max_risk_cap)
            return max(self.min_stake, round(stake, 2))

        else:  # "fixed"
            max_allowed = balance * self.max_risk_cap
            return max(self.min_stake, min(self.fixed_stake, max_allowed))
