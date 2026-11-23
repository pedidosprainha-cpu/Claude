# Auryndra Gold — Diagnóstico da página e plano de vendas

Página analisada: https://www.mql5.com/pt/market/product/204957 (lida em 23/11/2026)

## 1. Como a página está hoje

| Item | Situação |
|---|---|
| Produto | Expert Advisor MT5, XAUUSD, referência H1, conta Hedge em USD |
| Publicado | 30/10/2026 (há ~24 dias), versão 1.6 |
| Preço | US$ 399, **sem aluguel**, 5 ativações |
| Downloads da demo | **8** em ~24 dias |
| Avaliações / comentários | 0 / 0 |
| Sinal ao vivo vinculado | **Nenhum** |
| Vídeo | **Nenhum** |
| Imagens | Logo + 4 screenshots |
| Perfil do vendedor | Primeiro e único produto |
| Idiomas da descrição | PT, EN, ES, DE (RU e ZH mostram o texto em inglês) |

### Concorrentes diretos que aparecem na mesma página

Robôs de rompimento no ouro (Buy Stop/Sell Stop, sem martingale), que é exatamente o seu nicho:

| Produto | Preço | Avaliações | Sinal ao vivo |
|---|---|---|---|
| Gold Beaver | US$ 449 | 5,0 (14) | Sim, 2 sinais |
| AiX Gold MT5 | US$ 779 | 5,0 (2) | — |
| Dynamic Liquidity Intelligence | US$ 599 | 4,44 (9) | — |
| Vex Gold EA | US$ 249 | 5,0 (12) | Sim, 8 meses ao vivo |
| AugumAegis (novo) | US$ 99 | 0 | — |
| Gold Edge V1 (novo) | US$ 79 | 5,0 (1) | — |

**Conclusão:** um comprador que olha o Auryndra por US$ 399 tem ao lado, quase pelo mesmo preço, robôs do
mesmo tipo com sinal ao vivo e avaliações. Sem nenhuma prova ao vivo, a escolha racional dele é o outro.

## 2. Por que não vendeu (em ordem de peso)

1. **Quase ninguém está vendo o produto.** Foram 8 downloads de demo em 24 dias. Com esse tráfego, zero
   vendas é o resultado esperado, mesmo com uma página perfeita. O problema número 1 é tráfego, não o texto.
2. **Não há nenhuma prova ao vivo.** No MQL5, comprador de robô de ouro na faixa de US$ 300 ou mais quer ver
   um sinal em conta real. Hoje existe só backtest.
3. **O próprio teste mostra o período recente fraco.** Isso é o mais sério:
   - de 01/07 a 01/11/2026: PF 1,12 a 1,39, com drawdown de **40% a 55%**;
   - o teste de outubro, com ticks reais, terminou **no prejuízo**;
   - quem baixa a demo testa justamente os meses mais recentes, e vê isso.

   Divulgação não resolve esse ponto. Ele precisa ser tratado no robô ou nos presets (ver item 3.1).
4. **O drawdown do teste principal é alto para o público geral.** São 37% com US$ 200 e 20% com US$ 1.000,
   usando o modo `Extreme`. A maioria dos compradores procura um preset padrão com DD abaixo de 15–20%.
5. **O texto é honesto, mas não vende.** A transparência é um diferencial real, mantenha. O problema é que:
   - as primeiras linhas, que aparecem no card da vitrine, são genéricas
     ("Do nível à ordem. Da entrada à gestão.");
   - os pontos fortes estão escondidos no fim: proteção de DD diário para prop firm, filtros de NFP/CPI/juros
     e fechamento de sexta;
   - o resto é tão cheio de ressalvas técnicas que parece um laudo, não uma página de produto.
6. **US$ 399 sem aluguel** é uma barreira alta para o primeiro produto de um vendedor sem histórico.
7. **Falta vídeo.** Quase todos os mais vendidos têm vídeo no YouTube.

## 3. Plano de ação

### 3.1 Antes de divulgar (esta semana)

- [ ] **Revisar o desempenho recente.** No Strategy Tester, rode 01/07/2026 até hoje com cada `TradeFrequency`
  que não seja `Extreme`, e com risco menor.
  - Se alguma configuração mais conservadora segurar melhor o período recente, com DD abaixo de ~20%, ela vira o
    **preset padrão**. O `Extreme` passa a ser apenas uma opção agressiva.
  - Se todas as configurações estiverem fracas no período recente, a prioridade é o robô, não o marketing.
    Continue mostrando isso com honestidade, como você já faz.
