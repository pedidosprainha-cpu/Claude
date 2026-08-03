# Análise Forex Intraday — 03/08/2026, 03:15 UTC

## ⚠️ Aviso obrigatório sobre o acesso ao terminal MT5

**Não foi possível acessar o terminal MetaTrader 5.** O acesso era obrigatório no pedido, então
registro exatamente o que foi verificado, para que não haja ambiguidade:

| Verificação | Resultado |
|---|---|
| Binário do terminal (`terminal64.exe` / MetaTrader) no sistema | não existe |
| Pacote Python `MetaTrader5` | não instalado e **indisponível** (`No matching distribution found`) |
| Wine / camada de compatibilidade Windows | não instalado |
| Credenciais de corretora ou bridge/API MT5 em variáveis de ambiente | nenhuma |

Motivo de fundo: a API `MetaTrader5` do Python é **exclusiva para Windows** e este ambiente é um
contêiner Linux efêmero, sem terminal instalado e sem conta de corretora vinculada. Não há caminho
técnico para abrir o terminal aqui.

**O que foi usado no lugar:** dados de mercado spot ao vivo (OHLC 5m/15m/1h/1d) de 20 paridades,
capturados às 03:07–03:15 UTC. As leituras de preço, estrutura e volatilidade são reais e atuais.
As diferenças relevantes em relação ao MT5: não há dados de **volume de ticks**, **spread da sua
corretora**, **profundidade de mercado (DOM)** nem **swap**. Confirme os níveis no seu terminal
antes de executar — o preço da sua corretora terá pequeno desvio em relação ao spot.

---

## 1. O evento que domina a sessão

Às **00:15–00:45 UTC** houve um movimento violento de compra de JPY. Não é ruído técnico:

- O Japão **confirmou intervenção cambial coordenada com o Tesouro dos EUA** — a primeira ação
  conjunta desde 2011.
- A ministra das Finanças, Satsuki Katayama, declarou hoje (03/08) que o Japão comprou ienes "em
  coordenação com o Departamento do Tesouro dos EUA" e **sinalizou disposição para novas ações**.
- USDJPY marcou 155,20 — o iene mais forte em cerca de três meses.

Contexto de preço: USDJPY caiu de **163,90 (29/07) para 155,215 hoje** — cerca de **870 pips em três
sessões**. Este é o terceiro episódio de intervenção da série (30/07, 31/07, 03/08).

### Força relativa das moedas (% vs. cesta)

| Moeda | No dia | Últimos 30 min |
|---|---:|---:|
| **JPY** | **+2,302** | **−0,056** |
| EUR | −0,253 | +0,000 |
| USD | −0,318 | +0,024 |
| GBP | −0,342 | +0,000 |
| AUD | −0,441 | +0,012 |
| NZD | −0,556 | −0,006 |
| CAD | −0,932 | +0,024 |
| CHF | −0,998 | +0,026 |

O JPY domina o dia com folga. Note a inversão na janela curta: o iene já é a moeda **mais fraca**
dos últimos 30 minutos — é o repique corretivo pós-intervenção, não uma reversão de tendência.

---

## 2. Varredura das 20 paridades

Rodei um scorer de *qualidade de continuação* (`fx_continuation.py`) sobre toda a cesta: alinhamento
multi-timeframe, ADX, profundidade do pullback, impulso de retomada, sobre-extensão vs. ATR, regime
de volatilidade e espaço estrutural até o alvo.

**Resultado que precisa ser dito com clareza: nenhuma das 20 paridades apresenta um impulso de
continuação já em curso neste momento.** Todas as 20 têm `vol_ratio < 1,0` (volatilidade
comprimindo) e nenhuma tem impulso de retomada positivo nas últimas 6 velas de 5m. Às 03:15 UTC a
sessão de Tóquio está em consolidação pós-evento e Londres só abre às 07:00 UTC.

Os líderes do score fora do complexo JPY são inoperáveis na prática:

| Par | Score | Problema |
|---|---:|---|
| EURCHF | 47,8 | apenas **4,8 pips** até a resistência; ATR 1h de 12,4 pips |
| AUDNZD | 45,2 | fita morta — velas de 15m com 5–9 pips de amplitude |
| EURCAD | 45,0 | 11,8 pips de espaço; ADX 15m de 18,6 |
| GBPCHF | 43,3 | 4,0 pips de espaço |

Não há trade nesses. Forçar entrada aí é exatamente a "exposição desnecessária" que você quer evitar.

**A oportunidade real está no complexo JPY**, onde o evento concentrou o fluxo e a volatilidade.

---

## 3. Seleção do veículo dentro do complexo JPY

| Par | Spike (pips) | Recuperado | % retração | Integridade de fundos ascendentes | ATR 1h |
|---|---:|---:|---:|---:|---:|
| **USDJPY** | 264 | **+132** | **50,1%** | **0,86** | 73,5 |
| EURJPY | 275 | +111 | 40,2% | 0,86 | 77,9 |
| GBPJPY | 332 | +130 | 39,0% | 0,86 | 92,5 |
| CADJPY | 182 | +72 | 39,6% | 0,86 | 50,0 |
| AUDJPY | 178 | +66 | 37,1% | 0,71 | 50,5 |
| NZDJPY | 144 | +51 | 35,7% | 0,71 | 40,6 |
| CHFJPY | 291 | +83 | 28,4% | 0,71 | 79,3 |

**USDJPY é o líder do complexo** — maior retração, melhor estrutura, e é o par onde a intervenção
foi executada, portanto onde o fluxo oficial e a liquidez estão concentrados. É o veículo correto:
opera-se o líder, não os satélites.

---

## 4. Por que VENDIDO, e não comprado

O repique intraday é de alta, o que sugeriria compra. Testei essa hipótese contra o episódio anterior
e ela não se sustenta:

**Base histórica — episódio de 30/07:** spike de 504 pips; o repique topou em **45,5% de retração**,
levando **9h35min** para chegar lá.

**Hoje:** spike de 267 pips; o repique **já atingiu 53,0% de retração em apenas 2h22min**.

Ou seja, a correção de hoje **já superou a extensão máxima do episódio anterior, em um quarto do
tempo**. A retração está madura, não incipiente.

Confirmações adicionais:

1. **Momentum morrendo.** Progresso líquido da perna de alta em velas de 15m: primeiras 4 velas
   **+22,8 pips**, últimas 4 velas **+1,9 pips**.
2. **Teto testado três vezes e rejeitado.** 156,631 (02:00) → 156,556 (02:15) → 156,646 (03:10, com
   pavio superior de 10 pips e fechamento em 156,542). Duas horas travado abaixo de 156,65.
3. **Confluência exata com o fib de 50%** do spike: 156,551. O spot (156,535) está colado nele.
4. **Tendência macro intacta:** ADX 1h em 60,2; EMAs 8/20/50 alinhadas para baixo em 15m e 1h;
   queda de 870 pips em três sessões.
5. **O fluxo oficial trabalha a favor.** Comprar USDJPY aqui é operar contra o Banco do Japão *e* o
   Tesouro dos EUA, que declararam hoje estar prontos para intervir novamente. Vendido, esse risco
   de cauda passa a ser um vento a favor.

O ponto 5 é o que decide o trade. O setup técnico de compra é legítimo, mas carrega um risco de gap
anunciado publicamente — uma nova tranche de intervenção move 200–300 pips em minutos e atravessa
qualquer stop. Isso é incompatível com o mandato de exposição mínima.

---

## 5. O TRADE

### 🔻 VENDER USDJPY a mercado

| Parâmetro | Nível | Distância |
|---|---:|---:|
| **Entrada (a mercado)** | **156,53** | — |
| **Stop** | **156,72** | **19 pips** |
| Alvo 1 (parcial 50%) | 156,02 | 51 pips |
| **Alvo 2 (take principal)** | **155,60** | **93 pips** |
| Alvo 3 (runner opcional) | 155,22 | 131 pips |

**Risco/retorno:** 2,7R no Alvo 1 · **4,9R no Alvo 2** · 6,9R no Alvo 3.

### Por que a entrada a mercado é a entrada otimizada aqui

