## 2026-09-29T03:12:07Z
You are Worker M2 (worker_m2_backtest).
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\worker_m2_backtest\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md.
MANDATORY: Read PROJECT.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\PROJECT.md.
MANDATORY: Read Explorer Survey IQ 3 findings at:
c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_3\report.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

TOKEN SAVING DIRECTIVE:
Do NOT use cat, Get-Content, or full-file reads. Use the sidecar daemon or small slice reads.

SCOPE OF MILESTONE 2 (R3):
Implement the production modules for backtesting and hypotheses in `iq_regime_adaptive/`:
1. `iq_regime_adaptive/backtest/partitioner.py`:
   - Rigid chronological data partitioning: 50% In-Sample (IS), 25% Validation (VAL), 25% Out-of-Sample (OOS).
   - Strict h-bar boundary purging: purge any trade entry at index t where t + h > K_split to prevent outcome leakage into the adjacent partition.
   - Warmup embargo: skip W_warmup (default 60 bars) at partition boundaries so indicator rolling windows do not peek into adjacent partitions.
2. `iq_regime_adaptive/hypotheses/`:
   - `base_hypothesis.py`: Abstract Base Class BaseHypothesis defining generate_signals(df: pd.DataFrame, payout: float) and metadata.
   - `h001_range_mean_reversion.py`: Range regime + Bollinger touch + RSI oversold/overbought + rejection wick.
   - `h002_trend_pullback.py`: Trend regime + EMA 20/50 alignment + dynamic equilibrium retest.
   - `h003_volatility_expansion.py`: Expansion regime + Bollinger Bandwidth expansion + candle body dominance.
   - `h004_autocorrelation_reversion.py`: Negative lag-1 autocorrelation exhaustion mean reversion.
   - `h005_mtf_trend_alignment.py`: Multi-timeframe trend alignment (higher timeframe trend filter).
   - `h006_payout_filtered_edge.py`: High payout filtering (>= 80%) + conservative EV_WLB > 0 gating.
   - `h007_squeeze_breakout.py`: Volatility contraction squeeze (low BBW consolidation followed by volume/expansion breakout).
   - `h008_regime_adaptive_router.py`: Full regime router utilizing 5-tier classification with unconditional Chaos NO_TRADE veto.
   - `registry.py`: Registry helper to discover, instantiate, and run all hypotheses H001 to H008 by ID.
3. `iq_regime_adaptive/backtest/engine.py`:
   - Binary options simulation engine simulating trades at candle Close or next Open for expiry h bars (e.g. h=1 bar for M5).
   - Evaluates win/loss against payout yield and stake loss.
   - Integrates payout_filter.py and risk_allocation.py (fractional Kelly and fixed risk; zero martingale).
   - Logs individual trades with entry timestamp, direction, entry price, exit price, result, stake, PnL, running balance.
4. `iq_regime_adaptive/backtest/metrics.py`:
   - Computes nominal win rate, Wilson Lower Bound WLB_95%, normalized average EV per trade, Effective N (N_eff), Total PnL, Max Drawdown, Profit Factor, Sharpe/Sortino ratios.
5. `iq_regime_adaptive/backtest/degradation.py`:
   - Computes performance degradation across partitions:
     Delta EV = EV_IS - EV_OOS
     Degradation Index DI = (EV_IS - EV_OOS) / max(|EV_IS|, 1e-6)
     Delta WR = WR_IS - WR_OOS
     Composite Stability Score S_comp in [0, 100].
6. Unit and integration tests:
   - `iq_regime_adaptive/tests/test_backtest.py`
   - `iq_regime_adaptive/tests/test_hypotheses.py`
   - Ensure all tests run cleanly via `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`.
7. Deliver `handoff.md` and send message to orchestrator when complete.
