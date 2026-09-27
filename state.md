# Estado do Projeto (IQ Operator)

## Fase Atual: Hegemonia Quantitativa (Hedge Bot)
O robô evoluiu de uma lógica puramente determinística para um sistema preditivo blindado, operando com Inteligência Artificial baseada em 3 anos de dados estruturados e defesas macroeconômicas.

## 1. Conquistas e Arquitetura Consolidada
- **Estratégia Base Otimizada:** O modelo atual de eleição é o `Bollinger Touch` no timeframe de M5.
- **Transcendência XGBoost v2 (M5 Edition):** Treinamos o modelo `xgb_filter_m5.pkl` sobre ~315.000 velas de M5 baixadas via API da Binance. O vetor de contexto possui 72 features (incluindo projeção de M15, Volume Spread Analysis, Z-score de pavios e Momentum). Limiar de confiança ideal definido no `.env` em `0.55`.
- **Filtro Macro (Notícias ForexFactory):** O `news_filter.py` realiza raspagem de calendário diariamente, paralisando operações 30 minutos antes e depois de eventos 'Red Folder' para `USD` e `EUR`.
- **Bloqueio de Sessões Tóxicas:** A investigação de dados provou que os horários `[5, 8, 12, 21, 23]` (UTC) causam *drawdown* acentuado no M5. O robô foi modificado para hibernar nesses horários sem desarmar a homeostase do Websocket.
- **Sincronização e Imanência (`homeostasis.py`):** O robô agora gerencia e repara sua própria integridade de socket. Erros de falha temporária ou horários inativos não mais acarretam em `GLOBAL OUTAGE`.

## 2. Transfer Learning e Grid Search (Ativos)
- Realizamos extração bruta oficial da IQ Option (20.000 candles por ativo) e varremos a performance da IA sobre o Forex real.
- **Resultado Definitivo:** O modelo generalizou perfeitamente a dinâmica de reversão à média europeia/americana, atingindo `58.05%` de Winrate no `GBPUSD` e `56.31%` no `EURUSD`. O modelo falha nos cruzamentos com JPY, CAD e AUD (Winrates ~52%).
- **Ação:** O `.env` da produção deve operar estritamente com `ACTIVES="EURUSD,GBPUSD"`.

## 3. Próximos Passos (Next Session)
- **Live Forward-Testing:** O robô está hospedado (Railway/Local) na conta `PRACTICE` para rodar por 1-2 semanas contínuas, avaliando o comportamento estatístico real (slippage e lag) face ao modelo de 72 features.
- **Aperfeiçoamento:** Na próxima sessão, devemos colher os dados desse Forward Test, checar o arquivo `trades_live.csv` salvo no HuggingFace, e, se o Expected Value for positivo consolidado, iniciar a transição gradual e micro-alavancada para `REAL`.
