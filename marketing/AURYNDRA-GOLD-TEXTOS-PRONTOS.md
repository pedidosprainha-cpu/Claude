# Auryndra Gold — Textos prontos para colar

Complementa o arquivo `AURYNDRA-GOLD-PLANO-DE-VENDAS.md`. Os blocos em português e inglês estão na seção 4 daquele arquivo.

## Como aplicar na descrição (todos os idiomas)

Em cada idioma, **apague só os 4 primeiros parágrafos** da descrição atual:

1. a frase "Do nível à ordem. Da entrada à gestão.";
2. o parágrafo que começa com "Automatize entradas e saídas…";
3. o parágrafo que começa com "Nove configurações de estratégia…";
4. o parágrafo que começa com "Baixe a demonstração do Market…".

No lugar deles, cole o bloco novo do idioma. **Mantenha todo o resto como está**, a partir de "O que você controla".

Antes de publicar:
- se o preço não mudar, apague a linha do preço de lançamento;
- se o aluguel não for ativado, apague a linha do aluguel;
- apague os `[LINK]` que ainda não existirem.

---

## Español

```
AURYNDRA GOLD — EA de ruptura para el ORO (XAUUSD H1)

Sin martingala. Sin rejilla de espaciado fijo. Órdenes Buy Stop / Sell Stop en niveles identificados, con stop-loss, take-profit, break-even y trailing.

PRECIO DE LANZAMIENTO: 129 USD para las 10 primeras copias → después 199 USD → 279 USD → precio final 399 USD.
Alquiler disponible: 1 o 3 meses.

Por qué Auryndra Gold:
• 9 configuraciones de estrategia en un solo EA, con selección automática o manual
• Protección configurable del drawdown diario (pensada para prop firms)
• Filtros de noticias de EE. UU.: NFP, CPI y decisiones de tipos, con calendario integrado para el probador (2010–2027)
• Cierre opcional del viernes (órdenes pendientes y posiciones abiertas)
• Reserva inteligente de margen: el EA no coloca pendientes que la cuenta no pueda sostener
• Lote fijo o dinámico

Backtest de 6 años (2020–2026, OHLC de 1 minuto, calidad 98 %), sin optimización en esta campaña: PF 2,2 y más de 10 000 operaciones.
Los periodos negativos también se publican abajo, con todos los detalles.

Señal en vivo: [LINK]   |   Guía + archivos .set: [LINK DEL BLOG]   |   Vídeo: [LINK]

Descarga la demo gratuita y pruébala en el Probador de estrategias con el historial de tu bróker antes de comprar.
```

## Deutsch

```
AURYNDRA GOLD — Breakout-EA für GOLD (XAUUSD H1)

Kein Martingale. Kein Raster mit festen Abständen. Buy-Stop- / Sell-Stop-Orders auf identifizierten Kursniveaus, mit Stop-Loss, Take-Profit, Break-even und Trailing.

EINFÜHRUNGSPREIS: 129 USD für die ersten 10 Kopien → danach 199 USD → 279 USD → Endpreis 399 USD.
Miete verfügbar: 1 oder 3 Monate.

Warum Auryndra Gold:
• 9 Strategiekonfigurationen in einem EA, automatische oder manuelle Auswahl
• Konfigurierbarer Schutz vor täglichem Drawdown (geeignet für Prop-Firmen)
• US-Nachrichtenfilter: NFP, CPI und Zinsentscheidungen, mit integriertem Kalender für den Tester (2010–2027)
• Optionales Schließen am Freitag (Pending-Orders und offene Positionen)
• Intelligente Margin-Reservierung: Der EA platziert keine Pending-Orders, die das Konto nicht tragen kann
• Feste oder dynamische Lotgröße

6-Jahres-Backtest (2020–2026, 1-Minuten-OHLC, 98 % Qualität), ohne Optimierung in dieser Kampagne: PF 2,2 und über 10.000 Trades.
Verlustphasen sind unten vollständig veröffentlicht.

Live-Signal: [LINK]   |   Anleitung + .set-Dateien: [BLOG-LINK]   |   Video: [LINK]

Laden Sie die kostenlose Demo herunter und testen Sie sie vor dem Kauf im Strategietester mit der Historie Ihres Brokers.
```

---

## Post para o blog do MQL5: guia de instalação

Publique em **mql5.com → seu perfil → Publicações → Novo post** (blog), em PT e em EN. Depois, coloque o link
do post na descrição, no lugar de `[LINK DO BLOG]`. Anexe os arquivos `.set` do preset padrão e do `Extreme`
**depois de revisar o preset** (plano, item 3.1).

### Versão em português

