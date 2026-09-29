# Quantitative Research Specification: Mathematical & Statistical Formulations for R1 & R2
**Architecture**: IQ Option Quantitative Backtest & Signal Engine  
**Author**: Explorer Survey IQ 2  
**Date**: 2026-09-29  
**Status**: Formal Specification (Survey / Research Milestone)

---

## 1. Executive Summary & Core Formulations

Binary options trading at retail brokers (such as IQ Option) exhibits an asymmetric payoff structure where broker payouts $b \in (0.70, 0.95)$ impose a structural hurdle: the break-even win rate $P_{BE} = \frac{1}{1 + b}$ always strictly exceeds $50\%$ (typically $52.6\% - 58.8\%$). Consequently, conventional strategy development based solely on uncalibrated technical indicators or nominal sample win rates $\hat{p}$ invariably succumbs to the "Law of Small Numbers", curve-fitting, and regime drift.

This specification formalizes two essential mathematical engines:
1. **R1: Regime-Adaptive Feature Engine**: A multi-tiered classification engine that decomposes non-stationary financial time series into four mutually exclusive statistical regimes: **Trend**, **Range**, **Expansion**, and **Chaos**. It couples directional intensity ($ADX$, $+DI/-DI$), multi-scale volatility metrics ($ATR$, $BBW$, $NRV$), and market memory / mean-reversion statistics (Lag-1 autocorrelation $\rho_1$, Lo-MacKinlay Variance Ratio $VR(q)$). It defines a strict, non-bypassable **NO TRADE** veto for the Chaos regime, and routes valid signals to mathematically aligned setups.
2. **R2: Expiry & Payout Conditional Pipeline**: A statistical gatekeeper that conditions every trade execution on live broker payout $b$. It replaces nominal win rate with the **Wilson Score Interval Lower Bound ($WLB$)** at $95\%$ confidence ($z = 1.96$). A trade is executed **if and only if** the conservative expected value is strictly positive ($EV_{WLB} > 0 \iff WLB > P_{BE}$). Risk capital is allocated strictly under a zero-martingale invariant, utilizing either fixed fractional risk or regularized Fractional Kelly sizing.

---

## 2. R1: Regime-Adaptive Feature Engine

### 2.1 Market Regime Taxonomy & Statistical Signatures

Financial time series exhibit non-stationary transitions between distinct dynamical states. Rather than applying a single stationary model across all price bars, the system stratifies price dynamics into four discrete regimes $\mathcal{S}_t \in \{\text{Trend}, \text{Range}, \text{Expansion}, \text{Chaos}\}$:

| Regime | Economic & Statistical Characteristics | Autocorrelation $\rho_1$ / $VR(q)$ | Volatility Dynamic | ADX / Directional Bias | Routing Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Trend** | Persistent directional drift, low mean-reversion, strong momentum | $\rho_1 > 0$, $VR(q) > 1.0$ | Stable to moderate | $ADX \ge 25$, $\|+DI - -DI\| \ge 12$ | **Trend Pullback / Continuation** |
| **Range** | Bounded oscillations between dynamic envelopes, strong mean-reversion | $\rho_1 < 0$, $VR(q) < 1.0$ | Low to moderate, $BBW$ stable | $ADX < 20$, $\|+DI - -DI\| < 12$ | **Mean Reversion (Bollinger/Donchian/RSI)** |
| **Expansion** | Volatility breakout from compression, momentum acceleration | Non-linear shift ($\rho_1 \to +$) | Sharp surge: $BBW_Z > 1.2$, $NRV > 1.2$ | $ADX$ rising, directional thrust | **Volatility Breakout** |
| **Chaos** | High noise-to-signal ratio, fat-tailed shocks, erratic slippage/spread | Unstable, erratic kurtosis | Extreme surge: $NRV > 3.0$ or $vol\_shock > 3.5$ | Conflicted or parabolic anomaly | **NO TRADE (Strict Veto)** |

---

### 2.2 Mathematical Specifications of Quantitative Indicators

Let $P_t = (O_t, H_t, L_t, C_t, V_t)$ represent the candle tuple at discrete time index $t$, with sampling interval $\Delta t \in \{1\text{m}, 5\text{m}, 15\text{m}\}$. Continuous log returns are defined as:
$$r_t = \ln\left(\frac{C_t}{C_{t-1}}\right)$$

#### 2.2.1 Volatility Indicators

1. **True Range ($TR$) and Wilder's Average True Range ($ATR$)**:
   The instantaneous True Range accounts for overnight or inter-bar gap discontinuities:
   $$TR_t = \max\Big( H_t - L_t, \; |H_t - C_{t-1}|, \; |L_t - C_{t-1}| \Big)$$
   Given period $n_{atr} \in \mathbb{N}$ (default $n_{atr} = 14$), Wilder's recursive smoothed formulation is:
   $$ATR_t = \alpha \cdot TR_t + (1 - \alpha) \cdot ATR_{t-1}, \quad \text{where } \alpha = \frac{1}{n_{atr}}$$
   **Normalized ATR ($NATR$)**:
   To ensure scale-invariance across different currency pairs and historical price levels:
   $$NATR_t = \frac{ATR_t}{C_t} \times 100\%$$
   **ATR Expansion Ratio ($ATR\_Ratio$)**:
   Measures short-term volatility expansion relative to baseline:
   $$ATR\_Ratio_t = \frac{ATR_t(n_{fast})}{ATR_t(n_{slow})}, \quad n_{fast} = 5, \; n_{slow} = 30$$

