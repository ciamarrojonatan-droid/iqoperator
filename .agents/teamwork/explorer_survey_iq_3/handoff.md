# Handoff Report: Explorer Survey IQ 3

**Agent**: Explorer Survey IQ 3  
**Working Directory**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_3\`  
**Target Specification File**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_3\report.md`  
**Timestamp**: 2026-09-29T02:45:00Z  
**Type**: Hard Handoff (Task Complete)  

---

## 1. Observation

1. **Constitutional Requirements in `ORIGINAL_REQUEST.md` (lines 124-133)**:
   > "### R3. Estabilidade Out-of-Sample (OOS)  
   > A arquitetura deve separar rigidamente os dados em In-Sample (IS), Validation (VAL) e Out-of-Sample (OOS). O framework de backtest deve calcular a degradação de performance entre IS e OOS para avaliar a estabilidade de múltiplas hipóteses (H001-H008).  
   > ### Verificação Quantitativa  
   > - [ ] O backtester deve cuspir um relatório que inclua o N efetivo de trades, o EV médio normalizado e o Wilson Lower Bound da taxa de acerto.  
   > - [ ] A degradação (diferença de EV entre IS e OOS) deve ser calculada automaticamente para as hipóteses processadas.  
   > - [ ] O código não deve possuir dependências de martingale ou alocação assimétrica irracional (risco fixo/Kelly strict)."

2. **Existing Backtest Code Inspection**:
   - `backtest.py` (lines 145-161): Uses a basic Kelly fraction stake calculation and sequential evaluation, but lacks 3-way partitioning, boundary purging, and mathematical degradation scoring.
   - `research/h010/hypothesis.json` (lines 40-47): Precedent model H010 enforced $WLB_{95\%} > P_{BE}$ (+48.15 bps on $N=147$ across 153 OOS days) with $EV = +0.1578$ and monthly consistency checks.
   - `research/grid_families.py` (lines 76-245): Implements primitive signal generators (`fam_donchian`, `fam_boll`, `fam_stretch`, `fam_wick`, `fam_donchian_fade`, `fam_rsi_boll`), but used crude 70/30 splits without anti-leakage purging or automated degradation metrics.
   - `kelly.py` (lines 3-26): Formulates fractional Kelly $f^* = \frac{b \cdot p - q}{b}$ with risk cap `balance * max_risk`.

3. **Urgent Directive (2026-09-29T02:41:16Z)**:
   Strict prohibition of `cat`, `Get-Content`, and full-file views to conserve tokens. Read-only investigation required.

---

## 2. Logic Chain

1. **Binary Options Asymmetry Drives All Mathematical Formulations**:
   Because digital options pay $B \cdot \text{Stake}$ on wins ($B \in [0.75, 0.90]$) and lose $-1.0 \cdot \text{Stake}$ on losses, the break-even probability is strictly $P_{BE} = \frac{1}{1 + B} > 50\%$ (e.g., $54.05\%$ at $B=0.85$). Simple win rate is useless without pairing with payout $B$ and sample size $N$. Hence, Expected Value $EV = \hat{p}(1 + B) - 1$ and the conservative Wilson Lower Bound $WLB_{95\%}$ are the true invariants.

2. **From Time Series Properties to R3 Rigid Partitioning**:
   Financial time series are non-stationary with autoregressive volatility and regime switching. Random k-fold cross validation introduces catastrophic lookahead leakage. Therefore, data must be partitioned strictly chronologically: $50\%$ In-Sample (IS), $25\%$ Validation (VAL), and $25\%$ Out-of-Sample (OOS).

3. **From Binary Expiry Horizon to Purging & Embargo**:
   A trade entered at bar $t$ with expiry horizon $h$ resolves at $t+h$. If $t \in [K_{split} - h + 1, K_{split}]$, the outcome label uses price data from the next partition. Thus, mathematical purging of all entries where $t + h > K_{split}$ is strictly mandatory. Furthermore, because indicator state (EMA, RSI, ATR) has memory, an embargo window $E_{embargo} \ge \max(h, W_{warmup})$ must precede subsequent partitions.

