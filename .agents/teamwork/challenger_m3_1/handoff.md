# Handoff Report: Empirical Adversarial Challenge of M3 Research Runner & Reporting

## Verdict: REQUEST_CHANGES

---

## 1. Observation

### Obs 1: Fatal UnicodeEncodeError on Windows Console during Invalid Hypothesis Warning
- **Target File**: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\run_research.py`
- **Line Number**: 202
- **Code**:
  ```python
  try:
      hyp_instance = get_hypothesis(hyp_id)
  except KeyError:
      print(f"      ⚠️ Warning: Unknown hypothesis ID '{hyp_id}', skipping.")
      continue
  ```
- **Execution Command**:
  ```powershell
  powershell -NoProfile -Command ".\.venv\Scripts\python.exe run_research.py --hypotheses H999,INVALID"
  ```
- **Verbatim Error & Result**:
  ```text
  [FATAL ERROR] Research pipeline failed: 'charmap' codec can't encode characters in position 6-7: character maps to <undefined>
  Traceback (most recent call last):
    File "C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\run_research.py", line 200, in run_pipeline
      hyp_instance = get_hypothesis(hyp_id)
                     ^^^^^^^^^^^^^^^^^^^^^^
    File "C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\iq_regime_adaptive\hypotheses\registry.py", line 74, in get_hypothesis
      raise KeyError(f"Unknown hypothesis ID '{hypothesis_id}'. Valid IDs: {valid}")
  KeyError: "Unknown hypothesis ID 'H999'. Valid IDs: ..."

  During handling of the above exception, another exception occurred:

  Traceback (most recent call last):
    File "C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\run_research.py", line 305, in main
      run_pipeline(args)
    File "C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\run_research.py", line 202, in run_pipeline
      print(f"      \u26a0\ufe0f Warning: Unknown hypothesis ID '{hyp_id}', skipping.")
    File "C:\Program Files\Python311\Lib\encodings\cp1252.py", line 19, in encode
      return codecs.charmap_encode(input,self.errors,encoding_table)[0]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  UnicodeEncodeError: 'charmap' codec can't encode characters in position 6-7: character maps to <undefined>
  ```
- **Exit Code**: 1.
- **Root Cause**: The character `⚠️` (`\u26a0\ufe0f`) cannot be mapped by Python's `cp1252` encoding used by default on Windows standard console. When the CLI tries to warn that an ID is unknown, it triggers an unhandled `UnicodeEncodeError`, crashing the entire pipeline.

---

### Obs 2: Boundary Payout Behavior
- **Execution Commands**:
  - `python run_research.py --payout 0.10 --hypotheses H001 --quiet`
  - `python run_research.py --payout 0.95 --hypotheses H001 --quiet`
  - `python run_research.py --payout 0.00 --hypotheses H001 --quiet`
  - `python run_research.py --payout -1.0 --hypotheses H001 --quiet`
- **Results**:
  - `--payout 0.10`: $P_{BE} = 90.91\%$. Zero trades cleared $WLB > P_{BE}$. Backtest ran with $N_{IS}=0, N_{OOS}=0$. Degradation computed $\Delta EV = 0.000, DI = 0.00, S_{comp} = 70.0$, Verdict = `REJECTED`. No division-by-zero crashes.
  - `--payout 0.95`: $P_{BE} = 51.28\%$. Trades executed ($N_{IS}=21, N_{OOS}=13$). Degradation computed $\Delta EV = +0.075, DI = 3.00, S_{comp} = 35.0$, Verdict = `REJECTED`.
  - `--payout 0.00` & `--payout -1.0`: Function `compute_payout_be` in `pipeline/payout_filter.py` line 49 checks `if payout <= 0.0: return 1.0`, eliminating division-by-zero risk. Backtest generated 0 trades and exited with code 0.

---

### Obs 3: Nonexistent & Malformed Dataset Paths
- **Execution Commands & Errors**:
  - Nonexistent file (`--data nonexistent_file.csv`):
    `FileNotFoundError: Data file does not exist: ...\nonexistent_file.csv` (Trapped at line 149 of `run_research.py`).
  - 0-byte file (`--data data/test_empty.csv`):
    `DataValidationError: Candle CSV file is empty: ...` (Trapped by `data_loader.py` line 181).
  - Headers only (`--data data/test_headers.csv`):
    `DataValidationError: Candle CSV file is empty: ...` (Trapped by `data_loader.py` line 184).
  - Insufficient rows (5 bars):
    `ValueError: Dataset length 5 is insufficient for 3-way partitioning with warmup_bars=60 and horizon_bars=1. Minimum required is 186 bars.` (Trapped by `partitioner.py` line 123).
- **Result**: All invalid dataset edge cases raised precise, informative errors.

---

### Obs 4: Custom and Invalid Split Ratios
- **Execution Commands & Errors**:
  - Valid split (`--is-ratio 0.60 --val-ratio 0.20 --oos-ratio 0.20`): Successfully partitioned 20,000 bars into 12,000 / 4,000 / 4,000; executed backtest and exported valid reports.
  - Sum != 1.0 (`--is-ratio 0.50 --val-ratio 0.50 --oos-ratio 0.50`):
    `ValueError: Partition ratios must sum to 1.0. Given: is=0.5, val=0.5, oos=0.5 (sum=1.5)` (Trapped by `partitioner.py` line 86).
  - Negative ratio (`--is-ratio -0.10`):
    `ValueError: All partition ratios must be strictly positive.` (Trapped by `partitioner.py` line 91).
  - Zero ratio (`--oos-ratio 0.00`):
    `ValueError: All partition ratios must be strictly positive.` (Trapped by `partitioner.py` line 91).

---

### Obs 5: Zero-Trade Hypotheses Degradation Safety
- **Direct Empirical Verification of `compute_degradation` and `compute_backtest_metrics`**:
  - Empty DataFrame: `total_trades=0, expected_value=0.0, wilson_lower_bound=0.0`.
  - Degradation (IS 0 trades vs OOS 0 trades): $\Delta EV = 0.0, DI = 0.0, S_{comp} = 70.0$, Verdict = `REJECTED`.
  - Degradation (IS 10 trades vs OOS 0 trades): $\Delta EV = +0.2333, DI = 1.0, S_{comp} = 35.0$, Verdict = `REJECTED`.
  - Degradation (IS 0 trades vs OOS 10 trades): $\Delta EV = -0.2333, DI = -233333.33, S_{comp} = 67.1$, Verdict = `ANTIFRAGILE`.
  - Degradation (IS negative EV vs OOS 0 trades): $\Delta EV = -1.0, DI = -1.0, S_{comp} = 70.0$, Verdict = `REJECTED`.
- **Result**: Guard terms `eps = 1e-6` in `max(abs(ev_is), eps)` and `max(max_dd_is, 0.05)` strictly prevent `ZeroDivisionError` and `NaN` propagation under all tested zero-trade states.

---

### Obs 6: Report Generation Integrity (JSON & Markdown)
- **Full Run Verification**: Full 8-hypothesis pipeline (`e2e_full_test`) executed in 209s.
  - JSON Report (`reports/e2e_full_test.json`): Validated with `json.load()`. Fully populated with 8 hypotheses, degradation matrix with 8 rows, attestation showing 458 audited trades with zero martingale violations, and champion `H004_AUTOCORRELATION_MEAN_REVERSION`.
  - Markdown Report (`reports/e2e_full_test.md`): Validated 215 lines, cleanly structured with headers, summary table, LaTeX math formulas, governance section, individual breakdown for H001-H008, and conclusion.
  - Empty Run Report (`reports/test_invalid_hyp.json` / `.md`): When 0 hypotheses are evaluated, JSON contains empty list/dict, champion is null, and Markdown table renders without crash.

---

## 2. Logic Chain

1. **Premise 1**: The Objective mandates that when testing invalid hypothesis IDs (`--hypotheses H999,INVALID`), the "System raises informative errors or handles them gracefully without unhandled tracebacks."
2. **Premise 2**: Observation 1 proves that executing `python run_research.py --hypotheses H999,INVALID` on standard Windows consoles triggers `UnicodeEncodeError: 'charmap' codec can't encode characters in position 6-7: character maps to <undefined>` at line 202 due to the emoji `⚠️`.
3. **Premise 3**: This error occurs within the exception handling block for `KeyError`, converting what was intended to be a graceful skip/warning into an unhandled fatal crash with exit code 1 and a complete traceback.
4. **Premise 4**: Consequently, standard users on Windows attempting to run the CLI with any unrecognized or mistyped hypothesis flag will suffer an unhandled crash rather than an informative message or graceful continuation.
5. **Conclusion**: While all quantitative metrics, zero-trade degradation mathematics, dataset validation, partitioning splits, and report schemas are robust and correct, the CLI runner fails the graceful error handling requirement on Windows due to line 202. Therefore, the verdict is **REQUEST_CHANGES**.

