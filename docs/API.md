# API (v1)

Base: `http(s)://<servidor>/api/v1`. **Sem autenticação por padrão.** Com `FXI_REQUIRE_API_KEY=1`, envie o
cabeçalho `X-API-Key: <chave>` (no WebSocket, `?api_key=`).
Documentação interativa (OpenAPI/Swagger): `/docs`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | **Pública.** Status, provedores (latência/falhas/circuito), heartbeats das tarefas, banco, modelo |
| GET | `/instruments` | Especificações e instrumentos habilitados |
| GET | `/quotes` | Cotações Swissquote com bid/ask reais (fallback Yahoo/gold-api), fonte, `spread_source`, horário, idade, variação e `check` (divergência em pips vs. TrueFX/Yahoo) |
| GET | `/chart/{symbol}?tf=M5\|M15\|H1\|H4\|D1&bars=` | Candles (metais ajustados ao spot) |
| GET | `/calendar?hours=72` | Eventos econômicos |
| POST | `/analyze` | **ANALISAR MERCADO AGORA**: análise completa (ver estrutura abaixo) |
| GET | `/analysis/latest` · `/analyses` · `/analyses/{id}` | Última análise / histórico / detalhe |
| GET | `/instrument/{symbol}` | Detalhes por instrumento da última análise (resumos MTF, níveis, zonas, regime, fundamentos) |
| GET | `/signals?status=` · `/signals/{id}` | Sinais emitidos com status forward (ativo, tp1, tp2, stop, breakeven, encerrado_horizonte) e estatísticas |
| GET | `/alerts?since_id=` | Alertas (novo sinal, eventos, volatilidade, dados, status de sinais, demo, modelo) |
| GET | `/events` | Registro de eventos do motor |
| GET | `/model` · POST `/model/train` | Status/calibração do modelo · retreino em segundo plano |
| GET | `/report` | Último relatório de backtest/walk-forward (JSON) |
| GET / PUT | `/settings` | Configurações (PUT aceita patch parcial; risco por trade limitado a 2%) |
| GET | `/paper/positions` · POST `/paper/execute {signal_id}` | Conta demo |
| POST | `/broker/oanda/execute {signal_id, confirm}` | Execução real (desativada por padrão) |
| GET/POST/DELETE | `/keys` | Gestão de chaves de API |
| WS | `/ws` | Mensagens `hello`, `quotes` (a cada 10 s), `alert`, `analysis` |

## Estrutura da resposta de `/analyze`

```jsonc
{
  "id": "…", "created_at": "…", "status": "SINAL | SEM_OPORTUNIDADE", "headline": "…",
  "signal": {                       // null quando não há oportunidade qualificada
    "instrument": "EURUSD", "direction": "BUY", "setup": "PULLBACK", "execution_type": "Entrada imediata a mercado",
    "reference_quote": {"bid": 1.1, "ask": 1.10012, "spread_pips": 1.2, "spread_source": "estimated", "time": "…", "age_s": 12},
    "entry": {"price": 1.10012, "side": "ASK"},
    "stop_loss": {"price": 1.0975, "pips": 26.2, "basis": "…"},
    "take_profit": [{"label": "TP1 (50%)", "price": …, "rr": 1.6}, {"label": "TP2 …", "price": …, "rr": 2.8}],
    "risk_reward": {"rr_tp1": 1.6, "rr_net_tp1": 1.52, "cost_r": 0.05},
    "probability": {"model_p": 0.41, "calibrated_p": 0.34, "ci90": [0.31, 0.36], "n_oos_bin": 890, "event": "TP1 antes do Stop"},
    "expected_value_r": 0.07, "confidence": {"level": "média", "limitations": ["…"]},
    "score": 63.2, "score_components": {…},
    "justification": {"technical": ["…"], "fundamental": ["…"], "quantitative": ["…"]},
    "invalidation": ["…"], "validity": {"valid_until": "…", "minutes": 240},
    "scenarios": {"principal": "…", "alternativo": "…", "riscos": ["…"]},
    "gates": [{"gate": "spread", "passed": true, "detail": "…"}, …],
    "risk": {"approved": true, "sizing": {"lots": 0.19, "risk_amount": 49.6, "margin": …}}
  },
  "no_signal_reasons": ["modelo_validado: bloqueou 3 candidato(s)", …],
  "observations": [ …candidatos que não passaram em todos os portões… ],
  "market": [ …resumo por instrumento: tendências por TF, alinhamento, regime, score fundamental, eventos… ],
  "model": {…}, "fundamentals": {…}, "correlations": […], "data": {…}, "risk_state": {…},
  "timings": {"quotes_ms": …, "data_ms": …, "analysis_ms": …}, "elapsed_ms": …, "disclaimer": "…"
}
```