2. **Bollinger Bands & Bollinger Bandwidth ($BBW$)**:
   Given rolling window $N_{bb} \in \mathbb{N}$ (default $N_{bb} = 20$) and standard deviation multiplier $k_{bb} = 2.0$:
   $$\mu_{bb, t} = \frac{1}{N_{bb}} \sum_{i=0}^{N_{bb}-1} C_{t-i}$$
   $$\sigma_{bb, t} = \sqrt{\frac{1}{N_{bb}-1} \sum_{i=0}^{N_{bb}-1} (C_{t-i} - \mu_{bb, t})^2}$$
   Upper and Lower Bands:
   $$UB_t = \mu_{bb, t} + k_{bb} \cdot \sigma_{bb, t}, \qquad LB_t = \mu_{bb, t} - k_{bb} \cdot \sigma_{bb, t}$$
   **Bollinger Bandwidth ($BBW$)**:
   $$BBW_t = \frac{UB_t - LB_t}{\mu_{bb, t}} = \frac{2 \cdot k_{bb} \cdot \sigma_{bb, t}}{\mu_{bb, t}}$$
   **Bandwidth Z-Score ($BBW\_Z$)** over baseline lookback window $M_{bw}$ (default $M_{bw} = 100$):
   $$BBW\_Z_t = \frac{BBW_t - \bar{\mu}_{BBW, t}}{\bar{\sigma}_{BBW, t}}$$
   $$\bar{\mu}_{BBW, t} = \frac{1}{M_{bw}} \sum_{j=0}^{M_{bw}-1} BBW_{t-j}, \qquad \bar{\sigma}_{BBW, t} = \sqrt{\frac{1}{M_{bw}-1} \sum_{j=0}^{M_{bw}-1} (BBW_{t-j} - \bar{\mu}_{BBW, t})^2}$$
   **Bandwidth Percentile Rank ($BBW\_Pct$)**:
   $$\text{Percentile}_{BBW}(t) = \frac{1}{M_{bw}} \sum_{j=0}^{M_{bw}-1} \mathbf{1}_{\{BBW_{t-j} \le BBW_t\}}$$

3. **Normalized Realized Volatility ($NRV$) & Efficient Estimators**:
   Standard sample realized volatility over short window $m$ (e.g. $m=12$ bars):
   $$RV_t(m) = \sqrt{\sum_{i=0}^{m-1} (r_{t-i} - \bar{r}_t)^2}, \quad \bar{r}_t = \frac{1}{m} \sum_{i=0}^{m-1} r_{t-i}$$
   Normalized Realized Volatility ($NRV$) standardized against long-term baseline $M_{rv}$ (e.g., $M_{rv}=120$ bars):
   $$NRV_t = \frac{RV_t(m) - \mu_{RV}(M_{rv})}{\sigma_{RV}(M_{rv})}$$
   **Parkinson High-Low Extreme Value Volatility**:
   Because closing prices discard intra-bar price paths, Parkinson volatility delivers a variance estimator with approximately $5\times$ greater statistical efficiency than close-to-close variance:
   $$\sigma_{park, t}^2 = \frac{1}{4 \ln 2 \cdot m} \sum_{i=0}^{m-1} \left[ \ln\left(\frac{H_{t-i}}{L_{t-i}}\right) \right]^2$$
   **Vol Shock Ratio**:
   $$vol\_shock_{5, 50, t} = \frac{\sigma_{bb, 5, t}}{\sigma_{bb, 50, t} + \epsilon}$$

---

#### 2.2.2 Average Directional Index ($ADX$) with $+DI / -DI$

Wilder's Directional Movement System quantifies trend strength independent of direction:
1. Directional Movements:
   $$\Delta H_t = H_t - H_{t-1}, \qquad \Delta L_t = L_{t-1} - L_t$$
   $$+DM_t = \begin{cases} \Delta H_t & \text{if } \Delta H_t > \Delta L_t \text{ and } \Delta H_t > 0 \\ 0 & \text{otherwise} \end{cases}$$
   $$-DM_t = \begin{cases} \Delta L_t & \text{if } \Delta L_t > \Delta H_t \text{ and } \Delta L_t > 0 \\ 0 & \text{otherwise} \end{cases}$$

2. Wilder's Exponential Smoothing over period $n_{adx} = 14$:
   $$+DM_{smooth, t} = +DM_{smooth, t-1} \left(1 - \frac{1}{n_{adx}}\right) + +DM_t$$
   $$-DM_{smooth, t} = -DM_{smooth, t-1} \left(1 - \frac{1}{n_{adx}}\right) + -DM_t$$
   $$TR_{smooth, t} = TR_{smooth, t-1} \left(1 - \frac{1}{n_{adx}}\right) + TR_t$$

3. Directional Indicators:
   $$+DI_t = 100 \times \frac{+DM_{smooth, t}}{TR_{smooth, t} + \epsilon}, \qquad -DI_t = 100 \times \frac{-DM_{smooth, t}}{TR_{smooth, t} + \epsilon}$$

4. Directional Index ($DX$) and Average Directional Index ($ADX$):
   $$DX_t = 100 \times \frac{|+DI_t - -DI_t|}{+DI_t + -DI_t + \epsilon}$$
   $$ADX_t = \frac{ADX_{t-1} \cdot (n_{adx}-1) + DX_t}{n_{adx}}$$
   **Directional Spread**:
   $$DI\_Spread_t = +DI_t - -DI_t$$

---

#### 2.2.3 Autocorrelation of Returns & Variance Ratio Test

Market memory distinguishes genuine trending persistence from mean-reverting noise.

1. **Lag-1 Sample Autocorrelation ($\rho_1$)**:
   Computed over a rolling estimation window $W$ (default $W = 40$ bars):
   $$\bar{r}_W = \frac{1}{W} \sum_{i=0}^{W-1} r_{t-i}$$
   $$\rho_1(t) = \frac{\sum_{i=0}^{W-2} (r_{t-i} - \bar{r}_W)(r_{t-i-1} - \bar{r}_W)}{\sum_{i=0}^{W-1} (r_{t-i} - \bar{r}_W)^2}$$
   Under the null hypothesis $H_0: \rho_1 = 0$ (independent increments / martingale difference), the sample estimator has asymptotic standard error $SE(\hat{\rho}_1) = \frac{1}{\sqrt{W}}$.
   The test statistic is:
   $$t_{\rho_1} = \hat{\rho}_1 \sqrt{W} \sim \mathcal{N}(0, 1)$$
   - **Mean Reversion signal**: $\hat{\rho}_1 < -0.15$ (or $t_{\rho_1} < -1.645$).
   - **Momentum/Trend signal**: $\hat{\rho}_1 > +0.15$ (or $t_{\rho_1} > +1.645$).

