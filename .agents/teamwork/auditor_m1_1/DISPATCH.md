## 2026-09-28T23:54:41-03:00

You are Forensic Auditor M1-1 (auditor_m1_1).
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\auditor_m1_1\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md.
MANDATORY: Read PROJECT.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\PROJECT.md.

TOKEN SAVING DIRECTIVE:
Do NOT use cat, Get-Content, or full-file reads. Use the sidecar daemon or small slice reads.

OBJECTIVE:
Perform a forensic integrity audit on all Milestone 1 modules in `iq_regime_adaptive/`:
1. Static analysis: Check `pipeline/data_loader.py`, `feature_engine/indicators.py`, `feature_engine/regime_classifier.py`, `feature_engine/signal_router.py`, `pipeline/payout_filter.py`, `pipeline/risk_allocation.py`.
   - Verify zero hardcoded test results, zero mock passes, zero dummy/facade implementations.
   - Verify that mathematical formulas for Wilder's ATR/ADX, Variance Ratio, Wilson Score Lower Bound, Break-even payout, and Fractional Kelly are genuine, closed-form, and mathematically sound.
2. Anti-Cheating & Anti-Martingale Verification:
   - Verify that no martingale, d'Alembert, Fibonacci, or asymmetric loss-recovery logic exists anywhere in the codebase.
   - Verify that stake sizing strictly contracts or stays fixed during drawdowns.
3. Execution verification: Run tests via `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`.
4. Deliver `handoff.md` with explicit binary verdict: CLEAN or INTEGRITY VIOLATION.
5. Send a message to orchestrator when complete.