---

## 3. Caveats

- Tests were run on Windows 11 under PowerShell with Python 3.11.9 (`.venv\Scripts\python.exe`). On Linux or macOS where terminal stdout defaults to UTF-8, the `UnicodeEncodeError` in Obs 1 does not trigger, and the warning prints as expected. However, on Windows (the host operating system), `cp1252` is standard.
- When `PYTHONIOENCODING="utf-8"` is explicitly exported, line 202 succeeds and the pipeline executes with code 0.
- No source code modifications were performed by the Challenger, adhering to the "Review-only" constraint.

---

## 4. Conclusion & Actionable Mitigations

### Overall Risk Assessment: MEDIUM
The quantitative engine and reporting modules are mathematically sound and resilient. The defect is isolated to console output encoding in `run_research.py`.

### Required Changes:

1. **Fix `run_research.py` line 202 (CRITICAL for CLI robustness on Windows)**:
   - **Current**:
     ```python
     print(f"      ⚠️ Warning: Unknown hypothesis ID '{hyp_id}', skipping.")
     ```
   - **Fix**: Replace the Unicode emoji with an ASCII-safe indicator:
     ```python
     print(f"      [WARNING] Unknown hypothesis ID '{hyp_id}', skipping.")
     ```
   - *Alternative / Defense-in-depth*: At top of `run_research.py`, configure stdout stream:
     ```python
     if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
         sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
     ```

