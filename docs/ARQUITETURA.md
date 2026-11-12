# Arquitetura

## Visão geral

```
                ┌──────────────────────── Provedores de dados ────────────────────────┐
                │ Yahoo Finance (FX, PAXG, SI=F, DXY, ^TNX, ^VIX, ES=F, CL=F)          │
                │ gold-api.com (XAU/XAG spot)   OANDA v20 (bid/ask reais, opcional)     │
                │ ForexFactory/FairEconomy (calendário)   config/central_banks.json     │
                └───────────────┬──────────────────────────────────────────────────────┘
                                │ retry + backoff, rate limiting, circuit breaker, cache em disco
                        ┌───────▼────────┐
                        │   DataHub      │ cotações com failover · barras M5/M15/H1 (+H4/D1 derivadas)
                        └───────┬────────┘ reparo de rolagem · ajuste ao spot · spread estimado por sessão
   ┌────────────────────────────┼─────────────────────────────────────────────┐
   │                     Motor analítico (fxintel)                             │
   │  technical/  indicadores · estrutura BOS/CHoCH · SMC (FVG/OB/liquidez)    │
   │              níveis S/R · oferta/demanda · padrões · MTF                  │
   │  fundamental/ intermercados · força relativa · bancos centrais · eventos  │
   │  quant/      regimes · anomalias · correlação · features · rotulagem      │
   │              triple-barrier · modelo calibrado · estatística              │
   │  signals/    candidatos (PULLBACK, BREAKOUT, SWEEP, TREND) · SL/TP        │
   │  engine.py   portões de validação · pontuação multifatorial · sinal       │
   │  risk/       dimensionamento · limites de perda/exposição/correlação      │
   │  execution/  PaperBroker (demo) · OandaBroker (desativado por padrão)     │
   │  backtest/   simulador de portfólio · walk-forward · métricas · relatório │
   └────────────────────────────┬─────────────────────────────────────────────┘
                                │
                   ┌────────────▼─────────────┐      SQLite (WAL): análises, sinais,
                   │ Backend FastAPI          │◄────► eventos, alertas, posições demo,
                   │ REST + WebSocket         │       chaves de API (hash SHA-256)
                   │ tarefas em segundo plano │
                   └──────┬────────────┬──────┘
                          │            │
                 ┌────────▼───┐  ┌─────▼──────────────┐
                 │ Painel web │  │ App Android         │
                 │ (dashboard)│  │ Kotlin + Compose    │
                 └────────────┘  └────────────────────┘
```

## Módulos

| Pacote | Responsabilidade |
|---|---|
| `fxintel/data` | Provedores (`yahoo`, `goldapi`, `oanda`, `calendar`), `DataHub` (cache, failover, qualidade), modelos (`Quote`, sessões, utilidades de barras). |
| `fxintel/technical` | Indicadores vetorizados (EMA, RSI, MACD, ATR, ADX/DI, Bollinger, estocástico, eficiência de Kaufman, VWAP com volume real), estrutura de mercado causal, FVG/Order Blocks/deslocamento, S/R por agrupamento de swings, oferta/demanda, níveis de sessão, padrões de candle, divergências, análise multi-timeframe com alinhamento sem *look-ahead*. |
| `fxintel/fundamental` | Features intermercado point-in-time (DXY, Treasuries 3m/5a/10a, curva, VIX, S&P, WTI), medidor de força relativa das moedas, tabela de política monetária (carry e viés), risco de eventos e score fundamentalista explicável. |
| `fxintel/quant` | Regimes (regra explicável + mistura gaussiana), anomalias (z-score robusto), correlações de Spearman, features normalizadas pela direção, rotulagem triple-barrier com custos, modelo probabilístico (logística/gradient boosting), métricas de calibração, estatística (Wilson, bootstrap, PSR/DSR). |
| `fxintel/signals` | Geração de candidatos causais e cálculo de Stop/Alvos em pools de liquidez. |
| `fxintel/risk` | Conversão de moedas, dimensionamento por risco, `RiskManager` (perdas diária/semanal/sessão, posições, exposição por moeda, correlação, margem). |
| `fxintel/execution` | `BrokerAdapter`, `PaperBroker` (conta demo local) e `OandaBroker` (API v20, exige habilitação explícita). |
| `fxintel/backtest` | Simulador de portfólio orientado a eventos, walk-forward com purging/embargo, métricas e relatório Markdown/PNG/JSON. |
| `fxintel/engine.py` | Orquestração do comando *ANALISAR MERCADO AGORA*. |
| `fxintel/monitor.py` | Acompanhamento forward dos sinais emitidos e geração de alertas. |
| `backend/app/main.py` | API HTTP/WebSocket, autenticação, tarefas de fundo, painel web. |
| `android/` | Aplicativo Android nativo (Kotlin, Jetpack Compose, OkHttp, WorkManager). |

