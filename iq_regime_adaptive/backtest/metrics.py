"""
metrics.py - Quantitative Verification Metrics for Binary Options Backtests.

Formulations:
1. Nominal Win Rate:
   p_hat = N_wins / (N_wins + N_losses)

2. Exact Closed-Form Wilson Score Interval Lower Bound (95% confidence, z = 1.96):
   WLB = (p_hat + z^2/(2N) - z * sqrt(p_hat*(1-p_hat)/N + z^2/(4N^2))) / (1 + z^2/N)

3. Normalized Expected Value:
   EV = p_hat * (1 + B) - 1 = (N_wins * B - N_losses) / (N_wins + N_losses)
   EV_WLB = WLB * (1 + B) - 1

4. Effective Sample Size (N_eff) accounting for serial outcome correlation:
   N_eff = N / (1 + 2 * sum_{k=1}^K rho_k(Y))

5. Risk & Return Metrics:
   Total PnL, Max Drawdown ($ and %), Profit Factor, Sharpe & Sortino ratios.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
import pandas as pd

from iq_regime_adaptive.pipeline.payout_filter import (
    compute_wilson_lower_bound,
    compute_expected_value,
    compute_payout_be,
)


@dataclass(frozen=True)
class BacktestMetrics:
    """Standardized quantitative metrics container."""
    total_trades: int
    wins: int
    losses: int
    pushes: int
    nominal_win_rate: float
    wilson_lower_bound: float
    breakeven_win_rate: float
    expected_value: float
    ev_wlb: float
    effective_n: float
    total_pnl: float
    return_pct: float
    initial_balance: float
    final_balance: float
    peak_balance: float
    max_drawdown: float
    max_drawdown_pct: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    payout_tested: float
    monthly_consistency: str = "N/A"

    def to_dict(self) -> Dict[str, Any]:
        """Converts metrics to a serializable dictionary."""
        return asdict(self)


def compute_effective_n(outcomes: Sequence[int], max_lags: int = 3) -> float:
    """
    Computes Effective Degrees of Freedom (N_eff) penalizing serial correlation
    in binary outcomes:
    N_eff = N / (1 + 2 * sum_{k=1}^K rho_k(Y))
    """
    n = len(outcomes)
    if n <= max_lags + 1:
        return float(n)

    arr = np.array(outcomes, dtype=float)
    var = np.var(arr)
    if var < 1e-12:
        return float(n)

    mean = np.mean(arr)
    centered = arr - mean

    corr_sum = 0.0
    for k in range(1, max_lags + 1):
        if n - k <= 1:
            break
        cov_k = np.mean(centered[k:] * centered[:-k])
        rho_k = cov_k / var
        # Only penalize positive autocorrelation (clustering of outcomes)
        if rho_k > 0.0:
            corr_sum += rho_k

    n_eff = n / (1.0 + 2.0 * corr_sum)
    return float(np.clip(n_eff, 1.0, float(n)))


def compute_backtest_metrics(
    trades_df: pd.DataFrame,
    initial_balance: float = 1000.0,
    payout: float = 0.85,
    risk_free_rate: float = 0.0,
) -> BacktestMetrics:
    """
    Computes complete quantitative performance metrics from a trades DataFrame.

    Required columns in trades_df:
    - 'result': 'WIN', 'LOSS', 'PUSH' (or 1, 0, -1)
    - 'pnl': monetary profit and loss per trade
    - 'balance': running balance after each trade
    """
    total_trades = len(trades_df)
    p_be = compute_payout_be(payout)

    if total_trades == 0:
        return BacktestMetrics(
            total_trades=0,
            wins=0,
            losses=0,
            pushes=0,
            nominal_win_rate=0.0,
            wilson_lower_bound=0.0,
            breakeven_win_rate=p_be,
            expected_value=0.0,
            ev_wlb=0.0,
            effective_n=0.0,
            total_pnl=0.0,
            return_pct=0.0,
            initial_balance=initial_balance,
            final_balance=initial_balance,
            peak_balance=initial_balance,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            payout_tested=payout,
            monthly_consistency="0_TRADES",
        )

    # 1. Trade Results
    res_series = trades_df["result"].astype(str).str.upper()
    wins = int((res_series == "WIN").sum())
    losses = int((res_series == "LOSS").sum())
    pushes = int((res_series == "PUSH").sum())
    decisive_trades = wins + losses

    if decisive_trades > 0:
        win_rate = wins / decisive_trades
    else:
        win_rate = 0.0

    # 2. Wilson Lower Bound & EV
    wlb = compute_wilson_lower_bound(win_rate, decisive_trades, z=1.96)
    ev_nominal = compute_expected_value(win_rate, payout)
    ev_wlb = compute_expected_value(wlb, payout)

    # 3. Effective N
    binary_outcomes = [1 if r == "WIN" else 0 for r in res_series if r in ("WIN", "LOSS")]
    n_eff = compute_effective_n(binary_outcomes)

    # 4. PnL & Balance
    pnls = trades_df["pnl"].values
    total_pnl = float(np.sum(pnls))
    
    if "balance" in trades_df.columns:
        balances = trades_df["balance"].values
        final_balance = float(balances[-1])
        all_balances = np.concatenate(([initial_balance], balances))
    else:
        balances = initial_balance + np.cumsum(pnls)
        final_balance = float(balances[-1])
        all_balances = np.concatenate(([initial_balance], balances))

    return_pct = total_pnl / initial_balance if initial_balance > 0 else 0.0

    # 5. Drawdown
    peaks = np.maximum.accumulate(all_balances)
    dd_dollars = peaks - all_balances
    max_dd_dollars = float(np.max(dd_dollars))
    dd_pcts = dd_dollars / np.maximum(peaks, 1e-8)
    max_dd_pct = float(np.max(dd_pcts))
    peak_balance = float(np.max(peaks))

    # 6. Profit Factor
    gross_profit = float(np.sum(pnls[pnls > 0]))
    gross_loss = float(abs(np.sum(pnls[pnls < 0])))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = 999.0 if gross_profit > 0 else 1.0

    # 7. Sharpe & Sortino Ratios (per-trade)
    if len(pnls) > 1 and np.std(pnls) > 1e-8:
        mean_pnl = np.mean(pnls)
        std_pnl = np.std(pnls)
        sharpe_ratio = float(mean_pnl / std_pnl * np.sqrt(min(252, len(pnls))))
        
        downside = pnls[pnls < 0]
        if len(downside) > 0 and np.std(downside) > 1e-8:
            sortino_ratio = float(mean_pnl / np.std(downside) * np.sqrt(min(252, len(pnls))))
        else:
            sortino_ratio = 999.0 if mean_pnl > 0 else 0.0
    else:
        sharpe_ratio = 0.0
        sortino_ratio = 0.0

    # 8. Monthly Consistency
    monthly_consistency = "N/A"
    if "entry_time" in trades_df.columns and pd.api.types.is_datetime64_any_dtype(trades_df["entry_time"]):
        time_indexed = trades_df.set_index("entry_time")
        monthly_pnl = time_indexed["pnl"].resample("ME").sum()
        total_months = len(monthly_pnl)
        pos_months = int((monthly_pnl > 0).sum())
        monthly_consistency = f"{pos_months}_OF_{total_months}_MONTHS_PROFITABLE"

    return BacktestMetrics(
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        pushes=pushes,
        nominal_win_rate=float(win_rate),
        wilson_lower_bound=float(wlb),
        breakeven_win_rate=float(p_be),
        expected_value=float(ev_nominal),
        ev_wlb=float(ev_wlb),
        effective_n=float(n_eff),
        total_pnl=float(total_pnl),
        return_pct=float(return_pct),
        initial_balance=float(initial_balance),
        final_balance=float(final_balance),
        peak_balance=float(peak_balance),
        max_drawdown=float(max_dd_dollars),
        max_drawdown_pct=float(max_dd_pct),
        profit_factor=float(profit_factor),
        sharpe_ratio=float(sharpe_ratio),
        sortino_ratio=float(sortino_ratio),
        payout_tested=float(payout),
        monthly_consistency=monthly_consistency,
    )