2. **Clean error reporting in `main()`**:
   - For recognized user validation exceptions (`DataValidationError`, `ValueError`, `FileNotFoundError`), avoid calling `traceback.print_exc()` to provide clean CLI error reporting, reserving tracebacks for unexpected exceptions.

---

## 5. Verification Method

To verify the failure and subsequent fix:

1. **Reproduce the bug (Before Fix)**:
   ```powershell
   powershell -NoProfile -Command ".\.venv\Scripts\python.exe run_research.py --hypotheses H999,INVALID"
   ```
   *Expected Result*: Fails with `UnicodeEncodeError: 'charmap' codec can't encode characters in position 6-7`.

2. **Verify the fix (After replacing `⚠️` with `[WARNING]`)**:
   ```powershell
   powershell -NoProfile -Command ".\.venv\Scripts\python.exe run_research.py --hypotheses H999,INVALID"
   ```
   *Expected Result*: Exits cleanly with code 0, printing:
   `[WARNING] Unknown hypothesis ID 'H999', skipping.`
   `[WARNING] Unknown hypothesis ID 'INVALID', skipping.`

3. **Verify Full Baseline Test Suite**:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests
   ```
   *Expected Result*: All 141 tests pass.

4. **Verify Boundary Tests Matrix**:
   ```powershell
   # Extreme payouts
   .\.venv\Scripts\python.exe run_research.py --payout 0.10 --hypotheses H001 --quiet
   .\.venv\Scripts\python.exe run_research.py --payout 0.95 --hypotheses H001 --quiet
   
   # Custom split
   .\.venv\Scripts\python.exe run_research.py --is-ratio 0.60 --val-ratio 0.20 --oos-ratio 0.20 --hypotheses H001 --quiet
   
   # Invalid split (should raise informative ValueError without unhandled crash)
   .\.venv\Scripts\python.exe run_research.py --is-ratio 0.50 --val-ratio 0.50 --oos-ratio 0.50 --hypotheses H001
   ```