- [ ] **Fazer o padrão do robô bater com o que a página mostra.** Hoje, para reproduzir a tabela, o comprador
  precisa mudar parâmetros na mão. Coloque os valores divulgados como padrão, ou ofereça um `.set` pronto
  (por exemplo, num post do blog do MQL5).
- [ ] **Mudar o preço para um preço de lançamento escalonado**, que é o modelo usado por SomaOil, SomaForex e Gold Beaver:
  - US$ 129 para as 10 primeiras cópias;
  - depois US$ 199, US$ 279 e US$ 399.
  - Use esse modelo **só se for cumprir**. O comprador do MQL5 acompanha, e escassez falsa queima o vendedor.
- [ ] **Ativar o aluguel**, por exemplo 1 mês por US$ 49 e 3 meses por US$ 99. O aluguel tira o medo de quem não
  quer pagar o valor cheio num vendedor novo, e quem aluga também pode deixar avaliação.
- [ ] **Reescrever o começo da descrição** usando o texto da seção 4. Mantenha toda a parte técnica e as
  ressalvas, só que mais abaixo.

### 3.2 Construir prova (semanas 1 a 8)

- [ ] **Abrir um sinal em conta real** e vinculá-lo ao produto:
  - conta Hedge em USD, numa corretora com spread baixo no ouro;
  - de US$ 200 a 500 já serve;
  - rodando numa VPS, com o mesmo preset padrão divulgado.

  O sinal pode ser gratuito, o objetivo é ter prova pública. Depois de 4 a 8 semanas ele vira o seu principal
  argumento de venda.
- [ ] **Gravar um vídeo de 3 a 5 minutos para o YouTube** e colocar o link na página. Roteiro na seção 5.
- [ ] **Publicar um post no blog do MQL5** com o guia de instalação, a explicação dos presets e os `.set` para
  baixar. O Four Edge usa esse formato, e um post de blog pode trazer o link do produto.
- [ ] **Criar um canal público no MQL5** (MQL5 Channels) e postar o resultado semanal do sinal.
- [ ] **Dar suporte rápido aos primeiros compradores** e pedir uma avaliação honesta depois de algumas semanas
  de uso. Não ofereça nada em troca da avaliação e nunca crie avaliações falsas: as duas coisas violam as regras
  do MQL5.

### 3.3 Trazer tráfego de fora (contínuo)

- **YouTube.** É o canal que mais converte para robô. Publique um vídeo do backtest, um de "como instalar" e
  atualizações mensais do sinal ao vivo. Faça em português e, se possível, em inglês.
- **Telegram ou WhatsApp (canal de transmissão).** Poste o resultado semanal do sinal, sempre com o link do produto.
- **Instagram, TikTok e Reels.** Grave clipes curtos de operações no ouro com o painel do robô.
- **Artigo no MQL5.** A MetaQuotes paga por artigo aprovado, e o seu perfil de autor leva aos seus produtos.
  O seu robô tem temas técnicos originais, como a reserva de margem para ordens pendentes e o calendário de
  notícias embutido para o testador, e isso dá um artigo forte.
- **Comunidades brasileiras de trading.** Só onde a divulgação é permitida. Leia as regras de cada grupo, porque
  spam derruba a sua reputação. O fórum do MQL5 e o Forex Factory também proíbem propaganda comercial fora das
  áreas próprias.

### 3.4 Expectativa realista

- O mais comum é a primeira venda vir **depois** do preço de lançamento e de algumas semanas de sinal ao vivo.
- A primeira avaliação positiva costuma destravar as vendas seguintes.
- Meça toda semana: downloads da demo, visitas ao sinal e vendas. Se a demo for baixada e ninguém comprar, o
  problema está no resultado que o comprador vê no testador. Se a demo não for baixada, o problema é tráfego ou
  vitrine.

## 4. Novo começo da descrição (pronto para colar)

> Só afirmei o que já está na sua página. Confira cada linha antes de publicar, ajuste os números depois de
> revisar o preset padrão (item 3.1) e inclua a linha do sinal ao vivo só quando ele existir.

### Português

