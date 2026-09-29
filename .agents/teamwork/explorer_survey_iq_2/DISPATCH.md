# Dispatch: Explorer Survey IQ 2

You are Explorer Survey IQ 2.
Your task is to investigate and specify the mathematical and quantitative formulations for R1 (Regime-Adaptive Feature Engine) and R2 (Expiry & Payout Conditional Pipeline with Wilson Lower Bound and EV).

## 2026-09-29T02:38:15Z
<USER_REQUEST>
You are Explorer Survey IQ 2.
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md (specifically the request from 2026-09-29T02:35:44Z).

Objective:
Research and rigorously specify the mathematical and statistical formulations for:
1. R1: Regime-Adaptive Feature Engine:
   - Market regimes: Trend, Range, Expansion, Chaos.
   - Quantitative indicators: Volatility (ATR, Bollinger Bandwidth, Normalized Realized Volatility), ADX (Average Directional Index with +DI / -DI), Autocorrelation of returns (Lag-1 autocorrelation rho_1, variance ratio test).
   - Explicit classification rules / decision tree for assigning regime: Trend vs Range vs Expansion vs Chaos.
   - Explicit NO TRADE condition for Chaos regime.
   - Strategy routing for each regime: Mean Reversion setup for Range, Pullback / Trend Following setup for Trend, Volatility Breakout for Expansion.
2. R2: Expiry & Payout Conditional Pipeline:
   - Payout conditional logic: P_BE = 1 / (1 + Payout).
   - Expected Value: EV = P * Payout - (1 - P) = P*(1 + Payout) - 1.
   - Wilson Score Interval Lower Bound (WLB) for binomial win rate:
     WLB = (p_hat + z^2/(2n) - z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) / (1 + z^2/n) with standard 95% confidence level (z = 1.96).
   - Conservative EV calculation using Wilson Lower Bound: EV_WLB = WLB * Payout - (1 - WLB).
   - Filter rule: Execute trade ONLY IF EV_WLB > 0 (or equivalently WLB > P_BE).
   - Risk allocation constraints: Strict zero martingale, zero irrational asymmetric compounding; evaluate fixed stake or fractional Kelly.
3. Write your complete formulation report to `report.md` in your working directory and summarize in `handoff.md`.
4. Send a message back to the orchestrator when complete.
</USER_REQUEST>

## 2026-09-29T02:41:16Z
**Context**: [URGENT NEW DIRECTIVE FROM SENTINEL / USER]
**Content**: Vocês estão expressamente proibidos de usar `cat` ou `Get-Content` ou ferramentas de leitura completa de arquivos (`view_file` completo) que gastem muitos tokens. Para economizar tokens, usem o sidecar (daemon) do Hypervisor para auditar e extrair código: `python -m synaptic_hypervisor.sidecar.daemon --action extract_edges --file <arquivo>` ou fatias extremamente pequenas. Cancele qualquer leitura massiva em andamento imediatamente.
**Action**: Aplique imediatamente essa restrição estrita em todas as suas operações.
