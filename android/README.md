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
| **Analisar** | O botão grande. Mostra o progresso (30 s a 1 min) e depois a decisão: **EXECUTAR AGORA** (compra/venda, entrada, stop, alvos, lote, probabilidade) ou **NÃO EXECUTAR AGORA**, com o melhor candidato e o motivo. Botões *Copiar ordem* e *Compartilhar*. |
| **Ranking** | Todos os ativos ordenados pela nota; toque em um para ver o plano completo. Filtro "Executáveis". |
| **Mercado** | Força das 8 moedas, macro (VIX, Treasuries, DXY, petróleo, cobre), juros dos bancos centrais, agenda de alto impacto, COT e manchetes. |
| **Ajustes** | Saldo da conta, risco por trade (o lote é calculado com eles), ativos (Todos / Forex / Metais), estudo de edge histórico e manchetes. |

A última análise fica salva; se ela tiver mais de 5 minutos o app avisa para analisar de novo.

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
  data/Models.kt           JSON do motor -> modelos Kotlin
  data/Prefs.kt            ajustes e última análise
  ui/                      telas em Jetpack Compose (Analisar, Ranking, Mercado, Ajustes)
```

Bibliotecas Python no APK: numpy 1.26.2 e pandas 2.1.3 (builds Android do Chaquopy),
requests, tzdata. A suíte de testes do motor passa nessas versões.

---
Análise automatizada e probabilística; não é recomendação de investimento.
