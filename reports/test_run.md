# Quantitative Verification & Research Report: Binary Options Regime-Adaptive Engine

**Generated At**: 2026-09-29T03:32:30.559129+00:00  
**Broker Payout Tested**: `85.0%`  
**Break-Even Hurdle ($P_{BE}$)**: `54.05%`  
**Dataset**: `data\EURUSD_M5_iq.csv` (20,000 candles)  

---

## 1. Executive Summary

This report documents the rigorous quantitative evaluation of binary options trading hypotheses across chronologically partitioned market data under non-anticipative execution. Binary contracts feature asymmetric payoffs where break-even requires $\hat{p} > 1 / (1 + B)$. To safeguard capital against overfitting and sample bias, all hypotheses are subjected to Wilson Score Interval Lower Bound ($WLB_{95\%}$) verification, Effective Degrees of Freedom ($N_{eff}$) serial autocorrelation penalties, and strict Out-of-Sample (OOS) performance degradation analysis.

### Recommended Champion Strategy
- **Champion**: `H001_RANGE_MEAN_REVERSION` (H001)
- **Composite Stability Score ($S_{comp}$)**: **35.0 / 100**
- **Out-of-Sample Nominal Win Rate**: `46.15%`
- **Out-of-Sample Expected Value**: `-0.1462`
- **Stability Verdict**: **REJECTED**
- **Edge Governance Status**: **REJECTED**

---

## 2. Risk Governance & Anti-Martingale Verification Attestation

**Audit Status**: `[PASSED - VERIFIED ZERO MARTINGALE]`  
**Allocation Compliance**: `FIXED_RISK_AND_STRICT_KELLY_COMPLIANT`  
**Trades Audited**: `176`  

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
| **H001** | STATISTICAL_MEAN_REVERSION | 21 | 50.0% | -0.075 | 13 | 46.2% | 23.2% | -0.146 | +0.071 | 0.95 | 35.0 | **REJECTED** |
| **H002** | TREND_CONTINUATION | 20 | 55.0% | +0.018 | 20 | 30.0% | 14.5% | -0.445 | +0.463 | 26.43 | 24.8 | **REJECTED** |
| **H006** | PAYOUT_EV_OPTIMIZATION | 20 | 60.0% | +0.110 | 20 | 40.0% | 21.9% | -0.260 | +0.370 | 3.36 | 29.7 | **REJECTED** |

---

## 4. Comprehensive Hypotheses Breakdown

### H001: Range Mean Reversion (`H001_RANGE_MEAN_REVERSION`)
- **Family**: `STATISTICAL_MEAN_REVERSION`
- **Description**: Fades 2-sigma Bollinger band penetrations with RSI exhaustion in low-ADX range regimes.
- **Edge Governance Status**: **REJECTED**

| Partition | Trades ($N$) | Effective $N_{eff}$ | Nominal Win Rate | $WLB_{95\%}$ | Expected Value (EV) | Total PnL ($) | Max Drawdown | Profit Factor | Sharpe | Sortino |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **In-Sample (IS)** | 21 | 15.2 | 50.00% | 29.93% | -0.0750 | $-10.11 | 4.15% | 0.85 | -0.37 | -30.27 |
| **Validation (VAL)** | 21 | 20.0 | 60.00% | 38.66% | +0.1100 | $+14.13 | 1.95% | 1.27 | 0.53 | 62.37 |
| **Out-of-Sample (OOS)** | 13 | 13.0 | 46.15% | 23.21% | -0.1462 | $-12.57 | 2.34% | 0.72 | -0.58 | -81.62 |

**Degradation Diagnostics:**
- $\Delta EV$ ($EV_{IS} - EV_{OOS}$): `+0.0712`
- Degradation Index ($DI$): `0.9487`
- Win Rate Drop ($\Delta WR$): `+3.85 pp`
- Composite Stability Score ($S_{comp}$): **35.0 / 100** (\(\psi_{EV}=0.00, \psi_{stat}=0.00, \psi_{time}=1.00, \psi_{DD}=1.00\))
- Stability Verdict: **REJECTED**