```
AURYNDRA GOLD — Robô de rompimento para o OURO (XAUUSD H1)

Sem martingale. Sem grade de espaçamento fixo. Ordens Buy Stop / Sell Stop em níveis identificados, com stop-loss, take-profit, break-even e trailing.

PREÇO DE LANÇAMENTO: US$ 129 para as 10 primeiras cópias → depois US$ 199 → US$ 279 → preço final US$ 399.
Aluguel disponível: 1 mês ou 3 meses.

Por que o Auryndra Gold:
• 9 configurações de estratégia em um único robô, com seleção automática ou manual
• Proteção de drawdown diário configurável (pensada para prop firms)
• Filtros de notícias dos EUA: NFP, CPI e decisões de juros, com calendário embutido para o testador (2010–2027)
• Fechamento opcional na sexta-feira (pendentes e posições abertas)
• Reserva de margem inteligente: o robô não abre pendentes que a conta não comporta
• Lote fixo ou dinâmico

Backtest de 6 anos (2020–2026, OHLC M1, qualidade 98%), sem otimização na campanha: PF 2,2, mais de 10 mil operações.
Os períodos negativos também estão publicados abaixo, com todos os detalhes.

Sinal ao vivo: [LINK]   |   Guia + arquivos .set: [LINK DO BLOG]   |   Vídeo: [LINK]

Baixe a demo grátis e teste no Strategy Tester com o histórico da sua corretora antes de comprar.
```

### English

```
AURYNDRA GOLD — Breakout EA for GOLD (XAUUSD H1)

No martingale. No fixed-spacing grid. Buy Stop / Sell Stop orders at identified price levels, with stop-loss, take-profit, break-even and trailing.

LAUNCH PRICE: USD 129 for the first 10 copies → then USD 199 → USD 279 → final price USD 399.
Rental available: 1 or 3 months.

Why Auryndra Gold:
• 9 strategy configurations in one EA, automatic or manual selection
• Configurable daily drawdown protection (prop-firm friendly)
• US news filters: NFP, CPI and rate decisions, with a built-in calendar for the tester (2010–2027)
• Optional Friday close (pending orders and open positions)
• Smart margin reservation: the EA does not place pending orders the account cannot carry
• Fixed or dynamic lot sizing

6-year backtest (2020–2026, 1-minute OHLC, 98% quality), no optimization in this campaign: PF 2.2, 10,000+ trades.
Losing periods are published below in full detail.

Live signal: [LINK]   |   Guide + .set files: [BLOG LINK]   |   Video: [LINK]

Download the free demo and test it in the Strategy Tester on your broker's history before buying.
```

Abaixo desse bloco entra a sua descrição atual, com a tabela dos seis cenários, os períodos negativos, os
parâmetros e os limites. Ela continua valendo como o "lado técnico" para quem quer se aprofundar.

## 5. Roteiro de vídeo para o YouTube (3 a 5 minutos)

1. **0:00–0:15. Gancho:** "Robô de rompimento para o ouro, sem martingale. Vou mostrar 6 anos de teste,
   incluindo os meses em que ele perdeu."
2. **0:15–1:00. Como funciona:** níveis no gráfico, ordens Buy Stop e Sell Stop, stop-loss e trailing. Mostre o
   robô no gráfico.
3. **1:00–2:30. Backtest ao vivo na tela:** rode o Strategy Tester e mostre a curva, o drawdown e o relatório.
   Mostre também o período negativo. Essa honestidade é o seu diferencial.
4. **2:30–3:30. Proteções:** DD diário para prop firm, filtros de NFP/CPI/juros e fechamento de sexta.
5. **3:30–4:00. Instalação e preset padrão.**
6. **Fechamento:** "Baixe a demo grátis no MQL5. Link na descrição. Preço de lançamento para as 10 primeiras cópias."

## 6. Post para Telegram, Instagram ou WhatsApp (modelo)

```
🟡 Auryndra Gold — robô de rompimento para o OURO (XAUUSD) no MetaTrader 5

✅ Sem martingale, sem grade fixa
✅ Stop-loss, take-profit, break-even e trailing configuráveis
✅ Filtro de notícias (NFP, CPI, juros) e proteção de DD diário para prop firm
📊 6 anos de backtest publicados, incluindo os períodos de perda

🎯 Preço de lançamento: US$ 129 para as 10 primeiras cópias
🧪 Demo grátis para testar no Strategy Tester

👉 https://www.mql5.com/pt/market/product/204957

⚠️ Resultados passados não garantem resultados futuros. Operar com alavancagem pode causar perda de capital.
```
