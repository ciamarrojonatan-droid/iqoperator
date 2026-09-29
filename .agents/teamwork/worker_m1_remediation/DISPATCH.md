## 2026-09-29T03:03:03Z
Implement the 4 exact remediations specified in Challenger M1-1's handoff:
1. In `iq_regime_adaptive/pipeline/data_loader.py`:
   Catch `pd.errors.EmptyDataError` in `load_csv()` when calling `pd.read_csv(path)` and raise `DataValidationError(f"Candle CSV file is empty: {path}")`.
2. In `iq_regime_adaptive/feature_engine/regime_classifier.py`:
   - Early Input NaN check in `classify_latest()`:
     If `df[["open", "high", "low", "close"]].isna().any().any():`
     immediately return `RegimeOutput(regime=MarketRegime.CHAOS, allow_trade=False, reason="Corrupted data: NaN or missing values detected in candle window", tier_triggered=1, metrics={"candle_count": float(len(df))})`.
   - Kurtosis NaN sanitization:
     `if np.isnan(curr_kurt): curr_kurt = 0.0`.
     Sanitize all float metrics against NaN (replace NaN with 0.0 in `vr_4`, `z_vr`, etc. when populating `metrics` dictionary).
   - Persistent Alternating Whipsaw Guard in Tier 1:
     Add check in Tier 1 Chaos Guard:
     `if (curr_rho_1 <= -0.60 or vr_q <= 0.10) and bar_range > 0:`
     flag Chaos with reason `f"Extreme oscillating whipsaw (rho_1={curr_rho_1:.2f}, VR={vr_q:.2f})"`.
     Also ensure Tier 4 Range criteria checks `curr_rho_1 > -0.60` and `vr_q > 0.10`.
3. Verify by running:
   `.\.venv\Scripts\python.exe -m unittest iq_regime_adaptive/tests/test_adversarial_m1.py`
   and
   `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`
   Confirm that all tests (including the 23 adversarial tests) pass with 0 errors and 0 failures.
4. Write `handoff.md` and send message to orchestrator.