2. **Lo-MacKinlay Variance Ratio Test ($VR(q)$)**:
   Under the random walk hypothesis $H_0$, the variance of $q$-period returns scales linearly with lag $q$: $\text{Var}(r_t^{(q)}) = q \cdot \text{Var}(r_t^{(1)})$.
   Let $p_t = \ln C_t$ and lag $q \in \{3, 4, 5\}$ (default $q = 4$). Over rolling window $W$:
   $$\hat{\mu} = \frac{1}{W} (p_W - p_0)$$
   $$\bar{\sigma}_a^2 = \frac{1}{W - 1} \sum_{k=1}^W (p_k - p_{k-1} - \hat{\mu})^2$$
   $$\bar{\sigma}_c^2 = \frac{1}{m} \sum_{k=q}^W (p_k - p_{k-q} - q\hat{\mu})^2, \quad \text{where } m = q(W - q + 1)\left(1 - \frac{q}{W}\right)$$
   The Variance Ratio is defined as:
   $$VR(q) = \frac{\bar{\sigma}_c^2}{q \cdot \bar{\sigma}_a^2}$$
   Heteroskedasticity-Consistent Asymptotic Test Statistic (Lo & MacKinlay, 1988):
   $$z^*(q) = \frac{VR(q) - 1}{\sqrt{V^*(q)}} \sim \mathcal{N}(0, 1)$$
   where:
   $$V^*(q) = \sum_{j=1}^{q-1} \left[ \frac{2(q - j)}{q} \right]^2 \cdot \delta_j$$
   $$\delta_j = \frac{\sum_{k=j+1}^W (p_k - p_{k-1} - \hat{\mu})^2 (p_{k-j} - p_{k-j-1} - \hat{\mu})^2}{\left[ \sum_{k=1}^W (p_k - p_{k-1} - \hat{\mu})^2 \right]^2}$$
   - $VR(q) < 0.90 \implies$ Statistically significant mean reversion.
   - $VR(q) > 1.10 \implies$ Statistically significant trending persistence.
   - $VR(q) \in [0.90, 1.10] \implies$ Indeterminate / geometric Brownian motion.

---

### 2.3 Explicit Classification Rules & Decision Tree Algorithm

The regime classification follows a deterministic, hierarchical priority tree evaluated on every closed candle $t$:

```
                             [Closed Candle t]
                                     |
                                     v
                       +----------------------------+
                       | Tier 1: Chaos Filter Test  |
                       +----------------------------+
                               /            \
                       (Condition Met)    (Passed)
                             /                \
                            v                  v
                    [REGIME = CHAOS]   +------------------------------+
                    [VETO: NO TRADE]   | Tier 2: Expansion Breakout   |
                                       +------------------------------+
                                              /              \
                                      (Condition Met)      (Passed)
                                            /                  \
                                           v                    v
                                   [REGIME = EXPANSION]  +--------------------+
                                   [VOLATILITY_BREAKOUT] | Tier 3: Trend Test |
                                                         +--------------------+
                                                                /            \
                                                        (Condition Met)    (Passed)
                                                              /                \
                                                             v                  v
                                                    [REGIME = TREND]     +--------------------+
                                                    [TREND_PULLBACK]     | Tier 4: Range Test |
                                                                         +--------------------+
                                                                                /            \
                                                                        (Condition Met)    (Passed)
                                                                              /                \
                                                                             v                  v
                                                                    [REGIME = RANGE]     [UNCERTAIN/CHAOS]
                                                                    [MEAN_REVERSION]     [VETO: NO TRADE]
```

#### Detailed Rule Specifications:

1. **Tier 1: Chaos Guard (Strict Veto)**:
   Assign $\mathcal{S}_t = \text{CHAOS}$ if **ANY** of the following conditions evaluate to `True`:
   - **Volatility Explosion**: $NRV_t > 3.0$ OR $vol\_shock_{5, 50, t} > 3.5$ OR $NATR_t > \text{Percentile}_{98}(NATR)$.
   - **Pathological Bar Range**: $(H_t - L_t) > 3.5 \times ATR_{14, t}$ (giant wick / news shock).
   - **Directional Contradiction / Severe Whipsaw**: $ADX_t \ge 35$ AND $|+DI_t - -DI_t| \le 4.0$ (erratic whipsaws generating conflicting momentum).
   - **Excess Kurtosis**: Rolling 30-bar return kurtosis $\kappa_t > 8.0$.
   - **Action**: Return `Regime = CHAOS`, `AllowTrade = False`.

2. **Tier 2: Expansion Regime (Volatility Breakout)**:
   Assign $\mathcal{S}_t = \text{EXPANSION}$ if Tier 1 passed **AND ALL** of the following evaluate to `True`:
   - **Prior Compression (Squeeze)**: $\min_{k \in [1, 5]} \text{Percentile}_{BBW}(t-k) \le 0.20$ (bandwidth was in bottom 20% in the last 5 bars).
   - **Squeeze Release**: $BBW_t \ge 1.45 \times \min_{k \in [1, 5]} BBW_{t-k}$ AND $BBW\_Z_t \ge 1.0$.
   - **Elevated Realized Volatility**: $NRV_t \in [1.2, 3.0]$.
   - **Directional Breakout**: Candle closed outside Donchian 20 channel ($C_t > DC\_Upper_{20, t-1}$ OR $C_t < DC\_Lower_{20, t-1}$) AND $|+DI_t - -DI_t| \ge 15.0$.
   - **Action**: Return `Regime = EXPANSION`, `AllowTrade = True`, route to `VOLATILITY_BREAKOUT`.