```
Auryndra Gold — Guia de instalação e configuração

Produto: https://www.mql5.com/pt/market/product/204957

1. REQUISITOS
• MetaTrader 5, conta do tipo Hedge, denominada em USD
• Símbolo: XAUUSD (ouro). H1 é o timeframe de referência dos testes
• Confira com a sua corretora: tamanho do contrato, lote mínimo, spread, alavancagem e horário de negociação
• Recomendado: VPS, para o robô funcionar 24 horas por dia

2. INSTALAÇÃO
• Compre ou alugue no Market, ou baixe a demo para testar
• No MetaTrader 5, abra um gráfico XAUUSD H1 e arraste o Auryndra Gold para o gráfico
• Ative o "Algo Trading" na barra de ferramentas
• Carregue um dos arquivos .set anexados a este post: aba Parâmetros → Carregar

3. PRESETS
• Padrão: [DESCREVER O PRESET REVISADO: frequência, risco e drawdown esperado no backtest]
• Extreme (TradeFrequency=Extreme): mais operações e MAIS RISCO. É o preset usado na tabela de seis cenários da página do produto

4. PARÂMETROS PRINCIPAIS
• TradeFrequency e RunStrat1–RunStrat9: frequência e escolha das 9 configurações de estratégia
• AllowBuyTrades / AllowSellTrades: liga ou desliga compras e vendas
• Risk, StartLots, MaxAllowedDD, MaxRiskPerStrategy_: tamanho do lote e referências de exposição. Não são limites garantidos de perda
• AdjustLotsizeToVariableValues: desative se quiser exatamente o StartLots no modo de lote fixo
• MaxSpread: filtro de spread, em unidades de preço de 0,01
• FridayStopHour, FridayClosePending, FridayCloseOpen: comportamento na sexta-feira
• PropFirmMaxDailyDD: proteção de drawdown diário, útil em contas de prop firm
• EnableNFP_Filter, EnableCPI_Filter, EnableIR_Filter: filtros de notícias dos EUA
• ST1_MagicNumber: use um número diferente se rodar outro robô no mesmo símbolo

5. COMO REPRODUZIR O BACKTEST DA PÁGINA
• Strategy Tester → Auryndra Gold → XAUUSD → H1
• Modelagem: OHLC de 1 minuto (testes longos) ou Ticks reais
• Depósito: 200 ou 1.000 USD, alavancagem 1:100, moeda USD
• TradeFrequency=Extreme e os demais parâmetros no padrão da versão atual
• Os resultados podem variar de acordo com a corretora

6. SUPORTE
Envie mensagem privada pelo MQL5 ou comente na página do produto.

Aviso: backtests não são resultados de conta real. Resultados passados não garantem resultados futuros. Operar com alavancagem pode causar perda do capital.
```

### English version

```
Auryndra Gold — Installation and setup guide

Product: https://www.mql5.com/en/market/product/204957

1. REQUIREMENTS
• MetaTrader 5, Hedge account, denominated in USD
• Symbol: XAUUSD (gold). H1 is the reference timeframe for the tests
• Check your broker's contract size, minimum lot, spread, leverage and trading hours
• Recommended: a VPS, so the EA runs 24/5

2. INSTALLATION
• Buy or rent from the Market, or download the demo to test
• In MetaTrader 5, open an XAUUSD H1 chart and drag Auryndra Gold onto it
• Enable "Algo Trading" on the toolbar
• Load one of the .set files attached to this post: Inputs tab → Load

3. PRESETS
• Default: [DESCRIBE THE REVISED PRESET: frequency, risk and expected backtest drawdown]
• Extreme (TradeFrequency=Extreme): more trades and HIGHER RISK. This is the preset used in the six-scenario table on the product page

4. MAIN INPUTS
• TradeFrequency and RunStrat1–RunStrat9: activity and selection of the 9 strategy configurations
• AllowBuyTrades / AllowSellTrades: enable or disable each direction
• Risk, StartLots, MaxAllowedDD, MaxRiskPerStrategy_: sizing and exposure references. They are not guaranteed loss limits
• AdjustLotsizeToVariableValues: disable it to get exactly StartLots in fixed-lot mode
• MaxSpread: spread filter, in 0.01 price units
• FridayStopHour, FridayClosePending, FridayCloseOpen: Friday handling
• PropFirmMaxDailyDD: daily drawdown protection, useful for prop-firm accounts
• EnableNFP_Filter, EnableCPI_Filter, EnableIR_Filter: US news filters
• ST1_MagicNumber: use a different number if another EA trades the same symbol

5. HOW TO REPRODUCE THE PRODUCT-PAGE BACKTEST
• Strategy Tester → Auryndra Gold → XAUUSD → H1
• Modeling: 1-minute OHLC (long tests) or Real ticks
• Deposit: 200 or 1,000 USD, leverage 1:100, currency USD
• TradeFrequency=Extreme, all other inputs at the current version's defaults
• Results can differ between brokers

6. SUPPORT
Send a private message on MQL5 or comment on the product page.

Disclaimer: backtests are not live-account results. Past results do not guarantee future results. Leveraged trading can cause loss of capital.
```

---

## Canal do Telegram (ou canal no MQL5)

- **Nome:** Auryndra Gold — Resultados ao vivo
- **Descrição:**

```
Resultados semanais do Auryndra Gold, robô de rompimento para o ouro (XAUUSD) no MetaTrader 5.
Sinal ao vivo, atualizações de versão e suporte.
Produto: https://www.mql5.com/pt/market/product/204957
Resultados passados não garantem resultados futuros.
```

- **Modelo de post semanal:**

```
📊 Auryndra Gold — Semana [DD/MM a DD/MM]
Resultado da semana no sinal ao vivo: [+/-X%]
Operações: [N]  |  Drawdown máximo da semana: [X%]
Sinal completo: [LINK DO SINAL]
Inclusive nas semanas negativas: transparência total.
```

---

## Mensagem para o primeiro comprador (enviar por mensagem privada no MQL5)

```
Olá, [nome]! Obrigado por adquirir o Auryndra Gold.

Para começar:
1. Guia de instalação e arquivos .set: [LINK DO BLOG]
2. Recomendo começar com o preset padrão e risco baixo, numa conta demo ou com valor pequeno.
3. Se tiver qualquer dúvida sobre corretora, parâmetros ou instalação, me chame aqui. Respondo rápido.

Daqui a algumas semanas, se puder, deixe uma avaliação sincera na página do produto, seja ela qual for. Isso ajuda muito um vendedor novo.

Bons trades!
Gustavo
```

(Não ofereça nada em troca da avaliação. Isso viola as regras do MQL5.)
