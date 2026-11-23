# Aplicar as mudanças no painel do MQL5 (cerca de 5 minutos)

Painel do produto: https://www.mql5.com/pt/market/product/204957/controlpanel

## 1. Preço e aluguel (formulário "Preço")

| Campo | Hoje | Novo |
|---|---|---|
| Preço para uso ilimitado | 399,00 | **129,00** |
| Aluguel de 1 mês | desligado | **ligar, 49,00** |
| Aluguel de 3 meses | desligado | **ligar, 99,00** |
| Aluguel de 6 meses e de 1 ano | desligado | deixar desligado |
| Ativações | 5 | 5 (sem mudança) |

Clique em **Salvar**. O MQL5 só deixa mudar o preço **uma vez por dia**.

> **Compromisso:** a descrição nova promete subir o preço depois de 10 cópias (129 → 199 → 279 → 399).
> Acompanhe as vendas em "Estatísticas" e suba o preço quando chegar a 10 cópias.

## 2. Descrição (formulário "Descrição")

Aqui só mexemos em **Português** e **Inglês**. Os campos de espanhol, alemão e dos outros idiomas estão vazios
hoje: o MQL5 traduz automaticamente a partir do inglês. Deixe esses campos vazios.

Em cada idioma:

1. No editor, apague **só o começo**, do título "Do nível à ordem…" (em inglês, "From price level to order…")
   até o parágrafo "Baixe a demonstração do Market…" (em inglês, "Download the Market demo…"), inclusive.
2. No lugar, cole o bloco novo:
   - Português: o bloco da seção 4 de `AURYNDRA-GOLD-PLANO-DE-VENDAS.md`;
   - Inglês: o bloco "English" da mesma seção;
   - **apague a linha que tem `[LINK]`**, porque ainda não existem sinal, vídeo nem blog.
3. A partir de "O que você controla" (em inglês, "What you control"), não mude nada.

**Se o editor tiver modo HTML ou código-fonte:** use os arquivos `DescriptionPT-NOVA.html` e
`DescriptionEN-NOVA.html` desta pasta. Eles já trazem a descrição completa, com o começo novo e o resto original,
pronta para substituir tudo.

Clique em **Salvar**. Mudanças de descrição podem passar pela moderação do MQL5 antes de aparecer.

## 3. Se quiser desfazer

As descrições originais, salvas em 23/11/2026, estão em `original-backup-2026-11-23/`.
O preço original era 399,00, sem aluguel.

## 4. Segurança

- **Troque a senha do MQL5 agora**, porque ela foi enviada no chat:
  Perfil → Configurações → Segurança.
- Ative a **autenticação de dois fatores** na mesma tela.