Você está entrando **no topo de um range de duas horas**, encostado na resistência de 156,65 e no
fib de 50%. Isso significa que o stop estruturalmente correto fica a apenas **19 pips**. Esperar o
rompimento do piso do range (156,21) daria uma entrada 30 pips pior *e* exigiria um stop mais largo
— pior nos dois lados. Este é o ponto de risco mínimo do setup.

### Gestão

- Mover o stop para o zero a zero quando romper **156,21** (piso da consolidação) — a partir daí o
  trade fica sem risco.
- Realizar 50% no Alvo 1 (156,02) e deixar o restante correr para 155,60.
- **Janela:** a resolução deve vir até a abertura de Londres (07:00 UTC). Se às 07:00 o preço ainda
  estiver preso entre 156,20 e 156,65, o trade perdeu a premissa de continuação imediata — encerre
  no mercado e não carregue a posição para a sessão europeia.

### Invalidação

Fechamento de vela de 15m **acima de 156,65**. Isso abre o caminho para o fib de 61,8% (156,87) e
depois 75% (157,20), e a tese de retração madura morre.

---

## 6. Riscos que você precisa pesar antes de executar

1. **O repique pode estender.** Em 30/07 o repique correu 9h35min antes de topar. Hoje ele está com
   2h22min. A leitura de "maduro" vem da % de retração e da perda de momentum, não do relógio — mas
   é uma inferência, não uma certeza. É exatamente o que o stop de 19 pips protege.
2. **Stop apertado em ativo de ATR alto.** 19 pips contra um ATR de 73,5 pips na hora é agressivo por
   construção. Ele está corretamente posicionado acima da estrutura, mas a probabilidade de ser
   tocado por um pavio é real. Alternativa conservadora: stop em **156,87** (acima do fib de 61,8%),
   34 pips, o que ainda entrega 2,7R no Alvo 2 — com metade do tamanho de posição.
3. **Liquidez de Tóquio.** Às 03:15 UTC os spreads são mais largos e a fita é mais fina. Use ordem a
   mercado com atenção ao slippage e confirme o spread no seu terminal.
4. **Risco de nova intervenção — a favor da posição.** Uma nova tranche empurraria o USDJPY
   violentamente para baixo, acelerando o trade. É o único cenário de cauda que joga a seu favor
   aqui, e foi determinante na escolha da direção.
5. **Dados sem volume/DOM.** Sem o MT5 não há volume de ticks nem profundidade para confirmar a
   rejeição em 156,65. A rejeição está evidenciada pelo preço (três toques, pavios superiores), mas
   não pôde ser confirmada por fluxo.

---

### Resumo em uma linha

**Vender USDJPY a 156,53, stop 156,72, take principal 155,60 (4,9R)** — retração de 50% já madura
contra uma tendência de 870 pips, com Banco do Japão e Tesouro dos EUA empurrando na mesma direção
da posição.

---

## Fontes

- [Japan confirms joint yen intervention with U.S., signals readiness for more — CNBC](https://www.cnbc.com/2026/08/03/yen-intervention-us-japan-trump-bessent-katayama.html)
- [Japan confirms joint yen intervention with U.S. — The Japan Times](https://www.japantimes.co.jp/business/2026/08/03/markets/japan-us-joint-yen-intervention/)
- [Yen climbs to 155 per dollar as traders on alert for further intervention — Nikkei Asia](https://asia.nikkei.com/business/markets/currencies/yen-climbs-to-155-per-dollar-as-traders-on-alert-for-further-intervention)
- [Yen weakens after intervention-led surge ahead of BOJ policy decision — CNBC](https://www.cnbc.com/amp/2026/07/31/yen-weakens-after-intervention-led-surge-ahead-of-boj-policy-decision.html)
- [Breaking: Japanese Yen surges on suspected intervention — FXStreet](https://www.fxstreet.com/news/breaking-japanese-yen-surges-on-suspected-intervention-usd-jpy-plunges-below-16100-202607301350)

*Análise gerada em 03/08/2026 03:15 UTC. Níveis válidos para esta sessão. Não é recomendação de
investimento.*
