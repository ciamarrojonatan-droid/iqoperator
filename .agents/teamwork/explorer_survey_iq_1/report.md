# Quantitative Research Architecture Survey & Workspace Mapping Report

**Author**: Explorer Survey IQ 1  
**Timestamp**: 2026-09-29T02:44:00Z  
**Context**: Quantitative Research Architecture (Backtest & Signal Engine) for Binary Options (IQ Option)  
**Workspace Path**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\`  
**Parent Path**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\`  

---

## Executive Summary

This report establishes a complete empirical survey of the existing computational environment, Python virtual environments, installed packages, data assets, API wrappers/mocks, strategies, and backtesting scripts across the workspace. It translates the requirements of `ORIGINAL_REQUEST.md` (2026-09-29T02:35:44Z) into a definitive Quantitative Research Architecture blueprint (`iq_regime_adaptive`), specifically addressing:
1. **Regime-Adaptive Feature Engine** (Trend, Range, Expansion, Chaos $\rightarrow$ NO TRADE).
2. **Expiry & Dynamic Payout Conditional Pipeline** (Break-Even probability $P_{BE}$, Wilson Lower Bound, Expectation Value $EV > 0$).
3. **Out-of-Sample (OOS) Stability & Hypothesis Framework** (IS / VAL / OOS partitioning, EV degradation tracking for H001–H008, zero martingale / Kelly strict).

---

## 1. Python Environment & Dependency Ecosystem

### 1.1 Interpreter & Virtual Environment
- **Host System Python**: The global `python` binary is **not registered in PATH**.
- **Active Virtual Environment**: Fully configured and operational at:
  `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.venv\`
- **Python Version**: `Python 3.11.9` (64-bit Windows).
- **Executable Path**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.venv\Scripts\python.exe`.
- **Parent Directory**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\` contains exclusively the `iqoperator\` workspace directory.

### 1.2 Package Inventory & Quantitative Readiness
Inspection of `.venv\Scripts\pip.exe` and programmatic import validation revealed the following status:

| Package Category | Package Name | Version | Status | Suitability for Quantitative Architecture |
|---|---|---|---|---|
| **Core Scientific** | `numpy` | 2.4.6 | INSTALLED | Vectorized array math, rolling window matrices, EV calculations. |
| **Data Manipulation** | `pandas` | 3.0.6 | INSTALLED | Time series indexing, candle aggregation, IS/VAL/OOS slicing. |
| **Scientific Computing** | `scipy` | 1.17.1 | INSTALLED | Normal distribution quantiles, stats, autocorrelation, filter functions. |
| **Machine Learning** | `scikit-learn` | 1.9.1 | INSTALLED | Preprocessing, TimeSeriesSplit, scalers, classification models. |
| **Gradient Boosting** | `xgboost` | 3.2.0 | INSTALLED | Signal filtration, non-linear feature interaction, probabilistic calibration. |
| **Acceleration** | `numba` | 0.67.0 | INSTALLED | JIT-compilation of heavy backtest loops and regime transition checks. |
| **Deep Learning** | `torch` | 2.14.0 | INSTALLED | Deep sequence modeling if needed. |
| **Broker API** | `iqoptionapi` | 6.8.9.1 | INSTALLED | IQ Option websocket communication, candle retrieval, payout polling. |
| **Market Data** | `yfinance` | 1.7.0 | INSTALLED | External benchmark data ingestion (Yahoo Finance). |
| **Crypto Data** | `ccxt` | 4.5.84 | INSTALLED | Crypto spot/futures data retrieval (Binance). |
| **Networking & Async** | `websockets` | 17.1 | INSTALLED | Async streaming feeds. |
| **Visualization** | `matplotlib` | 3.11.2 | INSTALLED | Equity curve and drawdown distribution plotting. |
| **Testing** | `pytest` | — | **MISSING** | Standard library `unittest` is present and runs all 62 existing tests cleanly. |
| **Econometrics** | `statsmodels` | — | **MISSING** | Statistical indicators (ADX, ACF, Wilson score, ADF test) are implemented natively via `scipy` and `numpy` to eliminate external dependency bloat. |

> **Operational Directive**: All CLI invocations, test suites, and script executions must explicitly use `.\.venv\Scripts\python.exe`. Testing must target `python -m unittest` or implement isolated runner scripts unless `pytest` is added.

---

## 2. Codebase Assets, API Wrappers & Mocks

### 2.1 Existing Scripts & Entry Points
1. **`bot.py` (917 lines)**:
   - Primary asynchronous bot for IQ Option demo/live trading.
   - Operates a sequential multi-asset scanner across OTC and regular pairs (`EURUSD-OTC`, `GBPUSD-OTC`, `USDJPY-OTC`, `AUDUSD-OTC`, `EURGBP-OTC`, `USDCAD-OTC`).
   - Integrated with `HomeostasisManager` (`homeostasis.py`) for thread-safe reconnection backoff and watchdog synchronization.
   - Non-blocking order settlement using pending orders queue (`self.pending`) reconciled via `get_betinfo`.
   - Incorporates real-time payout extraction via `get_payout()` and Kelly staking via `calc_stake()`.
   - Contains real-time ML filter gating via `ml_filter.py`.

2. **`homeostasis.py` (435 lines)**:
   - Autonomic connection healing layer.
   - Implements thread locks (`_api_lock`), exponential backoff (2s up to 60s), and watchdog heartbeat touch (`_touch_bot_progress`).
   - Dynamically patches `IQ_Option` methods: `get_candles`, `get_betinfo`, `get_balances`, `get_balance`, `get_binary_option_detail`.

3. **`ml_filter.py` (578 lines)**:
   - Real-time XGBoost inference engine calibrated with decision threshold $\tau = 0.62$.
   - Feature vector calculates 72 technical, cyclical, and multi-timeframe features with strict zero-lookahead semantics.
   - Provides fail-open / fail-closed safety fallbacks.

4. **`kelly.py` (43 lines)**:
   - Implements Fractional Kelly Criterion:
     $$f^* = \frac{b \cdot p - (1 - p)}{b}$$
     where $b = \text{payout}$, $p = \text{winrate}$.
   - Staking formula: $\text{stake} = \min(\text{balance} \times f^* \times \text{fraction}, \text{balance} \times \text{max\_risk})$.
   - Implements Bayesian empirical win rate smoothing:
     $$p_{\text{bayes}} = \frac{p_{\text{prior}} \cdot w + \text{wins}}{w + N}$$

5. **`strategies.py` (378 lines)**:
   - Core collection of deterministic trading signals:
     - `donchian_fade_signal`: Fade 20-period breakout.
     - `bollinger_touch_signal`: 20-period, $2\sigma$ band touch mean reversion.
     - `rsi_m15_signal`: 14-period RSI 30/70 mean reversion.
     - `rsi_momentum_signal` & `rsi_momentum_trend_signal`: RSI momentum continuation.
     - `rsi_mtf_pullback_signal`: Multi-timeframe H1 EMA(50) bias + M15 RSI pullback.
     - `multi_mean_reversion_signal`: Ensemble of Donchian, Bollinger, and RSI.
     - `mhi_1_signal`: Probabilistic 3-candle color minority/majority in 5-minute quadrant.

### 2.2 Existing Backtesters & Research Hypotheses
1. **`backtest_h010.py` (270 lines)**:
   - Implements hypothesis H010 (macro 1D+H4 EMA bias, micro M15 RSI trigger, M5 confirmation).
   - Computes Wilson Lower Bound at 95% confidence (`wilson_lower(wins, n, z=1.96)`).
   - Strict 70% In-Sample / 30% Out-of-Sample chronological split.
   - Formal acceptance gates: $N \ge 50$, $W_{lower} > P_{BE}$, $Profit_{OOS} > 0$.

2. **`research/h010/BACKTEST_PLAN.md` & `hypothesis.json`**:
   - Documents quantitative hypothesis standards:
     - Pre-declared parameters and setup requirements.
     - Wilson lower bound 95% $> P_{BE}$.
     - Negative control verification (inverted logic must yield $WR < 50\%$).
     - Split consistency (positive return in both temporal halves).

3. **`research/grid_families.py` (342 lines)**:
   - Parameter search across signal families (Donchian breakout, Bollinger reversal, ATR stretch, momentum ignition, wick rejection).
   - Tracks data mining risk by counting total tested combinations (`TOTAL_CONFIGS`).

4. **`backtest_portfolio.py` (305 lines)**:
   - Multi-asset evaluation of Donchian, Bollinger, and MHI combined with ML gating.

### 2.3 Unit Testing & Mock Harnesses
- `tests/test_homeostasis.py` (543 lines): Contains mock classes `FakeAPI` and `FakeBot` implementing deterministic mocks for `getcandles`, `get_betinfo`, `get_balance`, `get_binary_option_detail`, and connection state transitions.
- `tests/test_mhi_strategy.py` (144 lines): Synthetic candle generation framework (`_create_candles`) for validating strategy edge cases without network access.
- `tests/test_ml_filter.py` (336 lines): Unit tests for feature alignment, NaN handling, and inference latency.
- **Current Test Status**: `Ran 62 tests in 22.741s — OK`.

---

## 3. Historical Candle Data Inventory & Fetchers

### 3.1 Historical Candle Datasets in `data/`

The workspace contains an extensive collection of real and broker-sourced historical candle files:

| File Path | Asset | Timeframe | Candle Count | Timestamp Span (UTC) | Schema |
|---|---|---|---|---|---|
| `data/EURUSD_M5_iq.csv` | EURUSD | M5 (300s) | 20,000 | 2026-06-22 10:20 to 2026-09-25 20:55 | `time,open,high,low,close` |
| `data/EURUSD_M15_histdata.csv` | EURUSD | M15 (900s) | 40,000 | 2024-05-23 17:30 to 2025-12-31 16:45 | `time,open,high,low,close` |
| `data/EURUSD_M15_yf.csv` | EURUSD | M15 (900s) | ~11,000 | 2026 Historical | `time,open,high,low,close` |
| `data/GBPUSD_M5_iq.csv` | GBPUSD | M5 (300s) | 20,000 | 2026-06 to 2026-09 | `time,open,high,low,close` |
| `data/USDJPY_M5_iq.csv` | USDJPY | M5 (300s) | 20,000 | 2026-06 to 2026-09 | `time,open,high,low,close` |
| `data/AUDUSD_M5_iq.csv` | AUDUSD | M5 (300s) | 20,000 | 2026-06 to 2026-09 | `time,open,high,low,close` |
| `data/USDCAD_M5_iq.csv` | USDCAD | M5 (300s) | 20,000 | 2026-06 to 2026-09 | `time,open,high,low,close` |
| `data/EURGBP_M5_iq.csv` | EURGBP | M5 (300s) | 20,000 | 2026-06 to 2026-09 | `time,open,high,low,close` |
| `data/BTCUSDT_M1_60d.csv` | BTCUSDT | M1 (60s) | 86,400 | 2026-07-29 06:35 to 2026-09-27 06:34 | `time,open,high,low,close,volume` |
| `data/BTCUSDT_M5_60d.csv` | BTCUSDT | M5 (300s) | 17,280 | 2026-07-29 to 2026-09-27 | `time,open,high,low,close,volume` |
| `data/BTCUSDT_M5_1y.csv` | BTCUSDT | M5 (300s) | 105,000 | 1 Year (2025–2026) | `time,open,high,low,close` |
| `data/BTCUSDT_M5_2024y.csv` | BTCUSDT | M5 (300s) | 105,120 | Full Year 2024 | `time,open,high,low,close` |
| `data/BTCUSDT_M5_3y.csv` | BTCUSDT | M5 (300s) | 315,360 | 2023-09-28 to 2026-09-27 (3 Years) | `time,open,high,low,close` |
| `data/BTCUSDT_M15_1y.csv` | BTCUSDT | M15 (900s) | 35,000 | 1 Year (2025–2026) | `time,open,high,low,close` |
| `data/BTCUSDT_H4_1y.csv` | BTCUSDT | H4 (14400s) | 2,200 | 1 Year | `time,open,high,low,close` |
| `data/BTCUSDT_D1_1y.csv` | BTCUSDT | D1 (86400s) | 400 | 1 Year | `time,open,high,low,close` |
| `data/BTCUSD_M5_iq.csv` | BTCUSD | M5 (300s) | 16,982 | IQ Option Feed | `time,open,high,low,close` |
| `data/ETHUSD_M5_iq.csv` | ETHUSD | M5 (300s) | 16,982 | IQ Option Feed | `time,open,high,low,close` |
| `data/XAUUSD_M5_iq.csv` | XAUUSD (Gold) | M5 (300s) | 13,683 | IQ Option Feed | `time,open,high,low,close` |
| `data/XAGUSD_M5_iq.csv` | XAGUSD (Silver) | M5 (300s) | 13,681 | IQ Option Feed | `time,open,high,low,close` |
| `data/SP500_M5_iq.csv` | S&P 500 | M5 (300s) | 4,679 | IQ Option Feed | `time,open,high,low,close` |

### 3.2 Data Fetchers & Ingestion Utilities
- **`fetch_iq_grid.py`**: Automated script that connects to IQ Option via `.env` credentials, iteratively fetches batches of 1,000 candles backwards in time with rate-limit pacing (`time.sleep(0.5)`), and saves 20,000 candles per asset for the top 6 currency pairs.
- **`fetch_iq.py`**: CLI utility for single-asset candle pulls with custom intervals (`--interval`) and candle counts (`--n`).
- **`fetch_binance.py` / `fetch_binance_m1.py` / `fetch_binance_m5_macro.py`**: Fetches Binance spot klines with volume.
- **`probe_assets.py`**: Live broker probe inspecting binary/turbo option availability, active schedule, and real-time payout across 14 assets.

### 3.3 Dynamic Payout & Market Microstructure Observations
- Broker payouts on IQ Option fluctuate based on instrument liquidity, volatility, and trading session:
  - Standard Binary: typically $0.75 - 0.88$ (e.g. 87% $\rightarrow P_{BE} = 53.48\%$).
  - Turbo (1–5 min): can reach $0.85 - 0.95$ during active sessions, dropping to $< 0.70$ during off-hours.
  - Low Payout Trap: Observed in `assets_performance_m5.csv` where an unconditioned win rate of $49\% - 52\%$ on 2,500 trades resulted in $-\$1,982.00$ net loss due to negative mathematical expectation against typical broker payouts ($< 80\%$).

---

## 4. Recommended Quantitative Research Architecture

In accordance with `ORIGINAL_REQUEST.md`, the Quantitative Research Architecture must replace static win-rate heuristics with an end-to-end mathematical expectation engine.

### 4.1 Core Mathematical Foundations

1. **Break-Even Win Rate ($P_{BE}$)**:
   For a binary option risking stake $S$ with broker payout multiplier $b \in (0, 1]$:
   $$\mathbb{E}[Trade] = p \cdot (S \cdot b) - (1 - p) \cdot S = 0 \implies p \cdot (b + 1) = 1 \implies P_{BE} = \frac{1}{1 + b}$$
   - At $b = 0.85 \implies P_{BE} \approx 54.05\%$.
   - At $b = 0.70 \implies P_{BE} \approx 58.82\%$.

2. **Wilson Score Interval (Lower Bound at Confidence $1 - \alpha$)**:
   Given $W$ wins out of $N$ completed trades ($N = W + L$), with sample proportion $\hat{p} = \frac{W}{N}$ and standard normal quantile $z$ (e.g. $z = 1.96$ for 95% confidence):
   $$W_{lower}(\hat{p}, N, z) = \frac{\hat{p} + \frac{z^2}{2N} - z \sqrt{\frac{\hat{p}(1 - \hat{p})}{N} + \frac{z^2}{4N^2}}}{1 + \frac{z^2}{N}}$$
   - *Property*: For small $N$, $W_{lower}$ strongly penalizes statistical uncertainty. As $N \to \infty$, $W_{lower} \to \hat{p}$.

3. **Expectation Value ($EV$) & Wilson-Conditioned EV ($EV_{wilson}$)**:
   $$\text{Normalized } EV = \hat{p} \cdot b - (1 - \hat{p})$$
   $$\text{Conservative } EV_{wilson} = W_{lower} \cdot b - (1 - W_{lower})$$
   - *Execution Invariant*: A trade signal is valid **if and only if** $EV_{wilson} > 0$ (equivalent to $W_{lower} > P_{BE}$).

4. **Out-of-Sample Performance Degradation ($\Delta EV$)**:
   $$\Delta EV = EV_{IS} - EV_{OOS}$$
   $$\text{Degradation Ratio} = \frac{EV_{IS} - EV_{OOS}}{\max(|EV_{IS}|, \epsilon)}$$
   - Acceptance criteria requires $\Delta EV$ to remain bounded ($\le 25\%$ degradation) and $EV_{OOS} > 0$.

5. **Staking Governance (Strict Non-Martingale)**:
   - Staking strictly employs Fractional Kelly ($f^* \times 0.25$, max bankroll risk $2.0\%$) or Fixed Risk ($1\% - 2\%$).
   - Martingale, geometric progression, or loss-chasing is strictly prohibited and flagged as a test failure.

---

### 4.2 Modular Directory Layout Blueprint

The proposed research architecture can reside under `iq_regime_adaptive/` or `src/iq_regime/`:

```text
iq_regime_adaptive/
├── __init__.py
├── config.py                         # Global constants, default confidence levels (95%), risk caps
│
├── feature_engine/                   # [R1] Regime-Adaptive Feature Engine
│   ├── __init__.py
│   ├── indicators.py                 # Vectorized ATR, ADX (+DI/-DI), Bollinger, Donchian, EMA, RSI
│   ├── autocorrelation.py            # Return autocorrelation (rho_1, rho_2), variance ratio test
│   ├── volatility.py                 # Historical volatility, Parkison/Garman-Klass, ATR shock ratio
│   └── regime_classifier.py          # Classifies market into: Trend, Range, Expansion, Chaos (NO_TRADE)
│
├── pipeline/                         # [R2] Expiry & Payout Conditional Pipeline
│   ├── __init__.py
│   ├── data_loader.py                # CSV ingestion, timestamp normalization (s/ms), gap validation
│   ├── payout_filter.py              # P_BE calculation, dynamic payout hurdle, minimum payout gate
│   ├── probability_estimator.py      # Historical/Bayesian conditional win rate estimator
│   └── signal_router.py              # Routes regime state to compatible strategy or enforces NO_TRADE
│
├── hypotheses/                       # [R3] Quantitative Hypotheses (H001 - H008)
│   ├── __init__.py
│   ├── base.py                       # Abstract Base Class for hypothesis definition, gates & negative control
│   ├── registry.py                   # Central hypothesis discovery & runner registry
│   ├── h001_range_mean_reversion.py  # Range regime + Donchian/Bollinger fade
│   ├── h002_trend_pullback.py        # Trend regime + EMA pullback + RSI trigger
│   ├── h003_expansion_breakout.py    # Expansion regime + Volatility shock continuation
│   ├── h004_vsa_absorption.py        # Wick rejection + Volume Spread Analysis (M1/M5)
│   ├── h005_multi_timeframe_bias.py  # H1 trend alignment + M5 trigger
│   ├── h006_session_breakout.py      # London/NY session open momentum
│   ├── h007_rsi_extreme_exhaust.py   # Double oversold exhaustion
│   └── h008_adaptive_composite.py    # Meta-selector combining H001-H007 by live regime
│
├── backtest/                         # Backtest Engine & Validation
│   ├── __init__.py
│   ├── partition.py                  # Strict IS (60%), VAL (20%), OOS (20%) chronological split
│   ├── engine.py                     # Vectorized/event-driven simulation with zero forward leakage
│   ├── metrics.py                    # N effective, WinRate, Wilson Lower Bound, EV, Sharpe, MaxDD
│   ├── degradation.py                # Computes IS vs OOS EV decay and degradation ratios
│   └── staking.py                    # Kelly strict, Bayesian prior, and fixed fractional sizing
│
├── reports/                          # [Acceptance Criteria] Quantitative Reporting
│   ├── __init__.py
│   ├── summary_reporter.py           # Markdown/Text table generator (N, EV, Wilson LB, Degradation)
│   └── visualizer.py                 # Equity curves, regime timeline, drawdown plots
│
└── tests/                            # Comprehensive Test Suite (unittest)
    ├── __init__.py
    ├── test_regime_classifier.py     # Validates Trend, Range, Expansion, and Chaos (NO_TRADE)
    ├── test_payout_filter.py         # Validates P_BE, EV calculation, and payout thresholds
    ├── test_wilson_lower.py          # Validates Wilson bounds against scipy reference
    ├── test_partition.py            # Validates zero lookahead and strict chronology
    ├── test_hypotheses.py            # Validates execution of H001-H008
    └── test_zero_martingale.py       # Asserts zero martingale / risk invariant
