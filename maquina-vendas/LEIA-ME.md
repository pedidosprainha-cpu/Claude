# Máquina de Vendas para Afiliados

Uma máquina que vende como afiliado (Hotmart, Kiwify, Eduzz) com tráfego pago
no Meta Ads (Facebook e Instagram) e chama você só quando precisa de uma decisão.

**Etapa atual: 1 de 4 (simulação).** Tudo funciona, mas com anúncios e vendas
simulados. Nenhum centavo de verdade é gasto.

---

## O que a máquina faz sozinha

| Tarefa | Como |
|---|---|
| Escolhe o que vender | Dá uma nota de 0 a 100 para cada produto (comissão, temperatura, preço, reembolso, se cabe no seu orçamento) e testa os melhores primeiro |
| Escreve os anúncios | Com o Claude (se houver chave da API da Anthropic) ou com modelos prontos |
| Evita bloqueio da conta | Pente-fino de política do Meta antes de qualquer publicação: barra "Você está acima do peso?", "renda garantida", "ganhe R$ X", "antes e depois" etc. |
| Cria as campanhas | Uma por anúncio, com R$ 10/dia de teste e código de rastreio no link de afiliado |
| Sabe de onde veio cada venda | Lê os avisos de venda das plataformas e liga cada venda à campanha certa |
| Corta o prejuízo | Pausa o anúncio que gastou o valor de uma comissão sem vender, o que tem CTR abaixo de 0,7% e o que devolve menos de R$ 0,80 por R$ 1 |
| Abandona produto ruim | Reprova o produto que não se paga depois de 2,5 comissões (ou 7 dias de teto) e passa para o próximo |
| Escala o que dá lucro | +20% de verba por dia na campanha com ROAS acima de 1,5; tira verba das piores para dar às melhores |
| Acha quem está perto de comprar | Cada ação na página de captura soma pontos na hora; acima de 60 o lead é **quente** |
| Avisa você | Resumo diário, vendas, alertas urgentes e pedidos de decisão (no app e, se quiser, no Telegram) |

## Quando ela chama você

Com a autonomia **automática com limites** (a que você escolheu):

1. **Aprovar anúncio novo:** você vê a prévia como vai aparecer no Instagram e toca em Aprovar ou Rejeitar.
2. **Liberar mais verba:** quando uma campanha dá lucro e quer crescer além do teto.

O resto ela faz sozinha. Dá para mudar a autonomia no app (aba **Mais**).

## Travas de segurança

- **Teto diário** (começa em R$ 30): a soma dos orçamentos ativos nunca passa dele. Pelo app você só consegue **reduzir**; para aumentar, só aprovando um pedido da máquina.
- **Teto absoluto** (R$ 100): nem uma aprovação pelo app passa disso. Só muda editando `TETO_ABSOLUTO_BRL` no servidor.
- **Botão "Pausar tudo"** na tela inicial: para todas as campanhas na hora.
- **Gasto acima do teto no dia:** se acontecer, pausa tudo até o dia seguinte e avisa você.
- **Diário de bordo:** tudo o que a máquina faz fica registrado, com data, hora e motivo.

> O Meta pode gastar até 75% a mais que o orçamento diário em alguns dias. Por isso, na
> etapa 2, você também vai definir um **limite de gastos da conta** no Gerenciador de Anúncios,
> igual ao teto absoluto. É uma segunda trava, fora da máquina.

## A conta honesta do orçamento

Com R$ 30/dia e produtos que pagam uns R$ 100 de comissão, cada produto leva de 5 a 10
dias para ser julgado. Na simulação de 60 dias, rodada em 6 cenários com sorte diferente
(aprovando os pedidos de aumento de teto, até R$ 100/dia), a máquina terminou entre
**−R$ 260 e +R$ 3.970**. Em 4 dos 6 cenários deu lucro.
É assim que tráfego pago funciona: o começo costuma dar prejuízo, até achar uma oferta que
se paga. A máquina acelera a busca e corta o prejuízo rápido, mas **não garante lucro**.

---

## Como ver funcionando (no computador)

Precisa do Python 3.10 ou mais novo.

```bash
cd maquina-vendas
pip install -r requirements.txt
uvicorn maquina.api:app --host 0.0.0.0 --port 8000
```