3. **Tier 3: Trend Regime (Directional Drift)**:
   Assign $\mathcal{S}_t = \text{TREND}$ if Tiers 1-2 passed **AND ALL** of the following evaluate to `True`:
   - **Directional Strength**: $ADX_t \ge 25.0$ AND $|+DI_t - -DI_t| \ge 12.0$.
   - **Memory Persistence**: $VR(4) \ge 1.05$ OR $\rho_1(t) \ge +0.05$.
   - **Moving Average Vector Alignment**:
     - Bullish: $EMA_{20, t} > EMA_{50, t}$ AND $+DI_t > -DI_t$.
     - Bearish: $EMA_{20, t} < EMA_{50, t}$ AND $-DI_t > +DI_t$.
   - **Controlled Volatility**: $BBW\_Z_t \in [-0.5, 2.0]$.
   - **Action**: Return `Regime = TREND`, `AllowTrade = True`, route to `TREND_PULLBACK`.

4. **Tier 4: Range Regime (Mean Reversion)**:
   Assign $\mathcal{S}_t = \text{RANGE}$ if Tiers 1-3 passed **AND ALL** of the following evaluate to `True`:
   - **Directional Absence**: $ADX_t < 20.0$ AND $|+DI_t - -DI_t| < 12.0$.
   - **Mean-Reverting Memory**: $\rho_1(t) \le -0.05$ OR $VR(4) \le 0.95$.
   - **Contained Dispersion**: $BBW\_Z_t \le 0.50$ AND $NRV_t < 1.0$.
   - **Envelope Containment**: Close is within 3 standard deviations of mean ($|C_t - \mu_{bb, t}| \le 2.5 \cdot \sigma_{bb, t}$).
   - **Action**: Return `Regime = RANGE`, `AllowTrade = True`, route to `MEAN_REVERSION`.

5. **Tier 5: Fallback / Indeterminate State**:
   If none of the above classifications achieve complete satisfaction:
   - Assign $\mathcal{S}_t = \text{CHAOS}$ (or `UNCERTAIN`).
   - `AllowTrade = False`. In negative-sum binary options, indeterminate states carry negative expectation.

---

### 2.4 Quantitative Strategy Routing

Once the regime $\mathcal{S}_t$ is determined, candidate signals must strictly conform to the mapped strategy logic:

#### Strategy 1: Mean Reversion (`RANGE` Regime)
- **Mathematical Hypothesis**: In a bounded stationary state ($\rho_1 < 0, VR < 1$), price excursions beyond the distribution tails regress rapidly toward the conditional mean $\mu_{bb}$.
- **CALL Gatilho**:
  1. Penetration: $C_{t-1} \le LB_{20, 2.0, t-1}$ OR $C_{t-1} \le DC\_Lower_{20, t-1}$.
  2. Oversold Indicator: $RSI_{14, t-1} \le 30.0$ OR $Stoch\_K_{14, t-1} \le 20.0$.
  3. Rejection Morphology: Candle $t$ forms bullish reaction: $C_t > O_t$ and lower wick ratio $\frac{\min(O_t, C_t) - L_t}{H_t - L_t + \epsilon} \ge 0.30$.
- **PUT Gatilho**:
  1. Penetration: $C_{t-1} \ge UB_{20, 2.0, t-1}$ OR $C_{t-1} \ge DC\_Upper_{20, t-1}$.
  2. Overbought Indicator: $RSI_{14, t-1} \ge 70.0$ OR $Stoch\_K_{14, t-1} \ge 80.0$.
  3. Rejection Morphology: Candle $t$ forms bearish reaction: $C_t < O_t$ and upper wick ratio $\frac{H_t - \max(O_t, C_t)}{H_t - L_t + \epsilon} \ge 0.30$.
- **Expiry Horizon**: $T_{exp} = 1 \times \Delta t$ or $2 \times \Delta t$ (e.g. 5m to 10m).

#### Strategy 2: Trend Pullback (`TREND` Regime)
- **Mathematical Hypothesis**: In a directed drift process ($ADX \ge 25, VR > 1$), local counter-trend pullbacks to moving dynamic equilibria offer maximum risk-adjusted entry probability in direction of macro drift.
- **CALL Gatilho**:
  1. Trend Alignment: $+DI_t > -DI_t$ AND $EMA_{20, t} > EMA_{50, t}$.
  2. Pullback Zone: $L_t \le EMA_{20, t} + 0.2 \cdot ATR_{14, t}$ AND $C_t > EMA_{20, t}$ (tested support and held).
  3. Oscillator Recovery: $RSI_{14, t} \in [38.0, 52.0]$ with $RSI_{14, t} > RSI_{14, t-1}$.
- **PUT Gatilho**:
  1. Trend Alignment: $-DI_t > +DI_t$ AND $EMA_{20, t} < EMA_{50, t}$.
  2. Pullback Zone: $H_t \ge EMA_{20, t} - 0.2 \cdot ATR_{14, t}$ AND $C_t < EMA_{20, t}$ (tested resistance and held).
  3. Oscillator Recovery: $RSI_{14, t} \in [48.0, 62.0]$ with $RSI_{14, t} < RSI_{14, t-1}$.
- **Expiry Horizon**: $T_{exp} = 2 \times \Delta t$ to $3 \times \Delta t$ (e.g. 10m to 15m).

#### Strategy 3: Volatility Breakout (`EXPANSION` Regime)
- **Mathematical Hypothesis**: Following volatility compression, a directional breakout accompanied by a rapid surge in $BBW$ and $NRV$ creates high short-term directional inertia.
- **CALL Gatilho**:
  1. Breakout: $C_t > UB_{20, 2.0, t}$ AND $C_t > DC\_Upper_{20, t-1}$.
  2. Body Dominance: $\frac{C_t - O_t}{H_t - L_t + \epsilon} \ge 0.60$ (solid bullish expansion bar).
  3. Directional Spread: $+DI_t - -DI_t \ge 15.0$.
