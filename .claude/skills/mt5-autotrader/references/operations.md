# Operação: instalação, arquivos e solução de problemas

## Índice
1. Instalação no Windows
2. Manter rodando 24h
3. Arquivos do robô
4. Diagnóstico rápido
5. Códigos de retorno da corretora
6. Problemas comuns
7. O que foi e o que não foi testado

## 1. Instalação no Windows

Pré-requisitos na máquina do MT5:

1. **MetaTrader 5** instalado, aberto e logado na conta (senha mestre, não a de investidor).
2. **Algo Trading** ligado: botão na barra de ferramentas do MT5, precisa ficar verde. Em
   Ferramentas → Opções → Expert Advisors, "Permitir algo trading" marcado.
3. **Python 3.9+ de 64 bits.** Se faltar: `winget install Python.Python.3.12`.
4. Dependências: `python -m pip install -r scripts/requirements.txt`.

Depois: `python scripts/fxbot.py doctor`. Ele diz o que falta, item por item.

Se houver mais de um terminal MT5 instalado, aponte o certo:
`python scripts/fxbot.py set terminal_path "C:\\Program Files\\MetaTrader 5\\terminal64.exe"`.

O robô se anexa ao terminal já logado; nenhuma senha é pedida ou gravada. Para um VPS sem
login salvo existe a alternativa por variáveis de ambiente `MT5_LOGIN`, `MT5_PASSWORD` e
`MT5_SERVER` — use apenas se o usuário pedir e nunca escreva a senha em arquivo.

## 2. Manter rodando 24h

- `start` lança o robô em segundo plano, desvinculado do terminal do Claude.
- `autostart --install` cria no Agendador de Tarefas do Windows a tarefa
  `MT5Autotrader-Watchdog`, que a cada 5 minutos religa o robô se ele deveria estar rodando e
  não está (queda, reinício, novo login). `autostart --remove` desfaz.
- `stop` marca a intenção como "parado"; o watchdog respeita e não religa.
- A tarefa roda na sessão do usuário: é preciso estar logado no Windows. Em VPS, configure
  login automático.
- Desative suspensão e hibernação da máquina.
- Mercado: domingo 17h a sexta 17h (Nova York). Fora disso o robô fica vivo, sem operar.

Se o PC ou o robô caírem com posições abertas, elas continuam protegidas: o stop-loss fica no
servidor da corretora. O que para é a gestão (saída por tempo), retomada quando o robô volta.

## 3. Arquivos do robô

Em `~/.mt5-autotrader/` (ou `FXBOT_HOME`, ou `--home`):

| Arquivo | Conteúdo |
|---|---|
| `config.json` | Só o que difere do padrão |
| `state.json` | Memória de risco, posições do robô, última barra processada |
| `heartbeat.json` | Último ciclo: modo, conta, risco, erros |
| `journal/decisions-AAAA-MM.jsonl` | Cada sinal avaliado e por que virou ou não ordem |
| `journal/trades.jsonl` | Cada operação fechada, com resultado em dinheiro e em R |
| `logs/fxbot.log` | Log rotativo do processo |
| `news_cache.json` | Calendário econômico da semana |
| `desired`, `STOP`, `commands.jsonl` | Controle entre a linha de comando e o processo |

`status` em `decisions`: `opened` (ordem executada), `observed` (operaria, mas está em modo
observação), `skipped` (barrado por uma regra; o motivo está em `detail`), `rejected` (a
corretora recusou). Um sinal que persiste por horas é registrado uma vez por motivo, não a
cada hora.

## 4. Diagnóstico rápido

| Sintoma | Onde olhar |
|---|---|
| `running: false` | `logs/fxbot.log` (últimas linhas), depois `doctor` |
| `mode: observe` em demo | `mode_reason`: Algo Trading desligado ou login sem permissão |
| Nenhuma operação há dias | `recent_decisions` e `scan`: sem esticão ≥ 1,0 não há sinal; conta pequena aparece como "minimum lot would risk..." |
| `heartbeat.status: error` | `heartbeat.error`; o robô tenta reconectar sozinho com espera crescente |
| `unresolved` com símbolos importantes | Nome diferente na corretora → `symbol_map` |
| `news.usable: false` | Calendário fora do ar; segue operando sem o filtro (`fail_mode`) |

## 5. Códigos de retorno da corretora

| Código | Significado | O que fazer |
|---|---|---|
| 10004, 10020, 10021 | Requote / preço mudou / sem cotação | O robô repete sozinho; se persistir, mercado fechado ou ilíquido |
| 10016 | Stops inválidos | Distância mínima da corretora; verifique `trade_stops_level` do símbolo |
| 10017 | Negociação desabilitada | Símbolo só para consulta nesta conta |
| 10018 | Mercado fechado | Normal fora do pregão |
| 10019 | Margem insuficiente | Conta pequena ou alavancagem baixa |
| 10027 | Algo Trading desligado no terminal | Religar o botão no MT5 |
| 10026 | Autotrading bloqueado pelo servidor | Falar com a corretora |
| 10030 | Tipo de preenchimento não suportado | O robô tenta os outros modos sozinho |
| 10031 | Sem conexão com o servidor | Internet / login da corretora |
| 10044, 10045 | Só fechamento permitido / regra FIFO | Restrição da conta |

## 6. Problemas comuns

**`MetaTrader5` não importa.** Só existe para Windows. Em Windows, se o erro citar numpy,
reinstale: `python -m pip install --upgrade MetaTrader5 numpy`.

**"could not attach to the MT5 terminal".** Terminal fechado, ou Python e terminal rodando com
privilégios diferentes (um como administrador, outro não). Abra os dois do mesmo jeito.

**"no trading account is logged in".** Faça login no MT5 (Arquivo → Login na conta de
negociação).

**Histórico insuficiente ("still loading").** Abra uma vez o gráfico H1 dos símbolos no MT5
para forçar o download e rode o `doctor` de novo. O robô precisa de 600 barras, usa até 4.000.

**Duas instâncias.** O `run` recusa iniciar se outra instância deu sinal de vida nos últimos
90 segundos.

**Posição do robô sem registro** (por exemplo `state.json` perdido): no ciclo seguinte ele a
adota, reconstruindo os dados a partir da posição e do comentário (`fxb:MR:85`).

**Conta netting.** Só existe uma posição por símbolo; o robô não entra onde houver posição
manual. Prefira conta hedging.

**Relógio.** Sessões e notícias usam o relógio UTC do computador; mantenha a sincronização
automática do Windows ligada.

## 7. O que foi e o que não foi testado

Testado, em Linux, com corretora simulada que imita a API `MetaTrader5` (mesmos nomes de
função, constantes e formatos de retorno): ciclo completo de análise, dimensionamento, envio de
ordem, stop e alvo, saída por tempo, diário, reinício com estado salvo, adoção de posições,
perda de conexão, ordem rejeitada, modo observação em conta real, comandos de operador,
processo em segundo plano e watchdog. O filtro de notícias foi conferido com o calendário real.
São 37 testes automáticos (`python -m unittest discover -s tests`) mais `selftest`.

**Não testado:** a conexão com um terminal MT5 de verdade e o agendamento no Windows
(`autostart`), porque o ambiente de desenvolvimento não tinha Windows nem MT5. Por isso, na
primeira execução numa máquina real, vá devagar: `doctor`, depois `scan`, depois um `cycle`
manual em conta demo conferindo a ordem e o stop no terminal, e só então `start`. Qualquer
diferença de comportamento da API real deve ser corrigida em `scripts/fxbot/broker.py`, que é
o único arquivo que fala com o MT5.