```

---

### 4.3 Component Specifications

#### R1: Regime-Adaptive Feature Engine (`feature_engine/`)
- **Inputs**: High, Low, Close, Volume series across $M5$ / $M15$.
- **Outputs**: Discrete market state $\in \{\text{TREND\_BULL}, \text{TREND\_BEAR}, \text{RANGE}, \text{EXPANSION}, \text{CHAOS}\}$.
- **Classification Rules**:
  - `TREND`: $ADX(14) \ge 25$ and consistent EMA slope ($\text{EMA}_{20} > \text{EMA}_{50}$).
  - `RANGE`: $ADX(14) < 20$, normalized ATR $\le 1.0$, and first-order autocorrelation $\rho_1 < -0.1$ (mean-reverting).
  - `EXPANSION`: $\frac{ATR(14)}{\text{SMA}(ATR, 50)} > 1.5$ and Bollinger bandwidth expanding at 95th percentile.
  - `CHAOS`: High volatility ($\text{Normalized } ATR > 2.5$) with low directional persistence and erratic wick ratios $\implies$ **EXPLICIT NO TRADE**.

#### R2: Expiry & Payout Conditional Pipeline (`pipeline/`)
- **Inputs**: Raw signal candidate, current payout $b$ ($0.70 \le b \le 0.95$), expiration time $H$.
- **Processing**:
  1. Computes $P_{BE} = \frac{1}{1 + b}$.
  2. Retrieves conditional empirical/Bayesian win rate estimate $\hat{p}$ and sample size $N$.
  3. Computes 95% Wilson lower bound $W_{lower}$.
  4. Computes $EV_{wilson} = W_{lower} \cdot b - (1 - W_{lower})$.
  5. **Gate**: If $EV_{wilson} \le 0$ or $b < \text{PAYOUT\_MIN}$, suppress trade with reason `NEGATIVE_EXPECTATION` or `INSUFFICIENT_PAYOUT`.

#### R3: Out-of-Sample (OOS) Stability & Hypothesis Framework (`hypotheses/` & `backtest/`)
- **Data Partitioning**:
  - `In-Sample (IS)`: Chronological first 60% of data (parameter search and optimization).
  - `Validation (VAL)`: Intermediate 20% (threshold calibration and feature selection).
  - `Out-of-Sample (OOS)`: Final 20% (strictly untouched until final model audit).
- **Hypothesis Definition Contract (`BaseHypothesis`)**:
  - Pre-defined setup parameters, regime condition, and target entry/expiry.
  - Negative control specification (inverted signal execution).
  - Acceptance Gate:
    1. Effective sample count $N_{OOS} \ge 100$.
    2. $W_{lower, OOS} > P_{BE}$.
    3. $EV_{OOS} > 0$.
    4. Degradation $\Delta EV \le 0.25 \times |EV_{IS}|$.
    5. Negative control win rate $< 50\%$.

---

## 5. Risk Assessment & Verification Roadmap

1. **Risk 1: Missing `pytest` & `statsmodels`**:
   - *Mitigation*: Leverage Python's built-in `unittest` framework (tested and confirmed working with all 62 tests) and self-contained mathematical routines using `scipy.stats.norm.ppf` and `numpy`.
2. **Risk 2: Timestamp Discrepancies**:
   - *Mitigation*: Historical files feature varying timestamp representations: epoch seconds (10 digits), epoch milliseconds (13 digits), and epoch microseconds. The `pipeline/data_loader.py` module must normalize all timestamps to UTC milliseconds/seconds upon loading.
3. **Risk 3: Lookahead Bias in Regime Detection**:
   - *Mitigation*: All rolling windows (ADX, ATR, EMA, Bollinger) must shift by at least 1 bar (`shift(1)`) so that signals calculated at candle close $t$ only consume data up to $t$.
4. **Risk 4: Payout Overestimation**:
   - *Mitigation*: Backtests must evaluate scenarios with conservative payouts ($0.75, 0.80, 0.85$) rather than assuming ideal broker quotes ($0.90+$).

---

## 6. Synthesis & Next Actions

The workspace possesses all necessary components to construct the Quantitative Research Architecture immediately:
- High quality historical datasets with over 300,000 multi-asset candles across M1, M5, M15.
- Robust, verified Python 3.11 environment with `numpy`, `pandas`, `scipy`, `scikit-learn`, `xgboost`, and `iqoptionapi`.
- Verified Kelly staking, Bayesian prior, and Wilson lower bound algorithms already developed in `backtest_h010.py` and `kelly.py`.
- Working broker mock and test harness in `tests/test_homeostasis.py`.

The subsequent development milestones can proceed with confidence into implementation.
