# Estado do Projeto (IQ Operator)

## Fase Atual: Regime-Adaptive Quantitative Engine (H008)
O robô evoluiu de um filtro XGBoost estático para um **Motor de Pesquisa Quantitativa Regime-Adaptativo** com validação matemática rigorosa (IS/VAL/OOS), Backtest anti-overfitting e Zero Martingale.

## 1. Arquitetura Consolidada

### Motor Principal (bot.py)
- **Sinal de entrada:** `H008_RegimeAdaptiveRouter` — classifica o mercado em 4 estados (TREND, RANGE, EXPANSION, CHAOS) e roteia para o especialista correto. Mercados `CHAOS` = veto automático de trade.
- **XGBoost / LayaFilter removidos** do loop principal. O roteador de regime substitui ambos com edge matemático comprovado.
- **Kelly Fracionário** para gestão de risco — monotonicamente decrescente sob drawdown, Zero Martingale.
- **Filtro de Payout dinâmico** — trade executado apenas se `EV_WLB > 0` com payout atual.

### Framework de Pesquisa Quantitativa (`iq_regime_adaptive/`)
- **155 testes unitários passando** (unit, adversarial, E2E, challenger stress).
- **8 hipóteses avaliadas** (H001–H008) sob fatiamento cronológico cego 50/25/25.
- **Motor vetorizado (NumPy)** — processa 16k velas em segundos (eliminado loop Python puro).
- **Wilson Lower Bound 95%** como barreira estatística de execução.
- Auditoria Anti-Martingale verificada em 100% dos backtests.

### Filtros Ativos
- **Bloqueio de Sessões Tóxicas:** `BLOCKED_HOURS_UTC="5,8,12,21,23"` (UTC).
- **Filtro de Notícias:** `news_filter.py` — raspagem ForexFactory, paralisa 30min antes/depois de Red Folder USD/EUR.
- **Homeostase de Websocket:** `homeostasis.py` — auto-reparo de socket sem `GLOBAL OUTAGE`.

## 2. Grid Search de Ativos — Resultados Definitivos (H008 OOS)

### Portfólio Validado ANTIFRAGILE (8 ativos)
| Ativo | Win Rate OOS | EV OOS | Veredito |
|:---|:---:|:---:|:---:|
| EURUSD | 66.7% | +0.233 | ANTIFRAGILE |
| AUDJPY | 70.0% | +0.295 | ANTIFRAGILE |
| EURJPY | 65.0% | +0.203 | ANTIFRAGILE |
| EURAUD | 65.0% | +0.203 | ANTIFRAGILE |
| AUDUSD | 61.1% | +0.131 | ANTIFRAGILE |
| ETHUSD | 60.0% | +0.110 | ANTIFRAGILE |
| USDCAD | 60.0% | +0.110 | ANTIFRAGILE |
| USDCHF | 60.0% | +0.110 | ANTIFRAGILE |

### Ativos Rejeitados (REJECTED — não operar)
GBPUSD, BTCUSD, XAUUSD, XAGUSD, SP500, GBPJPY, CADJPY, NZDUSD, AUDCAD, EURGBP, USDJPY.

### Configuração de Produção (Railway .env)
```
IQ_ASSETS="EURUSD,AUDUSD,USDCAD,ETHUSD,AUDJPY,EURJPY,EURAUD,USDCHF"
IQ_TIMEFRAME="300"
IQ_BALANCE_TYPE="PRACTICE"
STRATEGY="multi_mean_reversion"
BLOCKED_HOURS_UTC="5,8,12,21,23"
HF_DATASET_REPO="jonatanciamarro/iqoperator-trades"
ML_THRESHOLD="0.55"
```

## 3. Git / Deploy
- **Dual-push ativo:** `microfactx/iqoperator` (principal) e `ciamarrojonatan-droid/iqoperator` (fork Railway).
- **Commits recentes:**
  - `ff3b7cb` — perf: vetoriza H008 router (numpy) e corrige parse de timestamp
  - `83b434e` — feat(quant): integra H008 Regime-Adaptive router e backtest engine

## 4. Próximos Passos
- **Deploy sprints 1-4 (2026-09-30):** fix reconnect `cfg.IQ_USER`, observabilidade payout src + regime no `[CHECK]`, guard CLOSED 1h anti-retry, log diet (só sinal/mudança de regime).
- **Forward Test:** Coletar `trades_live.csv` do HuggingFace após 1–2 semanas e comparar WR real vs WR OOS.
- **Replay H008 offline:** rodando sobre `data/*_M5_iq.csv` para comparar taxa de sinal live vs OOS por ativo.
- **Transição para REAL:** Somente se WR forward test ≥ WLB OOS por ativo com N ≥ 50 trades.