### H002: Trend Pullback (`H002_TREND_PULLBACK`)
- **Family**: `TREND_CONTINUATION`
- **Description**: Exploits directional continuation from dynamic EMA equilibrium pullbacks in trending regimes.
- **Edge Governance Status**: **REJECTED**

| Partition | Trades ($N$) | Effective $N_{eff}$ | Nominal Win Rate | $WLB_{95\%}$ | Expected Value (EV) | Total PnL ($) | Max Drawdown | Profit Factor | Sharpe | Sortino |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **In-Sample (IS)** | 20 | 10.5 | 55.00% | 34.21% | +0.0175 | $+1.93 | 3.32% | 1.03 | 0.07 | 6.87 |
| **Validation (VAL)** | 21 | 7.8 | 65.00% | 43.29% | +0.2025 | $+26.46 | 3.32% | 1.57 | 1.01 | 88.53 |
| **Out-of-Sample (OOS)** | 20 | 16.6 | 30.00% | 14.55% | -0.4450 | $-56.82 | 6.72% | 0.36 | -2.37 | -100.95 |

**Degradation Diagnostics:**
- $\Delta EV$ ($EV_{IS} - EV_{OOS}$): `+0.4625`
- Degradation Index ($DI$): `26.4286`
- Win Rate Drop ($\Delta WR$): `+25.00 pp`
- Composite Stability Score ($S_{comp}$): **24.8 / 100** (\(\psi_{EV}=0.00, \psi_{stat}=0.00, \psi_{time}=1.00, \psi_{DD}=0.32\))
- Stability Verdict: **REJECTED**

### H006: Payout Filtered Dynamic Edge (`H006_PAYOUT_FILTERED_DYNAMIC_EDGE`)
- **Family**: `PAYOUT_EV_OPTIMIZATION`
- **Description**: Strictly gates execution by minimum payout (>=0.80) and EV_WLB mathematical expectation.
- **Edge Governance Status**: **REJECTED**

| Partition | Trades ($N$) | Effective $N_{eff}$ | Nominal Win Rate | $WLB_{95\%}$ | Expected Value (EV) | Total PnL ($) | Max Drawdown | Profit Factor | Sharpe | Sortino |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **In-Sample (IS)** | 20 | 14.8 | 60.00% | 38.66% | +0.1100 | $+14.13 | 2.59% | 1.26 | 0.52 | 81.60 |
| **Validation (VAL)** | 20 | 18.1 | 50.00% | 29.93% | -0.0750 | $-10.11 | 2.34% | 0.85 | -0.37 | -68.10 |
| **Out-of-Sample (OOS)** | 20 | 15.6 | 40.00% | 21.88% | -0.2600 | $-33.78 | 4.34% | 0.56 | -1.31 | -109.91 |

**Degradation Diagnostics:**
- $\Delta EV$ ($EV_{IS} - EV_{OOS}$): `+0.3700`
- Degradation Index ($DI$): `3.3636`
- Win Rate Drop ($\Delta WR$): `+20.00 pp`
- Composite Stability Score ($S_{comp}$): **29.7 / 100** (\(\psi_{EV}=0.00, \psi_{stat}=0.00, \psi_{time}=1.00, \psi_{DD}=0.65\))
- Stability Verdict: **REJECTED**

---

## 5. Architectural Verification & Conclusion

1. **R3 Partitioning Immunity**: Rigorous 50/25/25 chronological partitioning with boundary purging and warmup embargo eliminates lookahead bias and state contamination.
2. **Strict Mathematical Hurdles**: Filtering strategies by $WLB_{95\%} > P_{BE}$ penalizes insufficient sample sizes and protects capital from statistical noise.
3. **Zero-Martingale Governance**: Monotonic position contraction under fractional Kelly mathematically eliminates blowup risk, ensuring long-term institutional survival.
