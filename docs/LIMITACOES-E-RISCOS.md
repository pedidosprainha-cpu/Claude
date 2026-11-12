# Limitações metodológicas e riscos

## Resultado da validação (resumo honesto)

- Os setups técnicos (PULLBACK, BREAKOUT, SWEEP, TREND), avaliados em ~13 mil ocorrências em 16 instrumentos,
  têm **expectativa líquida negativa** (≈ −0,19R por trade) e **expectativa bruta praticamente nula** (≈ −0,04R).
  Em outras palavras, eles não têm vantagem direcional detectável, e os custos de transação determinam o resultado.
- O modelo probabilístico primário (logística) **não supera a taxa-base** fora da amostra no período completo
  (BSS −0,006; AUC 0,553). Suas probabilidades acima de 0,4 são superconfiantes (a frequência observada fica
  em ~0,33). Por isso, a probabilidade exibida é sempre a **frequência OOS da faixa**, e não o valor bruto do modelo.
- No holdout de 2026 houve sinais positivos (BSS +0,011, AUC 0,569; seleção superior à aleatória), mas com
  poucos trades, média não significativa e resultado oposto ao do período de desenvolvimento. Isso não basta
  para validar o modelo.
- **Consequência:** com a configuração padrão, o motor **não emite sinais** e informa que não há oportunidade
  qualificada. Esse comportamento é o exigido pela especificação ("não gerar recomendações quando não houver
  evidência estatística suficiente").

Detalhes e reprodução: `reports/RELATORIO-BACKTEST-*.md` e `python -m fxintel train`.

## Limitações de dados

1. **Bid/ask ao vivo reais, histórico não:** as cotações ao vivo vêm da Swissquote com bid/ask reais (sem
   chave), mas não existe bid/ask histórico gratuito, então o backtest usa spreads estimados. O perfil "premium"
   da Swissquote mostra spreads um pouco maiores que a tabela do backtest (ex.: EURUSD 1,5 vs. 1,0 pip), o que
   torna o backtest levemente otimista em custo. Os spreads reais dependem da sua corretora.
2. **Metais via proxy:** ouro via PAXG-USD (token cripto; prêmio/desconto vs. spot ≈ ±0,5%; liquidez de
   exchanges cripto) e prata via futuro SI=F (base, rolagens e intercalação de contratos, reparadas por
   heurística). Os níveis são ajustados ao spot atual, mas a microestrutura do proxy pode diferir do spot.
3. **Fontes públicas sem SLA:** Swissquote, TrueFX, Yahoo, gold-api e ForexFactory são endpoints públicos que
   podem mudar ou limitar requisições (o calendário responde 429 de forma intermitente). Há retry, cache e
   fallback. Se o calendário estiver indisponível, o portão de eventos **bloqueia** os sinais (conservador).
4. **Histórico curto:** ~2,8 anos de H1 dão ~1,8 ano de teste OOS, com poder estatístico limitado para
   detectar vantagens pequenas (≤ 0,05R).
5. **Calendário e juros sem histórico point-in-time:** não entram no modelo nem no backtest. O bloqueio por
   eventos atua apenas ao vivo. A tabela de juros é manual e pode estar desatualizada; as fontes consultadas
   divergiam para o RBA.
6. **Geopolítica:** não há ingestão de notícias. O risco aparece apenas indiretamente, pelos preços (VIX,
   ouro, JPY/CHF).
7. **Fins de semana e feriados:** gaps de abertura não são negociáveis ao preço do stop. O simulador executa no
   preço de abertura (pior caso), mas ao vivo o slippage pode ser maior.

## Limitações de modelagem

- Os componentes M15/M5 (tempo de entrada) e o score fundamentalista **não foram validados** no backtest (falta
  histórico M15/M5 suficiente e dados point-in-time). Eles afetam apenas a pontuação e as justificativas, nunca a
  elegibilidade estatística.
- Swap/rolagem overnight não modelado (posições de até 36h).
- Viés de seleção: foram avaliadas 3 versões de desenho × 2 modelos. O Deflated Sharpe Ratio e o holdout
  mitigam, mas não eliminam, esse viés.
- O regime estatístico (GMM) é descritivo e não foi otimizado.
- A estimativa de EV depende de payoffs médios do treino (k e L), que podem mudar com o regime.

## Limitações de engenharia e testes

- O **app Android não foi executado em dispositivo/emulador** neste ambiente (sem virtualização). Foi compilado,
  assinado, testado no parsing das respostas reais da API e renderizado na JVM (Paparazzi).
- Nenhuma fonte exige chave de API. O conector OANDA permanece no código apenas como exemplo de integração
  futura com corretora, desativado e desnecessário (não testado contra o servidor real).
- O app embute o modelo treinado no servidor; no aparelho não há retreino (exige anos de dados e CPU).
  Recompile o app após `python -m fxintel train` para atualizar o modelo.
- O modo autônomo do app não possui conta demo; o acompanhamento forward dos sinais funciona normalmente.
- A simulação em conta demonstrativa (paper trading) está implementada, mas **não houve período de operação
  demo** para medir o desempenho forward. Ele precisa ser acumulado em uso.

## Riscos para o usuário

- **Nenhuma metodologia garante rentabilidade.** Resultados simulados não são desempenho comprovado.
- Forex e metais alavancados podem gerar perdas superiores ao capital investido, conforme a corretora.
- Desativar `gates.require_model` ("modo pesquisa") permite sinais **sem** evidência estatística validada. Use
  apenas para estudo ou em conta demo.
- Um sinal **não é uma ordem**. Confirme o preço, o spread e as condições reais na plataforma da corretora antes de
  executar.
- Mantenha a chave de API em segredo e exponha o backend somente via HTTPS.
