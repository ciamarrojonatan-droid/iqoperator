# Original User Request

## 2026-09-24T22:51:53Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: small focused team

This is a single self-contained fix; keep it small and focused.

O bot sofre quedas constantes no deploy do Railway (reiniciado pelo Watchdog). Os logs revelam perda de conexão (`**error** get_candles need reconnect`, `TIMEOUT após 30s`) e congelamento no `get_betinfo`. Precisamos implementar uma "Homeostase Autonômica": um mecanismo resiliente de reconexão na biblioteca IQOption que recupere a sessão e evite que o Watchdog mate o processo durante quedas temporárias da corretora.

Working directory: c:/Users/WDAGUtilityAccount/Downloads/Nova pasta
Integrity mode: development

## Verification Resources (Logs de Erro)
```text
[err] ERROR **error** get_candles need reconnect
[err] WARNING get_candles AUDUSD-OTC: TIMEOUT após 30s em get_candles AUDUSD-OTC — pulando ciclo (1/3).
[err] ERROR **error** get_betinfo time out need reconnect
[err] ERROR WATCHDOG: sem progresso há 138s — reiniciando processo.
```

## Requirements

### R1. Mecanismo de Cura de Conexão (Reconnect Handling)
A equipe deve implementar um tratador de reconexão para lidar com os erros `need reconnect` do `get_candles` e `get_betinfo`. Quando a API da IQOption desconectar, o bot deve tentar um re-login/reconect suave com backoff exponencial, sem travar o thread principal infinitamente.

### R2. Sincronização com o Watchdog
A rotina de reconexão deve notificar o Watchdog interno de que o sistema está ativamente tentando se recuperar (estado de cura), impedindo que o Watchdog reinicie o processo abruptamente enquanto o bot aguarda o backoff da corretora.

### R3. Regras de Eficiência (Synaptic Orchestrator)
A equipe deve obrigatoriamente usar o ambiente de alta densidade semântica para todas as operações de leitura e testes:
- Não utilizar ferramentas padrão para ler arquivos inteiros.
- Utilizar a skill nativa detalhada em `synaptic_hypervisor/antigravity_integration/skills/synaptic-orchestrator/SKILL.md`.
- Executar testes e extrair código usando o daemon local (`python -m synaptic_hypervisor.sidecar.daemon`).

## Acceptance Criteria

### Homeostase de Conexão
- [ ] O sistema identifica falhas de socket/websocket da IQOption e aciona rotina de `reconnect()` ou `connect()`.
- [ ] O Watchdog não derruba a aplicação se ela estiver em loop controlado de reconexão (progress flag atualizada).
- [ ] O bot retoma o polling das 6 moedas assim que a conexão é restabelecida com sucesso.

## 2026-09-25T02:37:35Z

Projeto Híbrido de Transcendência: Integrar um modelo de Machine Learning (Classificação) como camada de inteligência (filtro preditivo) sobre os sinais das estratégias determinísticas atuais (`donchian_fade`, `bollinger_touch`). O objetivo é prever a probabilidade de um sinal ser falso/ruído.

Working directory: c:/Users/WDAGUtilityAccount/Downloads/Nova pasta

Integrity mode: development

## Requirements

### R1. Pipeline de Engenharia de Dados e Features
Carregar o histórico de preços (arquivos `.csv` ou via mock histórico do daemon se não houver `.csv` massivo) e extrair features temporais, técnicas (SMA, StdDev de múltiplos períodos) e a indicação de sinal das estratégias `donchian_fade` e `bollinger_touch`. Criar a variável alvo (Target = 1 se o preço reverteu com lucro na próxima hora, 0 se foi falso rompimento).

### R2. Modelagem Híbrida e Comparação
Criar um *Jupyter Notebook* (`transcendence_ml_analysis.ipynb`) estruturado contendo a Análise Exploratória (EDA). Treinar e comparar no mínimo um modelo Base (ex: Regressão Logística) e um Avançado (ex: Random Forest/XGBoost). A ordem de featurização deve ser estrita: dividir em treino/teste cronológico **antes** do fit dos scalers/encoders para evitar *lookahead bias*.

### R3. Análise em Markdown (ML Best Practices)
Cada bloco de código de avaliação no Notebook deve ser seguido de uma célula Markdown explicando os resultados matemáticos e o comportamento do modelo, de acordo com as regras restritas da skill `ml-best-practices`.

## Acceptance Criteria

### Integridade do Notebook e Dados
- [ ] O notebook roda de ponta a ponta sem erros de sintaxe ou de importação de biblioteca (verificável executando todas as células via motor Python).
- [ ] O *split* de validação do dataset é puramente cronológico (Time Series Split) e não aleatório (verificável via análise da função de split usada).

### Avaliação de Performance
- [ ] A última célula apresenta uma tabela Markdown final listando o *Precision*, *Recall* e *F1-Score* de todos os modelos avaliados.
- [ ] A avaliação matemática deve priorizar a métrica de *Precision* (minimização de Falsos Positivos) sobre *Accuracy* global.

