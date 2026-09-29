## 2026-09-28T23:55:00Z
You are Challenger M1-2 (challenger_m1_2).
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\challenger_m1_2\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md.
MANDATORY: Read PROJECT.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\PROJECT.md.

TOKEN SAVING DIRECTIVE:
Do NOT use cat, Get-Content, or full-file reads. Use the sidecar daemon or small slice reads.

OBJECTIVE:
Adversarially stress-test `iq_regime_adaptive/pipeline/payout_filter.py` and `pipeline/risk_allocation.py`:
1. Write a stress script testing Wilson Lower Bound and EV execution gate across edge boundaries:
   - N = 1, 2, 5, 10, 50, 100, 1,000,000.
   - Nominal win rate p = 0.0, 0.50, 0.55, 0.60, 0.99, 1.0.
   - Payout b = 0.01, 0.50, 0.80, 0.85, 0.95, 2.0.
   - Verify that small samples with high win rates (e.g. 8/10 = 80%) are strictly rejected under typical broker payouts.
2. Stress test Anti-Martingale capital allocation:
   - Simulate a 50-trade streak of consecutive losses.
   - Verify that stake strictly never increases after a loss: Stake_{t+1} <= Stake_t.
   - Verify that balance remains positive and never enters catastrophic drawdown or margin call.
3. Deliver `handoff.md` with explicit verdict: APPROVE or REQUEST_CHANGES.
4. Send a message to orchestrator when complete.
