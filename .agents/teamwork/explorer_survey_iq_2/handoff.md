# Handoff Report — Explorer Survey IQ 2
**Mission**: Research and Rigorous Specification of Mathematical & Statistical Formulations for R1 & R2  
**Target Milestone**: Survey IQ 2  
**Working Directory**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\`  
**Date**: 2026-09-29T02:41:45Z  

---

## 1. Observation

1. **System & Objective Specification**:
   - `ORIGINAL_REQUEST.md` (lines 118–123):
     - R1: "O sistema deve classificar o ambiente de mercado atual (ex: Trend, Range, Expansion, Chaos) baseando-se em volatilidade, ADX e autocorrelação, e rotear o sinal para o setup estatisticamente adequado... O estado 'Chaos' deve gerar a decisão explícita de 'NO TRADE'."
     - R2: "A avaliação de sinais deve obrigatoriamente cruzar a probabilidade condicional de vitória com o Payout atual. O motor deve calcular a probabilidade de Break-Even ($P_{BE}$) e o Expected Value (EV), executando o trade apenas se $EV > 0$ considerando o limite inferior de Wilson (Wilson Lower Bound)."
     - Acceptance Criteria (line 132): "O código não deve possuir dependências de martingale ou alocação assimétrica irracional (risco fixo/Kelly strict)."
2. **Current Codebase Assets**:
   - `kelly.py` (lines 1–26): Implements a basic Kelly fraction stake `kelly_fraction_stake(balance, payout, winrate, fraction=0.25, max_risk=0.02)`. However, it uses raw sample winrate or basic Bayesian mixing (`empirical_winrate` in lines 29–42) without the Wilson Score Interval Lower Bound ($WLB$) or dynamic regime gating.
   - `strategies.py` (lines 5–213): Implements `donchian_fade_signal`, `bollinger_touch_signal`, `multi_mean_reversion_signal`, `rsi_m15_signal`, and `rsi_momentum_trend_signal`. However, signals are not conditionally routed through a market regime classifier or filtered by payout break-even thresholds.
   - `ml_filter.py` (lines 212–276): Features Bollinger Bands ($BBW$, $\%b$), Donchian Channels, and moving averages, but lacks normalized realized volatility Z-score, Parkinson volatility, and variance ratio tests.
3. **Mathematical Verification Execution**:
   - Ran Python verification in `.venv\Scripts\python.exe`:
     - Command: `.\.venv\Scripts\python.exe -c "..."`
     - Evaluated payout $b=0.85 \implies P_{BE} = \frac{1}{1.85} \approx 0.540541$.
     - Evaluated $WLB$:
       - For $n=10, \hat{p}=0.70 \implies WLB = 0.3968 \implies EV_{WLB} = -0.2660 < 0 \implies$ REJECTED.
       - For $n=50, \hat{p}=0.66 \implies WLB = 0.5215 \implies EV_{WLB} = -0.0352 < 0 \implies$ REJECTED.
       - For $n=100, \hat{p}=0.65 \implies WLB = 0.5525 \implies EV_{WLB} = +0.0222 > 0 \implies$ ACCEPTED.
       - For $n=300, \hat{p}=0.60 \implies WLB = 0.5436 \implies EV_{WLB} = +0.0057 > 0 \implies$ ACCEPTED.
   - Results confirm that $WLB$ strictly penalizes small sample sizes and protects against curve-fitting.

---

## 2. Logic Chain

1. **Premise 1 (Asymmetric Payout Barrier)**: In binary options, payout $b \in (0, 1]$ creates an inherent disadvantage where losing trades forfeit $100\%$ of stake while winning trades return only $+b \cdot S$.
2. **Step 2 (Break-Even Formulation)**: Setting expected value $EV = P \cdot b - (1 - P) \ge 0$ yields the fundamental requirement $P \ge P_{BE} = \frac{1}{1 + b}$. At typical broker payouts ($b = 0.80$ to $0.85$), $P_{BE}$ is between $54.05\%$ and $55.56\%$.
3. **Step 3 (Sample Variance & Small Sample Risk)**: Point estimates of sample win rate $\hat{p} = \frac{w}{n}$ exhibit massive standard error $\sqrt{\frac{p(1-p)}{n}}$ for small $n$ (e.g. $SE = 0.10$ for $n=25$). Inferring an edge from nominal win rate alone leads to severe capital depletion when market conditions drift.
4. **Step 4 (Wilson Lower Bound Derivation)**: By inverting the score test without relying on the symmetric Wald approximation, the Wilson Score Interval Lower Bound:
   $$WLB = \frac{\hat{p} + \frac{z^2}{2n} - z \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$
   guarantees with $95\%$ confidence ($z = 1.96$) that the true success probability is at least $WLB$.
5. **Step 5 (Conservative Filtering Invariant)**: Defining $EV_{WLB} = WLB(1 + b) - 1$ ensures that a trade is permitted to execute if and only if $EV_{WLB} > 0 \iff WLB > P_{BE}$.
6. **Step 6 (Regime Stratification)**: Single-regime strategies (e.g., pure mean reversion or pure trend following) suffer catastrophic drawdowns during adverse regimes. By stratifying into Trend ($ADX \ge 25, VR > 1.05, \rho_1 > 0$), Range ($ADX < 20, VR < 0.95, \rho_1 < 0$), Expansion (prior squeeze + $BBW_Z > 1.0$), and Chaos (fat-tailed shocks: $NRV > 3.0$ or $vol\_shock > 3.5$), we isolate stationary sub-spaces and strictly veto trading during chaotic periods.
7. **Step 7 (Ruin Elimination)**: Martingale staking ($S_k \propto (1/b)^k$) has an asymptotic ruin probability $\lim_{N \to \infty} \mathbb{P}(\text{Ruin}) = 1.0$ under finite bankroll or broker limits. We replace it with Regularized Fractional Kelly ($f^*_{WLB} = \frac{EV_{WLB}}{b}$ scaled by $\gamma = 0.25$ and capped at $2\%$), which is mathematically proven to guarantee positive long-term geometric compounding while preventing drawdown cascades.

---

## 3. Caveats

1. **Broker Slippage & Execution Delays**: The mathematical formulations assume frictionless order execution at candle open/close. In live OTC or fast market trading, microsecond execution delay or quotation spread may slightly degrade effective payout $b_{eff} = b - \text{friction}$. Implementers should include an execution buffer (e.g., $b_{eff} = b - 0.02$).
2. **Non-overlapping vs. Overlapping Expiries**: The Wilson score interval assumes independent Bernoulli trials. If multiple trades are taken simultaneously on correlated pairs or overlapping expiry windows, the effective degrees of freedom $N_{eff}$ will be less than the nominal trade count $n$.
3. **Data Availability**: Calculating the 50-bar baseline for $BBW\_Z$, $NRV$, and Wilder's $ADX$ requires a minimum warmup buffer of at least 60 closed candles before issuing valid regime classifications.

---

## 4. Conclusion

1. **R1 (Regime-Adaptive Feature Engine)** is fully specified with exact formulas for Volatility ($ATR$, $BBW$, $NRV$, Parkinson), Trend ($ADX$, $+DI/-DI$), and Market Memory ($\rho_1$, Lo-MacKinlay $VR(q)$), organized into a 5-tier deterministic priority decision tree with a hard **CHAOS NO-TRADE VETO** and explicit routing to Mean Reversion, Trend Pullback, and Volatility Breakout.
2. **R2 (Expiry & Payout Conditional Pipeline)** is fully specified with exact equations for $P_{BE} = \frac{1}{1 + b}$, $EV = P(1+b)-1$, closed-form Wilson Score Interval Lower Bound ($WLB$), conservative $EV_{WLB} > 0$ execution gate, and Regularized Quarter-Kelly risk sizing with zero martingale.
3. The complete quantitative research specification, mathematical derivations, sensitivity tables, and reference Python implementation are preserved in `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\report.md`.

---

## 5. Verification Method

To independently verify the mathematical accuracy, consistency, and execution validity of the formulations:

1. **Inspect Research Report**:
   - File path: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\report.md`
   - Check Sections 2 (Regime taxonomy & equations), 3 (Wilson derivation & Kelly), and 4 (Python reference code).
2. **Execute Mathematical Test Command**:
   Run the verification script using the project's virtual environment:
   ```powershell
   .\.venv\Scripts\python.exe -c "from iq_regime_formulations import compute_wilson_lower_bound, compute_payout_be; print('Verified!')"
   ```
   Or run the embedded self-check script:
   ```powershell
   .\.venv\Scripts\python.exe -c "
   import numpy as np
   def wlb(p, n, z=1.96):
       return (p + z**2/(2*n) - z*np.sqrt(p*(1-p)/n + z**2/(4*n**2))) / (1 + z**2/n)
   assert abs(wlb(0.65, 100) - 0.5525) < 0.001
   assert abs(1.0 / (1.0 + 0.85) - 0.540541) < 0.0001
   print('Mathematical Assertions Verified Successfully!')
   "
   ```
3. **Invalidation Conditions**:
   - The formulation is invalidated if $WLB \le P_{BE}$ yields a positive $EV_{WLB}$, or if any trade is permitted when $\mathcal{S}_t = \text{CHAOS}$.
