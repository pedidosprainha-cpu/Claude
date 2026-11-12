# Instalação, configuração e uso

## 1. Backend (motor + API + painel web)

### Opção A: Python local (Linux, macOS ou Windows/WSL)

```bash
git clone <este repositório> fxintel && cd fxintel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m fxintel train          # baixa ~2,8 anos de histórico, roda o walk-forward e grava modelo + relatório (3–6 min)
python -m fxintel serve          # http://0.0.0.0:8000
```

Na primeira execução do servidor, uma **chave de API administrativa** é criada em `var/admin_api_key.txt`.
Abra `http://localhost:8000`, informe a chave e use o painel.

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
docker compose exec fxintel cat /data/admin_api_key.txt
docker compose exec fxintel python -m fxintel train
```

### Opção C: systemd

Veja `deploy/fxintel.service` (venv em `/opt/fxintel/.venv`, dados em `/var/lib/fxintel`).

## 2. Variáveis de ambiente

| Variável | Uso |
|---|---|
| `FXI_API_KEY` | define uma chave de API fixa (senão, uma é gerada) |
| `FXI_DATA_DIR` | dados, cache, modelos, logs e banco (padrão `./var`) |
| `FXI_CONFIG_DIR` | diretório de `settings.json` e `central_banks.json` (padrão `./config`) |
| `FXI_OANDA_TOKEN`, `FXI_OANDA_ACCOUNT`, `FXI_OANDA_ENV` | ativam cotações bid/ask reais da OANDA (`practice` ou `live`) |
| `FXI_LIVE_TRADING=1` | habilita o envio real de ordens via OANDA (cada ordem exige `confirm=true`) |
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

1. Instale `releases/FXIntel-1.0.0.apk` no aparelho (Android 8.0+). É preciso permitir "instalar apps de fontes
   desconhecidas".
2. Abra o app → **Ajustes** → informe a URL do servidor e a chave de API → **Testar conexão** → **Salvar**.
   - Mesma rede Wi-Fi: `http://IP-DO-COMPUTADOR:8000`. Libere a porta 8000 no firewall.
   - Pela internet: publique o backend com HTTPS (Docker + Caddy) e use `https://seu-dominio`.
3. Permita notificações para receber alertas.
4. Na aba **Painel**, toque em **ANALISAR MERCADO AGORA**.

Para compilar o APK, veja [ANDROID.md](ANDROID.md).

## 5. Rotina recomendada

1. `python -m fxintel train` semanalmente (o servidor retreina sozinho a cada 24h se `FXI_AUTO_RETRAIN` estiver ativo).
2. Atualize `central_banks.json` após as decisões dos bancos centrais.
3. Acompanhe a aba **Modelo & Backtest** (validação OOS) e o **Histórico** (resultado forward dos sinais).
4. Antes de qualquer uso com dinheiro real, opere por várias semanas na **conta demo** e compare o resultado com o backtest.