4. **From Hypotheses H001-H008 to Regime Gating**:
   Single static strategies suffer periodic drawdowns during unfavorable market conditions. By mapping H001 (Range Mean Reversion) to `REGIME_RANGE`, H002 (Trend Pullback) to `REGIME_TREND`, H003/H007 to `REGIME_EXPANSION`, and enforcing a strict **NO-TRADE VETO** in H008 under `REGIME_CHAOS`, capital is insulated against whipsaws.

5. **From In-Sample to Out-of-Sample Degradation Metrics**:
   Overfitting manifests as a collapse in EV and win rate from IS to OOS. The metric triplet:
   $$\Delta EV = EV_{IS} - EV_{OOS}$$
   $$DI = \frac{EV_{IS} - EV_{OOS}}{\max(|EV_{IS}|, \varepsilon)}$$
   $$\Delta WR = WR_{IS} - WR_{OOS}$$
   combined with the Composite Stability Score $S_{comp} \in [0, 100]$ provides an objective, automated gatekeeper to approve or reject models prior to deployment.

6. **From Mathematical Invariants to Martingale Elimination**:
   Under Fractional Kelly sizing, $\text{Stake}_t = Balance_t \cdot \kappa \cdot f^*$. Following a loss, $Balance_t$ decreases, strictly causing $\text{Stake}_{t+1} < \text{Stake}_t$. This monotonicity property mathematically proves the impossibility of Martingale or grid escalation.

---

## 3. Caveats

1. **Broker Quote Execution Latency**: Backtest assumes execution at candle $t+1$ Open or Close with simulated slippage/latency $\delta_{lat} \le 250\text{ms}$. In live IQ Option execution, network disconnects or API websocket lags could degrade fills on high-frequency $h=60s$ trades.
2. **OTC vs Real Market Liquidity**: Real currency pairs follow interbank feeds with weekend market closures. IQ Option OTC pairs operate on synthetic/proprietary quote algorithms with potentially higher autocorrelation ($\rho_1 \ll 0$), requiring asset-specific parameter calibration.
3. **Payout Dynamism**: The specification models instantaneous payout $B(t)$. If historical candle datasets lack synchronized tick-by-tick broker payout logs, backtests must use conservative static payout tiers ($B = 0.80$ to $0.85$).

---

## 4. Conclusion

1. **Comprehensive Specification Delivered**: The complete quantitative research and backtest engine architecture has been specified and recorded in `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_3\report.md`.
2. **Architectural Foundations Established**:
   - R3 Chronological Partitioning ($50\%$ IS, $25\%$ VAL, $25\%$ OOS) with $h$-bar Purging and Warmup Embargo.
   - Complete quantitative blueprints for Hypotheses H001 through H008 with mathematical formulas and regime pre-conditions.
   - Exact mathematical degradation metrics ($\Delta EV, DI, \Delta WR, S_{comp}$).
   - Standard Quantitative Verification Report schema and mathematical anti-martingale proof.
3. **Implementer Readiness**: The architecture is fully prepared for Phase 2 implementation under `src/iq_regime/`.

---

## 5. Verification Method

1. **File Inspection**:
   Inspect `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_3\report.md` to confirm:
   - Section 1 contains complete R3 chronological partitioning, boundary purging formulas, and embargo rules.
   - Section 2 contains all 8 hypotheses (H001 to H008) with mathematical indicator definitions, entry triggers, expiry horizons, and falsification rules.
   - Section 3 contains exact mathematical definitions of $EV, WLB, \Delta EV, DI, \Delta WR,$ and $S_{comp}$.
   - Section 4 contains the Quantitative Verification Report JSON schema, Degradation Matrix, and Anti-Martingale mathematical proofs.
   - Section 5 contains the modular package layout for implementation.
2. **Mathematical Consistency**:
   - Verify that $P_{BE} = \frac{1}{1 + B}$ satisfies $EV = 0$ when $\hat{p} = P_{BE}$.
   - Verify that $\frac{\partial S_t}{\partial Balance_t} > 0$ under Fractional Kelly, ensuring monotonic risk contraction upon losses.
