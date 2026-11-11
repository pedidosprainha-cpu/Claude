# FX Engine para Android

App Android que roda o motor `fxengine` **dentro do celular**: o Python, numpy,
pandas e o motor vão embutidos no APK (via [Chaquopy](https://chaquo.com/chaquopy/)).
Não há servidor: ao tocar em **ANALISAR**, o próprio aparelho baixa os preços ao vivo,
roda as quatro camadas de análise e mostra a melhor entrada a mercado.

## Instalar

1. Baixe o `FXEngine-x.y.z.apk` no celular (Android 8.0 ou mais novo, 64 bits).
2. Abra o arquivo. Se o Android pedir, permita "instalar apps desconhecidos" para o
   navegador ou gerenciador de arquivos.
3. Abra o **FX Engine**. Na primeira vez o app prepara o motor por alguns segundos.

Versões novas instalam por cima da antiga desde que assinadas com a mesma chave (veja
"Assinatura" abaixo); com outra chave, desinstale a anterior antes.

## Usar

| Aba | O que tem |
|---|---|
| **Analisar** | O botão grande. No topo escolha **Todos os ativos** ou **Um ativo**. Em *Todos*, mostra o progresso (30 s a 1 min) e depois a decisão: **EXECUTAR AGORA** (compra/venda, entrada, stop, ponto de +1R onde o stop vira móvel, lote, probabilidade de lucro e expectativa calibradas no histórico) ou **NÃO EXECUTAR AGORA**, com o melhor candidato e o motivo. Só recomenda executar sinais entre os 2% melhores do modelo histórico; o cartão **Validação histórica da análise** mostra quanto a análise rendeu em meses que o modelo não viu (antes × agora). Em *Um ativo*, toque em **Trocar ▾** para escolher qualquer um dos 28 pares ou 4 metais (com busca) e o botão analisa só ele (≈5–10 s): decisão, gráfico de candles H1/M15 com níveis e o plano desenhado (entrada, stop, alvos), rompimentos daquele ativo, leitura por timeframe, níveis-chave com distância em pips/ATR, amplitude do dia e pivôs, regime quantitativo, força das duas moedas, fundamentos componente a componente, agenda e manchetes das moedas do ativo. Botões *Copiar ordem* e *Compartilhar*. |
| **Rompimentos** | Reconhecimento de rompimentos (breakouts) em tempo real em M15 e H1. **Monitorar ao vivo** liga um serviço que varre os ativos a cada 1, 2 ou 5 min, inclusive com a tela apagada, e manda uma **notificação** a cada rompimento novo e acionável com a nota escolhida (A+, A ou B). Cada evento mostra o status (ROMPENDO AGORA, CONFIRMADO, RETESTE, FALSO ROMPIMENTO), o nível rompido (máxima/mínima de 12h/24h/5 dias, consolidação, range asiático, máx./mín. do dia e da semana, swings, números redondos), a nota, a **probabilidade calibrada de o alvo 1 vir antes do stop**, a expectativa em R, os fatores a favor/contra e o plano de entrada a mercado. A nota é relativa ao histórico: A+ = melhores 3% dos rompimentos, A = melhores 10%. |
| **Explosões** | Probabilidade calibrada de o preço andar ≥ 0,5× a amplitude diária média em até 4 h, em cada um dos 32 ativos, com nível (normal, elevada, alta, extrema), movimento típico, alcance provável, o que o modelo está vendo (compressão, squeeze, aceleração da volatilidade, horário, entropia, saltos) e eventos da agenda. Atualiza a cada hora cheia. No teste final, 43% dos alertas explodiram contra 13% de uma hora qualquer (59% no nível extremo). A direção aparece como "se explodir: alta/baixa X%" (probabilidade calibrada, com marca de alta confiança): o lado previsto saiu primeiro em 56% das explosões no histórico (58% nas leituras de alta confiança), uma vantagem pequena que não deu lucro comprovado como entrada a mercado; use como viés e confirme nas outras abas. |
| **Ranking** | Todos os ativos ordenados pela nota; toque em um para ver o plano completo e em **Análise completa** para abrir a análise individual do ativo. Filtro "Executáveis". |
| **Mercado** | Força das 8 moedas, macro (VIX, Treasuries, DXY, petróleo, cobre), juros dos bancos centrais, agenda de alto impacto, COT e manchetes. |
| **Ajustes** | Saldo da conta, risco por trade (o lote é calculado com eles), ativos analisados em *Todos* (Todos / Forex / Metais ou **Escolher** uma lista própria), modelo histórico (probabilidade calibrada, filtro e plano validado) e manchetes. |

A última análise fica salva (a geral e a do último ativo); se ela tiver mais de 5 minutos o app
avisa para analisar de novo. Nas abas Rompimentos e Ranking, **Análise completa de …** abre a
análise individual do ativo na aba Analisar.

### Monitor de rompimentos

- Escolha o plano na própria aba (**Entrada**):
  - **A mercado (tempo real)**, o padrão: o alerta "✅ AGORA a mercado" sai quando o candle
    seguinte fecha a favor do rompimento. Assertividade ~50% no histórico, expectativa ≈ 0.
  - **Limite no reteste:** alerta com a ordem limite sugerida e aviso "Entrada atingida" quando
    o preço chega nela. É o plano com resultado positivo validado.
  - Nos dois, o stop vira móvel depois de +1R.
- Na primeira vez o Android pede permissão de **notificações**: aceite para receber os alertas.
- Enquanto o monitor estiver ligado aparece um aviso fixo "Monitorando rompimentos", com o
  botão **Parar**. Tocar em um alerta abre direto a aba Rompimentos.
- Cada ciclo baixa só o necessário (M15 de 5 dias + H1 de 1 mês, com cache): cerca de
  70 MB/h a cada 1 min, 35 MB/h a cada 2 min e 15 MB/h a cada 5 min.
- Alguns fabricantes (Xiaomi, Samsung, Huawei…) encerram apps em segundo plano. Se os
  alertas pararem com a tela apagada, desative a otimização de bateria do FX Engine.

## Compilar

Requisitos: JDK 17+ (testado com 21), Android SDK (platform 36) e **Python 3.13** no PATH
(o Chaquopy usa para empacotar o motor).

```bash
cd android
./gradlew assembleRelease          # app/build/outputs/apk/release/app-release.apk
./gradlew recordRoborazziDebug     # capturas das telas no JVM: app/build/outputs/roborazzi
```

### Assinatura

A chave de assinatura **não fica no repositório**. Para assinar o release com a sua chave,
crie `android/keystore.properties` (ignorado pelo git):

```properties
storeFile=/caminho/para/sua.keystore
storePassword=...
keyAlias=...
keyPassword=...
```

ou defina `FX_KEYSTORE`, `FX_KEYSTORE_PASSWORD`, `FX_KEY_ALIAS` e `FX_KEY_PASSWORD`
(por exemplo, como secrets no GitHub Actions). Sem chave, o release é assinado com a chave
de debug, que também instala normalmente. Para atualizar o app sem desinstalar, use sempre
a mesma chave.

O código Python não é copiado para dentro de `android/`: o build sincroniza
`../fxengine` a cada compilação, então o app sempre usa a mesma versão do motor que o CLI.
No GitHub, o workflow `.github/workflows/android.yml` roda os testes do motor e publica o
APK como artefato a cada push.

Estrutura:

```
app/src/main/java/com/fxengine/app/
  engine/EngineRunner.kt   chama fxengine.app_api.run() e recebe o progresso
  data/Models.kt           JSON do motor -> modelos Kotlin (AssetModels.kt: análise de um ativo)
  data/Prefs.kt            ajustes e última análise
  ui/                      telas em Jetpack Compose (Analisar, Rompimentos, Ranking, Mercado,
                           Ajustes, AssetScreen + CandleChart + AssetPicker)
```

Bibliotecas Python no APK: numpy 1.26.2 e pandas 2.1.3 (builds Android do Chaquopy),
requests, tzdata. A suíte de testes do motor passa nessas versões.

---
Análise automatizada e probabilística; não é recomendação de investimento.
