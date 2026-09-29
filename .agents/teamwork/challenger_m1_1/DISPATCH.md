## 2026-09-29T02:54:41Z

You are Challenger M1-1 (challenger_m1_1).
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\challenger_m1_1\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md.
MANDATORY: Read PROJECT.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\PROJECT.md.

TOKEN SAVING DIRECTIVE:
Do NOT use cat, Get-Content, or full-file reads. Use the sidecar daemon or small slice reads.

OBJECTIVE:
Adversarially stress-test `iq_regime_adaptive/feature_engine/` and `pipeline/data_loader.py`:
1. Write a script or test harness to feed synthetic stress candles into the feature engine:
   - Extreme volatility flash crash / spike (50x standard deviation).
   - Flatline zero-volatility prices (constant Close).
   - Oscillating alternating whipsaws.
   - Massive wick anomalies.
   - Gaps, missing rows, and small sample frames (< 50 bars).
2. Verify that:
   - In all extreme conditions, `regime_classifier` robustly flags `CHAOS` without crashing.
   - In all `CHAOS` cases, `signal_router` outputs `MarketSignal.NO_TRADE` with `allow_trade == False`.
   - No division by zero or NaN propagation escapes unhandled.
3. Deliver `handoff.md` with explicit verdict: APPROVE or REQUEST_CHANGES.
4. Send a message to orchestrator when complete.
