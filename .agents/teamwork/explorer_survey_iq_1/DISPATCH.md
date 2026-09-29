# Dispatch: Explorer Survey IQ 1

You are Explorer Survey IQ 1.
Your task is to investigate the existing codebase, file layout, dependencies, and data assets in `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\` and parent folders.

## 2026-09-29T02:38:15Z

<USER_REQUEST>
You are Explorer Survey IQ 1.
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_1\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md (specifically the request from 2026-09-29T02:35:44Z).

Objective:
Map out the workspace environment:
1. Inspect `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\` and parent folder `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\` to identify existing Python environments, installed packages (numpy, pandas, scipy, statsmodels, pytest, etc.), existing scripts, modules, IQ Option API wrappers or mocks, strategies, and historical candle data files (.csv, parquet, etc.).
2. Check available data files (e.g. EURUSD, OTC pairs, M1, M5, M15 candles, payout data) or any candle fetchers/simulators.
3. Document the recommended directory layout and package structure for the Quantitative Research Architecture (e.g., `iq_regime_adaptive/` or `src/iq_regime/` containing `feature_engine/`, `pipeline/`, `backtest/`, `hypotheses/`, `reports/`, `tests/`).
4. Write your comprehensive findings to `report.md` in your working directory and summarize key findings in `handoff.md`.
5. Send a message back to the orchestrator when complete.
</USER_REQUEST>

## 2026-09-29T02:41:16Z

**Context**: [URGENT NEW DIRECTIVE FROM SENTINEL / USER]
**Content**: Vocês estão expressamente proibidos de usar `cat` ou `Get-Content` ou ferramentas de leitura completa de arquivos (`view_file` completo) que gastem muitos tokens. Para economizar tokens, usem o sidecar (daemon) do Hypervisor para auditar e extrair código: `python -m synaptic_hypervisor.sidecar.daemon --action extract_edges --file <arquivo>` ou fatias extremamente pequenas. Cancele qualquer leitura massiva em andamento imediatamente.
**Action**: Aplique imediatamente essa restrição estrita em todas as suas operações.
