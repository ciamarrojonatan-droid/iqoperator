# Quantitative Verification & Research Report: Binary Options Regime-Adaptive Engine

**Generated At**: 2026-10-01T05:50:13.180357+00:00  
**Broker Payout Tested**: `85.0%`  
**Break-Even Hurdle ($P_{BE}$)**: `54.05%`  
**Dataset**: `data\BTCUSDT_M5_3y.csv` (315,360 candles)  

---

## 1. Executive Summary

This report documents the rigorous quantitative evaluation of binary options trading hypotheses across chronologically partitioned market data under non-anticipative execution. Binary contracts feature asymmetric payoffs where break-even requires $\hat{p} > 1 / (1 + B)$. To safeguard capital against overfitting and sample bias, all hypotheses are subjected to Wilson Score Interval Lower Bound ($WLB_{95\%}$) verification, Effective Degrees of Freedom ($N_{eff}$) serial autocorrelation penalties, and strict Out-of-Sample (OOS) performance degradation analysis.

### Recommended Champion Strategy
- **Champion**: `H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER` (H008)
- **Composite Stability Score ($S_{comp}$)**: **32.2 / 100**
- **Out-of-Sample Nominal Win Rate**: `50.00%`
- **Out-of-Sample Expected Value**: `-0.0750`
- **Stability Verdict**: **REJECTED**
- **Edge Governance Status**: **REJECTED**

---

## 2. Risk Governance & Anti-Martingale Verification Attestation

**Audit Status**: `[VERIFIED_ZERO_MARTINGALE]`  
**Allocation Compliance**: `FIXED_RISK_AND_STRICT_KELLY_COMPLIANT`  
**Trades Audited**: `60`  

### Attestation Invariants Verified:
1. **Non-Increasing Loss Response Invariant**:
   $$\frac{\partial \text{Stake}_t}{\partial L_{t-1}} \le 0$$
   A loss strictly never triggers an increase in position stake.
2. **Strict Capital Bounding Invariant**:
   $$\text{Stake}_t \le \text{Balance}_t \times \text{MaxRiskCap}$$
   Position stake is strictly capped at $\le 2.0\%$ of account equity.
3. **Monotonic Balance Contraction (Fractional Kelly)**:
   Under capital decay, position sizes contract monotonically, preventing ruin dynamics.
4. **Capital Kill-Switch Circuit Breaker**:
   Automatic liquidation and trading halt activated if cumulative drawdown breaches the circuit breaker threshold.

> *The backtest engine and execution models strictly forbid martingale, grid-averaging, and irrational asymmetric loss recovery multipliers. All stake allocations adhere to regularized fractional Kelly (gamma=0.25) and fixed fractional risk with non-increasing loss response and strict equity caps.*

---

## 3. Comparative Degradation Matrix (H001 - H008)

The table below compares In-Sample (IS) vs Out-of-Sample (OOS) performance, quantifying Expected Value degradation ($\Delta EV$), the Degradation Index ($DI$), and the 4-component Composite Stability Score ($S_{comp} \in [0, 100]$):

| Hyp ID | Family | $N_{IS}$ | $WR_{IS}$ | $EV_{IS}$ | $N_{OOS}$ | $WR_{OOS}$ | $WLB_{OOS}$ | $EV_{OOS}$ | $\Delta EV$ | $DI$ | $S_{comp}$ | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **H008** | META_ENSEMBLE_ROUTER | 20 | 55.0% | +0.018 | 20 | 50.0% | 29.9% | -0.075 | +0.092 | 5.29 | 32.2 | **REJECTED** |

---

## 4. Comprehensive Hypotheses Breakdown

### H008: Regime-Adaptive Meta-Router (`H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER`)
- **Family**: `META_ENSEMBLE_ROUTER`
- **Description**: Dynamically routes signals across regimes with strict Chaos veto.
- **Edge Governance Status**: **REJECTED**

| Partition | Trades ($N$) | Effective $N_{eff}$ | Nominal Win Rate | $WLB_{95\%}$ | Expected Value (EV) | Total PnL ($) | Max Drawdown | Profit Factor | Sharpe | Sortino |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **In-Sample (IS)** | 20 | 8.1 | 55.00% | 34.21% | +0.0175 | $+1.92 | 3.32% | 1.03 | 0.07 | 5.15 |
| **Validation (VAL)** | 20 | 15.2 | 55.00% | 34.21% | +0.0175 | $+1.92 | 2.15% | 1.03 | 0.07 | 12.01 |
| **Out-of-Sample (OOS)** | 20 | 10.5 | 50.00% | 29.93% | -0.0750 | $-10.12 | 4.25% | 0.84 | -0.38 | -29.33 |

**Degradation Diagnostics:**
- $\Delta EV$ ($EV_{IS} - EV_{OOS}$): `+0.0925`
- Degradation Index ($DI$): `5.2857`
- Win Rate Drop ($\Delta WR$): `+5.00 pp`
- Composite Stability Score ($S_{comp}$): **32.2 / 100** (\(\psi_{EV}=0.00, \psi_{stat}=0.00, \psi_{time}=1.00, \psi_{DD}=0.82\))
- Stability Verdict: **REJECTED**

---

## 5. Architectural Verification & Conclusion

1. **R3 Partitioning Immunity**: Rigorous 50/25/25 chronological partitioning with boundary purging and warmup embargo eliminates lookahead bias and state contamination.
2. **Strict Mathematical Hurdles**: Filtering strategies by $WLB_{95\%} > P_{BE}$ penalizes insufficient sample sizes and protects capital from statistical noise.
3. **Zero-Martingale Governance**: Monotonic position contraction under fractional Kelly mathematically eliminates blowup risk, ensuring long-term institutional survival.
