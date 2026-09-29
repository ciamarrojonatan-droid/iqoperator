# Handoff Report — Challenger M1-1

**Verdict**: `REQUEST_CHANGES`

## 1. Observation

Adversarial stress-testing was executed against `iq_regime_adaptive/feature_engine/` and `pipeline/data_loader.py` using a newly authored empirical test suite located at `iq_regime_adaptive/tests/test_adversarial_m1.py` containing 23 stress tests.

Executing the suite via `.\.venv\Scripts\python.exe -m unittest iq_regime_adaptive/tests/test_adversarial_m1.py` yielded:
```text
Ran 23 tests in 0.171s
FAILED (failures=3, errors=1)
```

The specific failures and verbatim outputs observed are:

### Finding 1: Unhandled `pandas.errors.EmptyDataError` in `DataLoader.load_csv`
- **Location**: `iq_regime_adaptive/pipeline/data_loader.py:178`
- **Verbatim Error**:
```text
ERROR: test_dataloader_empty_csv_rejection (iq_regime_adaptive.tests.test_adversarial_m1.TestAdversarialStressM1.test_dataloader_empty_csv_rejection)
...
  File "C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\iq_regime_adaptive\pipeline\data_loader.py", line 178, in load_csv
    df = pd.read_csv(path)
...
pandas.errors.EmptyDataError: No columns to parse from file
```
- **Observed Code**:
```python
178:         df = pd.read_csv(path)
179:         if df.empty:
180:             raise DataValidationError(f"Candle CSV file is empty: {path}")
```
`pd.read_csv(path)` throws `EmptyDataError` on a 0-byte file before the empty check on line 179 can run.

---

### Finding 2: Unhandled `NaN` Escape in `metrics["kurtosis"]` on Flatline Zero-Volatility Data
- **Location**: `iq_regime_adaptive/feature_engine/regime_classifier.py:160, 180`
- **Verbatim Error**:
```text
FAIL: test_flatline_zero_volatility_detection (iq_regime_adaptive.tests.test_adversarial_m1.TestAdversarialStressM1.test_flatline_zero_volatility_detection)
AssertionError: np.True_ is not false : Metric 'kurtosis' in flatline metrics contains unhandled NaN
```
- **Observed Code**:
```python
159:         recent_ret = np.diff(np.log(close.values[-31:]))
160:         curr_kurt = float(kurtosis(recent_ret, fisher=True)) if len(recent_ret) >= 30 else 0.0
...
180:             "kurtosis": curr_kurt,
```
When prices are constant, `recent_ret` is an array of zeros. `scipy.stats.kurtosis(np.zeros(30), fisher=True)` evaluates to `np.nan`. Because `curr_kurt` is not sanitized (`if np.isnan(curr_kurt): curr_kurt = 0.0`), `out.metrics["kurtosis"]` contains `NaN`.

---

### Finding 3: Unsanitized `NaN` Input Leads to False `RANGE` Classification and Leaks `NaN` into Metrics
- **Location**: `iq_regime_adaptive/feature_engine/regime_classifier.py:89`
- **Verbatim Error**:
```text
FAIL: test_nan_in_candle_data_handling (iq_regime_adaptive.tests.test_adversarial_m1.TestAdversarialStressM1.test_nan_in_candle_data_handling)
AssertionError: <MarketRegime.RANGE: 'RANGE'> != <MarketRegime.CHAOS: 'CHAOS'>
```
- **Observed Behavior**:
When an incoming candle DataFrame contains `NaN` in one of its OHLC values (e.g. `df.loc[45, 'close'] = np.nan`), `RegimeClassifier.classify_latest` does not check for input `NaN` values. Rolling indicators compute over `NaN`s, and the decision tree falls through to `Tier 4 (RANGE)` with `allow_trade = True`. In addition, `out.metrics` contains `{'vr_4': nan, 'z_vr': nan, 'kurtosis': nan}`.

---

### Finding 4: Persistent Alternating Whipsaw Falsely Flagged as `RANGE` with `allow_trade=True`
- **Location**: `iq_regime_adaptive/feature_engine/regime_classifier.py:197, 270-283`
- **Verbatim Error**:
```text
FAIL: test_persistent_alternating_whipsaw_veto (iq_regime_adaptive.tests.test_adversarial_m1.TestAdversarialStressM1.test_persistent_alternating_whipsaw_veto)
AssertionError: <MarketRegime.RANGE: 'RANGE'> != <MarketRegime.CHAOS: 'CHAOS'> : Persistent alternating whipsaw flagged as 'RANGE' instead of CHAOS!
```
- **Observed Behavior**:
When fed a 100-bar square wave alternating between 1.1000 and 1.1100:
- `ADX` = 3.7, `di_diff` = 2.5
- `rho_1` = -0.98, `VR` = 0.00
- `bbw_z` = 0.0, `nrv` = -0.20
Tier 1 Chaos Guard does NOT catch it because Tier 1 only triggers whipsaw if `curr_adx >= 35.0 and curr_di_diff <= 4.0`.
Tier 4 (RANGE) checks:
- `absence_trend`: `curr_adx < 20.0` (True) and `curr_di_diff < 12.0` (True)
- `mean_reverting_memory`: `curr_rho_1 <= -0.05` (True)
- `contained_vol`: `curr_bbw_z <= 0.50` (True) and `curr_nrv < 1.0` (True)
- `in_envelope`: True
Result: `Stationary Range confirmed (ADX=3.7, VR=0.00, rho_1=-0.98)` with `allow_trade = True`!
An oscillating alternating whipsaw trap is classified as a tradable stationary range.