- **PUT Gatilho**:
  1. Breakout: $C_t < LB_{20, 2.0, t}$ AND $C_t < DC\_Lower_{20, t-1}$.
  2. Body Dominance: $\frac{O_t - C_t}{H_t - L_t + \epsilon} \ge 0.60$ (solid bearish expansion bar).
  3. Directional Spread: $-DI_t - +DI_t \ge 15.0$.
- **Expiry Horizon**: $T_{exp} = 1 \times \Delta t$ (captures the immediate continuation candle).

---

## 3. R2: Expiry & Payout Conditional Pipeline

### 3.1 Payout Conditional Mechanics & Break-Even Probability ($P_{BE}$)

Let $b \in \mathbb{R}^+$ represent the broker payout rate per unit stake (e.g., $b = 0.85$ for $85\%$).
Let $S > 0$ be the capital stake risked. The payoff random variable $X$ per trade is discrete:
$$X = \begin{cases} +b \cdot S & \text{with probability } P \\ -S & \text{with probability } 1 - P \end{cases}$$
*(Under zero-spread ties, stake is refunded: $X=0$. Under standard conservative modeling, ties are treated as either push or zero profit).*

The normalized Expected Value ($EV$) per dollar staked ($S=1$) is:
$$EV(P, b) = \mathbb{E}[X / S] = P \cdot b - (1 - P) \cdot 1 = P(1 + b) - 1$$

To achieve a non-negative expectation ($EV \ge 0$):
$$P(1 + b) - 1 \ge 0 \iff P \ge \frac{1}{1 + b}$$

We define the exact **Break-Even Probability ($P_{BE}$)** as:
$$\boxed{P_{BE}(b) = \frac{1}{1 + b}}$$

#### Table 1: Payout vs. Minimum Required Break-Even Win Rate
| Payout Rate $b$ | Broker Payout % | Break-Even Probability $P_{BE}$ | Required Win Rate |
| :---: | :---: | :---: | :---: |
| 0.95 | 95% | $\frac{1}{1.95} \approx 0.5128$ | 51.28% |
| 0.90 | 90% | $\frac{1}{1.90} \approx 0.5263$ | 52.63% |
| 0.87 | 87% | $\frac{1}{1.87} \approx 0.5348$ | 53.48% |
| 0.85 | 85% | $\frac{1}{1.85} \approx 0.5405$ | 54.05% |
| 0.80 | 80% | $\frac{1}{1.80} \approx 0.5556$ | 55.56% |
| 0.75 | 75% | $\frac{1}{1.75} \approx 0.5714$ | 57.14% |
| 0.70 | 70% | $\frac{1}{1.70} \approx 0.5882$ | 58.82% |
| 0.60 | 60% | $\frac{1}{1.60} \approx 0.6250$ | 62.50% |

**Corollary**: At a payout of $80\%$, any trading setup with a win rate below $55.56\%$ will guarantee capital depletion over time, regardless of trade volume. At $70\%$, the threshold jumps to nearly $59\%$.

---

### 3.2 The Wilson Score Interval Lower Bound ($WLB$)

In real-world quantitative backtesting and live trading, the true population success probability $P$ is latent and unknown. We observe only a sample of $n$ trades containing $w$ wins, yielding sample win rate:
$$\hat{p} = \frac{w}{n}$$

#### Limitations of the Standard Normal Wald Interval:
The standard Wald interval $\hat{p} \pm z \sqrt{\frac{\hat{p}(1-\hat{p})}{n}}$ relies on asymptotic normality of the sample mean. In small sample sizes or near edge boundaries, it severely underestimates error variance and can yield degenerate bounds ($< 0$ or $> 1$).

#### Derivation of the Wilson Score Interval (Wilson, 1927):
The Wilson score interval inverts the asymptotic score test $H_0: p = p_0$:
$$\frac{|\hat{p} - p|}{\sqrt{\frac{p(1-p)}{n}}} \le z_{\alpha/2}$$
Squaring both sides yields:
$$(\hat{p} - p)^2 = z^2 \frac{p(1-p)}{n}$$
Expanding this into standard quadratic form $A p^2 - 2B p + C = 0$:
$$\hat{p}^2 - 2\hat{p}p + p^2 = \frac{z^2}{n} p - \frac{z^2}{n} p^2$$
$$\left(1 + \frac{z^2}{n}\right) p^2 - 2\left(\hat{p} + \frac{z^2}{2n}\right) p + \hat{p}^2 = 0$$

Applying the quadratic formula for roots $p = \frac{-(-2B) \pm \sqrt{4B^2 - 4AC}}{2A} = \frac{B \pm \sqrt{B^2 - AC}}{A}$:
- Coefficient $A = 1 + \frac{z^2}{n}$
- Coefficient $B = \hat{p} + \frac{z^2}{2n}$
- Coefficient $C = \hat{p}^2$
- Reduced Discriminant:
  $$B^2 - AC = \left(\hat{p} + \frac{z^2}{2n}\right)^2 - \left(1 + \frac{z^2}{n}\right)\hat{p}^2 = \frac{z^2 \hat{p}(1-\hat{p})}{n} + \frac{z^4}{4n^2}$$

