---
name: analisar
description: Roda o motor fxengine (análise gráfica, quantitativa e fundamentalista de Forex e metais no preço spot ao vivo) e entrega a melhor entrada a mercado para execução imediata. Use quando o usuário pedir "analisar", "analise agora", "melhor entrada", "qual trade agora", "scan", ou citar um ativo para análise imediata.
---

# /analisar — melhor entrada a mercado agora

Argumentos opcionais (repasse ao motor): `$ARGUMENTS`
Exemplos: `-a metais`, `-a EURUSD,XAUUSD --detalhe`, `--saldo 25000 --risco 0.5`.

## Passos

1. Na raiz do repositório, rode a varredura ao vivo (leva ~15 s):

   ```bash
   mkdir -p reports && python3 -m fxengine scan --json reports/ultimo.json $ARGUMENTS
   ```

   Se faltar dependência: `pip install -r requirements.txt`.

2. Leia a saída do terminal e o `reports/ultimo.json` (campos `best`, `top_candidate`,
   `events_48h`, `headlines`, `data_status`).

3. Camada qualitativa (sua revisão, não substitui o motor):
   - Leia as manchetes e procure notícia de última hora sobre o ativo escolhido que o
     modelo quantitativo não capta (surpresa de banco central, intervenção, choque
     geopolítico). Se houver algo material contra o trade, diga explicitamente.
   - Confira eventos de alto impacto dentro do horizonte do trade (até o TP2).
   - Verifique `data_status`: se cotação ao vivo ou alguma fonte falhou, avise.

4. Responda em português, curto e direto:
   - **Decisão**: EXECUTAR ou NÃO EXECUTAR agora.
   - Ativo, lado, preço de entrada (bid/ask e horário da cotação), stop, TP1, TP2,
     regra de saída (stop móvel após +1R, encerrar em 48 h), lote para o saldo/risco usados,
     probabilidade de lucro e expectativa do modelo histórico calibrado, e nota.
   - Seja honesto sobre a validação: para entradas a mercado, nem os melhores sinais do modelo
     tiveram vantagem comprovada depois do spread (expectativa perto de zero; ver
     `research/RESULTADOS_SINAL.json`). Recomende risco pequeno.
   - 3–5 razões principais e 2–3 riscos; a regra de invalidação.
   - Se o motor não recomendou entrada: diga por quê (gates) e mostre o melhor
     candidato e o que precisaria mudar.

5. Se o usuário citar **um único ativo** ("analise o EURUSD", "e o ouro?"), rode a análise
   completa dele (≈5 s) em vez da varredura:

   ```bash
   python3 -m fxengine ativo -a EURUSD
   ```

   Apresente decisão, plano, leitura por timeframe, níveis-chave mais próximos, amplitude
   do dia (ADR usada), fundamentos e agenda das duas moedas. Com `--json -` sai o JSON.

6. Se o usuário pedir rompimentos/breakouts, rode também
   `python3 -m fxengine rompimentos --min-nota B` e apresente os acionáveis (✔): ativo,
   status, nível rompido, plano e pontos de atenção.

7. Se o usuário perguntar sobre explosões de preço, volatilidade ou "qual vai se mexer", rode
   `python3 -m fxengine explosoes` e apresente os ativos em alerta (⚡), a probabilidade, o
   movimento típico, a direção provável ("se explodir: alta/baixa X%", * = alta confiança) e
   os motivos. Deixe claro que a direção é um viés pequeno (acerto ≈ 56%, 58% em alta
   confiança) que não deu lucro comprovado como entrada a mercado.

8. Regras: use somente números da saída do motor (nunca invente preço); cite o horário
   da cotação; inclua o aviso de que é análise automatizada, não recomendação de investimento.