## 2026-09-25T04:22:18Z

This is a single self-contained fix; keep it small and focused.
Integração de Produção: Acoplar o modelo XGBoost (treinado e calibrado com $\tau=0.62$) ao fluxo ao vivo do `bot.py`, atuando como um filtro preditivo para as estratégias determinísticas.

Working directory: c:/Users/WDAGUtilityAccount/Downloads/Nova pasta

Integrity mode: development

## Requirements

### R1. Extração de Pesos e Serialização
O time deve extrair o modelo XGBoost treinado no notebook `transcendence_ml_analysis.ipynb` (ou rodar um script leve equivalente para gerar o modelo) e serializar os pesos (junto com o StandardScaler) em um artefato estático (ex: `models/xgb_filter.pkl` ou `xgb_filter.json`).

### R2. Acoplamento em Tempo Real (`bot.py`)
No fluxo de `bot.py`, imediatamente após as estratégias determinísticas emitirem um sinal e antes de disparar a ordem (`api.buy_multi()`), o bot deve calcular o vetor de features do candle atual em tempo real e passá-lo pelo modelo de ML. A ordem só deve ser enviada se a probabilidade predita for $\ge 0.62$. Sinais barrados devem ser logados (ex: `[ML FILTER] False Breakout detectado, trade cancelado`).

### R3. Micro-DSL e Invariantes
A comunicação de design entre os agentes deve seguir o formato de Context Paging do Synaptic Orchestrator (`MUTATE[mod::fn]{delta} CHECK{inv}`).

## Acceptance Criteria

### Resiliência e Lógica
- [ ] O arquivo `requirements.txt` foi atualizado com as bibliotecas necessárias para inferência (ex: `scikit-learn`, `xgboost`).
- [ ] O `bot.py` inicializa normalmente e carrega o modelo em memória sem lentidão excessiva.
- [ ] Existe um teste automatizado ou script de validação (`check_ml_filter.py`) provando que a função de inferência processa um candle mockado e cospe a probabilidade correta sem quebrar a tipagem.

## 2026-09-29T02:35:44Z

# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full team

Construir uma arquitetura de pesquisa quantitativa (Backtest & Signal Engine) para Opções Binárias (IQ Option) focada em Regime de Mercado (Trend, Range, Expansion), Filtro de Payout dinâmico e Expectativa Matemática (EV/Wilson Lower Bound) ao invés de simples Winrate.

Working directory: `~/teamwork_projects/iq_regime_adaptive`
Integrity mode: development

## Requirements

### R1. Regime-Adaptive Feature Engine
O sistema deve classificar o ambiente de mercado atual (ex: Trend, Range, Expansion, Chaos) baseando-se em volatilidade, ADX e autocorrelação, e rotear o sinal para o setup estatisticamente adequado (ex: Mean Reversion para Range, Pullback para Trend). O estado 'Chaos' deve gerar a decisão explícita de 'NO TRADE'.

### R2. Expiry & Payout Conditional Pipeline
A avaliação de sinais deve obrigatoriamente cruzar a probabilidade condicional de vitória com o Payout atual. O motor deve calcular a probabilidade de Break-Even ($P_{BE}$) e o Expected Value (EV), executando o trade apenas se $EV > 0$ considerando o limite inferior de Wilson (Wilson Lower Bound).

### R3. Estabilidade Out-of-Sample (OOS)
A arquitetura deve separar rigidamente os dados em In-Sample (IS), Validation (VAL) e Out-of-Sample (OOS). O framework de backtest deve calcular a degradação de performance entre IS e OOS para avaliar a estabilidade de múltiplas hipóteses (H001-H008).

## Acceptance Criteria

### Verificação Quantitativa
- [ ] O backtester deve cuspir um relatório que inclua o N efetivo de trades, o EV médio normalizado e o Wilson Lower Bound da taxa de acerto.
- [ ] A degradação (diferença de EV entre IS e OOS) deve ser calculada automaticamente para as hipóteses processadas.
- [ ] O código não deve possuir dependências de martingale ou alocação assimétrica irracional (risco fixo/Kelly strict).

## 2026-09-29T02:40:39Z

[URGENTE - NOVA REGRA HARD DO USUÁRIO PARA TODA A EQUIPE TEAMWORK]
Vocês estão proibidos de usar `cat` ou `Get-Content` ou ferramentas de leitura completa de arquivos (`view_file` completo) que gastem muitos tokens.
Para economizar tokens, TODOS os agentes devem usar EXCLUSIVAMENTE o sidecar (daemon) do Hypervisor para auditar e extrair o código:
Execute no terminal: `python -m synaptic_hypervisor.sidecar.daemon --action extract_edges --file <arquivo>`
Essa é uma REGRA HARD. Repasse para todos os agentes da equipe imediatamente. Cancele leituras massivas em andamento.
