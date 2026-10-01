# Live Join — replay vs live ([CHECK])

Comando:
```
.\.venv\Scripts\python.exe scripts/compare_signal_parity.py --data data/EURUSD_M5_iq.csv --limit 2000 --live-log data/sample_live_check.log --asset EURUSD
```

Live log: `data/sample_live_check.log` (8 linhas [CHECK] amostra, todas `-> None`, `forming=dropped`).

## Saída do script (verbatim)

```
[A] sem --candidates; usando fallback H008 (demonstrativo).
[A] fallback: H008 sobre data/EURUSD_M5_iq.csv (asset=EURUSD, payout=0.85, limit=2000) — rename time->from quando aplicavel.
[B] live-log: data/sample_live_check.log
=== PARIDADE DE SINAIS backtest x live ===
backtest: 12 linhas (12 CALL/PUT)
  regimes(backtest): {'RANGE': 11, 'TREND': 1}
  veto_codes(backtest): {'PASS': 12}
  (fallback: 2000 candles, 1519 barras CHAOS vetadas)
live: 8 linhas [CHECK] (0 CALL/PUT joinable; 0 sem chave joineavel)
  regimes(live): {'CHAOS': 6, 'RANGE': 2}
  direcoes(live): {'NONE': 8}
chaves backtest(CALL/PUT): 12 | live(CALL/PUT): 0
matches (mesma chave + mesma direcao): 0
conflitos (mesma chave, direcao diferente): 0
match/union (Jaccard): 0.000
match/backtest: 0.000
match/live:     nan
so-backtest (12): ['EURUSD|1782170400', 'EURUSD|1782172800', 'EURUSD|1782174300', 'EURUSD|1782251400', 'EURUSD|1782335100', 'EURUSD|1782338100', 'EURUSD|1782409800', 'EURUSD|1782411000', 'EURUSD|1782421800', 'EURUSD|1782437400', 'EURUSD|1782694200', 'EURUSD|1782885000']
so-live (0): []
```

## Interpretação (5 linhas)

1. Não há match acionável (Jaccard 0.000, match/backtest 0.000): esperado, pois o live tem 0 CALL/PUT (8/8 `-> None`) e o replay tem 12 CALL/PUT em chaves/ativos distintos (live é multi-asset, replay é só EURUSD; `from:1790821200` não aparece nas 12 chaves do replay ~1782xxxxxx).
2. Em distribuição incondicional, o live bate com o replay no ponto central: replay veta 1519/2000 barras CHAOS (~76%) e o live marca 6/8 CHAOS (75%) — mesma ordem de grandeza de filtragem CHAOS do H008.
3. Em distribuição condicional a sinal, não há divergência de direção: 0 conflitos; o live veta corretamente os 6 CHAOS (todos `None`) de forma coerente com o router, que só emite sinal em RANGE/TREND (11 RANGE + 1 TREND no replay).
4. Os 2 RANGE do live (ETHUSD, EURAUD) também deram `None` por `forming=dropped` + lag alto (413s/511s), não por regime — ou seja, o veto veio de formação/latência, camada fora do escopo do fallback H008 puro.
5. Conclusão: paridade de regime OK (filtro CHAOS consistente), paridade de sinal N/A neste recorte (sem chaves sobrepostas nem CALL/PUT no live para joinear); para medir match rate real é preciso log live com CALL/PUT no mesmo asset/janela do replay.
