# Instalação, configuração e uso

## 0. Só o aplicativo (recomendado): sem servidor e sem chave

1. Instale `releases/FXIntel-1.1.0.apk` no Android 8.0+ (permita "instalar apps de fontes desconhecidas").
2. Abra o app e toque em **ANALISAR MERCADO AGORA**.

O motor roda no aparelho e busca os dados direto das fontes públicas (Swissquote, TrueFX, Yahoo, gold-api,
ForexFactory). Não há cadastro, chave de API nem servidor. A primeira análise baixa ~2 anos de histórico H1
(alguns MB, comprimidos); as seguintes só atualizam os últimos dias.

## 1. Servidor (opcional: painel web, backtest, retreino do modelo)

### Opção A: Python local (Linux, macOS ou Windows/WSL)

```bash
git clone <este repositório> fxintel && cd fxintel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m fxintel train          # baixa ~2,8 anos de histórico, roda o walk-forward e grava modelo + relatório (3–6 min)
python -m fxintel serve          # http://0.0.0.0:8000
```

Abra `http://localhost:8000` e use o painel. **Não há chave de API por padrão.** Se for expor o servidor à
internet, inicie-o com `FXI_REQUIRE_API_KEY=1` (a chave é criada em `var/admin_api_key.txt`) e use HTTPS.

Comandos úteis:

| Comando | Função |
|---|---|
| `python -m fxintel analyze` | executa "ANALISAR MERCADO AGORA" no terminal (`--json` para a saída completa) |
| `python -m fxintel quotes` | cotações atuais com fonte, idade e spread |
| `python -m fxintel train` | retreina o modelo e regenera `reports/` |
| `python -m pytest` | testes automatizados (offline) |
| `python scripts/benchmark.py` | latência e confiabilidade da API (servidor ativo) |

### Opção B: Docker

```bash
cd deploy
docker compose up -d --build                 # API + painel em :8000
docker compose --profile https up -d          # + Caddy com HTTPS automático (edite deploy/Caddyfile)
docker compose exec fxintel python -m fxintel train
```

### Opção C: systemd

Veja `deploy/fxintel.service` (venv em `/opt/fxintel/.venv`, dados em `/var/lib/fxintel`).

## 2. Variáveis de ambiente

| Variável | Uso |
|---|---|
| `FXI_REQUIRE_API_KEY=1` | passa a exigir chave de API no servidor (padrão: sem chave) |
| `FXI_API_KEY` | chave fixa quando `FXI_REQUIRE_API_KEY=1` (senão, uma é gerada) |
| `FXI_DATA_DIR` | dados, cache, modelos, logs e banco (padrão `./var`) |
| `FXI_CONFIG_DIR` | diretório de `settings.json` e `central_banks.json` (padrão `./config`) |
| `FXI_OANDA_*`, `FXI_LIVE_TRADING` | **opcionais e desnecessários**: conector de corretora para quem quiser integrar no futuro (as cotações bid/ask já vêm da Swissquote sem chave) |
| `FXI_AUTO_RETRAIN=0` | desativa o retreino automático diário |
| `FXI_CORS` | origens permitidas (padrão `*`) |
| `FXI_EQUITY`, `FXI_UNIVERSE` | atalhos de configuração |

## 3. Configuração

- `config/settings.json` é criado ao salvar pelo painel ou pelo app. O modelo de referência é
  `config/settings.example.json` (universo, conta, risco, portões, slippage, multiplicadores de spread por sessão,
  pesos da pontuação, alertas, servidor).
- `spread_overrides_pips`: substitui o spread típico por instrumento (use os spreads da sua corretora).
- `server.auto_analyze_min`: análise automática periódica (0 = desligada).
- `gates.require_model`: com `true` (recomendado), nenhum sinal é emitido sem modelo validado. Com `false`
  ("modo pesquisa"), os demais portões continuam valendo, inclusive o de EV, que usa a probabilidade calibrada.
- **`config/central_banks.json`: atualize após cada decisão de política monetária.** O motor alerta quando a
  tabela tem mais de 45 dias.

## 4. Aplicativo Android

- **Modo autônomo (padrão):** ver a seção 0. Os instrumentos, o capital e os limites de risco são ajustados em **Ajustes**.
- **Modo servidor (opcional):** em **Ajustes → Fonte de dados**, desligue "No aparelho" e informe a URL do seu
  servidor (ex.: `http://192.168.0.10:8000` na mesma rede Wi-Fi). Chave só se o servidor exigir.
- Permita notificações para receber alertas (sinais acompanhados, eventos críticos, volatilidade).

Para compilar o APK, veja [ANDROID.md](ANDROID.md).

## 5. Rotina recomendada

1. `python -m fxintel train` semanalmente (o servidor retreina sozinho a cada 24h se `FXI_AUTO_RETRAIN` estiver ativo).
2. Atualize `central_banks.json` após as decisões dos bancos centrais.
3. Acompanhe a aba **Modelo & Backtest** (validação OOS) e o **Histórico** (resultado forward dos sinais).
4. Antes de qualquer uso com dinheiro real, opere por várias semanas na **conta demo** e compare o resultado com o backtest.