---

## 2. Logic Chain

1. **R1 / Objective Invariant Check**: The objective requires:
   - "In all extreme conditions, `regime_classifier` robustly flags `CHAOS` without crashing."
   - "In all `CHAOS` cases, `signal_router` outputs `MarketSignal.NO_TRADE` with `allow_trade == False`."
   - "No division by zero or NaN propagation escapes unhandled."
2. **Defect 1**: `pd.read_csv` throws `EmptyDataError` when reading a 0-byte file. Since `DataLoader.load_csv` specifies that schema failures raise `DataValidationError`, letting `EmptyDataError` bubble up crashes callers who catch `DataValidationError`.
3. **Defect 2**: `metrics['kurtosis']` returning `NaN` violates the invariant that no NaN propagation escapes unhandled. Downstream modules serializing metrics via `json.dumps()` or performing numeric operations will fail or produce invalid JSON.
4. **Defect 3**: An input DataFrame containing `NaN` is not rejected or flagged as `CHAOS`. Instead, it outputs `RANGE` with `allow_trade = True`. This poses a direct production risk because missing price feeds from IQOption could trigger false BUY/SELL signals while propagating `NaN`s in metrics (`vr_4: nan`, `z_vr: nan`).
5. **Defect 4**: Extreme negative autocorrelation ($\rho_1 \approx -1.0$) combined with zero variance ratio ($VR \approx 0.0$) represents an extreme whipsaw / microstructure oscillation. By only checking `curr_adx >= 35.0` for whipsaw in Tier 1, the classifier allows low-ADX alternating whipsaws to be misidentified as calm `RANGE` markets, permitting trades right into alternating whipsaw traps.

---

## 3. Caveats

- Flash crashes (50x stddev), flash spikes (50x stddev), massive wick anomalies (20x ATR pin bars), weekend gap jumps, and small sample frames (< 50 bars) were tested and all correctly triggered `CHAOS` with `MarketSignal.NO_TRADE` and `allow_trade == False`.
- In `signal_router.py`, the CHAOS veto logic itself (`if regime == MarketRegime.CHAOS or not regime_output.allow_trade: return SignalDecision(NO_TRADE)`) is robust whenever `regime_classifier` flags `CHAOS` or sets `allow_trade = False`. The vulnerability stems from `regime_classifier` failing to flag `CHAOS` on persistent alternating whipsaws and NaN inputs.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

The M1 Feature Engine and Data Loader require the following 4 concrete remediations before Milestone 1 can be approved:

1. **In `iq_regime_adaptive/pipeline/data_loader.py`**:
   Wrap `pd.read_csv(path)` in a `try...except pd.errors.EmptyDataError:` block and raise `DataValidationError(f"Candle CSV file is empty: {path}")`.

2. **In `iq_regime_adaptive/feature_engine/regime_classifier.py`**:
   - **Input Validation**: At the start of `classify_latest()`, check if `df[["open", "high", "low", "close"]].isna().any().any()`. If `True`, return `RegimeOutput(regime=MarketRegime.CHAOS, allow_trade=False, reason="Corrupted data: NaN or missing values detected in candle window", tier_triggered=1, metrics={"candle_count": float(n)})`.
   - **Kurtosis NaN Sanitization**: In line 160, sanitize `curr_kurt`:
     ```python
     if np.isnan(curr_kurt):
         curr_kurt = 0.0
     ```
   - **General Metrics NaN Sanitization**: Ensure all float values assigned to `metrics` (including `curr_natr`, `curr_bbw`, `vr_q`, `z_vr`) are sanitized against `np.isnan()`.
   - **Alternating Whipsaw Guard in Tier 1**: Add an explicit check in Tier 1 Chaos Guard:
     ```python
     if (curr_rho_1 <= -0.60 or vr_q <= 0.10) and bar_range > 0:
         chaos_reasons.append(f"Extreme oscillating whipsaw (rho_1={curr_rho_1:.2f}, VR={vr_q:.2f})")
     ```
     And/or tighten Tier 4 Range criteria so that extreme negative autocorrelation (`curr_rho_1 < -0.50` or `vr_q < 0.20`) cannot qualify as a stationary range.

---

## 5. Verification Method

To verify these findings and subsequently verify the applied fixes:

1. Run the targeted adversarial stress test suite:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest iq_regime_adaptive/tests/test_adversarial_m1.py
   ```
2. Run the complete test suite:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests
   ```
3. Invalidation condition: All 99 tests (including the 23 adversarial tests) pass with `OK` (0 failures, 0 errors).
