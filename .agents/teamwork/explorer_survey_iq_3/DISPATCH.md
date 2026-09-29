# Dispatch: Explorer Survey IQ 3

## 2026-09-29T02:38:15Z
You are Explorer Survey IQ 3.
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_3\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md (specifically the request from 2026-09-29T02:35:44Z).

Objective:
Research and rigorously specify the Backtest Engine Architecture, Out-of-Sample (OOS) Stability framework, and Hypotheses H001-H008:
1. R3: Data Partitioning:
   - Rigid chronological splitting into In-Sample (IS), Validation (VAL), and Out-of-Sample (OOS) partitions (e.g. 50% IS, 25% VAL, 25% OOS, or anchored walk-forward).
   - Zero lookahead bias, strict embargo/purging around candle transitions and expiry horizons.
2. Hypotheses H001 through H008:
   - Formulate concrete, testable quantitative trading hypotheses tailored to binary options (e.g.,
     H001: Range Mean Reversion (Bollinger + RSI/Stochastic) in Range regime with EV_WLB > 0.
     H002: Trend Pullback (EMA pullback + ADX confirmation) in Trend regime.
     H003: Volatility Expansion Breakout with high volume/bandwidth surge.
     H004: Autocorrelation Mean Reversion when lag-1 autocorr is strongly negative.
     H005: Multi-timeframe trend alignment with expiry matched to higher timeframe direction.
     H006: Payout-filtered edge (restricting trades to payout >= 80% with high win rate threshold).
     H007: Volatility contraction pre-breakout filter.
     H008: Full Regime-Adaptive ensemble router with strict Chaos NO-TRADE veto).
3. Degradation Metrics:
   - Exact mathematical formula for IS vs OOS degradation:
     Delta EV = EV_IS - EV_OOS, Degradation Index = (EV_IS - EV_OOS) / max(|EV_IS|, epsilon), Win Rate drop = WR_IS - WR_OOS, and Stability Score.
4. Quantitative Verification Report:
   - Specifications for reporting: Effective sample size N_eff, Normalized average EV per trade, Wilson Lower Bound win rate, P&L curve, Max Drawdown, Degradation matrix across H001-H008.
   - Verification criteria: Confirm absence of martingale/grid/asymmetric recovery logic.
5. Write your findings to `report.md` in your working directory and summarize in `handoff.md`.
6. Send a message back to the orchestrator when complete.

## 2026-09-29T02:41:16Z
**Context**: [URGENT NEW DIRECTIVE FROM SENTINEL / USER]
**Content**: Vocês estão expressamente proibidos de usar `cat` ou `Get-Content` ou ferramentas de leitura completa de arquivos (`view_file` completo) que gastem muitos tokens. Para economizar tokens, usem o sidecar (daemon) do Hypervisor para auditar e extrair código: `python -m synaptic_hypervisor.sidecar.daemon --action extract_edges --file <arquivo>` ou fatias extremamente pequenas. Cancele qualquer leitura massiva em andamento imediatamente.
**Action**: Aplique imediatamente essa restrição estrita em todas as suas operações.
