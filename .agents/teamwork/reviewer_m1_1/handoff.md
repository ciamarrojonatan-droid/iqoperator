# Reviewer & Adversarial Critic Report: Milestone 1 (R1 Feature Engine)

**Agent**: Reviewer M1-1 (`reviewer_m1_1`)  
**Parent / Caller**: `5300d532-e3aa-4ce2-bdf4-d9b54031954a` (Orchestrator)  
**Target Modules**: `iq_regime_adaptive/feature_engine/` (`indicators.py`, `regime_classifier.py`, `signal_router.py`, `test_feature_engine.py`)  
**Timestamp**: 2026-09-29T03:00:00Z  
**Type**: Hard Handoff (Review & Audit Complete)  
**Verdict**: **APPROVE**

---

## 1. Observation

### 1.1 Verified Artifacts & Line Numbers
1. `iq_regime_adaptive/feature_engine/indicators.py` (435 lines):
   - Lines 25–65: `compute_true_range`, `compute_atr`, `compute_natr`, `compute_atr_ratio`. Wilder's exponential smoothing with $\alpha = 1/\text{period}$, $NATR = (ATR / Close) \times 100$ with $10^{-12}$ division safeguard.
   - Lines 80–133: `compute_bollinger_bands`, `compute_bollinger_bandwidth`, `compute_bbw_zscore`, `compute_bbw_percentile`. Proper sample standard deviation ($ddof=1$) and rolling empirical CDF percentile ranking.
   - Lines 135–182: `compute_normalized_realized_volatility` ($NRV$), `compute_parkinson_volatility` ($\sigma_{park} = \sqrt{\frac{1}{4 \ln 2 \cdot m} \sum \ln(H/L)^2}$), and `compute_vol_shock`.
   - Lines 188–221: `compute_adx`. Wilder's Directional Movement System ($+DM$, $-DM$, $+DI$, $-DI$, $DX$, $ADX$) smoothed with $\alpha = 1/\text{period}$.
   - Lines 228–256: `compute_return_autocorrelation`. Sample lag-1 return autocorrelation $\rho_1$ and Bartlett $t$-statistic $t = \rho_1 \sqrt{T}$.
   - Lines 258–321: `compute_variance_ratio`. Lo & MacKinlay (1988) heteroskedasticity-consistent variance ratio $VR(q)$ and test statistic $z^*(q)$.
   - Lines 357–435: Strategy indicators (Wilder's RSI, Fast/Slow Stochastic, Donchian Channels 20, EMA 20/50, and Candle Morphology).

2. `iq_regime_adaptive/feature_engine/regime_classifier.py` (328 lines):
   - Lines 40–56: `MarketRegime` enum (`TREND`, `RANGE`, `EXPANSION`, `CHAOS`) and immutable `RegimeOutput` dataclass.
   - Lines 58–295: `RegimeClassifier` 5-Tier Decision Tree:
     - Tier 1 (lines 186–210): Chaos Guard (Strict Veto): fires when $NRV > 3.0$, $vol\_shock > 3.5$, $NATR > 98\text{th percentile}$, giant bar ($> 3.5 \times ATR$), severe whipsaw ($ADX \ge 35$ and $|+DI - -DI| \le 4$), excess kurtosis ($> 8.0$), or $n < 50$ bars. Unconditionally returns `allow_trade = False`, `recommended_strategy = "NONE"`.
     - Tier 2 (lines 213–242): Expansion Regime (Volatility Breakout): squeeze release ($BBW \ge 1.4 \times \min(BBW)$, $BBW\_Z \ge 1.0$), prior compression ($\le 25\text{th percentile}$), elevated $NRV \in [1.2, 3.0]$, and Donchian breach or strong directional spread.
     - Tier 3 (lines 245–266): Trend Regime (Directional Drift): $ADX \ge 25$, $DI\_diff \ge 12$, persistent memory ($VR(4) \ge 1.05$ or $\rho_1 \ge 0.05$), moving average alignment (EMA 20 vs 50 matching DI dominance), controlled volatility ($-0.5 \le BBW\_Z \le 2.0$).
     - Tier 4 (lines 268–284): Range Regime (Mean Reversion): absence of trend ($ADX < 20$, $DI\_diff < 12$), mean-reverting memory ($\rho_1 \le -0.05$ or $VR(4) \le 0.95$), contained volatility ($BBW\_Z \le 0.5$, $NRV < 1.0$), and envelope confinement ($\le 2.5 \sigma$).
     - Tier 5 (lines 286–295): Fallback Indeterminate State: maps unclassified market dynamics directly to `CHAOS` with `allow_trade = False`.
   - Lines 297–328: `classify_series` and top-level `classify_regime(df) -> pd.Series` interface contract returning categorical Series matching `PROJECT.md`.

3. `iq_regime_adaptive/feature_engine/signal_router.py` (296 lines):
   - Lines 36–52: `MarketSignal` (`CALL`, `PUT`, `NO_TRADE`) and `SignalDecision` dataclass.
   - Lines 77–87: Strict Non-Bypassable CHAOS Invariant:
     ```python
     if regime == MarketRegime.CHAOS or not regime_output.allow_trade:
         return SignalDecision(
             signal=MarketSignal.NO_TRADE,
             regime=MarketRegime.CHAOS,
             setup_name="NONE",
             expiry_bars=0,
             confidence=0.0,
             reason=f"CHAOS VETO: {regime_output.reason}",
             metadata={"regime_metrics": regime_output.metrics},
         )
     ```
   - Lines 149–189: Setup 1: `RANGE_MEAN_REVERSION` (1 bar expiry). CALL on lower band/Donchian breach + oversold indicator + rejection wick. PUT on upper band/Donchian breach + overbought indicator + rejection wick.
   - Lines 194–234: Setup 2: `TREND_PULLBACK` (2 bar expiry). Bullish/Bearish EMA equilibrium retest with RSI recovery in [35, 55] (bull) or [45, 65] (bear).
   - Lines 239–279: Setup 3: `VOLATILITY_BREAKOUT` (1 bar expiry). Bullish/Bearish band penetration with solid candle body ($\ge 50\%$) and directional spread ($\ge 12$).

### 1.2 Independent Verification Test Execution
1. Command:
   `.\.venv\Scripts\python.exe -m unittest iq_regime_adaptive/tests/test_feature_engine.py`
   Output:
   ```text
   ................
   ----------------------------------------------------------------------
   Ran 16 tests in 0.389s

   OK
   ```
2. Command:
   `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`
   Output:
   ```text
   ....................................................................
   ----------------------------------------------------------------------
   Ran 68 tests in 0.437s

   OK
   ```

3. Real Data Execution (`data/EURUSD_M5_iq.csv`, 20,000 bars):
   Tested on first 300 bars:
   - Regimes: CHAOS: 258, RANGE: 33, TREND: 9.
   - Signals generated: At bar 164, a genuine `RANGE_MEAN_REVERSION` CALL signal was emitted and routed properly.

---

## 2. Logic Chain

1. **Mathematical Accuracy of Indicators**:
   - Every formula in `indicators.py` was derived from foundational literature and verified against its mathematical definition:
     - Wilder (1978): Wilder's True Range, smoothing filter $\alpha = 1/N$, and Directional Movement System ($DX$, $ADX$, $+DI$, $-DI$).
     - Parkinson (1980): Extreme value estimator $\sigma_{park} = \sqrt{\frac{1}{4 \ln 2 \cdot m} \sum \ln(H_i/L_i)^2}$, verified with correct constant $1/(4 \ln 2)$ and squared log-price ratios.
     - Lo & MacKinlay (1988): Overlapping $q$-period variance estimator $\bar{\sigma}_c^2$ with normalization divisor $m = q(W-q+1)(1-q/W)$ and heteroskedasticity-consistent variance $V^*(q) = \sum_{j=1}^{q-1} [\frac{2(q-j)}{q}]^2 \hat{\delta}_j$.
   - Independent test simulations confirmed:
     - Random walk series produce $VR(4) \approx 1.0$.
     - Ornstein-Uhlenbeck mean-reverting series produce $VR(4) < 0.90$.
     - Trend series produce $VR(4) > 1.0$.

2. **Hierarchical 5-Tier Decision Tree & Chaos Guard**:
   - The decision tree enforces strict prioritization. Tier 1 executes prior to any strategy evaluation. Any market exhibiting volatility explosions ($NRV > 3.0$), news spikes ($> 3.5 \times ATR$), or severe whipsaw ($ADX \ge 35$ with $|+DI - -DI| \le 4$) is intercepted immediately with `allow_trade = False`.
   - Data scarcity ($n < 50$ bars) or indeterminate states (Tier 5) gracefully and defensively fall back to `CHAOS` with `allow_trade = False`.

3. **Signal Routing & Non-Bypassable Invariant**:
   - In `signal_router.py:78`, the check `if regime == MarketRegime.CHAOS or not regime_output.allow_trade:` creates a non-bypassable barrier. Even if a caller forged a setup or passed invalid state, no trade signal can be emitted under `CHAOS`.
   - Valid regimes route exclusively to their intended setups (`RANGE` $\to$ Mean Reversion, `TREND` $\to$ Trend Pullback, `EXPANSION` $\to$ Breakout).

4. **Integrity Audit**:
   - Full code inspection confirmed zero hardcoded outputs, zero facade/dummy mocks, zero TA-Lib shortcuts, and zero fabricated results. All calculations are executed dynamically via vectorized NumPy and Pandas.

---

## 3. Adversarial Challenges & Edge Case Findings

### Finding 1 [Minor / Cosmetic]: Ambiguous Log Description in Mean Reversion Reason String
- **Location**: `iq_regime_adaptive/feature_engine/signal_router.py`, lines 152 & 162.
- **Observation**: The condition for exhaustion checks:
  `oversold = (rsi1 <= 32.0) or (rsi0 <= 32.0) or (stoch1 <= 20.0) or (stoch0 <= 20.0)`
  However, the emitted reason string formats:
  `reason=f"Lower band bounce + oversold RSI ({rsi0:.1f}) + rejection wick ({lower_wick:.2f})"`
  When triggered on real EURUSD data (bar 164), `stoch0 <= 20.0` satisfied the condition while `rsi0` was 49.3, causing the reason string to state `"oversold RSI (49.3)"`.
- **Impact**: Purely cosmetic logging display; trading logic is functionally valid and sound.
- **Recommendation**: In a future refactoring or M3 cleanup, format reason to indicate whether RSI or Stochastic triggered exhaustion: `f"oversold momentum (RSI={rsi0:.1f}, Stoch={stoch0:.1f})"`.

### Finding 2 [Performance / Scalability Challenge]: Sequential Window Slicing in `classify_series`
- **Location**: `iq_regime_adaptive/feature_engine/regime_classifier.py`, lines 306–310.
- **Observation**: `classify_series` runs a Python loop over all bars from $50$ to $N$, slicing `sub_df = df.iloc[max(0, i-120):i]` and calling `classify_latest(sub_df)`.
- **Stress-Test Measurement**:
  - 1,000 bars took 8.97s (~9ms per candle).
  - While 9ms is near-instantaneous for live real-time execution (one candle every 5 minutes in M5), processing 20,000 bars in Milestone 2 backtests would take ~180 seconds.
- **Mitigation / Next Step for M2**: For high-speed backtesting, pre-calculate indicators vectorially across the entire dataframe and evaluate the decision tree column-wise or via vectorized masks.

---

## 4. Conclusion

The R1 Feature Engine implementation (`indicators.py`, `regime_classifier.py`, `signal_router.py`) in `iq_regime_adaptive/feature_engine/` satisfies all mathematical specifications, interface contracts, and architectural invariants defined in `PROJECT.md` and `ORIGINAL_REQUEST.md`:
1. Mathematical precision of all volatility, trend, and market memory indicators is verified.
2. The 5-Tier Decision Tree and strict non-bypassable CHAOS NO-TRADE condition are fully enforced.
3. Signal routing correctly separates setups by regime and protects capital.
4. Independent testing confirms 100% test pass rate with zero integrity violations.

**Verdict**: **APPROVE**

---

## 5. Verification Method

To independently reproduce the complete verification:
```powershell
# 1. Run Feature Engine unit tests
.\.venv\Scripts\python.exe -m unittest iq_regime_adaptive/tests/test_feature_engine.py

# 2. Run all repository tests
.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests

# 3. Verify Chaos Veto on pathological news spike
.\.venv\Scripts\python.exe -c "
import pandas as pd
from iq_regime_adaptive.feature_engine.regime_classifier import RegimeClassifier
from iq_regime_adaptive.feature_engine.signal_router import SignalRouter
from iq_regime_adaptive.tests.test_feature_engine import _generate_synthetic_candles
df = _generate_synthetic_candles(n=70)
df.iloc[-1, df.columns.get_loc('high')] = df.iloc[-1]['close'] + 0.1000
clf = RegimeClassifier()
res = clf.classify_latest(df)
decision = SignalRouter().route_signal(df)
print('Regime:', res.regime.value, '| allow_trade:', res.allow_trade, '| Signal:', decision.signal.value)
assert res.regime.value == 'CHAOS' and decision.signal.value == 'NO_TRADE'
"
```
Expected output:
```text
Regime: CHAOS | allow_trade: False | Signal: NO_TRADE
```