O token do painel aparece no terminal e fica salvo em `dados/painel_token.txt`.
Abra `http://localhost:8000`, digite o token e pronto. Na simulação, cada hora passa em
5 segundos; na aba **Mais** dá para avançar 1 ou 7 dias de uma vez.

Para rodar os testes: `python -m pytest`

## Como instalar no Android

1. Coloque o servidor na internet (veja abaixo) e abra o endereço no **Chrome** do celular.
2. Toque nos três pontinhos e em **Instalar app** (ou **Adicionar à tela inicial**).
3. O ícone da máquina aparece junto com os outros apps e abre em tela cheia.

Para receber avisos com o app fechado, configure o Telegram (abaixo). O app também mostra
notificações enquanto está aberto em segundo plano (aba **Mais**, "Ativar notificações").

## Como colocar na internet

O motor precisa ficar ligado 24 horas, então ele roda num servidor, não no celular.
Qualquer serviço que rode Docker com disco permanente serve (Railway, Render, Fly.io, ou
uma VPS de R$ 25 a R$ 50 por mês).

```bash
docker build -t maquina-vendas .
docker run -d -p 8000:8000 -v maquina-dados:/dados --env-file .env maquina-vendas
```

Copie `.env.example` para `.env` e preencha. **Use HTTPS** (domínio próprio): o Meta exige
para as páginas de captura, e o Android exige para instalar o app.

## Avisos no Telegram (opcional, recomendado)

1. No Telegram, fale com o **@BotFather**, mande `/newbot` e copie o token.
2. Mande qualquer mensagem para o seu bot novo.
3. Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` e copie o número em `"chat":{"id":...}`.
4. Preencha `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env` e reinicie o servidor.

## Anúncios escritos pelo Claude (opcional)

Preencha `ANTHROPIC_API_KEY` no `.env`. Cada rodada de 3 anúncios custa poucos centavos de
dólar. Sem a chave, a máquina usa modelos prontos (que também passam no pente-fino).
Se a IA recusar um pedido por segurança, a API tenta de novo com outro modelo automaticamente.

---

## Próximas etapas

**Etapa 2: ligar nas contas reais, com teto baixo.** O que você vai precisar providenciar:

- [ ] Conta no **Meta Business** verificada, com conta de anúncios, cartão e uma página no Facebook/Instagram
- [ ] **Pixel** do Meta e domínio verificado
- [ ] App no **Meta for Developers** com acesso à Marketing API (eu explico o passo a passo)
- [ ] Afiliação aprovada nos produtos da Hotmart/Kiwify/Eduzz que você quer vender
- [ ] Webhook de vendas de cada plataforma apontando para `https://seu-dominio/webhooks/hotmart` (ou `kiwify`, `eduzz`)
- [ ] Um domínio com HTTPS e o servidor no ar

O que eu faço na etapa 2: conexão real com a Marketing API (criar, pausar e mudar verba
das campanhas, puxar métricas), envio de eventos de conversão para o Meta (o algoritmo
aprende quem compra), conferência dos avisos de venda com exemplos reais de cada
plataforma e o app como APK, se você quiser.

**Etapa 3:** imagens e vídeos dos anúncios gerados automaticamente, público de remarketing
com os leads quentes e sequência de mensagens para quem abandonou o checkout.

**Etapa 4:** aumento gradual da verba nas ofertas que se pagam.

---

## Onde está cada coisa

```
maquina/
  config.py       travas de gasto e regras (todos os números ajustáveis)
  trava.py        a trava de gasto: todo orçamento passa por aqui
  otimizador.py   o cérebro: corta, escala e testa
  campanhas.py    cria/pausa/escala campanhas e calcula resultados
  produtos.py     nota dos produtos e catálogo da simulação
  criativos.py    textos dos anúncios (Claude ou modelos prontos)
  politica.py     pente-fino de política de anúncios do Meta
  afiliados.py    avisos de venda da Hotmart, Kiwify e Eduzz
  leads.py        pontuação de leads em tempo real (com consentimento, LGPD)
  simulador.py    finge ser o Meta e as plataformas na etapa 1
  motor.py        o ciclo que roda sozinho e suas decisões
  api.py          servidor: app, páginas de captura e webhooks
web/              o app (PWA instalável no Android)
tests/            38 testes automáticos
```