## Fluxo do comando "ANALISAR MERCADO AGORA"

1. **Cotações** de todo o universo (uma chamada multi-símbolo; OANDA quando configurado).
2. **Barras** M5/M15/H1 em paralelo (cache em disco com atualização incremental); H4/D1 derivadas de H1.
3. **Intermercados** e **calendário** (cache de 60 min, com uso de cópia anterior em caso de falha).
4. Para cada instrumento (em paralelo): quadro técnico (cacheado por candle H1 fechado), resumos D1/H4/H1/M15/M5,
   regime, anomalias, qualidade de dados, níveis e zonas, score fundamentalista, risco de eventos e candidatos dos
   últimos 2 candles H1 fechados.
5. Para cada candidato: preço de execução atual (ASK/BID), custos, features → probabilidade → frequência
   calibrada fora da amostra com IC 90% → valor esperado → **portões** → **pontuação**.
6. O melhor candidato que passa em todos os portões é submetido ao `RiskManager` (dimensionamento incluído).
7. Persistência e resposta. Sem candidato elegível, a resposta é **"Nenhuma oportunidade suficientemente
   qualificada"**, com os motivos agregados e as melhores observações (marcadas como não recomendadas).

Tempo medido (16 instrumentos, este ambiente): ~20 s na primeira análise de cada hora (cálculo completo dos
quadros) e ~2,4 s nas seguintes (cache por candle). O servidor pré-aquece o cache a cada hora.

## Sinal × Ordem

O motor gera **sinais**. Uma **ordem** só existe quando um `BrokerAdapter` a executa:

- `PaperBroker`: conta demo local, acionada pelo usuário (`POST /api/v1/paper/execute`).
- `OandaBroker`: envio real somente com `FXI_LIVE_TRADING=1`, credenciais e `confirm=true` na requisição.
  Ordens a mercado com `FOK`, `stopLossOnFill` e `takeProfitOnFill`.

## Confiabilidade, redundância e recuperação

- **Retry exponencial** e **circuit breaker** por provedor (abre por 60 s após 5 falhas seguidas).
- **Limitação de taxa** no cliente Yahoo (espaçamento e concorrência máxima) e alternância de host (query1/query2).
- **Failover de cotações:** OANDA → Yahoo/gold-api → proxy Yahoo (com spread ampliado e marcação de fonte).
- **Cache em disco** das barras: reinícios não exigem baixar todo o histórico; dados antigos são descartados.
- **Marcação de qualidade:** cada cotação carrega fonte, horário, idade e se o spread é real ou estimado;
  os portões bloqueiam dados atrasados, congelados ou divergentes.
- **Persistência SQLite em modo WAL**; o estado (sinais, posições demo, alertas) é recuperado no reinício.
- **Docker** com `restart: unless-stopped` e *healthcheck*; unidade `systemd` com `Restart=always`.
- **Monitoramento:** `/api/v1/health` (provedores, heartbeats das tarefas, banco, modelo) e alertas de falha de dados.

## Segurança

- Autenticação por chave de API (`X-API-Key`), armazenada como hash SHA-256; múltiplas chaves revogáveis.
- Atraso em respostas 401 (mitiga força bruta). Segredos apenas por variáveis de ambiente.
- HTTPS por proxy reverso (Caddy com Let's Encrypt incluído em `deploy/`).
- O app Android aceita HTTP apenas para uso em rede local; em redes públicas use HTTPS.
- Validação de entrada nas configurações (lista de chaves editáveis, limites de risco, instrumentos válidos).
- Logs estruturados (JSON) em `var/logs/fxintel.jsonl` e registro de eventos do motor no banco.
