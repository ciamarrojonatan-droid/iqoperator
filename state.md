# Estado do Projeto (IQ Operator)

## Fase Atual: MHI M1 + ML Sniper (XGBoost)
O projeto passou por um pivô estratégico drástico após a identificação de um vazamento de dados (*Lookahead Bias*) no backtest anterior. Abandonamos o antigo roteador H008 (M5) e migramos 100% do operacional para a estratégia matemática **MHI 1 (Timeframe M1)** puramente quantitativa, filtrada por uma Inteligência Artificial extremamente otimizada.

## 1. Arquitetura Consolidada

### Motor Principal (`bot.py`)
- **Timeframe:** M1 (1 minuto). Expiração de 1 minuto. Sem Martingale.
- **Roteador Atual:** `MHIMLRouter` (Substituiu completamente o `H008_RegimeAdaptiveRouter` e antigas lógicas de "Regime"). 
- **Lógica MHI:** Analisa os 3 últimos candles fechados. Conta as cores (Maioria Verde = Put, Maioria Vermelha = Call).
- **Filtro ML (XGBoost):** Após o sinal do MHI ser validado, calculamos 86 métricas técnicas e de fluxo (SMA, BB, RSI, Distâncias, Wick ratio, Sessão, etc). O XGBoost pontua a probabilidade daquele snipe dar certo.
- **Limpeza de Vazamentos:** Todas as features que representavam dados futuros (`next_candle_dir`, `y`, etc.) foram erradicadas da fase de engenharia de features (`train_xgb_v2.py`), tornando os backtests **100% justos e realistas**.
- **Filtros Bloqueados:** Seguindo estritamente o backtest original (onde o bot precisa operar "cru" o tempo todo), o filtro de notícias e as horas tóxicas foram **desativados via código** no `bot.py` (`is_toxic = False`, `is_news = False`). 

### O Novo Laboratório de Backtest EUR/USD (1 Ano)
Validamos a estratégia extraindo *525.600 candles* de 1 minuto do par EURUSDT (equivalente ao EUR/USD).
*   **MHI M1 Cru:** Assertividade base de 58.43% no EUR/USD.
*   **A Nova Inteligência Artificial:** Treinamos um modelo exclusivamente especializado no comportamento do EUR/USD (`xgb_filter_eurusd_1y.json`).
*   **Desempenho Out-of-Sample (OOS):**
    *   **Threshold 0.58:** 73.91% de Taxa de Acerto (mais de 11.000 trades catalogados no ano em dados que a IA nunca viu).
    *   **Threshold 0.62:** 75.30% de Taxa de Acerto.

## 2. Configurações Ativas e Deployment

O bot foi corrigido e encontra-se plenamente operacional e estável no Railway, superando os timeouts antigos causados por mercados fechados e resolvendo conflitos de feature names.

### Arquivos Chave Alterados
- `train_xgb_v2.py`: Corrigida a engenharia de features e vazamento de dados.
- `mhi_ml_router.py`: Responsável por rodar o sinal de MHI, traduzir colunas do JSON da IQ Option para o Pandas (ex: tratar erro de datetime), extrair as features exatas do XGBoost e devolver o bloqueio ou a autorização de trade (`ML_PASS` vs `ML_BLOCKED`).
- `bot.py`: Chama o roteador passando o caminho exato do modelo, desativa notícias/horários tóxicos, e implementa **resolução dinâmica e automática de ativos (Forex vs OTC)** com verificação de mercado aberto em tempo real (`_is_market_open`), fallback reativo imediato no `_fire_buy` e sincronização contínua de opcodes em `OP_code.ACTIVES`.
- `backtest_eurusd_1y.py` / `fetch_eurusdt_1y.py`: Scripts independentes de backtest para validação contra histórico da Binance.

### Configuração de Produção Recomendada (.env)
```env
IQ_ASSETS="EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,USDCHF,NZDUSD,EURGBP,EURJPY,GBPJPY,AUDJPY,EURAUD,EURCAD,EURNZD,EURCHF,GBPAUD,GBPCAD,GBPCHF,GBPNZD,AUDCAD,AUDNZD,AUDCHF,CADJPY,CHFJPY,CADCHF,NZDJPY,NZDCAD,BTCUSD,ETHUSD,XAUUSD"
IQ_MAX_CONCURRENT="5"
IQ_TIMEFRAME="60"
IQ_EXPIRATION="1"
IQ_BALANCE_TYPE="PRACTICE"
STRATEGY="mhi_1"
ML_THRESHOLD="0.58"
```
*(Nota: Graças ao mecanismo de resolução dinâmica de ativos adicionado ao `bot.py`, o bot detecta em tempo real se o mercado regular ou OTC está aberto na IQ Option e seleciona a variante correta automaticamente para cada um dos 30 ativos, funcionando 24/7 sem necessidade de alternar o `.env` nos finais de semana).*

## 3. Próximos Passos
- **Avaliação do Forward Testing (Ao Vivo):** Deixar o container rodar com o `xgb_filter_eurusd_1y.json` e comparar o log de `[CHECK]` contra a precisão do OOS (se a taxa de `ML_PASS` que gera vitórias vai refletir de forma convergente o que vimos nos 73% de backtest de EUR/USD).
- **Cuidado com a Liquidez OTC:** Nos testes cegos, o proxy usado foi o volume de exchanges reais (Binance). Os finais de semana da IQ Option usam ativos OTC matemáticos. Monitorar ativamente as próximas 48h de log.
- **Passar para Conta Real:** Se os resultados na conta PRACTICE sob validação de probabilidade diária se confirmarem > 55% num range de 100 operações, considerar flipar `CONFIRM_REAL=YES` e `IQ_BALANCE_TYPE=REAL`.