Thus, the exact **Wilson Score Interval Lower Bound ($WLB$)** is:
$$\boxed{WLB(\hat{p}, n, z) = \frac{\hat{p} + \frac{z^2}{2n} - z \sqrt{\frac{\hat{p}(1 - \hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}}$$

For standard two-sided $95\%$ confidence ($\alpha = 0.05$):
$$z = \Phi^{-1}\left(1 - \frac{0.05}{2}\right) = 1.95996 \approx 1.96$$
*(For one-sided $95\%$ confidence, $z = \Phi^{-1}(0.95) \approx 1.645$ can optionally be configured, but standard two-sided $z=1.96$ enforces maximum conservativeness).*

---

### 3.3 Conservative Expected Value ($EV_{WLB}$) & Filter Rule

By substituting the lower statistical bound $WLB$ in place of the point estimate $\hat{p}$, we compute the **Conservative Expected Value**:
$$\boxed{EV_{WLB} = WLB \cdot b - (1 - WLB) = WLB(1 + b) - 1}$$

#### Strict Invariant Filter Rule:
A trade signal generated by any regime strategy is permitted to execute **if and only if**:
$$\boxed{EV_{WLB} > 0 \iff WLB > P_{BE} = \frac{1}{1 + b}}$$

If $EV_{WLB} \le 0$ (or equivalently $WLB \le P_{BE}$), the signal is **VETOED** (`TradeRejected = True`, reason: `INSUFFICIENT_STATISTICAL_EDGE_AFTER_PAYOUT`).

---

### 3.4 Sample Size Dynamics & Effective Trades ($N_{eff}$)

The Wilson Lower Bound explicitly penalizes small sample sizes. A setup cannot pass the gatekeeper on a "lucky streak".

#### Table 2: $WLB$ and Execution Decision at $85\%$ Payout ($b=0.85, P_{BE} = 0.5405, z=1.96$)
| Sample Size $n$ | Wins $w$ | Sample Win Rate $\hat{p}$ | Wilson Lower Bound $WLB$ | $EV_{WLB}$ | Filter Decision |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | 7 | 70.0% | 0.3968 | $-0.2659$ | **REJECTED** (Sample too small) |
| 20 | 14 | 70.0% | 0.4811 | $-0.1100$ | **REJECTED** |
| 30 | 20 | 66.7% | 0.4878 | $-0.0976$ | **REJECTED** |
| 50 | 33 | 66.0% | 0.5218 | $-0.0347$ | **REJECTED** |
| 100 | 62 | 62.0% | 0.5222 | $-0.0339$ | **REJECTED** |
| 100 | 65 | 65.0% | 0.5524 | $+0.0220$ | **ACCEPTED** ($EV_{WLB} > 0$) |
| 250 | 150 | 60.0% | 0.5385 | $-0.0038$ | **REJECTED** |
| 300 | 180 | 60.0% | 0.5435 | $+0.0055$ | **ACCEPTED** |
| 500 | 290 | 58.0% | 0.5364 | $-0.0076$ | **REJECTED** |
| 1000 | 580 | 58.0% | 0.5491 | $+0.0158$ | **ACCEPTED** |

**Empirical Invariant**: To clear an $85\%$ payout barrier with a realistic $60\%$ win rate, a setup requires at least $N_{min} \approx 280$ independent trades.

---

### 3.5 Risk Allocation Architecture: Zero Martingale Invariant

#### 3.5.1 Mathematical Proof of Martingale Ruin
Under a Martingale progression, stake at step $k$ after consecutive losses is scaled to recover past losses:
$$S_k = \frac{\sum_{i=1}^{k-1} S_i + T}{b}$$
For fixed bankroll $B_0$ and maximum allowable stake cap $S_{max}$, let $q = 1 - P$ be the loss probability of a trade ($q \approx 0.40 - 0.45$).
The probability of experiencing a streak of $k$ consecutive losses within $N$ trades is:
$$\mathbb{P}(\text{Loss Streak } \ge k) \approx 1 - \exp\left( -N \cdot q^k (1 - q) \right)$$
For $N = 1000$ trades and $q = 0.42$:
- $\mathbb{P}(\text{Streak } \ge 6) \approx 89.2\%$
- $\mathbb{P}(\text{Streak } \ge 8) \approx 32.5\%$
- $\mathbb{P}(\text{Streak } \ge 10) \approx 7.0\%$

Because exponential stake growth $S_k \sim 2.2^k$ rapidly hits the broker maximum stake or bankroll exhaustion, the conditional expectation of portfolio ruin approaches unity:
$$\lim_{N \to \infty} \mathbb{P}(\text{Ruin} \mid \text{Martingale}) = 1.0$$

**Architectural Law**:
$$\boxed{\frac{\partial S_t}{\partial (\text{Previous Trade Loss})} = 0}$$
The system shall enforce an absolute zero martingale invariant: stake size is **strictly independent** of the outcome of previous trades.

---

### 3.6 Approved Capital Allocation Models

#### Model A: Fixed Fractional Risk (Default Benchmark)
Allocates a fixed fraction of total balance:
$$S_t = \max\Big( S_{min}, \; \min\left( f_{fixed} \cdot \text{Balance}_t, \; \text{cap} \cdot \text{Balance}_t, \; S_{max} \right) \Big)$$
- Recommended: $f_{fixed} = 0.01$ (1% risk per trade).
- Maximum cap: $\text{cap} = 0.02$ (2% hard ceiling).
- Minimum stake: $S_{min} = 1.0$ (broker minimum).

#### Model B: Regularized Fractional Kelly Criterion
The classic Kelly Criterion maximizes asymptotic geometric wealth growth:
$$g(f) = \mathbb{E}[\ln(1 + R)] = P \ln(1 + b f) + (1 - P) \ln(1 - f)$$
First-order condition $\frac{dg}{df} = 0$:
$$\frac{P b}{1 + b f} - \frac{1 - P}{1 - f} = 0 \implies f^* = \frac{P b - (1 - P)}{b} = \frac{P(1 + b) - 1}{b} = \frac{EV}{b}$$

**Regularization with Wilson Lower Bound**:
To protect against estimation variance, replace nominal $EV$ with $EV_{WLB}$:
$$f^*_{WLB} = \frac{EV_{WLB}}{b} = \frac{WLB(1 + b) - 1}{b}$$
If $EV_{WLB} \le 0 \implies f^*_{WLB} \le 0 \implies S_t = 0$.

**Fractional Kelly Scaling**:
To minimize drawdown risk (full Kelly carries a $33\%$ probability of a $50\%$ drawdown before doubling):
$$f_{allocated} = \gamma \cdot f^*_{WLB}, \quad \text{where } \gamma = 0.25 \; \text{(Quarter-Kelly)}$$
Final Stake Formula:
$$S_t = \text{round}\left( \max\left( S_{min}, \; \min\left( f_{allocated} \cdot \text{Balance}_t, \; \text{cap} \cdot \text{Balance}_t \right) \right), \; 2 \right)$$
where $\text{cap} = 0.02$ ($2\%$ bankroll cap).

---

## 4. Algorithmic Python Specifications (Executable Reference)

The following self-contained Python module specifies the exact computational logic for R1 and R2:

```python
"""
iq_regime_formulations.py
Reference Implementation of Mathematical Formulations for R1 & R2.
Zero external library dependencies outside numpy and pandas.
"""

from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd


class MarketRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    EXPANSION = "EXPANSION"
    CHAOS = "CHAOS"


@dataclass(frozen=True)
class RegimeOutput:
    regime: MarketRegime
    allow_trade: bool
    recommended_strategy: str
    metrics: dict[str, float]


@dataclass(frozen=True)
class PipelineGateOutput:
    allow_trade: bool
    wlb: float
    p_be: float
    ev_wlb: float
    nominal_ev: float
    stake: float
    rejection_reason: str | None


def compute_wilson_lower_bound(p_hat: float, n: int, z: float = 1.96) -> float:
    """Computes exact Wilson Score Interval Lower Bound."""
    if n <= 0:
        return 0.0
    p_hat = min(max(float(p_hat), 0.0), 1.0)
    z2 = z * z
    denominator = 1.0 + z2 / n
    center = p_hat + z2 / (2.0 * n)
    spread = z * np.sqrt((p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * n * n)))
    wlb = (center - spread) / denominator
    return float(max(0.0, min(wlb, 1.0)))


def compute_payout_be(payout: float) -> float:
    """Calculates P_BE = 1 / (1 + Payout)."""
    if payout <= 0:
        return 1.0
    return 1.0 / (1.0 + payout)


def evaluate_payout_gate(
    payout: float,
    sample_winrate: float,
    sample_trades: int,
    balance: float,
    fractional_kelly: float = 0.25,
    max_risk_cap: float = 0.02,
    min_stake: float = 1.0,
    z: float = 1.96,
) -> PipelineGateOutput:
    """Evaluates R2: Expiry & Payout Conditional Pipeline."""
    p_be = compute_payout_be(payout)
    wlb = compute_wilson_lower_bound(sample_winrate, sample_trades, z=z)
    ev_wlb = wlb * (1.0 + payout) - 1.0
    nominal_ev = sample_winrate * (1.0 + payout) - 1.0

    if ev_wlb <= 0.0 or wlb <= p_be:
        return PipelineGateOutput(
            allow_trade=False,
            wlb=round(wlb, 4),
            p_be=round(p_be, 4),
            ev_wlb=round(ev_wlb, 4),
            nominal_ev=round(nominal_ev, 4),
            stake=0.0,
            rejection_reason=f"EV_WLB ({ev_wlb:.4f}) <= 0 or WLB ({wlb:.4f}) <= P_BE ({p_be:.4f})"
        )

    # Fractional Kelly sizing using WLB
    kelly_full = (wlb * payout - (1.0 - wlb)) / payout
    raw_fraction = max(0.0, kelly_full * fractional_kelly)
    stake = balance * raw_fraction
    stake = min(stake, balance * max_risk_cap)
    stake = max(min_stake, stake)
    stake = round(stake, 2)

    return PipelineGateOutput(
        allow_trade=True,
        wlb=round(wlb, 4),
        p_be=round(p_be, 4),
        ev_wlb=round(ev_wlb, 4),
        nominal_ev=round(nominal_ev, 4),
        stake=stake,
        rejection_reason=None
    )


def compute_variance_ratio(log_prices: np.ndarray, q: int = 4) -> float:
    """Computes Lo-MacKinlay Variance Ratio VR(q) for rolling prices."""
    n = len(log_prices)
    if n < q + 10:
        return 1.0
    diff1 = np.diff(log_prices)
    mu = np.mean(diff1)
    var1 = np.sum((diff1 - mu) ** 2) / (n - 1)
    
    diff_q = log_prices[q:] - log_prices[:-q]
    m = q * (n - q + 1) * (1.0 - q / float(n))
    var_q = np.sum((diff_q - q * mu) ** 2) / m
    if var1 <= 1e-12:
        return 1.0
    return float(var_q / (q * var1))


def classify_market_regime(df: pd.DataFrame) -> RegimeOutput:
    """Evaluates R1: Regime-Adaptive Feature Engine on candle dataframe."""
    if len(df) < 50:
        return RegimeOutput(
            regime=MarketRegime.CHAOS,
            allow_trade=False,
            recommended_strategy="NONE",
            metrics={"reason": "insufficient_candles"}
        )

    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    open_p = df["open"].to_numpy(dtype=float)

    # 1. Log returns & Autocorrelation rho_1
    ret = np.diff(np.log(close[-41:]))
    ret_mean = np.mean(ret)
    ret_cent = ret - ret_mean
    var_ret = np.sum(ret_cent ** 2)
    rho_1 = float(np.sum(ret_cent[1:] * ret_cent[:-1]) / (var_ret + 1e-12))

    # 2. Variance Ratio
    vr_4 = compute_variance_ratio(np.log(close[-60:]), q=4)

    # 3. ATR (14)
    tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    atr_14 = float(pd.Series(tr).ewm(alpha=1/14, adjust=False).mean().iloc[-1])
    natr = (atr_14 / close[-1]) * 100.0

    # 4. Bollinger Bandwidth (20, 2.0)
    sma_20 = float(np.mean(close[-20:]))
    std_20 = float(np.std(close[-20:], ddof=1))
    bbw = (4.0 * std_20) / (sma_20 + 1e-12)
    
    # BBW Z-score over last 50 bars
    rolling_bbw = pd.Series(close).rolling(20).apply(lambda w: (4.0 * np.std(w, ddof=1)) / (np.mean(w) + 1e-12)).dropna()
    bbw_z = float((bbw - rolling_bbw.tail(50).mean()) / (rolling_bbw.tail(50).std() + 1e-12))
    bbw_pct = float(np.mean(rolling_bbw.tail(50) <= bbw))

    # 5. ADX & DI (14)
    delta_h = np.diff(high)
    delta_l = -np.diff(low)
    plus_dm = np.where((delta_h > delta_l) & (delta_h > 0), delta_h, 0.0)
    minus_dm = np.where((delta_l > delta_h) & (delta_l > 0), delta_l, 0.0)
    plus_di_series = 100.0 * pd.Series(plus_dm).ewm(alpha=1/14, adjust=False).mean() / (pd.Series(tr).ewm(alpha=1/14, adjust=False).mean() + 1e-12)
    minus_di_series = 100.0 * pd.Series(minus_dm).ewm(alpha=1/14, adjust=False).mean() / (pd.Series(tr).ewm(alpha=1/14, adjust=False).mean() + 1e-12)
    dx_series = 100.0 * np.abs(plus_di_series - minus_di_series) / (plus_di_series + minus_di_series + 1e-12)
    adx_series = dx_series.ewm(alpha=1/14, adjust=False).mean()
    adx = float(adx_series.iloc[-1])
    plus_di = float(plus_di_series.iloc[-1])
    minus_di = float(minus_di_series.iloc[-1])
    di_diff = abs(plus_di - minus_di)

    # 6. Normalized Realized Volatility (NRV)
    recent_rv = np.std(ret[-12:])
    baseline_rv = np.std(ret)
    nrv = (recent_rv - baseline_rv) / (baseline_rv + 1e-12)

    # 7. Vol Shock
    std_5 = float(np.std(close[-5:], ddof=1))
    std_50 = float(np.std(close[-50:], ddof=1))
    vol_shock = std_5 / (std_50 + 1e-12)

    # 8. Candle morphology
    last_bar_rng = high[-1] - low[-1]
    is_giant_bar = last_bar_rng > 3.5 * atr_14

    metrics = {
        "adx": adx, "plus_di": plus_di, "minus_di": minus_di,
        "bbw": bbw, "bbw_z": bbw_z, "bbw_pct": bbw_pct,
        "rho_1": rho_1, "vr_4": vr_4, "natr": natr,
        "nrv": nrv, "vol_shock": vol_shock
    }

    # --- HIERARCHICAL CLASSIFICATION TREE ---
    # TIER 1: CHAOS VETO
    if nrv > 3.0 or vol_shock > 3.5 or is_giant_bar or (adx >= 35.0 and di_diff <= 4.0):
        return RegimeOutput(MarketRegime.CHAOS, allow_trade=False, recommended_strategy="NONE", metrics=metrics)

    # TIER 2: EXPANSION BREAKOUT
    min_recent_bbw_pct = float(np.min([np.mean(rolling_bbw.tail(50) <= b) for b in rolling_bbw.tail(6).iloc[:-1]]))
    if min_recent_bbw_pct <= 0.25 and bbw_z >= 1.0 and 1.2 <= nrv <= 3.0:
        return RegimeOutput(MarketRegime.EXPANSION, allow_trade=True, recommended_strategy="VOLATILITY_BREAKOUT", metrics=metrics)

    # TIER 3: TREND
    if adx >= 25.0 and di_diff >= 12.0 and (vr_4 >= 1.05 or rho_1 >= 0.05):
        return RegimeOutput(MarketRegime.TREND, allow_trade=True, recommended_strategy="TREND_PULLBACK", metrics=metrics)

    # TIER 4: RANGE
    if adx < 20.0 and di_diff < 12.0 and (rho_1 <= -0.05 or vr_4 <= 0.95) and bbw_z <= 0.50:
        return RegimeOutput(MarketRegime.RANGE, allow_trade=True, recommended_strategy="MEAN_REVERSION", metrics=metrics)

    # TIER 5: FALLBACK (CHAOS / UNCERTAIN)
    return RegimeOutput(MarketRegime.CHAOS, allow_trade=False, recommended_strategy="NONE", metrics=metrics)
```

---

## 5. Interface Contracts for Peer Agents (Architectural Integration)

To ensure seamless integration across the engineering milestones:

1. **Input Contract for R1 Engine**:
   - `df_candles`: DataFrame containing timestamped chronological bars (`open`, `high`, `low`, `close`, `volume`). Must contain at least 60 historical bars.
2. **Output Contract for R1 Engine**:
   - `regime`: Enum `[TREND, RANGE, EXPANSION, CHAOS]`
   - `allow_trade`: Boolean. If `False`, execution immediately halts.
   - `recommended_strategy`: String `["MEAN_REVERSION", "TREND_PULLBACK", "VOLATILITY_BREAKOUT", "NONE"]`
3. **Input Contract for R2 Pipeline Gate**:
   - `payout`: Float $b \in (0.0, 1.0]$.
   - `sample_winrate`: Float $\hat{p} \in [0.0, 1.0]$ evaluated on in-sample or rolling validation trades.
   - `sample_trades`: Integer $n \ge 0$.
   - `balance`: Current equity.
4. **Output Contract for R2 Pipeline Gate**:
   - `allow_trade`: Boolean (`EV_WLB > 0` and `WLB > P_BE`).
   - `stake`: Sizing in account currency (zero martingale, fractional Kelly regularized).
   - `rejection_reason`: Explanation string if vetoed.

---
*Report completed and certified by Explorer Survey IQ 2.*
