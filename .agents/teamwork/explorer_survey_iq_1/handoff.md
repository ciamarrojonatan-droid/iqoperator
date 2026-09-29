# Handoff Report: Explorer Survey IQ 1

**Handoff Type**: Hard (Task Complete)  
**Agent**: Explorer Survey IQ 1  
**Timestamp**: 2026-09-29T02:45:00Z  
**Target Recipient**: Orchestrator (ID: `5300d532-e3aa-4ce2-bdf4-d9b54031954a`)  
**Artifacts Generated**:
- `report.md`: Comprehensive Quantitative Research Architecture survey report.
- `handoff.md`: 5-component self-contained handoff.
- `BRIEFING.md`: Working memory and state.
- `DISPATCH.md`: Inbound request and directive audit log.
- `progress.md`: Liveness heartbeat log.

---

## 1. Observation

1. **Python Environment & Package Verification**:
   - System command:
     `powershell -Command "Get-Command python"`
     returned: `The term 'python' is not recognized as the name of a cmdlet, function, script file, or operable program.`
   - Dedicated virtualenv exists at `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.venv\`.
   - Executable: `.\.venv\Scripts\python.exe --version` returned `Python 3.11.9`.
   - Package import test using `.\.venv\Scripts\python.exe -c "..."` confirmed:
     - `numpy`: 2.4.6 INSTALLED
     - `pandas`: 3.0.6 INSTALLED
     - `scipy`: 1.17.1 INSTALLED
     - `scikit-learn`: 1.9.1 INSTALLED
     - `xgboost`: 3.2.0 INSTALLED
     - `numba`: 0.67.0 INSTALLED
     - `torch`: 2.14.0 INSTALLED
     - `iqoptionapi`: 6.8.9.1 INSTALLED
     - `pytest`: MISSING (`ModuleNotFoundError: No module named 'pytest'`)
     - `statsmodels`: MISSING (`ModuleNotFoundError: No module named 'statsmodels'`)
   - Existing unit test suite executed via standard library:
     `.\.venv\Scripts\python.exe -m unittest discover tests`
     Output: `Ran 62 tests in 22.741s — OK`.

2. **Parent Directory Inspection**:
   - Directory listing of `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\` revealed 1 child directory: `iqoperator` and 0 other files.

3. **Data Assets Inventory in `data/`**:
   - `data/EURUSD_M5_iq.csv`: 20,000 rows (M5 candles, 2026-06-22 to 2026-09-25 UTC).
   - `data/EURUSD_M15_histdata.csv`: 40,000 rows (M15 candles, 2024-05-23 to 2025-12-31 UTC).
   - OTC pairs from IQ Option (20,000 M5 rows each): `AUDUSD_M5_iq.csv`, `GBPUSD_M5_iq.csv`, `USDJPY_M5_iq.csv`, `USDCAD_M5_iq.csv`, `EURGBP_M5_iq.csv`.
   - Crypto datasets:
     - `data/BTCUSDT_M1_60d.csv`: 86,400 rows (M1 candles with volume, 60 days).
     - `data/BTCUSDT_M5_3y.csv`: 315,360 rows (M5 candles, 3 years: 2023-09-28 to 2026-09-27).
     - `data/BTCUSDT_M15_1y.csv`: 35,000 rows (M15 candles, 1 year).
   - Commodities: `data/XAUUSD_M5_iq.csv` (13,683 rows), `data/XAGUSD_M5_iq.csv` (13,681 rows).
   - Unconditioned baseline performance: `data/assets_performance_m5.csv` showed that across 2,570 trades with WinRate ~47%-52%, net profit was $-\$1,982.00$ due to negative mathematical expectation against broker payouts.

4. **Codebase Machinery**:
   - `bot.py` (917 lines): Real-time multi-asset bot, non-blocking execution, pending order reconciliation, integration with `HomeostasisManager` (`homeostasis.py`) and `MLFilter` (`ml_filter.py`).
   - `strategies.py` (378 lines): Implementation of `donchian_fade_signal`, `bollinger_touch_signal`, `rsi_m15_signal`, `rsi_mtf_pullback_signal`, `mhi_1_signal`.
   - `kelly.py` (43 lines): `kelly_fraction_stake(balance, payout, winrate)` and `empirical_winrate(history, prior)`.
   - `backtest_h010.py` (270 lines): Adapted hypothesis H010 with `wilson_lower(wins, n, z=1.96)`, Breakeven calculation $P_{BE} = \frac{1}{1 + \text{payout}}$, and 70% IS / 30% OOS split.
   - `tests/test_homeostasis.py` (543 lines): Contains mock harness `FakeAPI` and `FakeBot` implementing deterministic mocks for `getcandles`, `get_betinfo`, `get_balance`, and `get_binary_option_detail`.

5. **Token Preservation Directive**:
   - Directive received from orchestrator at 2026-09-29T02:41:16Z prohibiting whole-file reading tools (`cat`, `Get-Content`, massive `view_file`) and directing agents to use small slice reads or the sidecar daemon.
   - Verified sidecar CLI: `.\.venv\Scripts\python.exe -m synaptic_hypervisor.sidecar.daemon index` executed with code 0 (`TSG indexado com sucesso! Total de nós mapeados: 257`).

---

## 2. Logic Chain

1. **From Observation 1 (Python Environment)**:
   - System python is not in PATH, but `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.venv\Scripts\python.exe` is a fully functional Python 3.11.9 runtime.
   - Core computational libraries (`numpy`, `pandas`, `scipy`, `scikit-learn`, `xgboost`, `numba`, `torch`) are already installed and tested.
   - `pytest` is absent, meaning all automated test runs must invoke Python's built-in `unittest` runner:
     `.\.venv\Scripts\python.exe -m unittest discover tests`.
   - `statsmodels` is absent, which implies statistical regime detection (ADX, ACF, volatility estimators) must be built using `scipy.stats`, `scipy.signal`, and `numpy` rather than relying on an external uninstalled package.

2. **From Observation 3 & 4 (Data & Baseline Performance)**:
   - Historical candle coverage is rich and immediately usable (over 315,000 M5 candles and 86,000 M1 candles with volume, plus 20,000 broker-native M5 candles for 6 major currency pairs).
   - In binary options, an edge cannot be assessed by win rate alone: $P_{BE} = \frac{1}{1 + b}$. A 52% win rate on an 80% payout is guaranteed ruin because $P_{BE} = 55.56\%$.
   - Incorporating the Wilson lower bound $W_{lower}$ ensures that small sample outliers are penalized, filtering out statistical noise before trading.

3. **From Requirements R1, R2, R3 in `ORIGINAL_REQUEST.md`**:
   - R1 demands routing signals based on market regime (Trend, Range, Expansion, Chaos $\rightarrow$ NO TRADE).
   - R2 demands filtering trades through dynamic payout and Wilson-conditioned expected value ($EV_{wilson} > 0$).
   - R3 demands out-of-sample stability verification across In-Sample (IS), Validation (VAL), and Out-of-Sample (OOS), tracking EV degradation ($\Delta EV$).
   - The logical structure requires a modular research package:
     `iq_regime_adaptive/` containing `feature_engine/`, `pipeline/`, `hypotheses/`, `backtest/`, `reports/`, and `tests/`.

---

## 3. Caveats

1. **Broker Live Payout Feed**: Real-time payout varies by time of day on IQ Option. While `api.get_binary_option_detail()` extracts live payouts in `bot.py`, backtests on historical CSVs must use payout scenarios (e.g. 75%, 80%, 85%, 87%) or historical payout distributions since historical candle CSVs do not contain historical broker payout columns.
2. **Timestamp Normalization**: CSV files across `data/` use different timestamp formats (epoch seconds vs epoch milliseconds vs datetime string). The data ingestion layer in `pipeline/data_loader.py` must detect and normalize timestamps automatically.
3. **No External Internet Access Required**: All research, feature engineering, backtesting, hypothesis testing, and reporting can run 100% offline using the existing local datasets and virtual environment.

---

## 4. Conclusion

The workspace is fully equipped and primed for the implementation of the Quantitative Research Architecture (`iq_regime_adaptive`).
- Runtime: Python 3.11.9 at `.venv\Scripts\python.exe`.
- Testing: Standard library `unittest` (all 62 existing tests pass in 22.7s).
- High-volume data: Over 500,000 historical candles across EURUSD, OTC currency pairs, and BTCUSDT.
- Architecture: A dedicated, modular architecture (`iq_regime_adaptive/` or `src/iq_regime/`) has been fully designed and documented in `report.md`, ready for delegation to implementers.

---

## 5. Verification Method

To independently verify all findings and validate the environment:

1. **Verify Python & Dependencies**:
   ```powershell
   cd "c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator"
   .\.venv\Scripts\python.exe -c "import numpy, pandas, scipy, sklearn, xgboost, numba, iqoptionapi; print('Core quant libraries OK')"
   ```
   *Expected result*: `Core quant libraries OK` (Exit code 0).

2. **Verify Existing Test Suite**:
   ```powershell
   cd "c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator"
   .\.venv\Scripts\python.exe -m unittest discover tests
   ```
   *Expected result*: `Ran 62 tests in ...s — OK` (Exit code 0).

3. **Verify Data Files Availability**:
   ```powershell
   cd "c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator"
   .\.venv\Scripts\python.exe -c "import os; assert os.path.exists('data/EURUSD_M5_iq.csv') and os.path.exists('data/BTCUSDT_M5_3y.csv'); print('Data files confirmed')"
   ```
   *Expected result*: `Data files confirmed` (Exit code 0).

4. **Verify Report Artifact**:
   Inspect `report.md` in `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_1\report.md`.
