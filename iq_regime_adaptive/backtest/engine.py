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
        payout: float = 0.85,
        horizon_bars: Optional[int] = None,
        warmup_bars: int = 0,
    ) -> BacktestResult:
        """
        Executes binary options backtest across OHLCV dataset.

        Args:
            df: Historical price data with open, high, low, close.
            hypothesis: A BaseHypothesis instance OR precomputed signal Series.
            payout: Broker payout rate B in (0, 1].
            horizon_bars: Contract duration in candles. If None, queries hypothesis.
            warmup_bars: Number of initial bars to embargo if 'trade_eligible' column absent.

        Returns:
            BacktestResult with complete trade ledger and performance metrics.
        """
        n = len(df)
        if n < 2:
            raise ValueError(f"Dataset too short for simulation (length {n}).")

        # Determine hypothesis ID and default horizon
        if isinstance(hypothesis, BaseHypothesis):
            hyp_id = hypothesis.hypothesis_id
            h = horizon_bars if horizon_bars is not None else hypothesis.default_horizon_bars
            signals = hypothesis.generate_signals(df, payout=payout)
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
            eligible_mask = df["trade_eligible"].values
        else:
            eligible_mask = np.ones(n, dtype=bool)
            if warmup_bars > 0:
                eligible_mask[:min(warmup_bars, n)] = False

        balance = float(self.initial_balance)
        peak_balance = balance
        trades: List[TradeRecord] = []
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

            # 1. Warmup embargo check
            if not eligible_mask[t]:
                vetoed_count += 1
                continue

            # 2. Concurrency check
            if not self.allow_concurrent and t < last_exit_idx:
                vetoed_count += 1
                continue

            # 3. Execution Bar & Purging Invariant
            if self.execution_mode == "next_open":
                entry_idx = t + 1
                exit_idx = t + h
            else:
                entry_idx = t
                exit_idx = t + h

            # Strict Boundary Purge: cannot resolve beyond dataset boundary
            if exit_idx >= n or entry_idx >= n:
                purged_count += 1
                continue

            # 4. Payout and EV Gating
            if self.enable_payout_filter and (wins_so_far + losses_so_far >= 20):
                gate = evaluate_trade_gate(wins_so_far, wins_so_far + losses_so_far, payout)
                if not gate.allow_trade:
                    vetoed_count += 1
                    continue

            # 5. Stake Allocation (Zero Martingale Invariant)
            stake = self._allocate_stake(balance, payout, wins_so_far, wins_so_far + losses_so_far)
            if stake < self.min_stake or stake > balance:
                vetoed_count += 1
                continue

            # 6. Trade Execution & Outcome Resolution
            entry_price = float(open_prices[entry_idx] if self.execution_mode == "next_open" else close_prices[entry_idx])
            exit_price = float(close_prices[exit_idx])

            entry_time = timestamps[entry_idx]
            exit_time = timestamps[exit_idx]

            if sig == MarketSignal.CALL.value:
                if exit_price > entry_price:
                    result = "WIN"
                    pnl = stake * payout
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
                    pnl = stake * payout
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
                payout=payout,
                stake=stake,
                pnl=pnl,
                balance=balance,
                return_pct=(balance - self.initial_balance) / self.initial_balance,
            )
            trades.append(rec)
            equity_times.append(exit_time)
            equity_values.append(balance)

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

        metrics = compute_backtest_metrics(
            trades_df=trades_df,
            initial_balance=self.initial_balance,
            payout=payout,
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
